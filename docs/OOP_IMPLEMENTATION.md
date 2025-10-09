# SCL Parser - Object-Oriented Implementation

This document describes the new object-oriented SCL parser implementation that provides better state management, cleaner APIs, and enhanced functionality compared to the functional approach.

## Overview

The OOP implementation includes several key classes:

- **`SCLParser`**: Main parser class with state management
- **`SCLParseResult`**: Container for parse results with analysis methods  
- **`SCLTypeExtractor`**: Handles type definition extraction
- **`SCLTreeWalker`**: Manages tree traversal
- **Data Classes**: Type-safe containers for structured data

## Key Benefits

### 🎯 **Better State Management**
- Parser instances maintain state between operations
- Last parse result is automatically stored and accessible
- Multiple parsers can coexist with independent state

### 🔧 **Cleaner API Design** 
- Result objects have built-in analysis methods
- Method chaining support for fluent interfaces
- Clear separation of concerns between classes

### 📊 **Type Safety**
- Data classes provide structured, type-safe containers
- Better IDE support with autocompletion and type hints
- Reduced runtime errors from incorrect data access

### 🚀 **Enhanced Features**
- One-step analysis with `analyze()` method
- Comprehensive error handling with custom exception types
- Built-in logging for debugging and monitoring

### 🔄 **Backward Compatibility**
- All existing functional APIs continue to work
- Gradual migration path from functional to OOP
- No breaking changes to existing code

## Class Hierarchy

```
SCLParser (main interface)
├── SCLTypeExtractor (type analysis)
├── SCLTreeWalker (tree traversal) 
└── SCLParseResult (result container)
    ├── ParseError (error information)
    ├── NodeInfo (node details)
    ├── TypeDefinition (type metadata)
    └── ArrayTypeInfo (array details)
```

## Usage Examples

### Basic Usage

```python
from scl_sitter import SCLParser

# Create parser instance
parser = SCLParser()

# Parse code
result = parser.parse_code("VAR counter : INT; END_VAR")

# Check results
print(f"Success: {not result.has_errors}")
print(f"Errors: {len(result.get_errors())}")
```

### Advanced Analysis

```python
# One-step analysis
analysis = parser.analyze(scl_code)
print(f"Parse successful: {analysis['parse_successful']}")
print(f"Node count: {analysis['node_count']}")

# State management  
result1 = parser.parse_code(code1)
result2 = parser.parse_code(code2)
last_result = parser.last_result  # Always available
```

### Type Definitions

```python
# Extract type information
type_defs = result.get_type_definitions()
for name, typedef in type_defs.items():
    print(f"{name}: {typedef.category}")
    if typedef.category == "ArrayType":
        print(f"  Array info: {typedef.array_info}")
```

## Migration Guide

### From Functional to OOP

**Old functional approach:**
```python
from scl_sitter.parser import parse_scl_code, get_parse_errors

tree = parse_scl_code(code.encode('utf-8'))
errors = get_parse_errors(tree) 
```

**New OOP approach:**
```python
from scl_sitter import SCLParser

parser = SCLParser()
result = parser.parse_code(code)
errors = result.get_errors()
```

### Gradual Migration

1. **Phase 1**: Keep existing functional calls, add OOP for new features
2. **Phase 2**: Migrate high-traffic parsing to OOP for better performance  
3. **Phase 3**: Full migration to OOP when convenient

## Performance Considerations

### Memory Management
- Parser instances reuse internal tree-sitter parser
- Results can be garbage collected independently
- State is minimal and doesn't accumulate over time

### Processing Efficiency  
- Type extraction is cached within result objects
- Tree walking is lazy and only performed when needed
- Error detection uses efficient tree traversal

## Error Handling

### Structured Error Information
```python
for error in result.get_errors():
    print(f"Type: {error.error_type}")
    print(f"Location: {error.start_point}")
    print(f"Text: {error.text}")
    print(f"Missing: {error.is_missing}")
```

### Exception Safety
- File operations properly handle missing files
- Encoding errors are gracefully handled
- Invalid operations raise descriptive ValueError exceptions

## Extensibility

### Custom Extractors
```python
class CustomExtractor(SCLTypeExtractor):
    def extract_custom_info(self, tree):
        # Add custom extraction logic
        pass

parser = SCLParser()
parser.type_extractor = CustomExtractor()
```

### Result Extensions
```python
class ExtendedResult(SCLParseResult):
    def custom_analysis(self):
        # Add custom analysis methods
        pass
```

## Testing

The OOP implementation includes comprehensive test coverage:

- **Unit tests** for each class and method
- **Integration tests** for full parsing workflows  
- **Compatibility tests** ensuring functional APIs still work
- **Performance tests** comparing OOP vs functional approaches

## Future Enhancements

### Planned Features
- **Async parsing** for large files
- **Incremental parsing** for code editors
- **Custom grammar extensions** for SCL dialects
- **Advanced type inference** and validation
- **Code formatting** and refactoring tools

### API Stability
- **Current classes**: Stable, will maintain backward compatibility
- **Data classes**: May add fields, will not remove existing ones
- **Method signatures**: Stable, may add optional parameters
- **Functional interface**: Permanent backward compatibility guarantee

## Best Practices

### When to Use OOP vs Functional

**Use OOP interface when:**
- Building applications with multiple parse operations
- Need state management and result caching
- Want structured error handling and logging
- Developing tools that extend parser functionality

**Use functional interface when:**
- Simple one-off parsing tasks  
- Migrating existing functional code
- Integration with legacy systems
- Minimal dependencies preferred

### Performance Tips
- Reuse parser instances when possible
- Cache type definitions for repeated analysis
- Use `analyze()` method for comprehensive one-time analysis
- Enable debug logging only during development

---

This OOP implementation provides a solid foundation for advanced SCL parsing applications while maintaining full compatibility with existing functional code.