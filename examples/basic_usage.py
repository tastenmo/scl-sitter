#!/usr/bin/env python3
"""
SCL Parser - Basic Usage Examples

This file demonstrates how to use the scl_sitter parser module
to parse SCL (Structured Control Language) code.
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

from scl_sitter.parser import (
    parse_scl_code, 
    parse_scl_file, 
    walk_tree, 
    get_parse_errors, 
    extract_type_definitions
)


def example_1_basic_parsing():
    """Example 1: Basic SCL code parsing"""
    logger.info("=" * 50)
    logger.info("Example 1: Basic SCL Code Parsing")
    logger.info("=" * 50)
    
    # Simple SCL variable declaration
    scl_code = "VAR_GLOBAL counter : INT; END_VAR"
    logger.info(f"Parsing: {scl_code}")
    
    # Parse the code
    tree = parse_scl_code(scl_code.encode('utf-8'))
    
    # Examine the result
    logger.info(f"✓ Parse tree root type: {tree.root_node.type}")
    logger.info(f"✓ Root node has {len(tree.root_node.children)} children")
    logger.info(f"✓ Tree text: {tree.root_node.text.decode('utf-8')}")
    logger.info("")


def example_2_parsing_methods():
    """Example 2: Different parsing methods"""
    logger.info("=" * 50)
    logger.info("Example 2: Different Parsing Methods")
    logger.info("=" * 50)
    
    # Method 1: Parse from string (convert to bytes)
    code_str = "VAR temperature : REAL; END_VAR"
    tree1 = parse_scl_code(code_str.encode('utf-8'))
    logger.info(f"From string: {code_str}")
    logger.info(f"✓ Root type: {tree1.root_node.type}")
    
    # Method 2: Parse from bytes directly
    code_bytes = b"VAR flag : BOOL; END_VAR"
    tree2 = parse_scl_code(code_bytes)
    logger.info(f"From bytes: {code_bytes.decode('utf-8')}")
    logger.info(f"✓ Root type: {tree2.root_node.type}")
    logger.info("")


def example_3_tree_walking():
    """Example 3: Walking through the parse tree"""
    logger.info("=" * 50)
    logger.info("Example 3: Walking Parse Tree Structure")
    logger.info("=" * 50)
    
    scl_code = "VAR speed : INT; END_VAR"
    tree = parse_scl_code(scl_code.encode('utf-8'))
    
    logger.info(f"Analyzing: {scl_code}")
    logger.info("Tree structure:")
    
    def log_node(node, indent=0):
        """Helper function to log tree nodes with indentation"""
        spaces = "  " * indent
        node_text = node.text.decode('utf-8', errors='replace') if node.text else ""
        
        # Truncate long text for readability
        if len(node_text) > 40:
            node_text = node_text[:40] + "..."
            
        # Replace newlines for single-line display
        node_text = node_text.replace('\n', '\\n')
        
        logger.info(f"{spaces}├─ {node.type}")
        if node_text.strip():
            logger.info(f"{spaces}   Text: '{node_text}'")
            
        # Recursively log children (limit depth to avoid overwhelming output)
        if indent < 4:
            for child in node.children:
                log_node(child, indent + 1)
    
    log_node(tree.root_node)
    logger.info("")


def example_4_error_detection():
    """Example 4: Parse error detection and handling"""
    logger.info("=" * 50)
    logger.info("Example 4: Parse Error Detection")
    logger.info("=" * 50)
    
    # Test with valid code
    valid_code = "VAR counter : INT; END_VAR"
    tree = parse_scl_code(valid_code.encode('utf-8'))
    errors = get_parse_errors(tree)
    
    logger.info(f"Valid code: {valid_code}")
    logger.info(f"✓ Errors found: {len(errors)}")
    
    # Test with invalid syntax
    invalid_codes = [
        "VAR invalid syntax here",
        "VAR missing_type : ; END_VAR",
        "INVALID_KEYWORD something : INT;",
    ]
    
    for bad_code in invalid_codes:
        tree = parse_scl_code(bad_code.encode('utf-8'))
        errors = get_parse_errors(tree)
        logger.warning(f"Invalid code: {bad_code}")
        logger.warning(f"✗ Errors found: {len(errors)}")
        if errors and len(errors) <= 3:  # Don't overwhelm with too many errors
            for i, error in enumerate(errors[:2]):  # Show first 2 errors
                error_text = error.get('text', '')[:30] + "..." if len(error.get('text', '')) > 30 else error.get('text', '')
                logger.error(f"  Error {i+1}: {error['type']} at {error['start_point']} - '{error_text}'")
    logger.info("")


def example_5_type_definitions():
    """Example 5: Extracting type definitions (if any are found)"""
    logger.info("=" * 50)
    logger.info("Example 5: Type Definition Extraction")
    logger.info("=" * 50)
    
    # Try to parse code that might contain type definitions
    test_codes = [
        "VAR_GLOBAL counter : INT; name : STRING; END_VAR",
        "TYPE MyInt : INT; END_TYPE",
        "VAR arr : ARRAY[1..10] OF REAL; END_VAR",
    ]
    
    for code in test_codes:
        tree = parse_scl_code(code.encode('utf-8'))
        type_definitions = extract_type_definitions(tree)
        
        logger.info(f"Code: {code}")
        logger.info(f"✓ Type definitions found: {len(type_definitions)}")
        
        if type_definitions:
            for type_name, type_info in type_definitions.items():
                logger.info(f"  - {type_name}: {type_info}")
        else:
            logger.info("  (No type definitions extracted)")
        logger.info("")


def example_6_file_parsing_demo():
    """Example 6: File parsing demonstration"""
    logger.info("=" * 50)
    logger.info("Example 6: File Parsing (Demonstration)")
    logger.info("=" * 50)
    
    logger.info("To parse SCL files from disk, use:")
    logger.info("  tree = parse_scl_file('path/to/your/file.scl')")
    logger.info("")
    logger.info("This function will:")
    logger.info("  1. Check if the file exists")
    logger.info("  2. Read the file content as bytes")
    logger.info("  3. Parse the content using parse_scl_code()")
    logger.info("  4. Return the parse tree")
    logger.info("")
    logger.info("Example usage:")
    logger.info("  try:")
    logger.info("      tree = parse_scl_file('example.scl')")
    logger.info("      errors = get_parse_errors(tree)")
    logger.info("      if not errors:")
    logger.info("          logger.info('File parsed successfully!')")
    logger.info("      else:")
    logger.info("          logger.warning(f'Found {len(errors)} parsing errors')")
    logger.info("  except FileNotFoundError:")
    logger.info("      logger.error('SCL file not found')")
    logger.info("")


def example_7_comprehensive_workflow():
    """Example 7: Complete parsing workflow"""
    logger.info("=" * 50)
    logger.info("Example 7: Complete Parsing Workflow")
    logger.info("=" * 50)
    
    scl_code = """VAR_GLOBAL
    counter : INT;
    status : BOOL;
