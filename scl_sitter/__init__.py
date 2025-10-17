# scl_sitter/__init__.py

"""
SCL Sitter - A Python Toolkit for Siemens SCL

This package provides a powerful, object-oriented interface for parsing SCL code.
It features a project-aware parser that can build a symbol table (dictionary) of
User-Defined Types (UDTs) to accurately resolve the full tag structure of Data Blocks.

The package also includes a GUI application for interactive analysis.
"""

__version__ = "0.1.0"

## CHANGE: The import list is drastically simplified.
## We only expose the main SCLParser class for developers to use as a library.
## The old, flawed functional API and dataclasses are no longer exposed.
from .parser_oop import SCLParser

## CHANGE: The gui module is imported separately.
## This is done so the `pyproject.toml` [project.scripts] entry point can find it.
## We do not add the `gui` module to `__all__` because it's not meant to be
## imported by other developers' code, only run as a script.
from . import gui


## CHANGE: The __all__ list is now very clean.
## It tells Python that `from scl_sitter import *` should only import SCLParser.
__all__ = [
    "SCLParser",
]