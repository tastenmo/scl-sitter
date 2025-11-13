# main_gui.py
"""
SCL UDT-Aware Tag Finder (v15 - Modularized)
- Main GUI application entry point.
- Manages UI, state, and worker threads.
"""
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import threading
import sys
from queue import Queue, Empty
from typing import Dict, List, Tuple, Any

# Check for dependencies before anything else
try:
    from tree_sitter import Parser, Node
    from tree_sitter_scl import language
except ImportError:
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(
        "Missing Dependency",
        "Required libraries not found.\n\n"
        "Please run: pip install tree-sitter tree-sitter-scl"
    )
    sys.exit(1)

# Import from our custom modules
from workers import worker_scan_project, worker_analyze_file, worker_analyze_folder
from scl_parser import _expansion_cache


class SclUdtResolverApp:
    def __init__(self, root):
        self.root = root
        self.root.title("SCL UDT-Aware Tag Finder (v15 - Modularized)")
        self.root.geometry("1600x900")

        self.udt_dictionary: Dict[str, List[Tuple[str, Dict]]] = {}
        self.udt_lock = threading.Lock()
        self.queue = Queue()
        self.processing_thread = None

        self._create_widgets()
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        self._process_queue()
        
    def _create_widgets(self):
        # ... (This method is identical to the original, copy it here)
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


    def _process_queue(self):
        try:
            while not self.queue.empty():
                msg_type, data = self.queue.get_nowait()
                if msg_type == "status": self.status_var.set(data)
                elif msg_type == "progress": self.progress_bar['value'], self.progress_bar['maximum'] = data
                elif msg_type == "log_error": self._append_to_text_widget(self.log_text, f"ERROR: {data}\n", "red")
                elif msg_type == "log_info": self._append_to_text_widget(self.log_text, f"INFO: {data}\n")
                elif msg_type == "udt_dictionary": self._update_udt_dictionary(data)
                elif msg_type == "results": self._display_results(data)
                elif msg_type == "source": self._display_source(data)
                elif msg_type == "show_info_message": messagebox.showinfo(data[0], data[1])
                elif msg_type == "done": self.status_var.set(data); self._end_processing()
        finally:
            self.root.after(100, self._process_queue)

    def _start_processing(self):
        try:
            while not self.queue.empty(): self.queue.get_nowait()
        except Empty: pass
        self.root.config(cursor="watch")
        for btn in [self.scan_button, self.analyze_file_button, self.analyze_folder_button, self.export_button]:
            btn.config(state=tk.DISABLED)
        self.progress_bar['value'] = 0

    def _end_processing(self):
        self.root.config(cursor="")
        for btn in [self.scan_button, self.analyze_file_button, self.analyze_folder_button]:
            btn.config(state=tk.NORMAL)
        self.processing_thread = None
        self.progress_bar['value'] = 0

    def scan_project_folder(self):
        folder_path = filedialog.askdirectory(title="Select folder with ALL source files (UDTs and DBs)")
        if not folder_path: return
        self._start_processing()
        self._clear_text_widget(self.tags_text)
        self.processing_thread = threading.Thread(target=worker_scan_project, args=(self.queue, folder_path), daemon=True)
        self.processing_thread.start()

    def analyze_source_file(self):
        with self.udt_lock:
            if not self.udt_dictionary:
                messagebox.showwarning("Warning", "Please scan a project folder first.")
                return
        filepath_str = filedialog.askopenfilename(title="Select a DB file", filetypes=[("DB Files", "*.db"), ("All Files", "*.*")])
        if not filepath_str: return
        _expansion_cache.clear()
        self._start_processing()
        with self.udt_lock:
            udt_dict_copy = dict(self.udt_dictionary)
        self.processing_thread = threading.Thread(target=worker_analyze_file, args=(self.queue, udt_dict_copy, filepath_str), daemon=True)
        self.processing_thread.start()

    def analyze_db_folder(self):
        with self.udt_lock:
            if not self.udt_dictionary:
                messagebox.showwarning("Warning", "Please scan a project folder first.")
                return
        folder_path_str = filedialog.askdirectory(title="Select folder with DB files to analyze")
        if not folder_path_str: return
        _expansion_cache.clear()
        self._start_processing()
        self._clear_text_widget(self.tags_text)
        self._clear_text_widget(self.source_text)
        with self.udt_lock:
            udt_dict_copy = dict(self.udt_dictionary)
        self.processing_thread = threading.Thread(target=worker_analyze_folder, args=(self.queue, udt_dict_copy, folder_path_str), daemon=True)
        self.processing_thread.start()

    # --- UI Update and Helper Methods ---
    def _update_udt_dictionary(self, data):
        with self.udt_lock:
            self.udt_dictionary = data
            _expansion_cache.clear()
        self._display_udt_dictionary()
        self.udt_status_label.config(text=f"Loaded {len(data)} UDTs.", foreground="green")
        
    def _display_udt_dictionary(self):
        # ... (This method is identical to the original, copy it here)
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
        self.export_button.config(state=tk.NORMAL if tags else tk.DISABLED)
        
    def _clear_text_widget(self, widget):
        # ... (This method is identical to the original, copy it here)
        widget.config(state=tk.NORMAL)
        widget.delete('1.0', tk.END)
        widget.config(state=tk.DISABLED)

    def _append_to_text_widget(self, widget, text, tag=None):
        # ... (This method is identical to the original, copy it here)
        widget.config(state=tk.NORMAL)
        if tag:
            widget.tag_configure(tag, foreground=tag)
            widget.insert(tk.END, text, tag)
        else:
            widget.insert(tk.END, text)
        widget.config(state=tk.DISABLED)
        widget.see(tk.END)

    def _on_closing(self):
        # ... (This method is identical to the original, copy it here)
        if self.processing_thread and self.processing_thread.is_alive():
            if messagebox.askokcancel("Quit", "A task is still running. Do you want to quit anyway?"):
                self.root.destroy()
        else:
            self.root.destroy()

    def export_results(self):
        # ... (This method is identical to the original, copy it here)
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