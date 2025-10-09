"""
Logging configuration for SCL Parser examples.

This module provides a standard logging configuration that can be imported
by example scripts to ensure consistent logging behavior.
"""

import logging
import sys


def setup_logging(level=logging.INFO, format_string=None):
    """
    Set up logging configuration for examples.
    
    Args:
        level: Logging level (default: INFO)
        format_string: Custom format string (optional)
    
    Returns:
        Configured logger instance
    """
    if format_string is None:
        format_string = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Clear any existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Configure logging
    logging.basicConfig(
        level=level,
        format=format_string,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    return logging.getLogger(__name__)


def get_example_logger(name):
    """
    Get a logger for an example script.
    
    Args:
        name: Name for the logger (usually __name__)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


# Convenience function for simple setup
def simple_setup():
    """Simple one-line setup for basic logging needs."""
    setup_logging()
    return get_example_logger('scl_examples')