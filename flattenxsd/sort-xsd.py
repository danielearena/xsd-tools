import argparse
import xml.etree.ElementTree as ET

def sort_xsd(file_path, output_path=None, name_first=False):
    """
    Sort an XSD file alphabetically by kind and name (default) or name and kind.

    Parameters:
        file_path (str): Path to the input XSD file.
        output_path (str): Path to save the sorted XSD file (optional).
        name_first (bool): If True, sort by name first, then kind. Default is kind first.

    Returns:
        str: The path to the sorted XSD file.
    """
    # Parse the XSD file
    tree = ET.parse(file_path)
    root = tree.getroot()

    # Namespace dictionary for XPath queries
    ns = {'xs': 'http://www.w3.org/2001/XMLSchema'}

    # Find all top-level elements in the schema
    elements = list(root.findall("xs:*", ns))

    # Define custom kind order
    kind_order = {"element": 0, "complexType": 1, "simpleType": 2, "attribute": 3}

    # Sort elements by the specified order
    def sort_key(element):
        kind = element.tag.split('}')[-1]  # Extract kind (e.g., 'element', 'complexType')
        kind_index = kind_order.get(kind, 99)  # Default to 99 if kind is not in the order
        name = element.attrib.get('name', '')  # Extract name (default to empty if not present)
        return (name, kind_index) if name_first else (kind_index, name)

    sorted_elements = sorted(elements, key=sort_key)

    # Remove all existing elements from the root
    for elem in elements:
        root.remove(elem)

    # Append sorted elements back to the root
    for elem in sorted_elements:
        root.append(elem)

    # Determine output file path
    if not output_path:
        output_path = file_path.replace('.xsd', '_sorted.xsd')

    # Write the sorted tree to the output file
    tree.write(output_path, encoding='utf-8', xml_declaration=True)
    
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Sort an XSD file alphabetically.")
    parser.add_argument("file", help="Path to the input XSD file.")
    parser.add_argument("--output", help="Path to the output XSD file.", default=None)
    parser.add_argument("--name-first", action="store_true", 
                        help="Sort by name first, then kind. Default is kind first.")

    args = parser.parse_args()

    sorted_file = sort_xsd(args.file, args.output, args.name_first)
    print(f"Sorted XSD file saved to: {sorted_file}")

if __name__ == "__main__":
    main()

