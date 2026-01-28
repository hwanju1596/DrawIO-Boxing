import xml.etree.ElementTree as ET
import sys
import os
import numpy as np
from collections import defaultdict
import json # Import json for config file handling

# --- Functions from circle.py integrated here ---

def extract_paths(xml_root, id_prefix: str):
    """
    Extracts paths (a list of points) from mxCell elements starting with a given ID prefix.
    A shape can be composed of multiple cells (paths).
    """
    paths = []
    # ElementTree's XPath support is limited and doesn't have starts-with.
    # We iterate through all cells with an 'id' and check it in Python.
    for cell in xml_root.findall(".//mxCell[@id]"):
        if not cell.get('id').startswith(id_prefix):
            continue

        geom = cell.find(".//mxGeometry")
        if geom is None:
            continue

        # This logic is for edges/paths, not simple vertices
        src = geom.find('./mxPoint[@as="sourcePoint"]')
        tgt = geom.find('./mxPoint[@as="targetPoint"]')
        arr = geom.find('./Array[@as="points"]')

        pts = []
        if src is not None:
            pts.append((float(src.get("x")), float(src.get("y"))))

        if arr is not None:
            for p in arr.findall("./mxPoint"):
                pts.append((float(p.get("x")), float(p.get("y"))))

        if tgt is not None:
            pts.append((float(tgt.get("x")), float(tgt.get("y"))))
        
        # Only add if the path has points
        if pts:
            paths.append(tuple(pts))
            
    return paths

def shape_signature(paths, tol=1e-4, scale_invariant=False):
    """
    Computes a comparable signature for a shape from its paths.
    - Removes translation by centering on the centroid.
    - Optionally removes scale by normalizing by RMS radius.
    - Quantizes to handle floating point errors.
    - Sorts to make it order-independent.
    """
    if not paths:
        return tuple()
        
    all_pts = np.array([pt for path in paths for pt in path], dtype=float)
    if len(all_pts) == 0:
        return tuple()

    centroid = all_pts.mean(axis=0)

    centered = []
    for path in paths:
        a = np.array(path, dtype=float) - centroid
        centered.append(a)

    if scale_invariant:
        # Normalize scale by the root mean square of distances from the centroid
        r = np.sqrt(((all_pts - centroid) ** 2).sum(axis=1).mean())
        if r > tol: # Avoid division by zero for single-point shapes
            centered = [a / r for a in centered]

    def quantize(arr: np.ndarray):
        q = np.rint(arr / tol).astype(int)
        return tuple(map(tuple, q.tolist()))

    sig = sorted(quantize(a) for a in centered)
    return tuple(sig)

# --- End of integrated functions ---


def highlight_text(input_file, output_file, search_texts, padding=5, size=None, offset=None): # padding and size added
    """Finds cells with a specific text value or value prefix and adds a highlight box around them."""
    tree = ET.parse(input_file)
    root = tree.getroot()
    
    graph_model_root = root.find("diagram/mxGraphModel/root")
    if graph_model_root is None:
        print("Error: Could not find root of the graph model.")
        return

    tmpl_layer = graph_model_root.find("./mxCell[@value='Layer_Tmpl']")
    if tmpl_layer is None:
        print("Error: Layer_Tmpl not found.")
        return
    tmpl_layer_id = tmpl_layer.get('id')

    all_found_cells = []
    for search_text in search_texts:
        for cell in graph_model_root.findall(".//mxCell[@value]"):
            cell_value = cell.get('value')
            if cell_value and cell_value.startswith(search_text):
                all_found_cells.append(cell)
    
    # Remove duplicates if a cell matches multiple prefixes
    unique_found_cells = list(dict.fromkeys(all_found_cells))

    if not unique_found_cells:
        print(f"No text found for prefixes: {', '.join(search_texts)}.")
        return

    print(f"Found {len(unique_found_cells)} instance(s) of text matching prefixes. Highlighting them...")
    for i, cell in enumerate(unique_found_cells):
        add_highlight_for_cell(cell.find("mxGeometry"), graph_model_root, tmpl_layer_id, f"text-highlight-{i}-{cell.get('id')}", padding, size, offset) # padding and size passed

    tree.write(output_file, encoding='utf-8', xml_declaration=True)
    print(f"Created highlighted file: {output_file}")


