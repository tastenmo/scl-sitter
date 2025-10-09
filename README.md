# SCL Sitter

A Python library for parsing Siemens SCL (Structured Control Language) code using tree-sitter.

## Features

- Parse SCL source code and files
- Extract type definitions (UDT - User Defined Types)
- Handle inline struct definitions
- Advanced array type parsing with detailed metadata
- Tree traversal utilities
- Error detection and reporting

## Installation

```bash
poetry install
```

## Usage

```python
from scl_sitter.parser import parse_scl_code, extract_type_definitions

# Parse SCL code
scl_code = '''
TYPE "MyType"
VERSION : 0.1
   STRUCT
      field1 : Bool;
      field2 : Int;
   END_STRUCT;
END_TYPE
'''

tree = parse_scl_code(scl_code.encode('utf-8'))
types = extract_type_definitions(tree)

print(types)
# Output: {'MyType': {'field1': 'Bool', 'field2': 'Int'}}
```

## Testing

```bash
poetry run pytest
```

## Features

### Type Definition Extraction
- Extracts UDT structures with field information
- Creates separate type definitions for inline structs
- Generates detailed array type metadata

### Array Type Support
- Parses array bounds and dimensions
- Calculates total element counts
- Supports multi-dimensional arrays
- Rich metadata for code generation

### Inline Struct Handling
- Automatically extracts inline struct definitions as separate types
- Maintains references using quoted type names
- Provides flat, navigable type structure

## Dependencies

- `tree-sitter`: Core parsing library
- `tree-sitter-scl`: SCL grammar for tree-sitter
- `pytest`: Testing framework (dev dependency)