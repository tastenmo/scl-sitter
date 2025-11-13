# scl_parser.py
"""
Core SCL parsing and UDT expansion logic.
- Uses tree-sitter to build an AST.
- Converts type nodes into serializable "descriptor" dictionaries.
- Recursively expands descriptors into a list of tag suffixes.
- Uses memoization (caching) for performance.
"""
import gc
from typing import Any, Dict, List, Tuple, Set
from tree_sitter import Node

# We'll cache expansions by creating a canonical, hashable key for descriptors.
_expansion_cache: Dict[Tuple, List[str]] = {}


def get_node_text(node: Node) -> str:
    """Return trimmed text for a node, strip outer quotes if present."""
    if not node:
        return ""
    return node.text.decode("utf8").strip().strip('"')


# --- Descriptor Factories ---
def make_name_descriptor(type_name: str) -> Dict[str, Any]:
    return {"kind": "name", "name": type_name}

def make_array_descriptor(dim_list: List[Tuple[Any, Any]], base_desc: Any) -> Dict[str, Any]:
    return {"kind": "array", "dims": dim_list, "base": base_desc}

def make_struct_descriptor(fields: List[Tuple[str, Any]]) -> Dict[str, Any]:
    return {"kind": "struct", "fields": fields}


def build_type_descriptor(type_node: Node) -> Dict[str, Any]:
    """Build a nested serializable descriptor from a Tree-sitter 'type' node."""
    if not type_node:
        return make_name_descriptor("UNKNOWN")

    struct_def = next((c for c in type_node.children if c.type == "struct_definition"), None)
    if struct_def:
        fields = []
        for field_node in struct_def.children:
            if field_node.type == "fields":
                fname_node = field_node.child_by_field_name("name")
                fname = get_node_text(fname_node)
                ftype_node = next((c for c in field_node.children if c.type == "type"), None)
                fdesc = build_type_descriptor(ftype_node)
                if fname:
                    fields.append((fname, fdesc))
        return make_struct_descriptor(fields)

    array_node = next((c for c in type_node.children if c.type == "array_type"), None)
    if array_node:
        bound_nodes = [c for c in array_node.children if c.type in ("integer_literal", "identifier")]
        dims = []
        for i in range(0, len(bound_nodes), 2):
            if i + 1 < len(bound_nodes):
                s, e = get_node_text(bound_nodes[i]), get_node_text(bound_nodes[i+1])
                try:
                    dims.append((int(s), int(e)))
                except ValueError:
                    dims.append((s, e))
        base_node = array_node.children[-1] if array_node.children else None
        base_desc = build_type_descriptor(base_node)
        return make_array_descriptor(dims, base_desc)

    return make_name_descriptor(get_node_text(type_node))


# --- Optimized Expansion (memoized) ---
def descriptor_key(desc: Any) -> Tuple:
    """Create a hashable representation for a descriptor to use as cache key."""
    kind = desc.get("kind")
    if kind == "name":
        return ("name", desc.get("name", ""))
    if kind == "array":
        dims = tuple((d[0], d[1]) for d in desc.get("dims", []))
        base_key = descriptor_key(desc.get("base"))
        return ("array", dims, base_key)
    if kind == "struct":
        fields = tuple((fname, descriptor_key(fdesc)) for fname, fdesc in desc.get("fields", []))
        return ("struct", fields)
    return ("other", str(desc))

def expand_descriptor_suffixes(desc: Dict[str, Any], udt_dict: Dict[str, List[Tuple[str, Dict]]]) -> List[str]:
    """
    Return a list of relative suffixes for a descriptor. Memoized for performance.
    """
    key = descriptor_key(desc)
    if key in _expansion_cache:
        return _expansion_cache[key]

    kind = desc.get("kind")
    results: List[str] = []
    local: Set[str] = set()

    def add_suffix(base, suffix):
        if suffix:
            if suffix.startswith('['):
                local.add(f"{base}{suffix}")
            else:
                local.add(f"{base}.{suffix}")
        else:
            local.add(base)

    if kind == "name":
        tname = desc.get("name", "")
        if tname in udt_dict:
            for field_name, field_desc in udt_dict[tname]:
                for s in expand_descriptor_suffixes(field_desc, udt_dict):
                    add_suffix(field_name, s)
            results = sorted(local)
        else:
            results = [""]
    elif kind == "struct":
        for field_name, field_desc in desc.get("fields", []):
            for s in expand_descriptor_suffixes(field_desc, udt_dict):
                add_suffix(field_name, s)
        results = sorted(local)
    elif kind == "array":
        dims, base = desc.get("dims", []), desc.get("base")

        def expand_for_dims(dims_list):
            if not dims_list: return [""]
            start, end = dims_list[0]
            indices = [f"[{i}]" for i in range(start, end + 1)] if isinstance(start, int) else [f"[{start}..{end}]"]
            return [f"{idx}{r}" for idx in indices for r in expand_for_dims(dims_list[1:])]

        index_parts = expand_for_dims(dims)
        base_suffixes = expand_descriptor_suffixes(base, udt_dict)

        for idx in index_parts:
            for s in base_suffixes:
                add_suffix(idx, s)
        results = sorted(local)
    else: # Fallback for primitive types
        results = [""]

    _expansion_cache[key] = results
    return results

def expand_descriptor_into(base_path: str, desc: Dict[str, Any], udt_dict: Dict[str, List[Tuple[str, Dict]]], out_list: List[str]):
    """Wrapper to expand descriptor and append full paths to out_list."""
    suffixes = expand_descriptor_suffixes(desc, udt_dict)
    for s in suffixes:
        if s:
            out_list.append(f"{base_path}.{s}")
        else:
            out_list.append(base_path)