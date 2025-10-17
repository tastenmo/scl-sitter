# parser_oop.py

"""
Object-oriented SCL parser module using tree-sitter.

## CHANGE: The description is updated to reflect the new, more powerful capabilities.
This module provides a high-level OOP interface for parsing SCL code,
managing a project-wide type dictionary (symbol table), and resolving
the full tag structure of Data Blocks.
"""

import os
import logging
from typing import Dict, List, Optional, Union, Any, Set
from pathlib import Path
from tree_sitter import Parser, Tree, Node
import tree_sitter_scl

# Configure module logger
logger = logging.getLogger(__name__)


## NEW: Added a robust helper function to get clean text from a node.
## This replaces inconsistent .text.decode() calls and handles stripping quotes.
def get_node_text(node: Optional[Node]) -> str:
    """Safely gets the text of a node, stripping quotes and whitespace."""
    if not node or not node.text:
        return ""
    return node.text.decode('utf8').strip().strip('"')

## NEW: Added a helper function to reconstruct full tag paths from the tree.
## This is a core part of the new tag extraction logic.
def get_full_member_path(node: Node) -> str:
    """Recursively reconstructs a full, dot-separated tag path from a nested member_expression node."""
    if node.type == 'member_expression':
        obj_node = node.child_by_field_name('object')
        prop_node = node.child_by_field_name('property')
        if obj_node and prop_node:
            return f"{get_full_member_path(obj_node)}.{prop_node.text.decode('utf8')}"
    return node.text.decode('utf8')


## DELETED: The original file had many dataclasses like SCLParseResult, ParseError,
## NodeInfo, etc. These have been removed to simplify the public API. The library
## now returns standard Tree-sitter objects or basic Python types (lists, dicts),
## which is more flexible for the end-user.


