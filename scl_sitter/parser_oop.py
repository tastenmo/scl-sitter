"""
Object-oriented SCL parser module using tree-sitter.

This module provides an OOP interface to the SCL parser functionality,
offering better state management and extensibility compared to the
functional approach.
"""

import os
import logging
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass
from tree_sitter import Parser, Tree, Node
import tree_sitter_scl


# Configure module logger
logger = logging.getLogger(__name__)


@dataclass
class ParseError:
    """Represents a parsing error."""
    error_type: str
    start_point: tuple
    end_point: tuple
    is_missing: bool
    text: Optional[str] = None
    
    def __str__(self) -> str:
        return f"{self.error_type} at {self.start_point}: {self.text[:50]}..."


@dataclass
class NodeInfo:
    """Represents information about a tree node."""
    node_type: str
    start_point: tuple
    end_point: tuple
    text: Optional[str] = None
    
    def __str__(self) -> str:
        return f"{self.node_type}: {self.text[:30]}..." if self.text else f"{self.node_type}"


@dataclass
class FieldInfo:
    """Represents field information in a type definition."""
    name: str
    field_type: str
    node_type: str
    start_point: tuple
    end_point: tuple
    nested_fields: Optional[Dict[str, Any]] = None


@dataclass
class ArrayTypeInfo:
    """Represents array type information."""
    element_type: str
    dimensions: List[Dict[str, Union[int, str]]]
    total_elements: Union[int, str]
    is_multi_dimensional: bool


@dataclass
class TypeDefinition:
    """Represents a complete type definition."""
    name: str
    fields: Dict[str, Any]
    category: str  # 'StructType', 'ArrayType', 'SimpleType'
    node_type: str
    start_point: tuple
    end_point: tuple
    base_type: Optional[str] = None
    array_info: Optional[ArrayTypeInfo] = None


class SCLParseResult:
    """Container for parse results with analysis methods."""
    
    def __init__(self, tree: Tree, source_code: str):
        self.tree = tree
        self.source_code = source_code
        self._errors: Optional[List[ParseError]] = None
        self._type_definitions: Optional[Dict[str, TypeDefinition]] = None
        
    @property
    def has_errors(self) -> bool:
        """Check if parsing resulted in errors."""
        return len(self.get_errors()) > 0
    
    @property
    def root_node_type(self) -> str:
        """Get the root node type."""
        return self.tree.root_node.type
    
    def get_errors(self) -> List[ParseError]:
        """Get all parsing errors."""
        if self._errors is None:
            self._errors = self._extract_errors()
        return self._errors
    
    def get_type_definitions(self) -> Dict[str, TypeDefinition]:
        """Get all type definitions found in the parsed code."""
        if self._type_definitions is None:
            self._type_definitions = self._extract_type_definitions()
        return self._type_definitions
    
    def _extract_errors(self) -> List[ParseError]:
        """Extract parsing errors from the tree."""
        errors = []
        
        def find_errors(node: Node):
            if node.has_error or "ERROR" in node.type or node.is_missing:
                errors.append(ParseError(
                    error_type=node.type,
                    start_point=node.start_point,
                    end_point=node.end_point,
                    is_missing=node.is_missing,
                    text=node.text.decode('utf-8', errors='replace') if node.text else None
                ))
            
            for child in node.children:
                find_errors(child)
        
        find_errors(self.tree.root_node)
        return errors
    
    def _extract_type_definitions(self) -> Dict[str, TypeDefinition]:
        """Extract type definitions from the parse tree."""
        # This would use the SCLParser's type extraction logic
        # For now, return empty dict - will be implemented by the parser
        return {}


