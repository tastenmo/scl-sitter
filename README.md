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

### Functional Interface (Original)

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

### Object-Oriented Interface (Recommended)

```python
from scl_sitter import SCLParser

# Create parser instance
parser = SCLParser()

# Parse and analyze in one step
analysis = parser.analyze(scl_code)

print(f"Parse successful: {analysis['parse_successful']}")
print(f"Type definitions: {len(analysis['type_definitions'])}")

# Or parse with detailed control
result = parser.parse_code(scl_code)
if not result.has_errors:
    types = result.get_type_definitions()
    for name, typedef in types.items():
        print(f"{name}: {typedef.category} with {len(typedef.fields)} fields")
```

## Testing

```bash
poetry run pytest
```

## Interfaces

### Functional Interface
- Simple function-based API
- Backward compatible with existing code
- Good for basic parsing tasks

### Object-Oriented Interface (New)
- Better state management with parser instances
- Rich result objects with built-in analysis methods
- Type-safe data classes for structured information
- Advanced error handling and logging
- Extensible design for custom processing

## Features

### Type Definition Extraction
- Extracts UDT structures with field information
- Creates separate type definitions for inline structs (OOP interface)
- Generates detailed array type metadata

### Array Type Support
- Parses array bounds and dimensions
- Calculates total element counts
- Supports multi-dimensional arrays
- Rich metadata for code generation

### Inline Struct Handling (OOP Interface)
- Automatically extracts inline struct definitions as separate types
- Maintains references using quoted type names
- Provides flat, navigable type structure

### Advanced Features (OOP Interface)
- Parse result caching and state management
- Comprehensive error reporting with location data
- One-step analysis for complete parsing workflows
- Tree traversal with structured node information

## Dependencies

- `tree-sitter`: Core parsing library
- `tree-sitter-scl`: SCL grammar for tree-sitter
- `pytest`: Testing framework (dev dependency)