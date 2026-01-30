import xml.etree.ElementTree as ET
import sys
import os
import json

# --- Yellow Highlight Functions ---

def apply_yellow_highlighting(graph_root, config):
    """Finds cells with specific text prefixes and adds a yellow highlight box."""
    cfg = config.get('yellow_highlight', {})
    search_texts = cfg.get('text_prefixes', [])
    if not search_texts:
        return

    padding = cfg.get('padding', 5)
    size = cfg.get('size')
    offset = cfg.get('offset')

    tmpl_layer = graph_root.find("./mxCell[@value='Layer_Tmpl']")
    if tmpl_layer is None:
        print("Warning: Layer_Tmpl not found for yellow highlighting.")
        return
    tmpl_layer_id = tmpl_layer.get('id')

    found_cells = []
    for search_text in search_texts:
        for cell in graph_root.findall(".//mxCell[@value]"):
            if cell.get('value', '').startswith(search_text):
                found_cells.append(cell)
    
    unique_found_cells = list(dict.fromkeys(found_cells))
    print(f"Found {len(unique_found_cells)} instances for yellow highlighting.")

    for i, cell in enumerate(unique_found_cells):
        geom = cell.find("mxGeometry")
        if geom is not None:
            add_yellow_highlight_box(geom.attrib, graph_root, tmpl_layer_id, f"text-highlight-{i}-{cell.get('id')}", padding, size, offset)

def add_yellow_highlight_box(geom_attrs, graph_root, layer_id, base_id, padding, size, offset):
    if not all(k in geom_attrs for k in ['x', 'y', 'width', 'height']):
        return
    
    x, y, width, height = float(geom_attrs.get('x',0)), float(geom_attrs.get('y',0)), float(geom_attrs.get('width',0)), float(geom_attrs.get('height',0))

    if size and 'width' in size and 'height' in size:
        box_width, box_height = float(size['width']), float(size['height'])
        box_x = x + (width - box_width) / 2
        box_y = y + (height - box_height) / 2
    else:
        box_x, box_y = x - padding, y - padding
        box_width, box_height = width + 2 * padding, height + 2 * padding
    
    if offset and 'x' in offset and 'y' in offset:
        box_x += float(offset['x'])
        box_y += float(offset['y'])

    obj = ET.Element('object', {'label': '', 'tags': 'Highlight', 'id': f"highlight-box-{base_id}"})
    style = 'rounded=1;fillColor=#fff2cc;arcSize=4;absoluteArcSize=1;verticalAlign=middle;align=center;strokeColor=#d6b656;strokeWidth=1.1811;opacity=50;noLabel=1'
    cell = ET.Element('mxCell', {'style': style, 'parent': layer_id, 'vertex': '1'})
    geom = ET.Element('mxGeometry', {'x': str(box_x), 'y': str(box_y), 'width': str(box_width), 'height': str(box_height), 'as': 'geometry'})
    cell.append(geom)
    obj.append(cell)
    graph_root.append(obj)

# --- Green Box for Text Functions ---

def apply_green_text_boxing(graph_root, config):
    """Finds groups of 2 or 3 adjacent text elements based on spatial proximity and boxes them."""
    cfg = config.get('green_box', {})
    y_threshold = cfg.get('y_threshold', 5.0)
    x_gap_threshold = cfg.get('x_gap_threshold', 25.0)
    x_overlap_threshold = 2.0  # Allow for minor overlaps

    # 1. Group all text elements by their parent ID
    cells_by_parent = {}
    for cell in graph_root.findall(".//mxCell[@value]"):
        geom = cell.find('mxGeometry')
        parent_id = cell.get('parent')
        if geom is not None and cell.get('value') and parent_id and cell.get('vertex') == '1':
            if parent_id not in cells_by_parent:
                cells_by_parent[parent_id] = []
            cells_by_parent[parent_id].append({
                'x': float(geom.get('x', 0)), 'y': float(geom.get('y', 0)),
                'width': float(geom.get('width', 0)), 'height': float(geom.get('height', 0)),
            })

    found_groups = []
    
    # 2. For each parent group, find lines and then text clusters within those lines
    for parent_id, elements in cells_by_parent.items():
        if len(elements) < 2:
            continue
        
        # Sort by Y then X to order elements for line-finding
        elements.sort(key=lambda e: (e['y'], e['x']))

        # Find continuous lines of text based on y_threshold
        lines = []
        if elements:
            current_line = [elements[0]]
            for i in range(1, len(elements)):
                # If the next element is on the same line (close y)
                if abs(elements[i]['y'] - current_line[-1]['y']) < y_threshold:
                    current_line.append(elements[i])
                else:
                    # New line starts
                    if len(current_line) >= 2:
                        lines.append(current_line)
                    current_line = [elements[i]]
            # Add the last line
            if len(current_line) >= 2:
                lines.append(current_line)

        # 3. In each line, find groups of 2 or 3
        for line in lines:
            i = 0
            while i < len(line):
                # Attempt to find a group of 3 (greedy)
                if i + 2 < len(line):
                    group = [line[i], line[i+1], line[i+2]]
                    gap1 = group[1]['x'] - (group[0]['x'] + group[0]['width'])
                    gap2 = group[2]['x'] - (group[1]['x'] + group[1]['width'])
                    
                    if (-x_overlap_threshold <= gap1 < x_gap_threshold) and \
                       (-x_overlap_threshold <= gap2 < x_gap_threshold):
                        found_groups.append(group)
                        i += 3
                        continue

                # Attempt to find a group of 2
                if i + 1 < len(line):
                    group = [line[i], line[i+1]]
                    gap = group[1]['x'] - (group[0]['x'] + group[0]['width'])
                    
                    if -x_overlap_threshold <= gap < x_gap_threshold:
                        found_groups.append(group)
                        i += 2
                        continue
                
                i += 1

    print(f"Found {len(found_groups)} text groups for green boxing.")

    # 4. Add a bounding box around each found group
    if not found_groups:
        return
        
    padding = cfg.get('padding', 2)
    size = cfg.get('size')
    offset = cfg.get('offset')
    
    tmpl_layer = graph_root.find("./mxCell[@value='Layer_Tmpl']")
    if tmpl_layer is None:
        print("Warning: Layer_Tmpl not found for green boxing.")
        return
    tmpl_layer_id = tmpl_layer.get('id')

    for i, group in enumerate(found_groups):
        add_green_box(group, graph_root, tmpl_layer_id, f"green-box-{i}", padding, size, offset)