class SCLTypeExtractor:
    """Handles extraction of type definitions from parse trees."""
    
    def __init__(self):
        self.inline_struct_counter = 0
        self.array_type_counter = 0
        
    def extract_type_definitions(self, tree: Tree) -> Dict[str, TypeDefinition]:
        """Extract type definitions from parse tree."""
        type_definitions = {}
        self.inline_struct_counter = 0
        self.array_type_counter = 0
        
        def find_type_definitions(node: Node):
            if node.type == "type_definition":
                type_info = self._extract_type_info_with_structs_and_arrays(
                    node, type_definitions
                )
                if type_info and type_info.name:
                    type_definitions[type_info.name] = type_info
            
            # Recursively search child nodes
            for child in node.children:
                find_type_definitions(child)
        
        find_type_definitions(tree.root_node)
        return type_definitions
    
    def _extract_type_info_with_structs_and_arrays(self, type_node: Node, 
                                                  type_definitions: Dict[str, TypeDefinition]) -> Optional[TypeDefinition]:
        """Extract type info with proper handling of inline struct definitions and array types."""
        if type_node.type != "type_definition":
            return None
        
        type_name = None
        fields = {}
        
        # Find the struct_definition node and extract type name
        struct_def = None
        for child in type_node.children:
            if child.type == "identifier":
                for subchild in child.children:
                    if subchild.type == "quoted_identifier":
                        text = subchild.text.decode('utf-8', errors='replace') if subchild.text else ""
                        if text.startswith('"') and text.endswith('"'):
                            type_name = text[1:-1]
            elif child.type == "struct_definition":
                struct_def = child
        
        if not struct_def or not type_name:
            return None
        
        # Extract fields from the struct definition
        fields_list = []
        for child in struct_def.children:
            if child.type == "fields":
                field_info = self._extract_field_from_fields_node(child)
                if field_info:
                    fields_list.append(field_info)
        
        # Process fields to group inline struct fields and extract arrays
        fields = self._process_fields_list(fields_list, type_name, type_definitions)
        
        return TypeDefinition(
            name=type_name,
            fields=fields,
            category="StructType",
            node_type=type_node.type,
            start_point=type_node.start_point,
            end_point=type_node.end_point
        )
    
    def _process_fields_list(self, fields_list: List[FieldInfo], 
                           type_name: str, type_definitions: Dict[str, TypeDefinition]) -> Dict[str, Any]:
        """Process a list of fields to handle inline structs and arrays."""
        processed_fields = {}
        i = 0
        
        while i < len(fields_list):
            field = fields_list[i]
            
            # Check if this field is an array type
            if self._is_array_type(field.field_type):
                array_info = self._parse_array_type(field.field_type)
                if array_info:
                    # Generate unique name for array type
                    self.array_type_counter += 1
                    array_type_name = f"{type_name}_{field.name}_ArrayType_{self.array_type_counter}"
                    
                    # Create array type definition
                    array_typedef = TypeDefinition(
                        name=array_type_name,
                        fields={},
                        category="ArrayType",
                        node_type="array_type",
                        start_point=field.start_point,
                        end_point=field.end_point,
                        array_info=array_info
                    )
                    type_definitions[array_type_name] = array_typedef
                    
                    # Reference the array type in the main field
                    processed_fields[field.name] = f'"{array_type_name}"'
                else:
                    processed_fields[field.name] = field.field_type
                i += 1
                
            elif field.field_type == 'Struct':
                # Handle inline struct
                nested_fields = {}
                j = i + 1
                
                # Collect nested fields
                nested_count = 0
                while j < len(fields_list) and nested_count < 10:
                    next_field = fields_list[j]
                    if self._looks_like_nested_field(next_field, field):
                        nested_fields[next_field.name] = next_field.field_type
                        nested_count += 1
                        j += 1
                    else:
                        break
                
                if nested_fields:
                    # Create separate type definition for inline struct
                    self.inline_struct_counter += 1
                    inline_type_name = f"{type_name}_{field.name}_InlineStruct_{self.inline_struct_counter}"
                    
                    inline_typedef = TypeDefinition(
                        name=inline_type_name,
                        fields=nested_fields,
                        category="StructType",
                        node_type="inline_struct",
                        start_point=field.start_point,
                        end_point=field.end_point
                    )
                    type_definitions[inline_type_name] = inline_typedef
                    
                    processed_fields[field.name] = f'"{inline_type_name}"'
                    i = j
                else:
                    processed_fields[field.name] = field.field_type
                    i += 1
            else:
                # Regular field
                processed_fields[field.name] = field.field_type
                i += 1
        
        return processed_fields
    
    def _extract_field_from_fields_node(self, fields_node: Node) -> Optional[FieldInfo]:
        """Extract field information from a fields node."""
        field_name = None
        field_type = None
        nested_fields = {}
        
        # Look for identifier and type within the fields node
        for child in fields_node.children:
            if child.type == "identifier":
                for subchild in child.children:
                    if subchild.type in ["simple_identifier", "quoted_identifier"]:
                        text = subchild.text.decode('utf-8', errors='replace') if subchild.text else ""
                        if text.startswith('"') and text.endswith('"'):
                            text = text[1:-1]
                        if text and not text.isspace() and not field_name:
                            field_name = text
            
            elif child.type == "type":
                text = child.text.decode('utf-8', errors='replace') if child.text else ""
                if text and not text.isspace() and not field_type:
                    field_type = text
            
            elif child.type == "struct_definition":
                field_type = "Struct"
                nested_fields = self._extract_inline_struct_fields(child)
        
        if field_name and field_type:
            return FieldInfo(
                name=field_name,
                field_type=field_type,
                node_type=fields_node.type,
                start_point=fields_node.start_point,
                end_point=fields_node.end_point,
                nested_fields=nested_fields if nested_fields else None
            )
        return None
    
    def _extract_inline_struct_fields(self, struct_node: Node) -> Dict[str, Any]:
        """Extract fields from an inline struct definition."""
        nested_fields = {}
        
        def extract_nested_field(node: Node):
            if node.type == "fields":
                field_info = self._extract_field_from_fields_node(node)
                if field_info and field_info.name:
                    if field_info.nested_fields:
                        nested_fields[field_info.name] = field_info.nested_fields
                    else:
                        nested_fields[field_info.name] = field_info.field_type
            
            for child in node.children:
                extract_nested_field(child)
        
        extract_nested_field(struct_node)
        return nested_fields
    
    def _is_array_type(self, type_string: str) -> bool:
        """Check if a type string represents an array type."""
        return type_string and type_string.startswith('Array[')
    
    def _parse_array_type(self, type_string: str) -> Optional[ArrayTypeInfo]:
        """Parse array type string and extract detailed array information."""
        if not self._is_array_type(type_string):
            return None
        
        try:
            # Extract bounds and element type from "Array[bounds] of element_type"
            start_bracket = type_string.find('[')
            end_bracket = type_string.find(']')
            if start_bracket == -1 or end_bracket == -1:
                return None
                
            bounds_str = type_string[start_bracket + 1:end_bracket]
            
            # Find "of" keyword and extract element type
            of_pos = type_string.find(' of ')
            if of_pos == -1:
                return None
                
            element_type = type_string[of_pos + 4:].strip()
            
            # Parse dimensions
            dimensions = []
            total_elements = 1
            
            bound_parts = [part.strip() for part in bounds_str.split(',')]
            
            for bound_part in bound_parts:
                if '..' in bound_part:
                    start_str, end_str = bound_part.split('..')
                    try:
                        start_val = int(start_str.strip())
                        end_val = int(end_str.strip())
                        size = end_val - start_val + 1
                        dimensions.append({
                            "start": start_val,
                            "end": end_val,
                            "size": size
                        })
                        total_elements *= size
                    except ValueError:
                        dimensions.append({
                            "start": start_str.strip(),
                            "end": end_str.strip(),
                            "size": f"{end_str.strip()} - {start_str.strip()} + 1"
                        })
                        total_elements = "calculated"
            
            return ArrayTypeInfo(
                element_type=element_type,
                dimensions=dimensions,
                total_elements=total_elements,
                is_multi_dimensional=len(dimensions) > 1
            )
            
        except Exception as e:
            logger.warning(f"Failed to parse array type '{type_string}': {e}")
            return None
    
    def _looks_like_nested_field(self, field: FieldInfo, struct_field: FieldInfo) -> bool:
        """Determine if a field looks like it belongs to an inline struct."""
        basic_types = ['String', 'Int', 'Real', 'Bool', 'UInt', 'DInt', 'Word', 'DWord']
        return field.field_type in basic_types


