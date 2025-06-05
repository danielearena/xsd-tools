#!/usr/bin/env python3
"""
find_missing_annotations.py

Scan a single XSD for any <xs:element>, <xs:attribute>, <xs:simpleType>, or <xs:complexType>
that does NOT have an <xs:annotation> child. Reports tag, name, and line number for each missing annotation.

Usage:
    python find_missing_annotations.py /path/to/schema.xsd

Run `python find_missing_annotations.py --help` for details.
"""

import sys
import os
import argparse
from lxml import etree

# XML Schema namespace URI.
XSD_NS = "http://www.w3.org/2001/XMLSchema"
NSMAP = {"xs": XSD_NS}


def find_missing_annotations(xsd_path):
    """
    Parse the XSD at xsd_path, then find all:
      - xs:element
      - xs:attribute
      - xs:simpleType
      - xs:complexType
    (whether global or local). For each, check if it has an <xs:annotation> child.
    Return a dict mapping each tag to a list of (name, line) for nodes missing annotation.
    """
    if not os.path.isfile(xsd_path):
        print(f"Error: “{xsd_path}” does not exist or is not a file.")
        sys.exit(1)

    try:
        tree = etree.parse(xsd_path)
    except (etree.XMLSyntaxError, OSError) as e:
        print(f"Failed to parse “{xsd_path}”: {e}")
        sys.exit(1)

    root = tree.getroot()
    if root.tag != f"{{{XSD_NS}}}schema":
        print("Warning: root element is not <xs:schema>. Proceeding anyway...")

    # Prepare a structure to collect missing-annotation records
    missing = {
        "xs:element": [],      # list of (name, line)
        "xs:attribute": [],    # list of (name, line)
        "xs:simpleType": [],   # list of (name, line)
        "xs:complexType": []   # list of (name, line)
    }

    # Helper to check a given node for annotation:
    def check_node(node, tag_key):
        """
        node: an Element for xs:element / xs:attribute / xs:simpleType / xs:complexType
        tag_key: string such as "xs:element" (must match the keys in `missing`)
        """
        # If it has no name attribute, skip (e.g. anonymous types inside definitions)
        name = node.get("name")
        if name is None:
            return

        # Look for an <xs:annotation> child (only immediate children count)
        ann = node.find("xs:annotation", NSMAP)
        if ann is None:
            # Record name and line number
            line = node.sourceline
            missing[tag_key].append((name, line))

    # 1) Scan all <xs:element> nodes (global or local)
    for el in root.findall(".//xs:element", NSMAP):
        check_node(el, "xs:element")

    # 2) Scan all <xs:attribute> nodes
    for attr in root.findall(".//xs:attribute", NSMAP):
        check_node(attr, "xs:attribute")

    # 3) Scan all <xs:simpleType> nodes
    for st in root.findall(".//xs:simpleType", NSMAP):
        check_node(st, "xs:simpleType")

    # 4) Scan all <xs:complexType> nodes
    for ct in root.findall(".//xs:complexType", NSMAP):
        check_node(ct, "xs:complexType")

    return missing


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Scan an XSD for any <xs:element>, <xs:attribute>, <xs:simpleType>, or <xs:complexType>\n"
            "that does NOT have an <xs:annotation> child. Reports tag, name, and line number."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "xsdfile",
        metavar="XSD_FILE",
        help="Path to the XSD file to check for missing annotations",
    )
    args = parser.parse_args()

    missing = find_missing_annotations(args.xsdfile)

    print(f"\n=== Missing <xs:annotation> Report for “{args.xsdfile}” ===\n")

    total_missing = 0
    for tag_key, entries in missing.items():
        if entries:
            print(f"{tag_key} definitions WITHOUT <xs:annotation>:")
            for name, line in entries:
                print(f"  - {tag_key} name=\"{name}\" (line {line})")
            print()
            total_missing += len(entries)

    if total_missing == 0:
        print("All <xs:element>, <xs:attribute>, <xs:simpleType>, and <xs:complexType> definitions have annotations.")
    else:
        print(f"Total items missing annotations: {total_missing}")
    print("\nScan complete.\n")


if __name__ == "__main__":
    main()

