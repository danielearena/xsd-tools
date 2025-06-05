#!/usr/bin/env python3
"""
find_missing_annotations.py

Scan a single XSD for any <xs:element>, <xs:attribute>, <xs:simpleType>, or <xs:complexType>
that does NOT have an <xs:annotation> child. For **local** elements and attributes, also
report the closest global ancestor (i.e., the top‐level element or type that directly
descends from <xs:schema>).

Usage:
    python find_missing_annotations.py /path/to/your/schema.xsd

Run `python find_missing_annotations.py --help` for details.
"""

import sys
import os
import argparse
from lxml import etree

# XML Schema namespace URI.
XSD_NS = "http://www.w3.org/2001/XMLSchema"
NSMAP = {"xs": XSD_NS}


def find_closest_global_ancestor(node, root):
    """
    Given a node (an lxml Element) and the schema root, return the nearest ancestor
    whose parent is the root. If node itself is global (parent == root), return None.
    Returns a tuple (ancestor_tag, ancestor_name) or (None, None) if node is global.
    """
    parent = node.getparent()
    if parent is None:
        return None, None

    # If parent is root, then node is a global definition: no ancestor to report.
    if parent == root:
        return None, None

    # Otherwise, climb until we find a child of root.
    curr = parent
    while curr is not None and curr.getparent() is not root:
        curr = curr.getparent()

    if curr is None or curr.getparent() is None:
        # Shouldn't happen under well‐formed XSD, but treat as no global ancestor
        return None, None

    # curr is now a direct child of root (i.e., a global <xs:element> or <xs:complexType>, etc.)
    tag_local = etree.QName(curr).localname  # e.g. "element", "complexType", etc.
    ancestor_tag = f"xs:{tag_local}"
    ancestor_name = curr.get("name")
    return ancestor_tag, ancestor_name


def find_missing_annotations(xsd_path):
    """
    Parse the XSD at xsd_path, then find all:
      - xs:element
      - xs:attribute
      - xs:simpleType
      - xs:complexType
    (both global and local). For each, check if it has an <xs:annotation> child.
    Return a dict mapping each tag to a list of tuples:
      - For xs:element or xs:attribute: (name, line, ancestor_tag, ancestor_name)
      - For xs:simpleType or xs:complexType: (name, line, None, None)
    """
    if not os.path.isfile(xsd_path):
        print(f"Error: “{xsd_path}” does not exist or is not a file.")
        sys.exit(1)

    try:
        parser = etree.XMLParser(remove_comments=False)
        tree = etree.parse(xsd_path, parser)
    except (etree.XMLSyntaxError, OSError) as e:
        print(f"Failed to parse “{xsd_path}”: {e}")
        sys.exit(1)

    root = tree.getroot()
    if root.tag != f"{{{XSD_NS}}}schema":
        print("Warning: root element is not <xs:schema>. Proceeding anyway...")

    # Prepare structure to collect missing-annotation records
    missing = {
        "xs:element": [],      # list of (name, line, ancestor_tag, ancestor_name)
        "xs:attribute": [],    # list of (name, line, ancestor_tag, ancestor_name)
        "xs:simpleType": [],   # list of (name, line, None, None)
        "xs:complexType": []   # list of (name, line, None, None)
    }

    # Helper to check a given node for an <xs:annotation> child.
    def check_node(node, tag_key):
        """
        node: an Element for xs:element / xs:attribute / xs:simpleType / xs:complexType
        tag_key: string such as "xs:element" (must match the keys in `missing`)
        """
        name = node.get("name")
        if name is None:
            # Skip anonymous definitions
            return

        # Immediate <xs:annotation> child?
        ann = node.find("xs:annotation", NSMAP)
        if ann is None:
            line = node.sourceline
            if tag_key in ("xs:element", "xs:attribute"):
                # Find closest global ancestor for local elements/attributes
                ancestor_tag, ancestor_name = find_closest_global_ancestor(node, root)
                missing[tag_key].append((name, line, ancestor_tag, ancestor_name))
            else:
                # For types, we don't need an ancestor
                missing[tag_key].append((name, line, None, None))

    # 1) Scan all <xs:element> nodes
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
            "that does NOT have an <xs:annotation> child. For local elements/attributes, also report\n"
            "the closest global ancestor (top-level element or type under <xs:schema>)."
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

    # Elements
    entries = missing["xs:element"]
    if entries:
        print("xs:element definitions WITHOUT <xs:annotation>:")
        for name, line, anc_tag, anc_name in entries:
            if anc_tag:
                print(
                    f"  - xs:element name=\"{name}\" (line {line}); "
                    f"closest global ancestor: {anc_tag} name=\"{anc_name}\""
                )
            else:
                # Global element
                print(f"  - xs:element name=\"{name}\" (line {line}); [GLOBAL]")
        print()
        total_missing += len(entries)

    # Attributes
    entries = missing["xs:attribute"]
    if entries:
        print("xs:attribute definitions WITHOUT <xs:annotation>:")
        for name, line, anc_tag, anc_name in entries:
            if anc_tag:
                print(
                    f"  - xs:attribute name=\"{name}\" (line {line}); "
                    f"closest global ancestor: {anc_tag} name=\"{anc_name}\""
                )
            else:
                # Global attribute
                print(f"  - xs:attribute name=\"{name}\" (line {line}); [GLOBAL]")
        print()
        total_missing += len(entries)

    # SimpleTypes
    entries = missing["xs:simpleType"]
    if entries:
        print("xs:simpleType definitions WITHOUT <xs:annotation>:")
        for name, line, _, _ in entries:
            print(f"  - xs:simpleType name=\"{name}\" (line {line})")
        print()
        total_missing += len(entries)

    # ComplexTypes
    entries = missing["xs:complexType"]
    if entries:
        print("xs:complexType definitions WITHOUT <xs:annotation>:")
        for name, line, _, _ in entries:
            print(f"  - xs:complexType name=\"{name}\" (line {line})")
        print()
        total_missing += len(entries)

    if total_missing == 0:
        print("All <xs:element>, <xs:attribute>, <xs:simpleType>, and <xs:complexType> definitions have annotations.")
    else:
        print(f"Total items missing annotations: {total_missing}")

    print("\nScan complete.\n")


if __name__ == "__main__":
    main()

