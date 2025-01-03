import os
import sys
import argparse
import xml.etree.ElementTree as ET

def flatten_xsd(input_file, output_file=None):
    if not os.path.isfile(input_file):
        raise FileNotFoundError(f"Input file '{input_file}' not found.")

    if output_file is None:
        base, ext = os.path.splitext(input_file)
        output_file = f"{base}_flattened{ext}"

    tree = ET.parse(input_file)
    root = tree.getroot()

    namespace = {'xs': 'http://www.w3.org/2001/XMLSchema'}

    def resolve_includes(element, base_path):
        for include in element.findall('xs:include', namespace):
            schema_location = include.get('schemaLocation')
            if schema_location:
                included_path = os.path.join(base_path, schema_location)
                if not os.path.isfile(included_path):
                    raise FileNotFoundError(f"Included file '{included_path}' not found.")

                included_tree = ET.parse(included_path)
                included_root = included_tree.getroot()
                resolve_includes(included_root, os.path.dirname(included_path))

                # Insert included content into the main schema
                for child in included_root:
                    element.append(child)

                # Remove the <xs:include> element after processing
                element.remove(include)

    resolve_includes(root, os.path.dirname(input_file))

    tree.write(output_file, encoding="utf-8", xml_declaration=True)
    print(f"Flattened schema saved to '{output_file}'")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Flatten an XSD file by resolving <xs:include> elements.")
    parser.add_argument("input_file", help="Path to the input XSD file.")
    parser.add_argument("-o", "--output", help="Path to the output XSD file (optional).")

    args = parser.parse_args()

    try:
        flatten_xsd(args.input_file, args.output)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

