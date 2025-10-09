#!/usr/bin/env python3
"""
Quick Start Example for SCL Parser

A minimal example showing the most common use cases.
"""

import sys
import os

# Import logging configuration
from logging_config import setup_logging, get_example_logger

# Set up logging
setup_logging()
logger = get_example_logger(__name__)

# Add parent directory to path for import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from scl_sitter.parser import parse_scl_code, get_parse_errors


def quick_example():
    """Quick example of parsing SCL code"""
    
    # Your SCL code as a string
    scl_code = "VAR_GLOBAL counter : INT; END_VAR"
    
    # Parse it (convert string to bytes first)
    tree = parse_scl_code(scl_code.encode('utf-8'))
    
    # Check for errors
    errors = get_parse_errors(tree)
    
    # Display results
    logger.info(f"Code: {scl_code}")
    logger.info(f"Parse successful: {tree.root_node.type == 'source_file'}")
    logger.info(f"Errors found: {len(errors)}")
    
    if errors:
        logger.warning("Parsing issues detected - check your SCL syntax")
        for i, error in enumerate(errors[:3]):  # Show first 3 errors
            logger.error(f"Error {i+1}: {error['type']} at {error['start_point']}")
    else:
        logger.info("Code parsed successfully!")


if __name__ == "__main__":
    logger.info("SCL Parser - Quick Start")
    logger.info("=" * 30)
    quick_example()