def add_green_box(element_group, graph_root, layer_id, base_id, padding, size, offset):
    """Draws a bounding box around a group of elements."""
    if not element_group:
        return

    min_x = min(e['x'] for e in element_group)
    min_y = min(e['y'] for e in element_group)
    max_x = max(e['x'] + e['width'] for e in element_group)
    max_y = max(e['y'] + e['height'] for e in element_group)
    
    group_width = max_x - min_x
    group_height = max_y - min_y

    if size and 'width' in size and 'height' in size:
        box_width, box_height = float(size['width']), float(size['height'])
        box_x = min_x + (group_width - box_width) / 2
        box_y = min_y + (group_height - box_height) / 2
    else:
        box_x, box_y = min_x - padding, min_y - padding
        box_width, box_height = group_width + 2 * padding, group_height + 2 * padding

    if offset and 'x' in offset and 'y' in offset:
        box_x += float(offset['x'])
        box_y += float(offset['y'])

    obj = ET.Element('object', {'label': '', 'tags': 'Door', 'id': base_id})
    style = "rounded=1;fillColor=#99FF99;arcSize=4;absoluteArcSize=1;verticalAlign=middle;align=center;strokeColor=#00CC00;strokeWidth=1.1811;opacity=50;"
    cell = ET.Element('mxCell', {'style': style, 'parent': layer_id, 'vertex': '1'})
    geom = ET.Element('mxGeometry', {
        'x': str(box_x), 'y': str(box_y),
        'width': str(box_width), 'height': str(box_height),
        'as': 'geometry'
    })
    cell.append(geom)
    obj.append(cell)
    graph_root.append(obj)

# --- Main Processing ---

def process_file(input_file, output_file, config):
    print(f"Processing {input_file}...")
    try:
        tree = ET.parse(input_file)
        root = tree.getroot()
        graph_model_root = root.find(".//root")
        if graph_model_root is None:
            raise ValueError("Could not find root in graph model.")

        tmpl_layer = graph_model_root.find("./mxCell[@value='Layer_Tmpl']")
        if tmpl_layer is None:
            layer_count = len(graph_model_root.findall("./mxCell[@parent='0']"))
            tmpl_layer = ET.Element('mxCell', {'id': f'dWr0-L{layer_count+1}', 'value': 'Layer_Tmpl', 'parent': '0'})
            graph_model_root.append(tmpl_layer)

        apply_yellow_highlighting(graph_model_root, config)
        apply_green_text_boxing(graph_model_root, config) # <-- Changed to new function

        tree.write(output_file, encoding='utf-8', xml_declaration=True)
        print(f"Successfully processed and saved to {output_file}")

    except (ET.ParseError, ValueError) as e:
        print(f"Could not process {input_file}: {e}")

def main():
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
    except FileNotFoundError:
        print("Error: config.json not found.")
        return
        
    target_folder = config.get("target_folder", ".")
    output_folder = os.path.join(target_folder, 'outputs')
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        
    print(f"Scanning for .drawio files in '{os.path.abspath(target_folder)}'")
    
    for filename in os.listdir(target_folder):
        if filename.endswith('.drawio'):
            input_path = os.path.join(target_folder, filename)
            if os.path.abspath(input_path).startswith(os.path.abspath(output_folder)):
                continue
            
            # The logic now targets specific files based on the overall goal
            # For now, we process all files in the target folder.
            # A more advanced version could parse the schedule, get targets,
            # and then only process floor plans that match the floor.
            
            output_path = os.path.join(output_folder, filename)
            process_file(input_path, output_path, config)

if __name__ == '__main__':
    main()
