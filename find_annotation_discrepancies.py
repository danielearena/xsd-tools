#!/usr/bin/env python3
"""
find_annotation_discrepancies.py

Scan an XSD for discrepancies between annotations on global element/attribute definitions
and annotations at their reference sites. For each <xs:element> or <xs:attribute> that is
defined globally and then referenced via ref="...", compare the <xs:annotation><xs:documentation>
content in the global definition vs. in the referencing node—**but only if the reference has an annotation**.
If the reference has no <xs:annotation>, it is disregarded. When both have annotations and they differ,
report the global name, the definition annotation, and for each reference site with a discrepancy:
the reference annotation, its line number, and the closest global ancestor.

Usage:
    python find_annotation_discrepancies.py /path/to/schema.xsd

Run `python find_annotation_discrepancies.py --help` for details.
"""

import sys
import os
import argparse
from lxml import etree

# XML Schema namespace URI
XSD_NS = "http://www.w3.org/2001/XMLSchema"
NSMAP = {"xs": XSD_NS}


def local_name(qname):
    """
    Extract the local part of a QName (e.g. '{uri}Foo' -> 'Foo', 'tns:Foo' -> 'Foo').
    """
    if qname is None:
        return None
    if qname.startswith("{"):
        return qname.split("}", 1)[1]
    if ":" in qname:
        return qname.split(":", 1)[1]
    return qname


def get_annotation_text(node):
    """
    Given an XSD node (<xs:element> or <xs:attribute>), find its immediate <xs:annotation>
    child and collect all <xs:documentation> text under it. Return a single string
    (joined by newlines) or '' if no annotation/documentation is found.
    """
    ann = node.find("xs:annotation", NSMAP)
    if ann is None:
        return ""
    docs = ann.findall("xs:documentation", NSMAP)
    texts = []
    for d in docs:
        if d.text and d.text.strip():
            texts.append(d.text.strip())
    return "\n".join(texts)


def find_closest_global_ancestor(node, root):
    """
    For a given node (an lxml Element) inside the schema, return the nearest ancestor
    whose parent is root. If node itself is a direct child of root, return (None, None).
    Returns a tuple (ancestor_tag, ancestor_name), where ancestor_tag is 'xs:element'
    or 'xs:complexType', etc., and ancestor_name is its @name.
    """
    parent = node.getparent()
    if parent is None or parent == root:
        return None, None

    curr = parent
    while curr is not None and curr.getparent() is not root:
        curr = curr.getparent()

    if curr is None or curr.getparent() is None:
        return None, None

    tag_local = etree.QName(curr).localname  # e.g. "element", "complexType"
    ancestor_tag = f"xs:{tag_local}"
    ancestor_name = curr.get("name")
    return ancestor_tag, ancestor_name


def find_annotation_discrepancies(xsd_path):
    """
    Parse the XSD at xsd_path. Collect:
      - All global <xs:element name="..."> and <xs:attribute name="..."> definitions,
        capturing their annotation text.
      - All <xs:element ref="..."> and <xs:attribute ref="..."> nodes that have an <xs:annotation>.
    For each reference with an annotation, compare the reference annotation vs. the global
    definition annotation. If they differ, record a discrepancy.

    Returns:
      discrepancies: a list of dicts with keys:
        'type'       -> 'element' or 'attribute'
        'name'       -> global name
        'def_text'   -> annotation text at definition ('' if none)
        'ref_text'   -> annotation text at reference (non-empty)
        'ref_line'   -> line number of the referencing node
        'ancestor_tag', 'ancestor_name' -> closest global ancestor info for the reference
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

    # 1) Collect global element definitions and their annotation text
    global_el_ann = {}   # name -> annotation text
    for el in root.findall("xs:element", NSMAP):
        name = el.get("name")
        if name:
            global_el_ann[name] = get_annotation_text(el)

    # 2) Collect global attribute definitions and their annotation text
    global_attr_ann = {}  # name -> annotation text
    for attr in root.findall("xs:attribute", NSMAP):
        name = attr.get("name")
        if name:
            global_attr_ann[name] = get_annotation_text(attr)

    discrepancies = []

    # 3) Check all <xs:element ref="..."> that have an annotation
    for ref_node in root.findall(".//xs:element[@ref]", NSMAP):
        ref_text = get_annotation_text(ref_node)
        # If reference has no annotation, skip entirely
        if not ref_text:
            continue

        ref_q = ref_node.get("ref")
        name = local_name(ref_q)
        if name is None or name not in global_el_ann:
            continue

        def_text = global_el_ann.get(name, "")
        if def_text != ref_text:
            line = ref_node.sourceline
            anc_tag, anc_name = find_closest_global_ancestor(ref_node, root)
            discrepancies.append({
                "type": "element",
                "name": name,
                "def_text": def_text,
                "ref_text": ref_text,
                "ref_line": line,
                "ancestor_tag": anc_tag,
                "ancestor_name": anc_name
            })

    # 4) Check all <xs:attribute ref="..."> that have an annotation
    for ref_node in root.findall(".//xs:attribute[@ref]", NSMAP):
        ref_text = get_annotation_text(ref_node)
        # Skip references without annotation
        if not ref_text:
            continue

        ref_q = ref_node.get("ref")
        name = local_name(ref_q)
        if name is None or name not in global_attr_ann:
            continue

        def_text = global_attr_ann.get(name, "")
        if def_text != ref_text:
            line = ref_node.sourceline
            anc_tag, anc_name = find_closest_global_ancestor(ref_node, root)
            discrepancies.append({
                "type": "attribute",
                "name": name,
                "def_text": def_text,
                "ref_text": ref_text,
                "ref_line": line,
                "ancestor_tag": anc_tag,
                "ancestor_name": anc_name
            })

    return discrepancies


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Scan an XSD for annotation discrepancies between global definitions and their references.\n"
            "For each global <xs:element> or <xs:attribute> defined with a <xs:annotation>,\n"
            "compare that annotation to any <xs:annotation> at ref=\"...\" sites—but only if the reference\n"
            "itself has an annotation. If they differ, report the discrepancy with reference line\n"
            "and closest global ancestor."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "xsdfile",
        metavar="XSD_FILE",
        help="Path to the XSD file to scan for annotation discrepancies",
    )
    args = parser.parse_args()

    discrepancies = find_annotation_discrepancies(args.xsdfile)

    print(f"\n=== Annotation Discrepancies Report for “{args.xsdfile}” ===\n")

    if not discrepancies:
        print("No annotation discrepancies found (or references without annotation were ignored).")
        print("\nScan complete.\n")
        return

    for disc in discrepancies:
        typ = disc["type"]
        name = disc["name"]
        def_text = disc["def_text"] or "[None]"
        ref_text = disc["ref_text"]  # guaranteed non-empty
        line = disc["ref_line"]
        anc_tag = disc["ancestor_tag"]
        anc_name = disc["ancestor_name"]

        print(f"Discrepancy for global xs:{typ} \"{name}\":")
        print(f"  - Definition annotation: {def_text!r}")
        if anc_tag:
            print(
                f"  - Reference at line {line} inside {anc_tag} name=\"{anc_name}\":"
            )
        else:
            print(f"  - Reference at line {line} [GLOBAL CONTEXT]:")
        print(f"      Reference annotation: {ref_text!r}")
        print()

    print(f"Total discrepancies found: {len(discrepancies)}")
    print("\nScan complete.\n")


if __name__ == "__main__":
    main()

