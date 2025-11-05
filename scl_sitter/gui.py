# gui_udt_resolver_v15.py
"""
SCL UDT-Aware Tag Finder (v15) - Optimized
- Cached descriptor expansion (memoized)
- Optimized recursion that returns relative suffix lists
- Temporarily disables GC during heavy expansions
- CSV export for results
- Compatible UI & workflow with v14
"""

import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
from pathlib import Path
import threading
import time
import sys
import gc
from queue import Queue, Empty
from typing import Any, Dict, List, Tuple, Set

try:
    from tree_sitter import Parser, Node
    from tree_sitter_scl import language
except ImportError:
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(
        "Missing Dependency",
        "Required libraries not found.\n\n"
        "Please ensure tree_sitter and your SCL binding (tree_sitter_scl) are installed."
    )
    sys.exit(1)


# -------------------------
# Helper utilities
# -------------------------
def get_node_text(node: Node) -> str:
    """Return trimmed text for a node, strip outer quotes if present."""
    if not node:
        return ""
    return node.text.decode("utf8").strip().strip('"')


# Descriptor factories (same shapes)
def make_name_descriptor(type_name: str) -> Dict[str, Any]:
    return {"kind": "name", "name": type_name}


def make_array_descriptor(dim_list: List[Tuple[Any, Any]], base_desc: Any) -> Dict[str, Any]:
    return {"kind": "array", "dims": dim_list, "base": base_desc}


def make_struct_descriptor(fields: List[Tuple[str, Any]]) -> Dict[str, Any]:
    return {"kind": "struct", "fields": fields}


def build_type_descriptor(type_node: Node) -> Dict[str, Any]:
    """
    Build a nested serializable descriptor from a Tree-sitter 'type' node.
    """
    if not type_node:
        return make_name_descriptor("UNKNOWN")

    # inline struct_definition?
    struct_def = next((c for c in type_node.children if c.type == "struct_definition"), None)
    if struct_def:
        fields = []
        for field_node in struct_def.children:
            if field_node.type == "fields":
                fname_node = field_node.child_by_field_name("name")
                fname = get_node_text(fname_node)
                ftype_node = next((c for c in field_node.children if c.type == "type"), None)
                fdesc = build_type_descriptor(ftype_node)
                if fname:
                    fields.append((fname, fdesc))
        return make_struct_descriptor(fields)

    # array_type?
    array_node = next((c for c in type_node.children if c.type == "array_type"), None)
    if array_node:
        bound_nodes = [c for c in array_node.children if c.type in ("integer_literal", "identifier")]
        dims = []
        for i in range(0, len(bound_nodes), 2):
            if i + 1 < len(bound_nodes):
                s = get_node_text(bound_nodes[i])
                e = get_node_text(bound_nodes[i + 1])
                try:
                    s_i = int(s)
                    e_i = int(e)
                    dims.append((s_i, e_i))
                except ValueError:
                    dims.append((s, e))
        base_node = array_node.children[-1] if len(array_node.children) > 0 else None
        base_desc = build_type_descriptor(base_node)
        return make_array_descriptor(dims, base_desc)

    # fallback: just capture text
    name_text = get_node_text(type_node)
    return make_name_descriptor(name_text)


# -------------------------
# Optimized Expansion (memoized)
# -------------------------
# We'll cache expansions by creating a canonical, hashable key for descriptors.
_expansion_cache: Dict[Tuple, List[str]] = {}


def descriptor_key(desc: Any) -> Tuple:
    """Create a hashable representation for a descriptor to use as cache key."""
    kind = desc.get("kind")
    if kind == "name":
        return ("name", desc.get("name", ""))
    if kind == "array":
        dims = tuple((d[0], d[1]) for d in desc.get("dims", []))
        base_key = descriptor_key(desc.get("base"))
        return ("array", dims, base_key)
    if kind == "struct":
        fields = tuple((fname, descriptor_key(fdesc)) for fname, fdesc in desc.get("fields", []))
        return ("struct", fields)
    # fallback (shouldn't happen)
    return ("other", str(desc))