def highlight_circles(input_file, output_file, ref_prefix="AR_G_2_", tolerance=0.5, padding=5, size=None, offset=None): # padding and size added
    """Finds path-based shapes that match a reference circle shape and highlights them."""
    tree = ET.parse(input_file)
    root = tree.getroot()

    graph_model_root = root.find("diagram/mxGraphModel/root")
    if graph_model_root is None:
        print("Error: Could not find root of the graph model.")
        return

    tmpl_layer = graph_model_root.find("./mxCell[@value='Layer_Tmpl']")
    if tmpl_layer is None:
        print("Error: Layer_Tmpl not found.")
        return
    tmpl_layer_id = tmpl_layer.get('id')

    # 1. Get the signature of the reference circle shape, ignoring scale.
    ref_paths = extract_paths(graph_model_root, ref_prefix)
    if not ref_paths:
        print(f"Error: Could not find reference shape with prefix '{ref_prefix}'.")
        return
    ref_sig = shape_signature(ref_paths, tol=tolerance, scale_invariant=True)
    print(f"Reference shape '{ref_prefix}' has {len(ref_paths)} paths. Using it to find other circles with tolerance {tolerance}.")

    # 2. Group all path-based cells by their ID prefix (e.g., "AR_G_1_").
    shape_prefixes = defaultdict(list)
    for cell in graph_model_root.findall(".//mxCell[@id]"):
        cell_id = cell.get('id')
        parts = cell_id.split('_')
        if len(parts) > 2 and parts[0] == 'AR' and parts[1] == 'G':
            prefix = f"{parts[0]}_{parts[1]}_{parts[2]}_"
            shape_prefixes[prefix].append(cell)
            
    # 3. Iterate through shapes and compare them to the reference.
    found_circles_count = 0
    for prefix, _ in shape_prefixes.items():
        current_paths = extract_paths(graph_model_root, prefix)
        if not current_paths:
            continue
            
        current_sig = shape_signature(current_paths, tol=tolerance, scale_invariant=True)
        
        if current_sig == ref_sig:
            found_circles_count += 1
            all_points = [pt for path in current_paths for pt in path]
            if not all_points:
                continue

            min_x = min(p[0] for p in all_points)
            max_x = max(p[0] for p in all_points)
            min_y = min(p[1] for p in all_points)
            max_y = max(p[1] for p in all_points)
            
            width = max_x - min_x
            height = max_y - min_y

            bbox_geom = {'x': str(min_x), 'y': str(min_y), 'width': str(width), 'height': str(height)}
            add_highlight_for_bbox(bbox_geom, graph_model_root, tmpl_layer_id, f"circle-highlight-{prefix}", padding, size, offset) # padding and size passed

    if found_circles_count == 0:
        print("No matching circle shapes found to highlight.")
        return

    print(f"Found and highlighted {found_circles_count} circle shape(s).")
    tree.write(output_file, encoding='utf-8', xml_declaration=True)
    print(f"Created highlighted file: {output_file}")


def add_highlight_for_bbox(geom_attrs, graph_root, layer_id, base_id, padding=5, size=None, offset=None): # size added as parameter
    """Helper function to add a highlight box for a given bounding box dictionary."""
    if not all(k in geom_attrs for k in ['x', 'y', 'width', 'height']):
        return
    
    x = float(geom_attrs['x'])
    y = float(geom_attrs['y'])
    width = float(geom_attrs['width'])
    height = float(geom_attrs['height'])

    # Priority: 1. Absolute size, 2. Padding
    if size and 'width' in size and 'height' in size:
        try:
            box_width = float(size['width'])
            box_height = float(size['height'])
            # Center the custom-sized box over the original element
            box_x = x + (width - box_width) / 2
            box_y = y + (height - box_height) / 2
        except (ValueError, TypeError):
            print(f"Warning: Invalid 'size' values in config: {size}. Falling back to padding.")
            box_x = x - padding
            box_y = y - padding
            box_width = width + 2 * padding
            box_height = height + 2 * padding
    else:
        # Use the passed padding
        box_x = x - padding
        box_y = y - padding
        box_width = width + 2 * padding
        box_height = height + 2 * padding
    
    # Apply offset if provided
    if offset and 'x' in offset and 'y' in offset:
        try:
            offset_x = float(offset['x'])
            offset_y = float(offset['y'])
            box_x += offset_x
            box_y += offset_y
        except (ValueError, TypeError):
            print(f"Warning: Invalid 'offset' values in config: {offset}. Ignoring.")
    
    new_id = f"highlight-box-{base_id}"
    
    if graph_root.find(f".//object[@id='{new_id}']") is not None:
        return

    obj = ET.Element('object', {'label': '', 'tags': 'Highlight', 'id': new_id})
    cell_style = 'rounded=1;fillColor=#fff2cc;arcSize=4;absoluteArcSize=1;verticalAlign=middle;align=center;strokeColor=#d6b656;strokeWidth=1.1811;opacity=50;noLabel=1'
    new_cell = ET.Element('mxCell', {'style': cell_style, 'parent': layer_id, 'vertex': '1'})
    
    geometry = ET.Element('mxGeometry', {
        'x': str(box_x), 'y': str(box_y),
        'width': str(box_width), 'height': str(box_height),
        'as': 'geometry'
    })

    new_cell.append(geometry)
    obj.append(new_cell)
    graph_root.append(obj)

def add_highlight_for_cell(geom_element, graph_root, layer_id, base_id, padding=5, size=None, offset=None): # size added
    """Wrapper to use the same highlighter for cells with mxGeometry."""
    if geom_element is None:
        return
    add_highlight_for_bbox(geom_element.attrib, graph_root, layer_id, base_id, padding, size, offset)


