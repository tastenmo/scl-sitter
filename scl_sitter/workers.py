# workers.py
"""
Worker functions for background processing.
These functions are designed to be run in separate threads to avoid freezing the GUI.
They communicate with the main GUI thread via a queue.
"""
import gc
import time
from pathlib import Path
from queue import Queue
from typing import Dict, List, Tuple, Set, Any

from tree_sitter import Parser, Node
from tree_sitter_scl import language

# Import from our custom module
from scl_parser import build_type_descriptor, expand_descriptor_into, get_node_text, _expansion_cache


def _parse_and_add_udts_from_file(filepath: Path, udt_dict: Dict[str, List[Tuple[str, Dict]]], parser: Parser, queue: Queue):
    try:
        tree = parser.parse(filepath.read_bytes())
        for type_def_node in tree.root_node.children:
            if type_def_node.type != 'type_definition': continue
            udt_name_node = type_def_node.child_by_field_name('name')
            if not udt_name_node: continue
            udt_name = get_node_text(udt_name_node)
            if udt_name not in udt_dict:
                udt_dict[udt_name] = []

            struct_def = next((c for c in type_def_node.children if c.type == 'struct_definition'), None)
            if struct_def:
                for field_node in struct_def.children:
                    if field_node.type == 'fields':
                        field_name = get_node_text(field_node.child_by_field_name('name'))
                        field_type_node = next((c for c in field_node.children if c.type == 'type'), None)
                        field_desc = build_type_descriptor(field_type_node)
                        if field_name:
                            udt_dict[udt_name].append((field_name, field_desc))
    except Exception as e:
        queue.put(("log_error", f"Error parsing UDTs from {filepath.name}: {e}"))
    finally:
        try: del tree; gc.collect()
        except Exception: pass

def _resolve_db_tags(db_node: Node, udt_dict: Dict[str, List[Tuple[str, Dict]]], queue: Queue) -> List[str]:
    db_name_node = db_node.child_by_field_name('name')
    if not db_name_node: return []
    db_name = get_node_text(db_name_node)
    result_list: List[str] = []

    # Case 1: DB is instance of a UDT: DATA_BLOCK "Name" "UDTName"
    implicit_type_node = db_node.child_by_field_name('type')
    if implicit_type_node:
        desc = build_type_descriptor(implicit_type_node)
        expand_descriptor_into(db_name, desc, udt_dict, result_list)
        return result_list

    # Case 2: inline STRUCT inside DATA_BLOCK
    struct_def_node = next((c for c in db_node.children if c.type == 'struct_definition'), None)
    if struct_def_node:
        for field_node in struct_def_node.children:
            if field_node.type == 'fields':
                tag_name = get_node_text(field_node.child_by_field_name('name'))
                tag_type_node = next((c for c in field_node.children if c.type == 'type'), None)
                if tag_name and tag_type_node:
                    desc = build_type_descriptor(tag_type_node)
                    expand_descriptor_into(f"{db_name}.{tag_name}", desc, udt_dict, result_list)
        return result_list

    # Case 3: DB with VAR sections
    var_sections = [c for c in db_node.children if c.type == 'variable_declaration_section']
    if var_sections:
        for var_section in var_sections:
            for var_decl in var_section.children:
                if var_decl.type == 'variable_declaration':
                    tag_name = get_node_text(var_decl.child_by_field_name('name'))
                    tag_type_node = var_decl.child_by_field_name('data_type')
                    if tag_name and tag_type_node:
                        desc = build_type_descriptor(tag_type_node)
                        expand_descriptor_into(f"{db_name}.{tag_name}", desc, udt_dict, result_list)
        return result_list
    
    queue.put(("log_info", f"Data block '{db_name}' appears empty or has unsupported structure."))
    return []


def worker_scan_project(queue: Queue, folder_path: str):
    try:
        queue.put(("status", f"Scanning {folder_path} for type definitions..."))
        source_files = list(Path(folder_path).rglob("*.udt")) + list(Path(folder_path).rglob("*.db"))
        if not source_files:
            queue.put(("show_info_message", ("No Files Found", "No '.udt' or '.db' files found.")))
            return

        parser = Parser()
        parser.language = language
        local_udt_dict: Dict[str, List[Tuple[str, Dict]]] = {}

        for i, file in enumerate(source_files):
            queue.put(("status", f"Scanning {i+1}/{len(source_files)}: {file.name}..."))
            queue.put(("progress", (i + 1, len(source_files))))
            _parse_and_add_udts_from_file(file, local_udt_dict, parser, queue)

        queue.put(("udt_dictionary", local_udt_dict))
    except Exception as e:
        queue.put(("log_error", f"Unhandled exception during project scan: {e}"))
    finally:
        queue.put(("done", "Type scan complete. Ready to analyze."))
        try: del parser; gc.collect()
        except Exception: pass

