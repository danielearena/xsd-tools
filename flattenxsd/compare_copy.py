from lxml import etree
import difflib
import argparse
import re

# Function to extract XML content as a string
def extract_element_as_string(element, prefix, ignore_name=True):
    """Convert XML element to a formatted string for comparison, flattening whitespace and ignoring xmlns attributes."""
    raw_string = etree.tostring(element, pretty_print=True, encoding='unicode')
    # Remove xmlns declarations
    raw_string = re.sub(r'\s+xmlns(:\w+)?="[^"]*"', '', raw_string)
    # Replace all consecutive whitespace with a single space
    raw_string = re.sub(r'\s+', ' ', raw_string).strip()
    # Remove all whitespace between > and <
    raw_string = re.sub(r'>\s+<', '><', raw_string)

    if ignore_name:
        # Remove the 'name' attribute specifically
        raw_string = re.sub(r'name="[^"]*"', '', raw_string)
    # Remove prefix in any attribute value
    raw_string, count = re.subn(rf'(\s\w+="){prefix}_([\w\-]+)(")', r'\1\2\3', raw_string)
    print(f"DEBUG: After removing '{prefix}' prefixes in attributes: (Replacements made: {count})")
    return raw_string

# Function to find matching elements by tag name in the XSD
def find_matching_element(schema_root, tag, name):
    """Find an element with a specific name in the XSD schema."""
    xpath_query = f"//xs:{tag}[@name='{name}']"
    return schema_root.xpath(xpath_query, namespaces={'xs': 'http://www.w3.org/2001/XMLSchema'})

# Function to compare two elements and print differences
def compare_elements(element1, element2, prefix):
    """Compare two XML elements and return the differences ignoring the name attribute."""
    str1 = extract_element_as_string(element1, prefix)
    str2 = extract_element_as_string(element2, prefix)
    
    diff = list(difflib.unified_diff(str1.splitlines(), str2.splitlines(),
                                     fromfile='original', tofile='copy', lineterm=''))
    return '\n'.join(diff) if diff else "OK"

# Main function to parse and compare XSD files
def compare_xsd_files(prefix, original_file, copy_file):
    """Compare elements, attributes, simpleTypes, and complexTypes between two XSD files."""
    # Parse the XSD files
    original_tree = etree.parse(original_file)
    copy_tree = etree.parse(copy_file)
    
    original_root = original_tree.getroot()
    copy_root = copy_tree.getroot()
    
    # XSD components to compare
    components = ['element', 'attribute', 'simpleType', 'complexType']
    
    for component in components:
        # Find all matching components in the "copy" XSD that start with the prefix
        matching_elements = copy_root.xpath(f"//xs:{component}[starts-with(@name, '{prefix}_')]",
                                           namespaces={'xs': 'http://www.w3.org/2001/XMLSchema'})
        
        for copy_element in matching_elements:
            # Extract name without prefix
            original_name = copy_element.attrib['name'][len(prefix) + 1:]
            
            # Search for the corresponding element in the original file
            original_elements = find_matching_element(original_root, component, original_name)
            
            if not original_elements:
                print(f"No matching '{component}' for '{copy_element.attrib['name']}' in original file.")
                continue
            
            # Compare the two elements ignoring the name attribute
            diff_result = compare_elements(original_elements[0], copy_element, prefix)
            print(f"\nComparison for {component} (Original: '{original_name}', Copy: '{copy_element.attrib['name']}'): ")
            print(diff_result)

# Command-line argument parsing
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare prefixed elements in two XSD files.")
    parser.add_argument("prefix", help="The prefix string to match in the copy XSD file.")
    parser.add_argument("original_file", help="Path to the original XSD file.")
    parser.add_argument("copy_file", help="Path to the copy XSD file.")
    args = parser.parse_args()
    
    compare_xsd_files(args.prefix, args.original_file, args.copy_file)