################################################################################################
def expand_descriptor_suffixes(desc: Dict[str, Any], udt_dict: Dict[str, List[Tuple[str, Dict]]]) -> List[str]:
    """
    Return a list of relative suffixes for a descriptor.
    Example:
      STRUCT with field 'A' (primitive) and field 'B' (STRUCT {X,Y})
      -> ['A', 'B.X', 'B.Y']
    Arrays expand to index suffixes. The output never includes an extra '.' before '[n]'.
    This function is memoized to avoid recomputation for identical descriptor shapes.
    """
    key = descriptor_key(desc)
    if key in _expansion_cache:
        return _expansion_cache[key]

    kind = desc.get("kind")
    results: List[str] = []

    # ----- Primitive / Named Type -----
    if kind == "name":
        tname = desc.get("name", "")
        if tname in udt_dict:
            local: Set[str] = set()
            for field_name, field_desc in udt_dict[tname]:
                sub_suffixes = expand_descriptor_suffixes(field_desc, udt_dict)
                for s in sub_suffixes:
                    # START OF FIX for 'name' block
                    if s:
                        if s.startswith('['):
                            local.add(f"{field_name}{s}")
                        else:
                            local.add(f"{field_name}.{s}")
                    else:
                        local.add(f"{field_name}")
                    # END OF FIX
            results = sorted(local)
        else:
            # primitive type → terminal (no suffix)
            results = [""]
        _expansion_cache[key] = results
        return results

    # ----- STRUCT -----
    if kind == "struct":
        local: Set[str] = set()
        for field_name, field_desc in desc.get("fields", []):
            sub_suffixes = expand_descriptor_suffixes(field_desc, udt_dict)
            for s in sub_suffixes:
                # START OF FIX for 'struct' block
                if s:
                    if s.startswith('['):
                        local.add(f"{field_name}{s}")
                    else:
                        local.add(f"{field_name}.{s}")
                else:
                    local.add(f"{field_name}")
                # END OF FIX
        results = sorted(local)
        _expansion_cache[key] = results
        return results

    # ----- ARRAY -----
    if kind == "array":
        dims = desc.get("dims", [])
        base = desc.get("base")

        # build all index combinations
        def expand_for_dims(dims_list):
            if not dims_list:
                return [""]
            start, end = dims_list[0]
            if isinstance(start, int) and isinstance(end, int):
                indices = [f"[{i}]" for i in range(start, end + 1)]
            else:
                indices = [f"[{start}..{end}]"]
            rest = expand_for_dims(dims_list[1:])
            out = []
            for idx in indices:
                for r in rest:
                    out.append(f"{idx}{r}")
            return out

        index_parts = expand_for_dims(dims)
        base_suffixes = expand_descriptor_suffixes(base, udt_dict)
        local: Set[str] = set()

        for idx in index_parts:
            for s in base_suffixes:
                if s:
                    # This logic was already correct here
                    if s.startswith('['):
                        local.add(f"{idx}{s}")
                    else:
                        local.add(f"{idx}.{s}")
                else:
                    local.add(f"{idx}")

        results = sorted(local)
        _expansion_cache[key] = results
        return results

    # ----- Fallback -----
    results = [""]
    _expansion_cache[key] = results
    return results
#############################################################################################
def expand_descriptor_into(base_path: str, desc: Dict[str, Any], udt_dict: Dict[str, List[Tuple[str, Dict]]], out_list: List[str]):
    """
    Wrapper to expand descriptor and append full paths (base_path + suffix)
    Uses expand_descriptor_suffixes for fast memoized expansion.
    """
    # Temporarily disable GC only at the outermost call if needed
    suffixes = expand_descriptor_suffixes(desc, udt_dict)
    # Build final paths efficiently using join when suffix present
    for s in suffixes:
        if s:
            out_list.append(f"{base_path}.{s}")
        else:
            out_list.append(base_path)


