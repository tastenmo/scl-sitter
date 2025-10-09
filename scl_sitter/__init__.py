"""
SCL Sitter - SCL (Structured Control Language) Parser

This package provides both functional and object-oriented interfaces 
for parsing SCL code using tree-sitter.

Available interfaces:
- Functional: parse_scl_code(), parse_scl_file(), get_parse_errors(), etc.
- Object-oriented: SCLParser class with improved state management and features
"""

__version__ = "0.1.0"

# Import functional interface (backward compatibility)
from .parser import (
    parse_scl_code,
    parse_scl_file, 
    walk_tree,
    get_parse_errors,
    extract_type_definitions
)

# Import object-oriented interface (recommended)
from .parser_oop import (
    SCLParser,
    SCLParseResult,
    ParseError,
    NodeInfo,
    FieldInfo,
    ArrayTypeInfo,
    TypeDefinition,
    SCLTypeExtractor,
    SCLTreeWalker
)

# Convenience imports for both interfaces
__all__ = [
    # Functional interface
    "parse_scl_code",
    "parse_scl_file", 
    "walk_tree",
    "get_parse_errors",
    "extract_type_definitions",
    
    # Object-oriented interface
    "SCLParser",
    "SCLParseResult", 
    "ParseError",
    "NodeInfo",
    "FieldInfo", 
    "ArrayTypeInfo",
    "TypeDefinition",
    "SCLTypeExtractor",
    "SCLTreeWalker"
]