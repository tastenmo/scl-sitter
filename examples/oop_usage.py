#!/usr/bin/env python3
"""
Object-Oriented SCL Parser Example

This file demonstrates how to use the new object-oriented SCL parser interface,
which provides better state management, cleaner code organization, and more
advanced features compared to the functional approach.
"""

import sys
import os

# Import logging configuration
from logging_config import setup_logging, get_example_logger

# Set up logging
setup_logging()
logger = get_example_logger(__name__)

# Add the parent directory to Python path to import scl_sitter
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from scl_sitter.parser_oop import SCLParser, SCLParseResult, TypeDefinition, ParseError


def example_1_basic_oop_usage():
    """Example 1: Basic usage of the OOP parser"""
    logger.info("=" * 50)
    logger.info("Example 1: Basic OOP Parser Usage")
    logger.info("=" * 50)
    
    # Create a parser instance
    parser = SCLParser()
    logger.info(f"Created parser: {parser}")
    
    # Parse some SCL code
    scl_code = "VAR_GLOBAL counter : INT; flag : BOOL; END_VAR"
    logger.info(f"Parsing: {scl_code}")
    
    result = parser.parse_code(scl_code)
    logger.info(f"✓ Result type: {type(result).__name__}")
    logger.info(f"✓ Root node: {result.root_node_type}")
    logger.info(f"✓ Has errors: {result.has_errors}")
    logger.info("")


def example_2_result_analysis():
    """Example 2: Detailed result analysis"""
    logger.info("=" * 50)
    logger.info("Example 2: Result Analysis")
    logger.info("=" * 50)
    
    parser = SCLParser()
    code = "VAR_GLOBAL temperature : REAL; END_VAR"
    result = parser.parse_code(code)
    
    # Analyze the result
    logger.info(f"Code: {code}")
    logger.info(f"Parse successful: {not result.has_errors}")
    
    # Check for errors
    errors = result.get_errors()
    logger.info(f"Errors found: {len(errors)}")
    for i, error in enumerate(errors[:3]):
        logger.warning(f"  Error {i+1}: {error.error_type} at {error.start_point}")
    
    # Get type definitions
    type_defs = result.get_type_definitions()
    logger.info(f"Type definitions: {len(type_defs)}")
    for name, typedef in type_defs.items():
        logger.info(f"  - {name}: {typedef.category}")
    
    logger.info("")


def example_3_state_management():
    """Example 3: Parser state management"""
    logger.info("=" * 50)
    logger.info("Example 3: Parser State Management")
    logger.info("=" * 50)
    
    parser = SCLParser()
    
    # Parse multiple code snippets
    codes = [
        "VAR x : INT; END_VAR",
        "VAR y : REAL; END_VAR", 
        "VAR invalid syntax"
    ]
    
    results = []
    for i, code in enumerate(codes):
        logger.info(f"Parse {i+1}: {code}")
        result = parser.parse_code(code)
        results.append(result)
        
        status = "✓ Success" if not result.has_errors else f"✗ {len(result.get_errors())} errors"
        logger.info(f"  Status: {status}")
    
    # Access last result
    logger.info(f"Last result available: {parser.last_result is not None}")
    if parser.last_result:
        logger.info(f"Last parse had {len(parser.last_result.get_errors())} errors")
    
    logger.info("")


def example_4_one_step_analysis():
    """Example 4: One-step analysis"""
    logger.info("=" * 50)
    logger.info("Example 4: One-Step Analysis")
    logger.info("=" * 50)
    
    parser = SCLParser()
    code = "VAR_GLOBAL status : BOOL; counter : INT; END_VAR"
    
    # Analyze everything in one call
    analysis = parser.analyze(code)
    
    logger.info(f"Code: {code}")
    logger.info("Analysis results:")
    logger.info(f"  ✓ Parse successful: {analysis['parse_successful']}")
    logger.info(f"  ✓ Root node type: {analysis['root_node_type']}")
    logger.info(f"  ✓ Error count: {len(analysis['errors'])}")
    logger.info(f"  ✓ Type definitions: {len(analysis['type_definitions'])}")
    logger.info(f"  ✓ Total nodes: {analysis['node_count']}")
    
    logger.info("")


