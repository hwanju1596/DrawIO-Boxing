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

import re
import csv

def apply_green_text_boxing(graph_root, config, filename):
    """Finds groups of 2 or 3 adjacent text elements based on spatial proximity and boxes them."""
    cfg = config.get('green_box', {})
    y_threshold = cfg.get('y_threshold', 5.0)
    x_gap_threshold = cfg.get('x_gap_threshold', 25.0)
    x_gap_threshold_2 = cfg.get('x_gap_threshold_2', x_gap_threshold)
    x_overlap_threshold = 2.0  # Allow for minor overlaps
    required_font_size = cfg.get('required_font_size')
    exclude_hangul = cfg.get('exclude_hangul', False)
    max_x_coordinate = cfg.get('max_x_coordinate')
    max_y_coordinate = cfg.get('max_y_coordinate') # New config
    max_group_width = cfg.get('max_group_width')
    min_group_width = cfg.get('min_group_width')
    min_group_width_2 = cfg.get('min_group_width_2', 27.0)

    extracted_texts = []

    # 1. Group all text elements by their parent ID, filtering by font size
    # ... (existing logic)
    cells_by_parent = {}
    for cell in graph_root.findall(".//mxCell[@value]"):
        geom = cell.find('mxGeometry')
        parent_id = cell.get('parent')
        if geom is not None and cell.get('value') and parent_id and cell.get('vertex') == '1':
            
            if required_font_size:
                style_str = cell.get('style', '')
                style_parts = dict(part.split('=') for part in style_str.split(';') if '=' in part)
                font_size = style_parts.get('fontSize')
                if font_size != required_font_size:
                    continue  # Skip if font size does not match

            if parent_id not in cells_by_parent:
                cells_by_parent[parent_id] = []
            cells_by_parent[parent_id].append({
                'value': cell.get('value'),
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
                        lines.append(sorted(current_line, key=lambda e: e['x']))
                    current_line = [elements[i]]
            # Add the last line
            if len(current_line) >= 2:
                lines.append(sorted(current_line, key=lambda e: e['x']))

        # 3. In each line, find groups of 2 or 3
        for line in lines:
            i = 0
            while i < len(line):
                success = False
                # Attempt to find a group of 3 (greedy)
                if i + 2 < len(line):
                    group = [line[i], line[i+1], line[i+2]]
                    gap1 = group[1]['x'] - (group[0]['x'] + group[0]['width'])
                    gap2 = group[2]['x'] - (group[1]['x'] + group[1]['width'])
                    
                    if (-x_overlap_threshold <= gap1 < x_gap_threshold) and \
                       (-x_overlap_threshold <= gap2 < x_gap_threshold):
                        
                        is_hangul_present = False
                        if exclude_hangul:
                            combined_text = "".join(e['value'] for e in group)
                            if re.search('[\uac00-\ud7a3]', combined_text):
                                is_hangul_present = True
                        
                        is_beyond_max_x = False
                        if max_x_coordinate is not None:
                            if any(e['x'] > max_x_coordinate for e in group):
                                is_beyond_max_x = True

                        is_beyond_max_y = False
                        if max_y_coordinate is not None:
                            if any(e['y'] > max_y_coordinate for e in group):
                                is_beyond_max_y = True

                        if not is_hangul_present and not is_beyond_max_x and not is_beyond_max_y:
                            min_x = min(e['x'] for e in group)
                            max_x = max(e['x'] + e['width'] for e in group)
                            group_width = max_x - min_x
                            combined_text = "".join(e['value'] for e in group)
                            
                            is_out_of_bounds = (min_group_width is not None and group_width < min_group_width) or \
                                               (max_group_width is not None and group_width > max_group_width)
                            
                            if is_out_of_bounds:
                                print(f"DEBUG: [{os.path.basename(filename)}] Group Width Out of Range (3): {combined_text} ({group_width:.2f})")
                            else:
                                print(f"[{os.path.basename(filename)}] Green Box Text (3): {combined_text}")
                                found_groups.append(group)
                                extracted_texts.append({'text': combined_text, 'width': group_width})
                                i += 3
                                success = True
                                continue

                # Attempt group of 2 if 3 failed or wasn't possible
                if not success and i + 1 < len(line):
                    group = [line[i], line[i+1]]
                    gap1 = group[1]['x'] - (group[0]['x'] + group[0]['width'])
                    
                    if (-x_overlap_threshold <= gap1 < x_gap_threshold_2):
                        is_hangul_present = False
                        if exclude_hangul:
                            combined_text = "".join(e['value'] for e in group)
                            if re.search('[\uac00-\ud7a3]', combined_text):
                                is_hangul_present = True
                        
                        is_beyond_max_x = False
                        if max_x_coordinate is not None:
                            if any(e['x'] > max_x_coordinate for e in group):
                                is_beyond_max_x = True

                        is_beyond_max_y = False
                        if max_y_coordinate is not None:
                            if any(e['y'] > max_y_coordinate for e in group):
                                is_beyond_max_y = True

                        if not is_hangul_present and not is_beyond_max_x and not is_beyond_max_y:
                            min_x = min(e['x'] for e in group)
                            max_x = max(e['x'] + e['width'] for e in group)
                            group_width = max_x - min_x
                            combined_text = "".join(e['value'] for e in group)
                            
                            is_out_of_bounds = (min_group_width_2 is not None and group_width < min_group_width_2) or \
                                               (max_group_width is not None and group_width > max_group_width)
                            
                            if is_out_of_bounds:
                                # pass 
                                print(f"DEBUG: [{os.path.basename(filename)}] Group Width Out of Range (2): {combined_text} ({group_width:.2f})")
                            else:
                                print(f"[{os.path.basename(filename)}] Green Box Text (2): {combined_text}")
                                found_groups.append(group)
                                extracted_texts.append({'text': combined_text, 'width': group_width})
                                i += 2
                                success = True
                                continue
                
                if not success:
                    i += 1

    print(f"Found {len(found_groups)} text groups for green boxing.")

    # 4. Add a bounding box around each found group
    if not found_groups:
        return extracted_texts
        
    padding = cfg.get('padding', 2)
    size = cfg.get('size')
    offset = cfg.get('offset')
    
    tmpl_layer = graph_root.find("./mxCell[@value='Layer_Tmpl']")
    if tmpl_layer is None:
        print("Warning: Layer_Tmpl not found for green boxing.")
        return extracted_texts
    tmpl_layer_id = tmpl_layer.get('id')

    for i, group in enumerate(found_groups):
        add_green_box(group, graph_root, tmpl_layer_id, f"green-box-{i}", padding, size, offset)
    
    return extracted_texts

def add_green_box(element_group, graph_root, layer_id, base_id, padding, size, offset):
    # ... (existing logic)
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
        extracted_texts = apply_green_text_boxing(graph_model_root, config, input_file)

        tree.write(output_file, encoding='utf-8', xml_declaration=True)
        print(f"Successfully processed and saved to {output_file}")
        return extracted_texts

    except (ET.ParseError, ValueError) as e:
        print(f"Could not process {input_file}: {e}")
        return []

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
    
    all_extracted_data = []
    
    for filename in os.listdir(target_folder):
        if filename.endswith('.drawio'):
            input_path = os.path.join(target_folder, filename)
            if os.path.abspath(input_path).startswith(os.path.abspath(output_folder)):
                continue
            
            output_path = os.path.join(output_folder, filename)
            results = process_file(input_path, output_path, config)
            
            for item in results:
                all_extracted_data.append({
                    'Filename': filename, 
                    'Text': item['text'], 
                    'Width': f"{item['width']:.2f}"
                })

    if all_extracted_data:
        csv_path = os.path.join(target_folder, 'extracted_green_boxes.csv')
        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=['Filename', 'Text', 'Width'])
            writer.writeheader()
            writer.writerows(all_extracted_data)
        print(f"Successfully extracted {len(all_extracted_data)} items to {csv_path}")

if __name__ == '__main__':
    main()