def print_usage():
    print("Usage:")
    print("  For text: python highlight_drawio.py <input> <output> --text <search_text_or_comma_separated_list> [--padding <int>]")
    print("  For text with config: python highlight_drawio.py <input> <output> --config <path_to_config.json> [--padding <int>]")
    print("    Note: Config can specify 'padding' or 'size' ({'width': w, 'height': h}). 'size' takes precedence.")
    print("  For shapes: python highlight_drawio.py <input> <output> --shape circle [--ref_prefix <prefix>] [--tolerance <float>] [--padding <int>]")

if __name__ == '__main__':
    args = sys.argv[1:]
    if len(args) < 3: # input, output, mode
        print_usage()
        sys.exit(1)

    input_f = args.pop(0)
    output_f = args.pop(0)
    
    mode_arg = args.pop(0)

    # Store padding from CLI if provided, but don't apply it yet.
    padding_from_cli = None
    temp_args = []
    while args:
        arg = args.pop(0)
        if arg == '--padding':
            if not args:
                print("Error: --padding requires an integer value.")
                sys.exit(1)
            try:
                padding_from_cli = int(args.pop(0))
            except ValueError:
                print("Error: Padding must be an integer.")
                sys.exit(1)
        else:
            temp_args.append(arg)
    args = temp_args # Put back remaining args
    
    # Set a default padding
    effective_padding = 10
    size_to_use = None
    offset_to_use = None

    if mode_arg == '--text':
        # For text mode, CLI padding overrides the default
        if padding_from_cli is not None:
            effective_padding = padding_from_cli

        if not args:
            print("Error: --text mode requires a search term or comma-separated list.")
            sys.exit(1)
        search_param = args.pop(0)
        if ',' in search_param:
            search_texts = [s.strip() for s in search_param.split(',')]
        else:
            search_texts = [search_param]
        highlight_text(input_f, output_f, search_texts, padding=effective_padding, size=size_to_use, offset=offset_to_use)

    elif mode_arg == '--config':
        if not args:
            print("Error: --config mode requires a path to a config file.")
            sys.exit(1)
        config_file_path = args.pop(0)
        
        try:
            with open(config_file_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except FileNotFoundError:
            print(f"Error: Config file not found at '{config_file_path}'.")
            sys.exit(1)
        except json.JSONDecodeError:
            print(f"Error: Invalid JSON in config file '{config_file_path}'.")
            sys.exit(1)
        
        # Precedence for padding: CLI > config > default
        padding_from_config = config.get("padding")
        if padding_from_config is not None:
            try:
                effective_padding = int(padding_from_config)
            except (ValueError, TypeError):
                print(f"Warning: Invalid 'padding' value '{padding_from_config}' in config. Using default.")
        
        if padding_from_cli is not None:
            effective_padding = padding_from_cli

        # Check for absolute size, which overrides padding logic
        size_from_config = config.get("size")
        if size_from_config:
            if not (isinstance(size_from_config, dict) and 'width' in size_from_config and 'height' in size_from_config):
                print(f"Warning: Invalid 'size' object in config: {size_from_config}. It must be a dictionary with 'width' and 'height'. Ignoring.")
            else:
                size_to_use = size_from_config
        
        offset_from_config = config.get("offset")
        if offset_from_config:
            if not (isinstance(offset_from_config, dict) and 'x' in offset_from_config and 'y' in offset_from_config):
                print(f"Warning: Invalid 'offset' object in config: {offset_from_config}. It must be a dictionary with 'x' and 'y'. Ignoring.")
            else:
                offset_to_use = offset_from_config

        if "text_prefixes" in config and isinstance(config["text_prefixes"], list):
            highlight_text(input_f, output_f, config["text_prefixes"], padding=effective_padding, size=size_to_use, offset=offset_to_use)
        elif "tasks" in config and isinstance(config["tasks"], list):
            print("Error: 'tasks' config type not yet fully supported. Please use 'text_prefixes'.")
            sys.exit(1)
        else:
            print("Error: Config file must contain a 'text_prefixes' list.")
            sys.exit(1)

    elif mode_arg == '--shape':
        # For shape mode, CLI padding overrides the default
        if padding_from_cli is not None:
            effective_padding = padding_from_cli

        if not args or args[0] != 'circle':
            print("Error: --shape mode requires 'circle'.")
            sys.exit(1)
        args.pop(0) # consume 'circle'

        # Set defaults
        ref_prefix = "AR_G_2_"
        tolerance = 0.5 

        # Parse optional args specific to --shape
        while args:
            opt = args.pop(0)
            if opt == '--ref_prefix':
                if not args:
                    print("Error: --ref_prefix requires a value.")
                    sys.exit(1)
                ref_prefix = args.pop(0)
            elif opt == '--tolerance':
                if not args:
                    print("Error: --tolerance requires a float value.")
                    sys.exit(1)
                try:
                    tolerance = float(args.pop(0))
                except ValueError:
                    print("Error: Tolerance must be a number.")
                    sys.exit(1)
            else:
                print(f"Unknown option for --shape: {opt}")
                print_usage()
                sys.exit(1)

        highlight_circles(input_f, output_f, ref_prefix=ref_prefix, tolerance=tolerance, padding=effective_padding, size=size_to_use, offset=offset_to_use)
    else:
        print(f"Error: Invalid mode '{mode_arg}'.")
        print_usage()
        sys.exit(1)
