import xml.etree.ElementTree as ET
import sys
import os
import json
from collections import defaultdict

def find_text_elements(root, style_substring, parent_substring):
    elements = []
    # Find all mxCell elements that are vertices
    for cell in root.findall(".//mxCell[@vertex='1']"):
        style = cell.get('style', '')
        if style_substring in style and parent_substring in cell.get('parent', ''):
            geom = cell.find('mxGeometry')
            if geom is not None:
                try:
                    elements.append({
                        'id': cell.get('id'),
                        'x': float(geom.get('x', 0)),
                        'y': float(geom.get('y', 0)),
                        'width': float(geom.get('width', 0)),
                        'height': float(geom.get('height', 0)),
                        'elem': cell
                    })
                except (ValueError, TypeError):
                    continue
    return elements

def group_elements(elements, y_tolerance=5, x_gap_tolerance=25):
    if not elements:
        return []

    # Sort elements primarily by Y, then by X
    elements.sort(key=lambda e: (e['y'], e['x']))

    groups = []
    if not elements:
        return []
    
    current_group = [elements[0]]

    for i in range(1, len(elements)):
        prev_elem = current_group[-1]
        current_elem = elements[i]

        # Check for vertical alignment
        if abs(current_elem['y'] - prev_elem['y']) < y_tolerance:
            # Check for horizontal proximity
            gap = current_elem['x'] - (prev_elem['x'] + prev_elem['width'])
            if 0 <= gap < x_gap_tolerance:
                current_group.append(current_elem)
            else:
                if len(current_group) >= 3:
                    groups.append(list(current_group))
                current_group = [current_elem]
        else:
            if len(current_group) >= 3:
                groups.append(list(current_group))
            current_group = [current_elem]
    
    if len(current_group) >= 3:
        groups.append(current_group)

    final_groups = []
    for group in groups:
        # From a larger group, extract all possible groups of 3
        if len(group) >= 3:
            for j in range(len(group) - 2):
                final_groups.append(group[j:j+3])

    return final_groups

def add_bounding_box(graph_root, group, layer_id, box_id, padding=5):
    if not group:
        return

    min_x = min(e['x'] for e in group)
    min_y = min(e['y'] for e in group)
    max_x = max(e['x'] + e['width'] for e in group)
    max_y = max(e['y'] + e['height'] for e in group)

    box_x = min_x - padding
    box_y = min_y - padding
    box_width = (max_x - min_x) + (2 * padding)
    box_height = (max_y - min_y) + (2 * padding)
    
    # Use a unique ID for the new object to avoid conflicts
    new_id = f"bbox-{box_id}-{group[0]['id']}"

    obj = ET.Element('object', {'label': '', 'tags': 'DivTitleBox', 'id': new_id})
    
    style = "rounded=1;fillColor=none;arcSize=20;absoluteArcSize=1;verticalAlign=middle;align=right;strokeColor=#00FF00;strokeWidth=2;dashed=1;dashPattern=1 1;labelPosition=left;verticalLabelPosition=middle;fontSize=18;"
    
    new_cell = ET.Element('mxCell', {'style': style, 'parent': layer_id, 'vertex': '1'})
    
    geometry = ET.Element('mxGeometry', {
        'x': str(box_x),
        'y': str(box_y),
        'width': str(box_width),
        'height': str(box_height),
        'as': 'geometry'
    })

    new_cell.append(geometry)
    obj.append(new_cell)
    graph_root.append(obj)

def process_file(input_file, output_file):
    print(f"Processing {input_file} -> {output_file}")
    try:
        tree = ET.parse(input_file)
    except ET.ParseError as e:
        print(f"Error parsing XML from {input_file}: {e}")
        with open(input_file, 'r', encoding='utf-8') as f:
            xml_content = f.read()
        xml_content = xml_content.encode('utf-8', 'ignore').decode('utf-8')
        try:
            root_element = ET.fromstring(xml_content)
            tree = ET.ElementTree(root_element)
        except ET.ParseError as e2:
            print(f"Failed to recover from parsing error for {input_file}: {e2}")
            return
            
    root = tree.getroot()
    graph_model_root = root.find(".//root")

    if graph_model_root is None:
        print("Error: Could not find graph model root.")
        return

    tmpl_layer = graph_model_root.find("./mxCell[@value='Layer_Tmpl']")
    if tmpl_layer is None:
        print("Layer_Tmpl not found, creating it.")
        layer_count = len(graph_model_root.findall("./mxCell[@parent='0']"))
        new_layer_id = f"dWr0-L{layer_count+1}"
        tmpl_layer = ET.Element('mxCell', {'id': new_layer_id, 'value': 'Layer_Tmpl', 'parent': '0'})
        graph_model_root.append(tmpl_layer)
    tmpl_layer_id = tmpl_layer.get('id')
    
    style_substring = "strokeColor=#00FF00"
    parent_substring = "dWr0-7"
    
    text_elements = find_text_elements(graph_model_root, style_substring, parent_substring)
    
    groups_of_three = group_elements(text_elements)
    
    print(f"Found {len(text_elements)} text elements, forming {len(groups_of_three)} groups.")

    for i, group in enumerate(groups_of_three):
        add_bounding_box(graph_model_root, group, tmpl_layer_id, f"group-{i}")

    tree.write(output_file, encoding='utf-8', xml_declaration=True)
    print(f"Finished processing. Output saved to {output_file}")

def main():
    try:
        with open('batch_config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
    except FileNotFoundError:
        print("Error: batch_config.json not found.")
        return
        
    target_folder = config.get("target_folder", ".")
    
    output_folder = os.path.join(target_folder, 'outputs')
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        
    print(f"Scanning for .drawio files in '{os.path.abspath(target_folder)}'")
    
    found_files = []
    for filename in os.listdir(target_folder):
        if filename.endswith('.drawio'):
             # Make sure we don't process files in the output directory
            if os.path.abspath(os.path.join(target_folder, filename)).startswith(os.path.abspath(output_folder)):
                continue
            found_files.append(filename)

    if not found_files:
        print("No .drawio files found to process.")
        return

    for filename in found_files:
        input_file_path = os.path.join(target_folder, filename)
        output_file_path = os.path.join(output_folder, filename)
        process_file(input_file_path, output_file_path)

if __name__ == '__main__':
    main()
