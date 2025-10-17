# scl_sitter/gui.py

import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
from pathlib import Path
import sys

# Import the powerful parser class from our own library
# The relative import works because this file is inside the package
from .parser_oop import SCLParser, get_node_text

class SclTagFinderGUI:
    """
    The main GUI application for the SCL Smart Tag Finder.
    This application uses the SCLParser library to perform its analysis.
    """
    def __init__(self, root):
        self.root = root
        self.root.title("SCL Smart Tag Finder (Library Edition)")
        self.root.geometry("1600x900")
        
        # The GUI now owns an instance of the SCLParser engine
        self.parser = SCLParser()

        self._create_widgets()

    def _create_widgets(self):
        top_frame = ttk.Frame(self.root, padding="10")
        top_frame.pack(fill=tk.X, side=tk.TOP)
        ttk.Button(top_frame, text="1. Scan Project Folder for Types...", command=self.scan_project).pack(side=tk.LEFT)
        ttk.Button(top_frame, text="2. Analyze Source File...", command=self.analyze_file).pack(side=tk.LEFT, padx=10)
        self.udt_status_label = ttk.Label(top_frame, text="Types not scanned.", foreground="red")
        self.udt_status_label.pack(side=tk.LEFT, padx=10)

        main_pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        udt_frame = ttk.Frame(main_pane, padding=5)
        ttk.Label(udt_frame, text="Type Dictionary", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)
        self.udt_text = scrolledtext.ScrolledText(udt_frame, wrap=tk.WORD, font=("Consolas", 10), state=tk.DISABLED)
        self.udt_text.pack(fill=tk.BOTH, expand=True)
        main_pane.add(udt_frame, weight=1)
        
        source_frame = ttk.Frame(main_pane, padding=5)
        ttk.Label(source_frame, text="Source Code", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)
        self.source_text = scrolledtext.ScrolledText(source_frame, wrap=tk.WORD, font=("Consolas", 11), state=tk.DISABLED)
        self.source_text.pack(fill=tk.BOTH, expand=True)
        main_pane.add(source_frame, weight=2)

        tags_frame = ttk.Frame(main_pane, padding=5)
        ttk.Label(tags_frame, text="Resolved Tag Paths", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)
        self.tags_text = scrolledtext.ScrolledText(tags_frame, wrap=tk.WORD, font=("Consolas", 11), state=tk.DISABLED)
        self.tags_text.pack(fill=tk.BOTH, expand=True)
        main_pane.add(tags_frame, weight=2)
        
        self.status_var = tk.StringVar(value="Ready. Please scan a project folder first.")
        ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W, padding=5).pack(fill=tk.X, side=tk.BOTTOM)

    def scan_project(self):
        folder_path = filedialog.askdirectory(title="Select folder containing ALL source files")
        if not folder_path: return
        
        self.status_var.set(f"Scanning {folder_path} for all type definitions...")
        self.root.update_idletasks()
        
        # Call the library's method to build the UDT dictionary
        self.parser.scan_project_for_types(folder_path)
        
        self._display_udt_dictionary()
        self.udt_status_label.config(text=f"Loaded {len(self.parser.udt_dictionary)} UDTs.", foreground="green")
        self.status_var.set("Type scan complete. Ready to analyze a source file.")

    def analyze_file(self):
        if not self.parser.udt_dictionary:
            messagebox.showwarning("Warning", "Please scan a project folder first.")
            return
            
        filepath_str = filedialog.askopenfilename(title="Select a source file to analyze", filetypes=[("Source Files", "*.scl *.udt *.db"), ("All Files", "*.*")])
        if not filepath_str: return
        
        self.status_var.set(f"Analyzing {filepath_str}...")
        self.root.update_idletasks()
        
        try:
            # Display source code
            source_bytes = Path(filepath_str).read_bytes()
            self._display_source(source_bytes.decode('utf-8', errors='replace'))

            # Use the library to parse the file
            tree = self.parser.parse_file(filepath_str)

            # Use the comprehensive analysis method to get all tags
            all_tags = self._analyze_file_contents(tree.root_node)
            
            self._display_results(all_tags)
            self.status_var.set(f"Analysis complete. Found {len(all_tags)} resolved tag paths.")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred during analysis:\n{e}")
            self.status_var.set(f"Error: {e}")

    def _analyze_file_contents(self, root_node):
        """
        Iterates through all top-level blocks in a file and extracts tags from each,
        using the appropriate method for each block type.
        """
        all_found_tags = set()
        
        for node in root_node.children:
            if node.type == 'data_block':
                # This is a DB, resolve it fully using the UDT dictionary and code usage
                tags_from_db = self.parser.get_all_tags_from_db_node(node)
                all_found_tags.update(tags_from_db)
            
            elif node.type == 'type_definition':
                # This is a UDT defined in the file. Extract its fields.
                tags_from_udt = self._extract_udt_fields(node)
                all_found_tags.update(tags_from_udt)
                
        return sorted(list(all_found_tags))

    def _extract_udt_fields(self, type_def_node):
        """Extracts and resolves field names from a single TYPE definition block."""
        udt_name = get_node_text(type_def_node.child_by_field_name('name'))
        if not udt_name: return set()
        
        resolved_sub_tags = set()
        struct_def_node = next((c for c in type_def_node.children if c.type == 'struct_definition'), None)
        
        if struct_def_node:
            for field_node in struct_def_node.children:
                if field_node.type == 'fields':
                    field_name = get_node_text(field_node.child_by_field_name('name'))
                    field_type_node = next((c for c in field_node.children if c.type == 'type'), None)
                    
                    # Use the parser's internal _expand_tag method to resolve this field
                    self.parser._expand_tag(f"{udt_name}.{field_name}", field_type_node, resolved_sub_tags)
                    
        return resolved_sub_tags

    def _display_udt_dictionary(self):
        self.udt_text.config(state=tk.NORMAL)
        self.udt_text.delete('1.0', tk.END)
        text_to_insert = ""
        for udt_name, fields in sorted(self.parser.udt_dictionary.items()):
            text_to_insert += f"TYPE {udt_name}:\n"
            for field_name, field_type_node in fields:
                text_to_insert += f"  - {field_name}: {get_node_text(field_type_node)}\n"
            text_to_insert += "\n"
        self.udt_text.insert('1.0', text_to_insert if text_to_insert else "No UDTs found.")
        self.udt_text.config(state=tk.DISABLED)

    def _display_source(self, source_string):
        self.source_text.config(state=tk.NORMAL)
        self.source_text.delete('1.0', tk.END)
        self.source_text.insert('1.0', source_string)
        self.source_text.config(state=tk.DISABLED)
        
    def _display_results(self, tags):
        self.tags_text.config(state=tk.NORMAL)
        self.tags_text.delete('1.0', tk.END)
        self.tags_text.insert('1.0', "\n".join(tags))
        self.tags_text.config(state=tk.DISABLED)

def main():
    """Entry point for the scl-sitter-gui script."""
    app_root = tk.Tk()
    SclTagFinderGUI(app_root)
    app_root.mainloop()

if __name__ == "__main__":
    main()