def worker_analyze_file(queue: Queue, udt_dictionary: Dict, filepath_str: str):
    start_time = time.perf_counter()
    try:
        filepath = Path(filepath_str)
        queue.put(("status", f"Analyzing {filepath.name}..."))
        
        parser = Parser()
        parser.language = language
        analysis_dict = dict(udt_dictionary)

        # Pre-scan file for locally-defined types
        _parse_and_add_udts_from_file(filepath, analysis_dict, parser, queue)
        
        source_bytes = filepath.read_bytes()
        queue.put(("source", source_bytes.decode('utf-8', errors='replace')))
        
        tree = parser.parse(source_bytes)
        if tree.root_node.has_error:
            queue.put(("log_info", f"File '{filepath.name}' has syntax errors. Results may be incomplete."))

        all_tags_list: List[str] = []
        gc_was_enabled = gc.isenabled()
        if gc_was_enabled: gc.disable()
        try:
            for node in tree.root_node.children:
                if node.type == 'data_block':
                    all_tags_list.extend(_resolve_db_tags(node, analysis_dict, queue))
        finally:
            if gc_was_enabled: gc.enable()

        all_tags = sorted(set(all_tags_list))
        duration = time.perf_counter() - start_time
        queue.put(("log_info", f"Extracted {len(all_tags)} tags from {filepath.name} in {duration:.3f}s."))
        queue.put(("results", all_tags))
    except Exception as e:
        queue.put(("log_error", f"Failed to analyze file {filepath_str}: {e}"))
    finally:
        queue.put(("done", "Analysis complete."))
        try: del parser; gc.collect()
        except Exception: pass

def worker_analyze_folder(queue: Queue, udt_dictionary: Dict, folder_path_str: str):
    total_start_time = time.perf_counter()
    all_tags_from_folder: Set[str] = set()
    try:
        folder_path = Path(folder_path_str)
        queue.put(("status", f"Finding .db files in {folder_path}..."))
        db_files = list(folder_path.rglob("*.db"))
        if not db_files:
            queue.put(("show_info_message", ("No Files Found", "No '.db' files found.")))
            return

        parser = Parser()
        parser.language = language
        analysis_dict = dict(udt_dictionary)

        queue.put(("status", "Pre-scanning folder for contextual types..."))
        for filepath in db_files:
            _parse_and_add_udts_from_file(filepath, analysis_dict, parser, queue)

        for i, filepath in enumerate(db_files):
            file_start_time = time.perf_counter()
            queue.put(("status", f"Analyzing {i+1}/{len(db_files)}: {filepath.name}..."))
            queue.put(("progress", (i + 1, len(db_files))))
            try:
                tree = parser.parse(filepath.read_bytes())
                tags_from_file: List[str] = []
                gc_was_enabled = gc.isenabled()
                if gc_was_enabled: gc.disable()
                try:
                    for node in tree.root_node.children:
                        if node.type == 'data_block':
                            tags_from_file.extend(_resolve_db_tags(node, analysis_dict, queue))
                finally:
                    if gc_was_enabled: gc.enable()

                duration = time.perf_counter() - file_start_time
                queue.put(("log_info", f"Extracted {len(set(tags_from_file))} tags from {filepath.name} in {duration:.3f}s."))
                all_tags_from_folder.update(tags_from_file)
            except Exception as e:
                queue.put(("log_error", f"Failed to process {filepath.name}: {e}"))

        queue.put(("results", sorted(list(all_tags_from_folder))))
    except Exception as e:
        queue.put(("log_error", f"Unhandled exception during folder analysis: {e}"))
    finally:
        total_duration = time.perf_counter() - total_start_time
        msg = f"Batch analysis complete. Found {len(all_tags_from_folder)} total unique tags in {total_duration:.2f}s."
        queue.put(("done", msg))
        try: del parser; gc.collect()
        except Exception: pass