# -------------------------
# GUI Application (same structure as v14, with export)
# -------------------------
class SclUdtResolverApp:
    def __init__(self, root):
        self.root = root
        self.root.title("SCL UDT-Aware Tag Finder (v15 - optimized)")
        self.root.geometry("1600x900")

        self.udt_dictionary: Dict[str, List[Tuple[str, Dict]]] = {}
        self.udt_lock = threading.Lock()
        self.queue = Queue()
        self.processing_thread = None

        self._create_widgets()
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        self._process_queue()

    def _create_widgets(self):
        top = ttk.Frame(self.root, padding="10")
        top.pack(fill=tk.X, side=tk.TOP)

        self.scan_button = ttk.Button(top, text="1. Scan Project Folder for Types...", command=self.scan_project_folder)
        self.scan_button.pack(side=tk.LEFT)
        self.analyze_file_button = ttk.Button(top, text="2. Analyze Single DB File...", command=self.analyze_source_file)
        self.analyze_file_button.pack(side=tk.LEFT, padx=10)
        self.analyze_folder_button = ttk.Button(top, text="3. Analyze DB Folder...", command=self.analyze_db_folder)
        self.analyze_folder_button.pack(side=tk.LEFT)
        self.export_button = ttk.Button(top, text="Export Results to CSV", command=self.export_results, state=tk.DISABLED)
        self.export_button.pack(side=tk.LEFT, padx=10)
        self.udt_status_label = ttk.Label(top, text="Types not scanned.", foreground="red")
        self.udt_status_label.pack(side=tk.LEFT, padx=10)

        main_pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        udt_frame = ttk.Frame(main_pane, padding=5)
        ttk.Label(udt_frame, text="Type Dictionary", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)
        self.udt_text = scrolledtext.ScrolledText(udt_frame, wrap=tk.WORD, font=("Consolas", 10), state=tk.DISABLED)
        self.udt_text.pack(fill=tk.BOTH, expand=True)
        main_pane.add(udt_frame, weight=1)

        source_frame = ttk.Frame(main_pane, padding=5)
        ttk.Label(source_frame, text="Source Code (Last Processed File)", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)
        self.source_text = scrolledtext.ScrolledText(source_frame, wrap=tk.WORD, font=("Consolas", 11), state=tk.DISABLED)
        self.source_text.pack(fill=tk.BOTH, expand=True)
        main_pane.add(source_frame, weight=2)

        results_notebook = ttk.Notebook(main_pane)
        main_pane.add(results_notebook, weight=2)

        tags_frame = ttk.Frame(results_notebook, padding=5)
        ttk.Label(tags_frame, text="Resolved Tag Paths", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)
        self.tags_text = scrolledtext.ScrolledText(tags_frame, wrap=tk.WORD, font=("Consolas", 11), state=tk.DISABLED)
        self.tags_text.pack(fill=tk.BOTH, expand=True)
        results_notebook.add(tags_frame, text="Results")

        log_frame = ttk.Frame(results_notebook, padding=5)
        log_top = ttk.Frame(log_frame)
        log_top.pack(fill=tk.X)
        ttk.Label(log_top, text="Logs & Errors", font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
        ttk.Button(log_top, text="Clear Log", command=lambda: self._clear_text_widget(self.log_text)).pack(side=tk.RIGHT)
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, font=("Consolas", 10),
                                                  state=tk.DISABLED, background="#f0f0f0")
        self.log_text.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        results_notebook.add(log_frame, text="Logs")

        bottom_frame = ttk.Frame(self.root)
        bottom_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=10, pady=(0, 5))
        self.progress_bar = ttk.Progressbar(bottom_frame, orient='horizontal', mode='determinate')
        self.progress_bar.pack(fill=tk.X)
        self.status_var = tk.StringVar(value="Ready. Please scan a project folder first.")
        ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W, padding=5).pack(fill=tk.X, side=tk.BOTTOM)

    # Queue processing loop
    def _process_queue(self):
        try:
            while not self.queue.empty():
                msg_type, data = self.queue.get_nowait()
                if msg_type == "status":
                    self.status_var.set(data)
                elif msg_type == "progress":
                    self.progress_bar['maximum'] = data[1]
                    self.progress_bar['value'] = data[0]
                elif msg_type == "log_error":
                    self._append_to_text_widget(self.log_text, f"ERROR: {data}\n", "red")
                elif msg_type == "log_info":
                    self._append_to_text_widget(self.log_text, f"INFO: {data}\n")
                elif msg_type == "udt_dictionary":
                    with self.udt_lock:
                        self.udt_dictionary = data
                    self._display_udt_dictionary()
                    self.udt_status_label.config(text=f"Loaded {len(self.udt_dictionary)} UDTs.", foreground="green")
                elif msg_type == "results":
                    self._display_results(data)
                    self.export_button.config(state=tk.NORMAL if data else tk.DISABLED)
                elif msg_type == "source":
                    self._display_source(data)
                elif msg_type == "done":
                    self.status_var.set(data)
                    self._end_processing()
        finally:
            self.root.after(100, self._process_queue)

    def _clear_queue(self):
        try:
            while not self.queue.empty():
                self.queue.get_nowait()
        except Empty:
            pass

    def _start_processing(self):
        self._clear_queue()
        self.root.config(cursor="watch")
        self.scan_button.config(state=tk.DISABLED)
        self.analyze_file_button.config(state=tk.DISABLED)
        self.analyze_folder_button.config(state=tk.DISABLED)
        self.export_button.config(state=tk.DISABLED)
        self.progress_bar['value'] = 0

    def _end_processing(self):
        self.root.config(cursor="")
        self.scan_button.config(state=tk.NORMAL)
        self.analyze_file_button.config(state=tk.NORMAL)
        self.analyze_folder_button.config(state=tk.NORMAL)
        # export_button state is managed when results arrive
        self.processing_thread = None
        self.progress_bar['value'] = 0

    # Scan project folder
    def scan_project_folder(self):
        folder_path = filedialog.askdirectory(title="Select folder containing ALL source files (UDTs and DBs)")
        if not folder_path:
            return

        with self.udt_lock:
            self.udt_dictionary = {}
            _expansion_cache.clear()

        self._start_processing()
        self._clear_text_widget(self.tags_text)
        self.processing_thread = threading.Thread(target=self._worker_scan_project, args=(folder_path,), daemon=True)
        self.processing_thread.start()

    def _worker_scan_project(self, folder_path: str):
        try:
            self.queue.put(("status", f"Scanning {folder_path} for all type definitions..."))
            source_files = list(Path(folder_path).rglob("*.udt")) + list(Path(folder_path).rglob("*.db"))
            if not source_files:
                messagebox.showinfo("No Files Found", "No '.udt' or '.db' files were found in the selected folder.")
                self.queue.put(("done", "Scan complete. No source files found."))
                return

            total_files = len(source_files)
            parser = Parser()
            parser.language = language
            local_udt_dict: Dict[str, List[Tuple[str, Dict]]] = {}

            for i, file in enumerate(source_files):
                self.queue.put(("status", f"Scanning {i+1}/{total_files}: {file.name}..."))
                self.queue.put(("progress", (i + 1, total_files)))
                self._parse_and_add_udts_from_file(file, local_udt_dict, parser)

            # atomic publish
            self.queue.put(("udt_dictionary", local_udt_dict))
            self.queue.put(("done", "Type scan complete. Ready to analyze a source file."))
        except Exception as e:
            self.queue.put(("log_error", f"Unhandled exception during project scan: {e}"))
            self.queue.put(("done", "Type scan failed."))
        finally:
            try:
                del parser
            except Exception:
                pass
            gc.collect()

    def _parse_and_add_udts_from_file(self, filepath: Path, udt_dict: Dict[str, List[Tuple[str, Dict]]], parser: Parser):
        try:
            data = filepath.read_bytes()
            tree = parser.parse(data)

            for type_def_node in tree.root_node.children:
                if type_def_node.type != 'type_definition':
                    continue
                udt_name_node = type_def_node.child_by_field_name('name')
                if not udt_name_node:
                    continue
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

            try:
                del tree
            except Exception:
                pass
            gc.collect()
        except Exception as e:
            self.queue.put(("log_error", f"Error parsing UDTs from {filepath.name}: {e}"))

    # Analyze single file
    def analyze_source_file(self, filepath_str=None):
        with self.udt_lock:
            if not self.udt_dictionary:
                messagebox.showwarning("Warning", "Please scan a project folder first.")
                return

        if not filepath_str:
            filepath_str = filedialog.askopenfilename(title="Select a DB file", filetypes=[("DB Files", "*.db"), ("All Files", "*.*")])
        if not filepath_str:
            return

        self._start_processing()
        self.processing_thread = threading.Thread(target=self._worker_analyze_file, args=(filepath_str,), daemon=True)
        self.processing_thread.start()

    def _worker_analyze_file(self, filepath_str: str):
        start_time = time.perf_counter()
        try:
            filepath = Path(filepath_str)
            self.queue.put(("status", f"Analyzing {filepath.name}..."))

            parser = Parser()
            parser.language = language

            with self.udt_lock:
                analysis_dict = dict(self.udt_dictionary)

            # Try to parse local TYPE definitions inside file
            try:
                tree = parser.parse(filepath.read_bytes())
                for type_def_node in tree.root_node.children:
                    if type_def_node.type == 'type_definition':
                        udt_name_node = type_def_node.child_by_field_name('name')
                        if udt_name_node:
                            udt_name = get_node_text(udt_name_node)
                            if udt_name not in analysis_dict:
                                analysis_dict[udt_name] = []
                            struct_def = next((c for c in type_def_node.children if c.type == 'struct_definition'), None)
                            if struct_def:
                                for field_node in struct_def.children:
                                    if field_node.type == 'fields':
                                        fname = get_node_text(field_node.child_by_field_name('name'))
                                        ftype_node = next((c for c in field_node.children if c.type == 'type'), None)
                                        fdesc = build_type_descriptor(ftype_node)
                                        if fname:
                                            analysis_dict[udt_name].append((fname, fdesc))
                try:
                    del tree
                except Exception:
                    pass
                gc.collect()
            except Exception:
                # continue even if local type parse fails
                pass

            source_bytes = filepath.read_bytes()
            self.queue.put(("source", source_bytes.decode('utf-8', errors='replace')))

            tree = parser.parse(source_bytes)
            if tree.root_node.has_error:
                self.queue.put(("log_info", f"File '{filepath.name}' contains syntax errors. Results may be incomplete."))

            # Reset expansion cache for consistent analysis (to avoid stale cache across different analysis_dict)
            _expansion_cache.clear()

            all_tags_list: List[str] = []

            # We will temporarily disable GC during the heavy expansion stage to reduce GC pauses:
            gc_was_enabled = gc.isenabled()
            if gc_was_enabled:
                gc.disable()

            try:
                for node in tree.root_node.children:
                    if node.type == 'data_block':
                        db_tags = self._resolve_db_tags(node, analysis_dict)
                        all_tags_list.extend(db_tags)
            finally:
                if gc_was_enabled:
                    gc.enable()

            # deduplicate & sort
            all_tags = sorted(set(all_tags_list))

            duration = time.perf_counter() - start_time
            self.queue.put(("log_info", f"Extracted {len(all_tags)} tags from {filepath.name} in {duration:.3f} seconds."))
            self.queue.put(("results", all_tags))
            self.queue.put(("status", f"Analysis of {filepath.name} complete. Found {len(all_tags)} resolved tag paths."))

        except Exception as e:
            self.queue.put(("log_error", f"Failed to analyze file {filepath_str}: {e}"))
        finally:
            try:
                del parser
            except Exception:
                pass
            gc.collect()
            self.queue.put(("done", "Analysis complete."))

    # Analyze folder
    def analyze_db_folder(self):
        with self.udt_lock:
            if not self.udt_dictionary:
                messagebox.showwarning("Warning", "Please scan a project folder first.")
                return
        folder_path_str = filedialog.askdirectory(title="Select folder containing DB files to analyze")
        if not folder_path_str:
            return
        self._start_processing()
        self._clear_text_widget(self.tags_text)
        self._clear_text_widget(self.source_text)
        self.processing_thread = threading.Thread(target=self._worker_analyze_folder, args=(folder_path_str,), daemon=True)
        self.processing_thread.start()

    def _worker_analyze_folder(self, folder_path_str: str):
        total_start_time = time.perf_counter()
        all_tags_from_folder: Set[str] = set()
        try:
            folder_path = Path(folder_path_str)
            self.queue.put(("status", f"Finding .db files in {folder_path}..."))
            db_files = list(folder_path.rglob("*.db"))
            if not db_files:
                messagebox.showinfo("No Files Found", "No '.db' files were found in the selected folder.")
                self.queue.put(("done", "Batch scan complete. No .db files found."))
                return

            with self.udt_lock:
                analysis_dict = dict(self.udt_dictionary)

            parser = Parser()
            parser.language = language

            self.queue.put(("status", "Pre-scanning folder for contextual types..."))
            for filepath in db_files:
                self._parse_and_add_udts_from_file(filepath, analysis_dict, parser)

            total_files = len(db_files)
            for i, filepath in enumerate(db_files):
                file_start_time = time.perf_counter()
                self.queue.put(("status", f"Analyzing {i+1}/{total_files}: {filepath.name}..."))
                self.queue.put(("progress", (i + 1, total_files)))
                try:
                    tree = parser.parse(filepath.read_bytes())
                    tags_from_file: List[str] = []
                    # disable GC during heavy expansions
                    gc_was_enabled = gc.isenabled()
                    if gc_was_enabled:
                        gc.disable()
                    try:
                        for node in tree.root_node.children:
                            if node.type == 'data_block':
                                tags_from_file.extend(self._resolve_db_tags(node, analysis_dict))
                    finally:
                        if gc_was_enabled:
                            gc.enable()

                    duration = time.perf_counter() - file_start_time
                    self.queue.put(("log_info", f"Extracted {len(set(tags_from_file))} tags from {filepath.name} in {duration:.3f} seconds."))
                    all_tags_from_folder.update(tags_from_file)
                except Exception as e:
                    self.queue.put(("log_error", f"Failed to process {filepath.name}: {e}"))

            self.queue.put(("results", sorted(list(all_tags_from_folder))))
        except Exception as e:
            self.queue.put(("log_error", f"Unhandled exception during folder analysis: {e}"))
        finally:
            total_duration = time.perf_counter() - total_start_time
            try:
                del parser
            except Exception:
                pass
            gc.collect()
            self.queue.put(("done", f"Batch analysis complete. Found {len(all_tags_from_folder)} total unique tags in {total_duration:.2f} seconds."))

    # Resolve tags within a data_block node (returns list)
    def _resolve_db_tags(self, db_node: Node, udt_dict: Dict[str, List[Tuple[str, Dict]]]) -> List[str]:
        db_name_node = db_node.child_by_field_name('name')
        if not db_name_node:
            return []
        db_name = get_node_text(db_name_node)
        result_list: List[str] = []

        # SCENARIO 1: DB is instance of a UDT: DATA_BLOCK "Name" "UDTName"
        implicit_type_node = db_node.child_by_field_name('type')
        if implicit_type_node:
            desc = build_type_descriptor(implicit_type_node)
            expand_descriptor_into(db_name, desc, udt_dict, result_list)
            return result_list

        # SCENARIO 2: inline STRUCT inside DATA_BLOCK
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

        # SCENARIO 3: DB with VAR sections
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

        # none matched
        self.queue.put(("log_info", f"Data block '{db_name}' appears to be empty or has an unsupported structure."))
        return []

    # UI display helpers
    def _display_udt_dictionary(self):
        self.udt_text.config(state=tk.NORMAL)
        self.udt_text.delete('1.0', tk.END)
        with self.udt_lock:
            sd = dict(self.udt_dictionary)
        for udt_name, fields in sorted(sd.items()):
            self.udt_text.insert(tk.END, f"TYPE {udt_name}:\n")
            for field_name, field_desc in fields:
                kind = field_desc.get("kind", "unknown")
                if kind == "name":
                    ttext = field_desc.get("name", "")
                elif kind == "array":
                    dims = ",".join([f"{a}..{b}" for a, b in field_desc.get("dims", [])])
                    base = field_desc.get("base")
                    base_name = base.get("name") if isinstance(base, dict) and base.get("kind") == "name" else "<complex>"
                    ttext = f"ARRAY[{dims}] OF {base_name}"
                elif kind == "struct":
                    ttext = "STRUCT"
                else:
                    ttext = "<complex>"
                self.udt_text.insert(tk.END, f"  - {field_name}: {ttext}\n")
            self.udt_text.insert(tk.END, "\n")
        self.udt_text.config(state=tk.DISABLED)

    def _display_source(self, source_string: str):
        self._clear_text_widget(self.source_text)
        self._append_to_text_widget(self.source_text, source_string)

    def _display_results(self, tags: List[str]):
        self._clear_text_widget(self.tags_text)
        self._append_to_text_widget(self.tags_text, "\n".join(tags))

    def _clear_text_widget(self, widget):
        widget.config(state=tk.NORMAL)
        widget.delete('1.0', tk.END)
        widget.config(state=tk.DISABLED)

    def _append_to_text_widget(self, widget, text, tag=None):
        widget.config(state=tk.NORMAL)
        if tag:
            widget.tag_configure(tag, foreground=tag)
            widget.insert(tk.END, text, tag)
        else:
            widget.insert(tk.END, text)
        widget.config(state=tk.DISABLED)
        widget.see(tk.END)

    def _on_closing(self):
        if self.processing_thread and self.processing_thread.is_alive():
            if messagebox.askokcancel("Quit", "A task is still running. Do you want to quit anyway?"):
                self.root.destroy()
        else:
            self.root.destroy()

    def export_results(self):
        # read tags from results text widget (simple)
        text = self.tags_text.get('1.0', tk.END).strip()
        if not text:
            messagebox.showinfo("No Results", "No results to export.")
            return
        save_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files","*.csv"),("All files","*.*")])
        if not save_path:
            return
        try:
            with open(save_path, "w", encoding="utf-8") as f:
                for line in text.splitlines():
                    # write simple CSV with one column
                    f.write(f"\"{line.replace('\"','\"\"')}\"\n")
            messagebox.showinfo("Export Complete", f"Results exported to {save_path}")
        except Exception as e:
            messagebox.showerror("Export Failed", f"Failed to export results: {e}")


def main():
    root = tk.Tk()
    SclUdtResolverApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
