#!/usr/bin/env python3
"""
find_orphans.py

Scan a single XSD for “orphan” global elements, attributes, simple types, and complex types:
those <xs:element name="…">, <xs:attribute name="…">, <xs:simpleType name="…">, or
<xs:complexType name="…"> definitions that never appear as a ref="…", type="…", or base="…" anywhere.

Usage:
    python find_orphans.py /path/to/schema.xsd

Run `python find_orphans.py --help` for details.
"""

import sys
import os
import argparse
from collections import defaultdict
from lxml import etree

# XML Schema namespace URI.
XSD_NS = "http://www.w3.org/2001/XMLSchema"
NSMAP = {"xs": XSD_NS}


def local_name(qname):
    """
    Extract just the local part of a QName, whether it's in "{uri}local" or "prefix:local" form.
    Returns None if qname is None.
    """
    if qname is None:
        return None
    if qname.startswith("{"):
        return qname.split("}", 1)[1]
    if ":" in qname:
        return qname.split(":", 1)[1]
    return qname


def find_orphans(xsd_path):
    """
    Parse the given XSD file. Collect:
      - Global <xs:element name="..."> definitions.
      - Global <xs:attribute name="..."> definitions.
      - Global <xs:simpleType name="..."> definitions.
      - Global <xs:complexType name="..."> definitions.
    Then collect all references:
      - <xs:element ref="..."> and <xs:attribute ref="...">
      - Any @type="..." on <xs:element> or <xs:attribute>
      - Any @base="..." on xs:extension or xs:restriction under simpleContent/complexContent, or on <xs:restriction> directly.
    Finally, compute which definitions never got referenced, returning four lists:
      (orphan_elements, orphan_attributes, orphan_simple_types, orphan_complex_types)
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

    # 1) Collect all global definitions under <xs:schema>:
    global_elements = set()
    for el in root.findall("xs:element", NSMAP):
        name = el.get("name")
        if name:
            global_elements.add(name)

    global_attributes = set()
    for attr in root.findall("xs:attribute", NSMAP):
        name = attr.get("name")
        if name:
            global_attributes.add(name)

    global_simple_types = set()
    for st in root.findall("xs:simpleType", NSMAP):
        name = st.get("name")
        if name:
            global_simple_types.add(name)

    global_complex_types = set()
    for ct in root.findall("xs:complexType", NSMAP):
        name = ct.get("name")
        if name:
            global_complex_types.add(name)

    # 2) Find all references to elements/attributes via ref="..."
    referenced_elements = set()
    for el in root.findall(".//xs:element[@ref]", NSMAP):
        ref_qname = el.get("ref")
        local = local_name(ref_qname)
        if local:
            referenced_elements.add(local)

    referenced_attributes = set()
    for attr in root.findall(".//xs:attribute[@ref]", NSMAP):
        ref_qname = attr.get("ref")
        local = local_name(ref_qname)
        if local:
            referenced_attributes.add(local)

    # 3) Find all type="..." references (elements/attributes using a named type)
    referenced_types = set()
    for el in root.findall(".//xs:element[@type]", NSMAP):
        type_qname = el.get("type")
        local = local_name(type_qname)
        if local:
            referenced_types.add(local)

    for attr in root.findall(".//xs:attribute[@type]", NSMAP):
        type_qname = attr.get("type")
        local = local_name(type_qname)
        if local:
            referenced_types.add(local)

    # 4) Find all base="..." references (for extension/restriction under complexContent/simpleContent)
    #    This also catches <xs:restriction base="..."> directly inside a simpleType or complexType.
    for node in root.findall(".//*[@base]", NSMAP):
        base_qname = node.get("base")
        local = local_name(base_qname)
        if local:
            referenced_types.add(local)

    # 5) Compute orphans by set difference
    orphan_elements = sorted(global_elements - referenced_elements)
    orphan_attributes = sorted(global_attributes - referenced_attributes)
    orphan_simple_types = sorted(global_simple_types - referenced_types)
    orphan_complex_types = sorted(global_complex_types - referenced_types)

    return orphan_elements, orphan_attributes, orphan_simple_types, orphan_complex_types


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Scan an XSD for orphan global definitions:\n"
            "  - <xs:element name=\"...\"> never referenced via ref=\"...\"\n"
            "  - <xs:attribute name=\"...\"> never referenced via ref=\"...\"\n"
            "  - <xs:simpleType name=\"...\"> never referenced via type=\"...\" or base=\"...\"\n"
            "  - <xs:complexType name=\"...\"> never referenced via type=\"...\" or base=\"...\""
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "xsdfile",
        metavar="XSD_FILE",
        help="Path to the XSD file to scan for orphan definitions",
    )
    args = parser.parse_args()

    xsd_file = args.xsdfile
    orphans_el, orphans_attr, orphans_st, orphans_ct = find_orphans(xsd_file)

    print(f"\n=== Scan of “{xsd_file}” for orphan global definitions ===\n")

    if orphans_el:
        print("Orphan global <xs:element> definitions (never used via ref):")
        for name in orphans_el:
            print(f"  - {name}")
    else:
        print("No orphan global <xs:element> definitions found.")

    print()

    if orphans_attr:
        print("Orphan global <xs:attribute> definitions (never used via ref):")
        for name in orphans_attr:
            print(f"  - {name}")
    else:
        print("No orphan global <xs:attribute> definitions found.")

    print()

    if orphans_st:
        print("Orphan global <xs:simpleType> definitions (never used via type/base):")
        for name in orphans_st:
            print(f"  - {name}")
    else:
        print("No orphan global <xs:simpleType> definitions found.")

    print()

    if orphans_ct:
        print("Orphan global <xs:complexType> definitions (never used via type/base):")
        for name in orphans_ct:
            print(f"  - {name}")
    else:
        print("No orphan global <xs:complexType> definitions found.")

    print("\nScan complete.\n")


if __name__ == "__main__":
    main()