class SCLTreeWalker:
    """Handles walking through parse trees."""
    
    def walk_tree(self, tree: Tree) -> List[NodeInfo]:
        """Walk through tree nodes using tree-sitter cursor."""
        cursor = tree.walk()
        visited_nodes = []
        
        def visit_node():
            node = cursor.node
            visited_nodes.append(NodeInfo(
                node_type=node.type,
                start_point=node.start_point,
                end_point=node.end_point,
                text=node.text.decode('utf-8', errors='replace') if node.text else None
            ))
        
        def traverse():
            visit_node()
            
            if cursor.goto_first_child():
                traverse()
                while cursor.goto_next_sibling():
                    traverse()
                cursor.goto_parent()
        
        traverse()
        return visited_nodes


class SCLParser:
    """
    Object-oriented SCL parser using tree-sitter.
    
    This class provides a high-level interface for parsing SCL code,
    managing parser state, and extracting structured information.
    """
    
    def __init__(self):
        """Initialize the SCL parser."""
        self._parser = Parser()
        self._parser.language = tree_sitter_scl.language
        self.type_extractor = SCLTypeExtractor()
        self.tree_walker = SCLTreeWalker()
        self._last_result: Optional[SCLParseResult] = None
        
        logger.debug("SCL Parser initialized")
    
    @property
    def language(self):
        """Get the parser language."""
        return self._parser.language
    
    @property
    def last_result(self) -> Optional[SCLParseResult]:
        """Get the last parse result."""
        return self._last_result
    
    def parse_code(self, code: Union[str, bytes]) -> SCLParseResult:
        """
        Parse SCL code from string or bytes.
        
        Args:
            code: SCL source code as string or bytes
            
        Returns:
            SCLParseResult containing the parse tree and analysis methods
        """
        if isinstance(code, str):
            code_bytes = code.encode('utf-8')
            source_code = code
        else:
            code_bytes = code
            source_code = code.decode('utf-8', errors='replace')
        
        logger.debug(f"Parsing SCL code ({len(code_bytes)} bytes)")
        
        tree = self._parser.parse(code_bytes)
        result = SCLParseResult(tree, source_code)
        
        # Inject type extraction functionality
        result._extract_type_definitions = lambda: self.type_extractor.extract_type_definitions(tree)
        
        self._last_result = result
        logger.debug(f"Parse completed, root type: {tree.root_node.type}")
        
        return result
    
    def parse_file(self, file_path: str) -> SCLParseResult:
        """
        Parse SCL file.
        
        Args:
            file_path: Path to SCL file
            
        Returns:
            SCLParseResult containing the parse tree and analysis methods
            
        Raises:
            FileNotFoundError: If file doesn't exist
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        logger.debug(f"Parsing SCL file: {file_path}")
        
        with open(file_path, 'rb') as f:
            content = f.read()
        
        result = self.parse_code(content)
        logger.info(f"Successfully parsed file: {file_path}")
        return result
    
    def walk_tree(self, result: Optional[SCLParseResult] = None) -> List[NodeInfo]:
        """
        Walk through tree nodes.
        
        Args:
            result: Parse result to walk (uses last result if None)
            
        Returns:
            List of NodeInfo objects
        """
        if result is None:
            result = self.last_result
        
        if result is None:
            raise ValueError("No parse result available. Parse some code first.")
        
        return self.tree_walker.walk_tree(result.tree)
    
    def get_errors(self, result: Optional[SCLParseResult] = None) -> List[ParseError]:
        """
        Get parse errors.
        
        Args:
            result: Parse result to check (uses last result if None)
            
        Returns:
            List of ParseError objects
        """
        if result is None:
            result = self.last_result
        
        if result is None:
            raise ValueError("No parse result available. Parse some code first.")
        
        return result.get_errors()
    
    def extract_type_definitions(self, result: Optional[SCLParseResult] = None) -> Dict[str, TypeDefinition]:
        """
        Extract type definitions from parse tree.
        
        Args:
            result: Parse result to analyze (uses last result if None)
            
        Returns:
            Dictionary mapping type names to TypeDefinition objects
        """
        if result is None:
            result = self.last_result
        
        if result is None:
            raise ValueError("No parse result available. Parse some code first.")
        
        return result.get_type_definitions()
    
    def analyze(self, code: Union[str, bytes]) -> Dict[str, Any]:
        """
        Parse and analyze SCL code in one step.
        
        Args:
            code: SCL source code
            
        Returns:
            Dictionary with complete analysis results
        """
        result = self.parse_code(code)
        
        return {
            'parse_successful': not result.has_errors,
            'root_node_type': result.root_node_type,
            'errors': result.get_errors(),
            'type_definitions': result.get_type_definitions(),
            'node_count': len(self.walk_tree(result))
        }
    
    def __repr__(self) -> str:
        return f"SCLParser(language={self.language})"


# Backward compatibility functions that delegate to the OOP interface
_default_parser = None

def get_default_parser() -> SCLParser:
    """Get the default parser instance."""
    global _default_parser
    if _default_parser is None:
        _default_parser = SCLParser()
    return _default_parser


def parse_scl_code(code: bytes) -> Tree:
    """Parse SCL code from bytes (backward compatibility)."""
    parser = get_default_parser()
    result = parser.parse_code(code)
    return result.tree


def parse_scl_file(file_path: str) -> Tree:
    """Parse SCL file (backward compatibility)."""
    parser = get_default_parser()
    result = parser.parse_file(file_path)
    return result.tree


def walk_tree(tree: Tree) -> List[Dict[str, Any]]:
    """Walk through tree nodes (backward compatibility)."""
    parser = get_default_parser()
    walker = SCLTreeWalker()
    nodes = walker.walk_tree(tree)
    
    # Convert to old format
    return [
        {
            'type': node.node_type,
            'start_point': node.start_point,
            'end_point': node.end_point,
            'text': node.text
        }
        for node in nodes
    ]


def get_parse_errors(tree: Tree) -> List[Dict[str, Any]]:
    """Get parse errors from tree (backward compatibility)."""
    # Create a temporary result object
    result = SCLParseResult(tree, "")
    errors = result.get_errors()
    
    # Convert to old format
    return [
        {
            'type': error.error_type,
            'start_point': error.start_point,
            'end_point': error.end_point,
            'is_missing': error.is_missing,
            'text': error.text
        }
        for error in errors
    ]


def extract_type_definitions(tree: Tree) -> Dict[str, Any]:
    """Extract type definitions from parse tree (backward compatibility)."""
    # Use the original parser's implementation for full backward compatibility
    from .parser import extract_type_definitions as original_extract
    return original_extract(tree)