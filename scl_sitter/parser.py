
"""
Simple SCL parser module using tree-sitter.
"""

import os
from tree_sitter import Parser, Tree
import tree_sitter_scl

# Initialize parser
parser = Parser()
parser.language = tree_sitter_scl.language


def parse_scl_code(code: bytes) -> Tree:
    """Parse SCL code from bytes.
    
    Args:
        code: SCL source code as bytes
        
    Returns:
        Parse tree
    """
    tree = parser.parse(code)
    return tree


def parse_scl_file(file_path: str) -> Tree:
    """Parse SCL file.
    
    Args:
        file_path: Path to SCL file
        
    Returns:
        Parse tree
        
    Raises:
        FileNotFoundError: If file doesn't exist
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
        
    with open(file_path, 'rb') as f:
        content = f.read()
    return parse_scl_code(content)


def walk_tree(tree: Tree):
    """Walk through tree nodes using tree-sitter cursor.
    
    Args:
        tree: Parse tree to walk
        
    Returns:
        List of node information
    """
    cursor = tree.walk()
    
    visited_nodes = []
    
    def visit_node():
        node = cursor.node
        visited_nodes.append({
            'type': node.type,
            'start_point': node.start_point,
            'end_point': node.end_point,
            'text': node.text.decode('utf-8', errors='replace') if node.text else None
        })
    
    def traverse():
        visit_node()
        
        if cursor.goto_first_child():
            traverse()
            while cursor.goto_next_sibling():
                traverse()
            cursor.goto_parent()
    
    traverse()
    return visited_nodes


def get_parse_errors(tree: Tree):
    """Get parse errors from tree.
    
    Args:
        tree: Parse tree to check
        
    Returns:
        List of error nodes
    """
    errors = []
    
    def find_errors(node):
        if node.has_error or "ERROR" in node.type or node.is_missing:
            errors.append({
                'type': node.type,
                'start_point': node.start_point,
                'end_point': node.end_point,
                'is_missing': node.is_missing,
                'text': node.text.decode('utf-8', errors='replace') if node.text else None
            })
        
        for child in node.children:
            find_errors(child)
    
    find_errors(tree.root_node)
    return errors


def extract_type_definitions(tree: Tree):
    """Extract type definitions from parse tree.
    
    Args:
        tree: Parse tree to analyze
        
    Returns:
        Dictionary with type names as keys and field dictionaries as values
        Format: {"TypeName": {"field1": "Bool", "field2": "ArrayTypeName"}}
        Array types are separate definitions with dict values containing detailed array info
    """
    type_definitions = {}
    inline_struct_counter = [0]  # Use list to allow modification in nested function
    array_type_counter = [0]    # Counter for array types
    
    def find_type_definitions(node):
        if node.type == "type_definition":
            type_info = _extract_type_info_with_structs_and_arrays(node, type_definitions, inline_struct_counter, array_type_counter)
            if type_info and 'name' in type_info:
                type_definitions[type_info['name']] = type_info['fields']
        
        # Recursively search child nodes
        for child in node.children:
            find_type_definitions(child)
    
    find_type_definitions(tree.root_node)
    return type_definitions


def _extract_type_info_with_structs_and_arrays(type_node, type_definitions, inline_struct_counter, array_type_counter):
    """Extract type info with proper handling of inline struct definitions and array types."""
    if type_node.type != "type_definition":
        return None
    
    type_info = {
        'name': None,
        'fields': {}
    }
    
    # Find the struct_definition node and extract type name
    struct_def = None
    for child in type_node.children:
        if child.type == "identifier":
            for subchild in child.children:
                if subchild.type == "quoted_identifier":
                    text = subchild.text.decode('utf-8', errors='replace') if subchild.text else ""
                    if text.startswith('"') and text.endswith('"'):
                        type_info['name'] = text[1:-1]
        elif child.type == "struct_definition":
            struct_def = child
    
    if not struct_def:
        return type_info
    
    # Extract fields from the struct definition, handling inline structs and arrays
    fields_list = []
    for child in struct_def.children:
        if child.type == "fields":
            field_info = _extract_field_from_fields_node(child)
            if field_info:
                fields_list.append(field_info)
    
    # Process fields to group inline struct fields and extract arrays
    i = 0
    while i < len(fields_list):
        field = fields_list[i]
        
        # Check if this field is an array type
        if _is_array_type(field['type']):
            # Extract array information and create separate array type
            array_info = _parse_array_type(field['type'])
            if array_info:
                # Generate unique name for array type
                array_type_counter[0] += 1
                array_type_name = f"{type_info['name']}_{field['name']}_ArrayType_{array_type_counter[0]}"
                
                # Create array type definition with list value [bounds, element_type]
                type_definitions[array_type_name] = array_info
                
                # Reference the array type in the main field
                type_info['fields'][field['name']] = f'"{array_type_name}"'
            else:
                # Fallback to original type if parsing failed
                type_info['fields'][field['name']] = field['type']
            i += 1
            
        elif field['type'] == 'Struct':
            # This field is an inline struct - collect subsequent fields until we reach the boundary
            nested_fields = {}
            j = i + 1
            
            # Look for fields that belong to this inline struct
            # Stop when we find a field that doesn't look nested or when we've found enough nested fields
            nested_count = 0
            while j < len(fields_list) and nested_count < 10:  # Safety limit
                next_field = fields_list[j]
                
                # Check if this field looks like it belongs to the inline struct
                if _looks_like_nested_field(next_field, field):
                    nested_fields[next_field['name']] = next_field['type']
                    nested_count += 1
                    j += 1
                else:
                    # This field doesn't look nested, so stop grouping
                    break
            
            # Create separate type definition for inline struct if it has fields
            if nested_fields:
                # Generate unique name for inline struct type
                inline_struct_counter[0] += 1
                inline_type_name = f"{type_info['name']}_{field['name']}_InlineStruct_{inline_struct_counter[0]}"
                
                # Add the inline struct as a separate type definition
                type_definitions[inline_type_name] = nested_fields
                
                # Reference the inline struct type in the main field
                type_info['fields'][field['name']] = f'"{inline_type_name}"'
                i = j  # Skip the fields we've already processed
            else:
                type_info['fields'][field['name']] = field['type']
                i += 1
        else:
            # Regular field
            type_info['fields'][field['name']] = field['type']
            i += 1
    
    return type_info


def _is_array_type(type_string):
    """Check if a type string represents an array type."""
    return type_string and type_string.startswith('Array[')


def _parse_array_type(type_string):
    """Parse array type string and extract detailed array information.
    
    Args:
        type_string: Array type string like "Array[0..5] of Int" or "Array[0..2, 0..3] of Real"
        
    Returns:
        Dictionary with array details: {
            "element_type": "Int",
            "dimensions": [{"start": 0, "end": 5, "size": 6}],
            "total_elements": 6,
            "is_multi_dimensional": False
        }
    """
    if not _is_array_type(type_string):
        return None
    
    try:
        # Extract bounds and element type from "Array[bounds] of element_type"
        # Find the bounds part between [ and ]
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
        
        # Split by comma for multi-dimensional arrays
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
                    # If we can't parse as integers, store as strings
                    dimensions.append({
                        "start": start_str.strip(),
                        "end": end_str.strip(),
                        "size": f"{end_str.strip()} - {start_str.strip()} + 1"
                    })
                    total_elements = "calculated"
        
        return {
            "element_type": element_type,
            "dimensions": dimensions,
            "total_elements": total_elements,
            "is_multi_dimensional": len(dimensions) > 1
        }
        
    except Exception:
        return None


def _looks_like_nested_field(field, struct_field):
    """Determine if a field looks like it belongs to an inline struct.
    
    This is a simple heuristic based on field types.
    """
    # Fields with basic types that come from regular 'fields' nodes might be nested
    if field['type'] in ['String', 'Int', 'Real', 'Bool', 'UInt', 'DInt', 'Word', 'DWord']:
        return True
    
    # Other types are likely not nested
    return False


def _extract_type_info(type_node):
    """Extract information from a type_definition node.
    
    Args:
        type_node: A type_definition node from the parse tree
        
    Returns:
        Dictionary with type information
    """
    if type_node.type != "type_definition":
        return None
    
    type_info = {
        'name': None,
        'node_type': type_node.type,
        'start_point': type_node.start_point,
        'end_point': type_node.end_point,
        'text': type_node.text.decode('utf-8', errors='replace') if type_node.text else None,
        'fields': [],
        'base_type': None
    }
    
    # Search for type name and structure fields
    def extract_details(node):
        # Look for type name in quoted_identifier or identifier
        if node.type == "quoted_identifier":
            text = node.text.decode('utf-8', errors='replace') if node.text else ""
            # Remove quotes from string literals
            if text.startswith('"') and text.endswith('"'):
                text = text[1:-1]
            if not type_info['name'] and text and not text.isspace():
                type_info['name'] = text
        
        # Look for fields node which contains field declarations
        elif node.type == "fields":
            field_info = _extract_field_from_fields_node(node)
            if field_info:
                type_info['fields'].append(field_info)
        
        # Look for base type information
        elif node.type in ["data_type", "type_reference"]:
            if node.text and not type_info['base_type']:
                type_info['base_type'] = node.text.decode('utf-8', errors='replace')
        
        # Recursively process children
        for child in node.children:
            extract_details(child)
    
    extract_details(type_node)
    return type_info


def _extract_field_from_fields_node(fields_node):
    """Extract field information from a fields node.
    
    Args:
        fields_node: A fields node containing field declarations
        
    Returns:
        Dictionary with field information or None
    """
    field_info = {
        'name': None,
        'type': None,
        'node_type': fields_node.type,
        'start_point': fields_node.start_point,
        'end_point': fields_node.end_point,
        'nested_fields': {}  # For inline struct definitions
    }
    
    # Look for identifier and type within the fields node
    for child in fields_node.children:
        if child.type == "identifier":
            # Check if it's a simple_identifier or quoted_identifier child
            for subchild in child.children:
                if subchild.type in ["simple_identifier", "quoted_identifier"]:
                    text = subchild.text.decode('utf-8', errors='replace') if subchild.text else ""
                    # Remove quotes if present
                    if text.startswith('"') and text.endswith('"'):
                        text = text[1:-1]
                    if text and not text.isspace() and not field_info['name']:
                        field_info['name'] = text
        
        elif child.type == "type":
            # Extract type information
            text = child.text.decode('utf-8', errors='replace') if child.text else ""
            if text and not text.isspace() and not field_info['type']:
                field_info['type'] = text
        
        # Check for inline struct definition
        elif child.type == "struct_definition":
            field_info['type'] = "Struct"
            # Extract nested fields from the inline struct
            field_info['nested_fields'] = _extract_inline_struct_fields(child)
    
    return field_info if field_info['name'] and field_info['type'] else None


def _extract_inline_struct_fields(struct_node):
    """Extract fields from an inline struct definition.
    
    Args:
        struct_node: A struct_definition node
        
    Returns:
        Dictionary mapping field names to their types
    """
    nested_fields = {}
    
    def extract_nested_field(node):
        if node.type == "fields":
            # Extract field info from this fields node
            field_info = _extract_field_from_fields_node(node)
            if field_info and field_info['name']:
                if field_info['nested_fields']:
                    # This field has its own nested struct - use dict
                    nested_fields[field_info['name']] = field_info['nested_fields']
                else:
                    # Simple field - use type string
                    nested_fields[field_info['name']] = field_info['type']
        
        # Recursively process children
        for child in node.children:
            extract_nested_field(child)
    
    extract_nested_field(struct_node)
    return nested_fields


def _extract_field_info(field_node):
    """Extract field information from a field declaration node.
    
    Args:
        field_node: A field declaration node
        
    Returns:
        Dictionary with field information
    """
    field_info = {
        'name': None,
        'type': None,
        'node_type': field_node.type,
        'start_point': field_node.start_point,
        'end_point': field_node.end_point
    }
    
    def extract_field_details(node):
        if node.type in ["identifier", "field_name"] and not field_info['name']:
            text = node.text.decode('utf-8', errors='replace') if node.text else ""
            if text and not text.isspace():
                field_info['name'] = text
        
        elif node.type in ["data_type", "type_reference", "primitive_type"] and not field_info['type']:
            text = node.text.decode('utf-8', errors='replace') if node.text else ""
            if text and not text.isspace():
                field_info['type'] = text
        
        # Recursively process children
        for child in node.children:
            extract_field_details(child)
    
    extract_field_details(field_node)
    return field_info if field_info['name'] else None

