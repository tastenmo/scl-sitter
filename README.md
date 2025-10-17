# SCL Sitter: A Tree-sitter-based Parser and Toolkit for Siemens SCL

SCL Sitter provides a robust, high-performance parser for Siemens Structured Control Language (SCL), built on the modern `tree-sitter` parsing framework. It is designed for developers and engineers who need to programmatically analyze, lint, or process SCL source code from `.scl`, `.udt`, and `.db` files.

This project includes:
1.  A powerful, installable **Python library** (`scl-sitter`) for advanced semantic analysis.
2.  An easy-to-use **GUI application** for interactive tag exploration.

![SCL Smart Tag Finder GUI](path/to/your/screenshot.png) 
*(Optional: Replace this with a path to a screenshot of your GUI if you add one to your repository)*

## Features

-   **High-Performance Parsing:** Leverages `tree-sitter`'s incremental parsing for speed.
-   **Comprehensive Grammar:** Accurately parses a wide range of SCL constructs, including `DATA_BLOCK`, `FUNCTION_BLOCK`, `TYPE` (UDTs), `STRUCT`, `ARRAY`, and complex expressions.
-   **Intelligent Tag Resolution:** The Python library can scan an entire project to build a symbol table of User-Defined Types (UDTs), allowing it to accurately resolve the full, nested structure of tags within a Data Block.
-   **Array Expansion:** Correctly expands array declarations (e.g., `ARRAY[0..19] OF ...`) into individual tag elements.
-   **Included GUI Application:** A user-friendly tool to visually analyze source files and extract a complete list of all resolved tags.

---

## Installation

### Prerequisites

To install and use this library, you will need the following tools on your system:

1.  **Python:** Version 3.10 or higher.
2.  **Git:** Required to clone the `tree-sitter-scl` grammar dependency. You can download it from [git-scm.com](https://git-scm.com).
3.  **A C Compiler:** This is necessary to build the parser's C extension.
    *   **Windows:** Install [Microsoft C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/). During installation, select the "Desktop development with C++" workload.
    *   **macOS:** Install Xcode Command Line Tools by running `xcode-select --install`.
    *   **Linux (Debian/Ubuntu):** Install the build essentials package: `sudo apt-get install build-essential`.

### Installation Steps

It is highly recommended to install this package within a Python virtual environment.

1.  **Clone this repository (or download the source):**
    ```bash
    git clone https://github.com/your-username/scl-sitter-main.git
    cd scl-sitter-main
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    # Create the environment
    python -m venv venv

    # Activate the environment
    # On Windows (PowerShell):
    .\venv\Scripts\Activate.ps1
    # On macOS/Linux:
    # source venv/bin/activate
    ```

3.  **Install the package in editable mode:**
    This single command will install all dependencies (including cloning and building the grammar from GitHub) and create the command-line script for the GUI.
    ```bash
    pip install -e .
    ```

The installation is now complete.

---

## Usage

### 1. Using the GUI Application

The easiest way to analyze your projects is with the included GUI.

1.  Make sure your virtual environment is activated.
2.  Run the following command in your terminal:
    ```bash
    scl-sitter-gui
    ```

**Workflow within the GUI:**

1.  **Step 1: Scan Project Folder for Types:** Click this button first and select the root folder of your PLC project. This scans all `.udt` and `.db` files to build a complete dictionary of your custom data types.
2.  **Step 2: Analyze Source File:** After the scan is complete, click this button and select a specific `.db` file you wish to analyze. The application will display the source code and the fully resolved list of all tags within that Data Block.

### 2. Using as a Python Library

You can also import and use the `SCLParser` class in your own Python scripts for custom automation and analysis.

```python
from scl_sitter import SCLParser
from pathlib import Path

# 1. Initialize the parser
parser = SCLParser()

# 2. First Pass: Scan the entire project to build the type dictionary
project_folder = "C:/path/to/your/plc_project"
parser.scan_project_for_types(project_folder)

# 3. Second Pass: Parse a specific DB file
db_file_path = "C:/path/to/your/db/MyDataBlock.db"
tree = parser.parse_file(db_file_path)

# Find the DATA_BLOCK node in the tree
# (Note: This simple example assumes one DB per file)
db_node = next((n for n in tree.root_node.children if n.type == 'data_block'), None)

# 4. Resolve and print all tags within that DB
if db_node:
    all_tags = parser.get_all_tags_from_db_node(db_node)
    
    print(f"Found {len(all_tags)} tags in {Path(db_file_path).name}:")
    for tag in all_tags:
        print(tag)