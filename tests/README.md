# SCL Sitter Testing

This document describes the testing setup for the SCL Sitter project.

## Test Structure

```
tests/
├── __init__.py
└── test_parser_simple.py    # Tests for scl_sitter.parser module
```

## Test Categories

### Parser Tests (`test_parser_simple.py`)
Tests for the core SCL parser functionality:

- **Function Existence Tests**: Verify all expected functions are available
- **Basic Parsing Tests**: Test parsing simple SCL code snippets
- **File Parsing Tests**: Test parsing SCL files from disk
- **Tree Walking Tests**: Test syntax tree traversal functionality
- **Integration Tests**: Test parsing complete SCL constructs (function blocks, UDTs)
- **Error Detection Tests**: Verify parser can handle invalid syntax
- **Parametrized Tests**: Test various code snippets and file extensions

## Running Tests

### Quick Test
```bash
poetry run pytest tests/ -v
```

### Specific Test Classes
```bash
# Run only parser tests
poetry run pytest tests/test_parser_simple.py -v

# Run specific test class
poetry run pytest tests/test_parser_simple.py::TestSCLParser -v
```

### Test with Coverage (if installed)
```bash
poetry run pytest tests/ --cov=scl_sitter --cov-report=html
```

## Test Dependencies

The tests automatically skip tree-sitter related tests if the required dependencies are not available:

- `tree-sitter`
- `tree-sitter-scl`

Tests use the `@pytest.mark.skipif` decorator to handle missing dependencies gracefully.

## Test Results Summary

Recent test run results:
- ✅ 23 tests passed
- ✅ All parser functions working correctly
- ✅ Tree-sitter SCL integration working
- ✅ File operations tested
- ✅ Error handling tested

## Adding New Tests

To add new tests:

1. Create test functions that start with `test_`
2. Use `@pytest.mark.skipif(not _is_tree_sitter_available())` for tests requiring tree-sitter
3. Use `tmp_path` fixture for file operations
4. Follow the naming convention: `TestClassName::test_method_name`

## Test Utilities

Helper functions available:
- `_is_tree_sitter_available()`: Check if tree-sitter dependencies are available
- `_collect_node_types()`: Recursively collect node types from parse tree
- `_tree_has_errors()`: Check if parse tree contains error nodes

## Manual Testing

You can also test the parser manually:

```python
from scl_sitter.parser import parse_scl_code, walk_tree, get_parse_errors

# Parse some SCL code
code = b'VAR test : Bool; END_VAR'
tree = parse_scl_code(code)

# Walk the tree
nodes = walk_tree(tree)
print(f"Found {len(nodes)} nodes")

# Check for errors
errors = get_parse_errors(tree)
print(f"Found {len(errors)} errors")
```