def example_5_file_parsing():
    """Example 5: File parsing with OOP interface"""
    logger.info("=" * 50)
    logger.info("Example 5: File Parsing")
    logger.info("=" * 50)
    
    parser = SCLParser()
    
    # Create a temporary SCL file for demonstration
    temp_file = "temp_example.scl"
    scl_content = """VAR_GLOBAL
    counter : INT;
    temperature : REAL;
    active : BOOL;
END_VAR"""
    
    try:
        # Write temporary file
        with open(temp_file, 'w') as f:
            f.write(scl_content)
        
        logger.info(f"Created temporary file: {temp_file}")
        logger.info(f"Content:\n{scl_content}")
        
        # Parse the file
        result = parser.parse_file(temp_file)
        logger.info(f"✓ File parsed successfully")
        logger.info(f"✓ Root type: {result.root_node_type}")
        logger.info(f"✓ Has errors: {result.has_errors}")
        
        # Clean up
        os.remove(temp_file)
        logger.info(f"✓ Cleaned up temporary file")
        
    except Exception as e:
        logger.error(f"File parsing error: {e}")
        # Clean up on error
        if os.path.exists(temp_file):
            os.remove(temp_file)
    
    logger.info("")


def example_6_advanced_features():
    """Example 6: Advanced OOP features"""
    logger.info("=" * 50)
    logger.info("Example 6: Advanced Features")
    logger.info("=" * 50)
    
    parser = SCLParser()
    
    # Parse code with potential type definitions
    complex_code = """VAR_GLOBAL
    simple_var : INT;
    complex_var : STRING[50];
END_VAR"""
    
    result = parser.parse_code(complex_code)
    
    # Use method chaining and properties
    logger.info(f"Code: {complex_code}")
    logger.info(f"✓ Parser language: {parser.language}")
    logger.info(f"✓ Result has errors: {result.has_errors}")
    
    # Walk the tree using the parser
    nodes = parser.walk_tree(result)
    logger.info(f"✓ Tree contains {len(nodes)} nodes")
    
    # Show first few nodes
    logger.info("First 3 nodes:")
    for i, node in enumerate(nodes[:3]):
        logger.info(f"  {i+1}. {node.node_type}: '{node.text[:20]}...' if node.text else 'no text'")
    
    # Error handling demonstration
    logger.info("\nTesting error handling:")
    try:
        empty_parser = SCLParser()
        empty_parser.get_errors()  # Should raise ValueError
    except ValueError as e:
        logger.info(f"✓ Proper error handling: {e}")
    
    logger.info("")


def example_7_backward_compatibility():
    """Example 7: Using both OOP and functional interfaces"""
    logger.info("=" * 50)
    logger.info("Example 7: Backward Compatibility")
    logger.info("=" * 50)
    
    # Import old functional interface
    from scl_sitter.parser_oop import parse_scl_code, get_parse_errors
    
    code = "VAR test : INT; END_VAR"
    
    # Use new OOP interface
    logger.info("Using OOP interface:")
    oop_parser = SCLParser()
    oop_result = oop_parser.parse_code(code)
    logger.info(f"  ✓ OOP result: {oop_result.root_node_type}, errors: {len(oop_result.get_errors())}")
    
    # Use old functional interface 
    logger.info("Using functional interface:")
    func_tree = parse_scl_code(code.encode('utf-8'))
    func_errors = get_parse_errors(func_tree)
    logger.info(f"  ✓ Functional result: {func_tree.root_node.type}, errors: {len(func_errors)}")
    
    logger.info("✓ Both interfaces work seamlessly!")
    logger.info("")


def main():
    """Run all OOP examples"""
    logger.info("SCL Parser - Object-Oriented Examples")
    logger.info("=" * 70)
    logger.info("This script demonstrates the new OOP interface for SCL parsing.")
    logger.info("=" * 70)
    logger.info("")
    
    # Run all examples
    example_1_basic_oop_usage()
    example_2_result_analysis()
    example_3_state_management()
    example_4_one_step_analysis()
    example_5_file_parsing()
    example_6_advanced_features()
    example_7_backward_compatibility()
    
    logger.info("=" * 70)
    logger.info("All OOP examples completed!")
    logger.info("")
    logger.info("Key benefits of the OOP interface:")
    logger.info("  • Better state management with parser instances")
    logger.info("  • Cleaner result objects with built-in analysis methods")
    logger.info("  • Type-safe data classes for structured information")
    logger.info("  • Improved error handling and logging")
    logger.info("  • Full backward compatibility with functional interface")
    logger.info("  • Extensible design for future enhancements")


if __name__ == "__main__":
    main()