END_VAR"""
    
    logger.info("Complete workflow for parsing SCL code:")
    logger.info(f"Input code:\n{scl_code}")
    logger.info("")
    
    # Step 1: Parse
    logger.info("Step 1: Parse the code")
    tree = parse_scl_code(scl_code.encode('utf-8'))
    logger.info(f"✓ Parsed successfully, root type: {tree.root_node.type}")
    
    # Step 2: Check for errors
    logger.info("Step 2: Check for parsing errors")
    errors = get_parse_errors(tree)
    if errors:
        logger.warning(f"✗ Found {len(errors)} errors - code may have syntax issues")
        for error in errors[:2]:  # Show first 2 errors
            logger.error(f"  - {error['type']} at line {error['start_point'].row + 1}")
    else:
        logger.info("✓ No parsing errors found")
    
    # Step 3: Extract information
    logger.info("Step 3: Extract type definitions")
    type_definitions = extract_type_definitions(tree)
    if type_definitions:
        logger.info(f"✓ Found {len(type_definitions)} type definitions")
        for name, info in type_definitions.items():
            logger.info(f"  - {name}: {info}")
    else:
        logger.info("✓ No explicit type definitions found (variables use built-in types)")
    
    # Step 4: Analyze structure
    logger.info("Step 4: Analyze tree structure")
    logger.info(f"✓ Root node has {len(tree.root_node.children)} child nodes")
    
    logger.info("\nWorkflow complete!")
    logger.info("")


def main():
    """Run all examples"""
    logger.info("SCL Parser - Usage Examples")
    logger.info("=" * 70)
    logger.info("This script demonstrates various ways to use the SCL parser.")
    logger.info("=" * 70)
    logger.info("")
    
    # Run all examples
    example_1_basic_parsing()
    example_2_parsing_methods()
    example_3_tree_walking()
    example_4_error_detection()
    example_5_type_definitions()
    example_6_file_parsing_demo()
    example_7_comprehensive_workflow()
    
    logger.info("=" * 70)
    logger.info("All examples completed!")
    logger.info("")
    logger.info("Available functions in scl_sitter.parser:")
    logger.info("  • parse_scl_code(code_bytes) - Parse SCL from bytes")
    logger.info("  • parse_scl_file(file_path) - Parse SCL from file")  
    logger.info("  • walk_tree(tree) - Walk through all nodes")
    logger.info("  • get_parse_errors(tree) - Get parsing errors")
    logger.info("  • extract_type_definitions(tree) - Extract type definitions")
    logger.info("")
    logger.info("For more information, see the documentation in the parser module.")


if __name__ == "__main__":
    main()