# --- Main Parser Class ---
## CHANGE: The class description is updated to highlight its new role as a
## project-aware analyzer with a symbol table.
class SCLParser:
    """
    High-level SCL parser that manages a project-wide symbol table (UDT dictionary)
    for accurate tag resolution.
    """
    
    def __init__(self):
        """Initialize the SCL parser."""
        self._parser = Parser()
        self._parser.language = tree_sitter_scl.language
        
        ## NEW: Added a dictionary to store UDT definitions. This is the "symbol table".
        self.udt_dictionary: Dict[str, List[tuple[str, Node]]] = {}
        
        ## DELETED: The original had separate TypeExtractor and TreeWalker classes.
        ## Their logic is now integrated directly into this main SCLParser class
        ## for a more cohesive design.
        
        logger.debug("SCL Parser initialized")
    
    def parse_file(self, file_path: str) -> Tree:
        """Parses a single SCL file and returns the tree."""
        ## CHANGE: Simplified from the original `parse_file` which returned a custom
        ## SCLParseResult object. Now returns a standard tree-sitter Tree.
        return self._parser.parse(Path(file_path).read_bytes())

    ## NEW: This entire method is new. It implements the crucial "first pass" of our
    ## new strategy, scanning an entire project to build the symbol table (UDT dictionary).
    def scan_project_for_types(self, folder_path: str):
        """
        Scans an entire folder for .udt and .db files to build a
        complete dictionary of all User-Defined Types (UDTs).

        This is the crucial first pass and must be called before resolving tags.
        """
        self.udt_dictionary.clear()
        
        # Scan both .udt and .db files for maximum coverage of type definitions.
        source_files = list(Path(folder_path).rglob("*.udt")) + list(Path(folder_path).rglob("*.db"))
        logger.info(f"Found {len(source_files)} source files to scan for types.")

        for file in source_files:
            self._parse_and_add_udts_from_file(file)
        
        logger.info(f"Type scan complete. Loaded {len(self.udt_dictionary)} UDT definitions.")

    ## NEW: A helper method to support the project scan. It parses one file
    ## and extracts only the TYPE definitions, adding them to the dictionary.
    def _parse_and_add_udts_from_file(self, filepath: Path):
        """Helper to parse a file and add its TYPE definitions to the dictionary."""
        try:
            tree = self._parser.parse(filepath.read_bytes())
            for type_def_node in tree.root_node.children:
                if type_def_node.type == 'type_definition':
                    udt_name = get_node_text(type_def_node.child_by_field_name('name'))
                    if udt_name and udt_name not in self.udt_dictionary:
                        self.udt_dictionary[udt_name] = []
                        for child in type_def_node.children:
                            if child.type == 'struct_definition':
                                for field_node in child.children:
                                    if field_node.type == 'fields':
                                        field_name = get_node_text(field_node.child_by_field_name('name'))
                                        # Store the actual type NODE for later, more robust parsing.
                                        field_type_node = next((c for c in field_node.children if c.type == 'type'), None)
                                        self.udt_dictionary[udt_name].append((field_name, field_type_node))
        except Exception as e:
            logger.warning(f"Could not parse file for UDTs {filepath.name}: {e}")

    ## NEW: This is the main "second pass" analysis method. It combines the logic
    ## of resolving a DB's structure with finding tags used in its code.
    def get_all_tags_from_db_node(self, db_node: Node) -> List[str]:
        """
        Analyzes a DATA_BLOCK node and returns a combined list of all tags,
        both from its resolved structure and from its code block usage.
        """
        all_tags = set()
        db_name = get_node_text(db_node.child_by_field_name('name'))
        if not db_name:
            return []
            
        # 1. Get tags from the DB's declared structure (recursive).
        resolved_tags = self._resolve_db_structure_tags(db_node, db_name)
        all_tags.update(resolved_tags)

        # 2. Get tags from usage inside the BEGIN...END block.
        tags_from_usage = self._find_tags_in_code_block(db_node, db_name)
        all_tags.update(tags_from_usage)
        
        return sorted(list(all_tags))

    ## NEW: This method contains the logic to analyze a DB's top-level structure.
    def _resolve_db_structure_tags(self, db_node: Node, db_name: str) -> Set[str]:
        """Processes a DATA_BLOCK's declarations and resolves its tags."""
        resolved_tags = set()
        base_tags_to_process = []

        implicit_type_node = db_node.child_by_field_name('type')
        if implicit_type_node:
            base_tags_to_process.append(("", implicit_type_node))
        else:
            for var_section in db_node.children_by_field_name('variable_declaration_section'):
                for var_decl in var_section.children_by_field_name('variable_declaration'):
                    tag_name = get_node_text(var_decl.child_by_field_name('name'))
                    tag_type_node = var_decl.child_by_field_name('data_type')
                    if tag_name and tag_type_node:
                        base_tags_to_process.append((tag_name, tag_type_node))
            
            struct_nodes = [child for child in db_node.children if child.type == 'struct_definition']
            for struct_def in struct_nodes:
                 for field_node in struct_def.children:
                    if field_node.type == 'fields':
                        field_name = get_node_text(field_node.child_by_field_name('name'))
                        field_type_node = next((c for c in field_node.children if c.type == 'type'), None)
                        base_tags_to_process.append((field_name, field_type_node))

        for tag_name, tag_type_node in base_tags_to_process:
            base_path = db_name if tag_name == "" else f"{db_name}.{tag_name}"
            self._expand_tag(base_path, tag_type_node, resolved_tags)
        
        return resolved_tags

    ## NEW: This is the core recursive engine. It replaces the old, flawed
    ## string-parsing logic with a robust, tree-based approach that correctly
    ## handles named UDTs, inline structs, and arrays with dimensions.
    def _expand_tag(self, base_path: str, type_node: Optional[Node], resolved_tags: Set[str]):
        """Recursively expands a tag, handling Primitives, Named UDTs, inline Structs, and Arrays."""
        if not type_node: return

        struct_def_node = next((c for c in type_node.children if c.type == 'struct_definition'), None)
        if struct_def_node:
            for field_node in struct_def_node.children:
                if field_node.type == 'fields':
                    sub_tag_name = get_node_text(field_node.child_by_field_name('name'))
                    sub_type_node = next((c for c in field_node.children if c.type == 'type'), None)
                    self._expand_tag(f"{base_path}.{sub_tag_name}", sub_type_node, resolved_tags)
            return

        array_def_node = next((c for c in type_node.children if c.type == 'array_type'), None)
        if array_def_node:
            base_type_node_of_array = array_def_node.children[-1]
            dim_nodes = [c for c in array_def_node.children if c.type == 'integer_literal']
            try:
                if len(dim_nodes) == 2:
                    start_index = int(get_node_text(dim_nodes[0]))
                    end_index = int(get_node_text(dim_nodes[1]))
                    for i in range(start_index, end_index + 1):
                        self._expand_tag(f"{base_path}[{i}]", base_type_node_of_array, resolved_tags)
                    return
            except (ValueError, IndexError): pass
            self._expand_tag(f"{base_path}[]", base_type_node_of_array, resolved_tags)
            return

        clean_type_name = get_node_text(type_node)
        if clean_type_name in self.udt_dictionary:
            for sub_tag_name, sub_tag_type_node in self.udt_dictionary[clean_type_name]:
                self._expand_tag(f"{base_path}.{sub_tag_name}", sub_tag_type_node, resolved_tags)
        else:
            resolved_tags.add(base_path)

    ## NEW: This logic was also part of your GUI and is now correctly
    ## placed inside the parser library to find tags used in code blocks.
    def _find_tags_in_code_block(self, parent_node: Node, db_name: str) -> Set[str]:
        """Finds all member_expression tags used inside a block and prepends the DB name."""
        tags_from_usage = set()
        nodes_to_visit = [parent_node]
        while nodes_to_visit:
            node = nodes_to_visit.pop(0)
            if node.type == 'member_expression':
                if not (node.parent and node.parent.type == 'member_expression'):
                    full_path = get_full_member_path(node)
                    tags_from_usage.add(f"{db_name}.{full_path}")
            if node != parent_node and node.type in ['data_block', 'type_definition']:
                continue
            nodes_to_visit.extend(node.children)
        return tags_from_usage

## DELETED: The entire backward-compatibility section at the end of the original
## file was removed. This enforces the use of the new, superior SCLParser class
## and removes old, redundant code.