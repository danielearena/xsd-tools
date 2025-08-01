import os
import lxml.etree as ET
import argparse


def read_exclude_file(exclude_file):
    excluded_items = set()
    if exclude_file and os.path.isfile(exclude_file):
        with open(exclude_file, "r", encoding="utf-8") as f:
            excluded_items = {line.strip() for line in f if line.strip()}
    print(f"Excluding items from renaming: {excluded_items}")
    return excluded_items


def resolve_dependencies(tree, references, xs_ns, debuglevel):
    """
    Recursively find all required definitions based on the references.
    """
    root = tree.getroot()
    definitions = {
        "elements": {},
        "simpleTypes": {},
        "complexTypes": {},
        "attributes": {},
        "groups": {}
    }
    processed = set()

    def resolve_reference(ref, ref_type):
        # Normalize and skip already processed references
        normalized_ref = ref.strip()
        if (normalized_ref, ref_type) in processed:
            if debuglevel >= 2:
                print(f"DEBUG: Skipping already processed reference: {normalized_ref} ({ref_type})")
            return

        if debuglevel >= 2:
            print(f"DEBUG: Processing reference: {normalized_ref} ({ref_type})")
        processed.add((normalized_ref, ref_type))

        # Find the definition
        definition = None
        if ref_type == "simpleType":
            definition = root.find(f".//xs:simpleType[@name='{normalized_ref}']", namespaces={"xs": xs_ns})
        elif ref_type == "complexType":
            definition = root.find(f".//xs:complexType[@name='{normalized_ref}']", namespaces={"xs": xs_ns})
        elif ref_type == "element":
            definition = root.find(f"./xs:element[@name='{normalized_ref}']", namespaces={"xs": xs_ns})
            if definition is None:
                # Fallback to a broader search if the global definition is not found
                definition = root.find(f".//xs:element[@name='{normalized_ref}']", namespaces={"xs": xs_ns})
            #definition = root.find(f".//xs:element[@name='{normalized_ref}']", namespaces={"xs": xs_ns})
            #print(f"XPath for definition: {definition.getroottree().getpath(definition)}")
        elif ref_type == "attribute":
            definition = root.find(f".//xs:attribute[@name='{normalized_ref}']", namespaces={"xs": xs_ns})
        elif ref_type == "group":
            definition = root.find(f".//xs:group[@name='{normalized_ref}']", namespaces={"xs": xs_ns})

        if definition is not None:
            definitions[ref_type + "s"][normalized_ref] = definition
            if debuglevel >= 2:
                print(f"DEBUG: Resolved definition: {normalized_ref} ({ref_type}), Tag: {definition.tag}")

            #print("*** DEBUG all ***")
            #for elem in definition.findall(".[@type]", namespaces={"xs": xs_ns}):
            #    print(elem.tag, elem.attrib)
            #print("*** END DEBUG all ***")

            # Recursively resolve dependencies
            for dep_attr in ["type", "base", "ref", "group"]:
                if debuglevel >= 2:
                    print(f"DEBUG: Looking for {dep_attr} dependencies")
                for ref_elem in [definition] + definition.findall(f".//*[@{dep_attr}]", namespaces={"xs": xs_ns}):
                    if debuglevel >= 2:
                        #print(ET.tostring(ref_elem, pretty_print=True).decode())
                        print(f"DEBUG: ref_elem: {ref_elem.get(dep_attr)}")
                        print(f"DEBUG: Processing element: {ref_elem.tag}, type attribute: {ref_elem.get('type')}")
                    dep_ref = ref_elem.get(dep_attr)
                    if dep_ref and ":" not in dep_ref:  # Local reference (no prefix)
                        if dep_attr in ["type", "base"]:
                            resolve_reference(dep_ref, "simpleType")
                            resolve_reference(dep_ref, "complexType")
                        elif dep_attr == "ref":
                            if ref_elem.tag == f"{{{xs_ns}}}element":
                                resolve_reference(dep_ref, "element")
                            elif ref_elem.tag == f"{{{xs_ns}}}attribute":
                                resolve_reference(dep_ref, "attribute")
                        elif dep_attr == "group":
                            resolve_reference(dep_ref, "group")

            # Handle inline complexType or simpleType
            inline_type = definition.find(".//xs:complexType", namespaces={"xs": xs_ns})
            if inline_type is None:  # If no complexType, check for simpleType
                inline_type = definition.find(".//xs:simpleType", namespaces={"xs": xs_ns})

            # Do not treat inline types as global definitions
            if inline_type is not None:
                if "name" not in inline_type.attrib:  # Inline type
                    if debuglevel >= 2:
                        print(f"DEBUG: Skipping inline type for: {ref} ({ref_type})")
                else:  # Only include named types
                    if debuglevel >= 2:
                        print(f"DEBUG: Resolving named inline type for: {ref} ({ref_type})")
                    definitions["complexTypes" if inline_type.tag.endswith("complexType") else "simpleTypes"][ref] = inline_type


        else:
            print(f"WARNING: Definition for reference '{normalized_ref}' ({ref_type}) not found in schema.")

    # Start by resolving the initial set of references
    for ref, ref_type in references:
        if debuglevel >= 2:
            print(f"DEBUG: Initial reference to resolve: {ref} ({ref_type})")
        resolve_reference(ref, ref_type)

    return definitions


def rename_and_copy_definitions(definitions, prefix, xs_ns, debuglevel,excluded_items):
    """Rename and copy the required definitions with the prefix."""
    renamed_definitions = []
    #print (f"definitions.items: {definitions.items()}")
    for ref_type, defs in definitions.items():
        if debuglevel >= 2:
            print(f"DEBUG: ref_type: {ref_type}, defs: {defs}")
        for ref, definition in defs.items():
            # Ensure definition is an XML element and not a dictionary
            if isinstance(definition, ET._Element):
                if debuglevel >= 2:
                    print(f"DEBUG: Processing definition: {ref}, Tag: {definition.tag}")

                # Create a deep copy of the definition without copying the nsmap for every child
                definition_copy = ET.Element(definition.tag)

                # Copy relevant attributes while excluding usage-specific ones like 'minOccurs', 'maxOccurs', etc.
                for key, value in definition.attrib.items():
                    if debuglevel >= 2:
                        print(f"DEBUG: definition.attrib.items: key={key}, value={str(value)}")
                    if key not in ["minOccurs", "maxOccurs", "nillable", "use"]:
                        definition_copy.set(key, str(value))

                if debuglevel >= 2:
                    print (f"DEBUG: definition_copy.attrib: {definition_copy.attrib}")
                if "name" in definition_copy.attrib:
                    if debuglevel >= 2:
                        print (f"DEBUG: Processing copy of {definition_copy.attrib['name']}")
                    original_name = definition.attrib["name"]
                    #parent = definition.getparent()
                    #print (parent.tag)

                    # Check if the element or type is global

                    is_global = definition.getroottree().getpath(definition).startswith("/xs:schema/")
                    #is_global = parent.tag == f"{{{xs_ns}}}schema" if parent is not None else False

                    if is_global:
                        # Rename global definitions
                        renamed_name = f"{prefix}{original_name}"
                        if original_name not in excluded_items:
                            definition_copy.attrib["name"] = renamed_name
                            if debuglevel >= 2:
                                print(f"DEBUG: Renamed global definition from '{original_name}' to '{renamed_name}'")
                    else:
                        # Skip renaming for local definitions
                        if debuglevel >= 2:
                            print(f"DEBUG: Skipped renaming local definition: {original_name}")

                # Rename references in the top-level definition's attributes
                for dep_attr in ["type", "ref", "base"]:
                    if dep_attr in definition_copy.attrib:
                        dep_ref = definition_copy.attrib[dep_attr]
                        if ":" not in dep_ref and dep_ref not in excluded_items:  # Local reference
                            new_ref = f"{prefix}{dep_ref}"
                            definition_copy.attrib[dep_attr] = new_ref
                            if debuglevel >= 2:
                                print(f"DEBUG: Updated attribute '{dep_attr}' from '{dep_ref}' to '{new_ref}'")

                # Recursively rename all children and attributes in the definition
                def recursive_rename(element, parent):
                    if not isinstance(element.tag, str):
                        if debuglevel >= 2:
                            print(f"DEBUG: Skipping non-element node: {element.tag}")
                        return

                    if debuglevel >= 2:
                        print(f"DEBUG: Recursively processing element: {element.tag}, Parent: {parent.tag}")

                    # Create a deep copy of the child element without copying nsmap
                    element_copy = ET.Element(element.tag)

                    # Copy relevant attributes while excluding usage-specific ones like 'minOccurs', 'maxOccurs', 'nillable', 'use'
                    for key, value in element.attrib.items():
                        #if key not in ["minOccurs", "maxOccurs", "nillable", "use"]:  # Removed 'use' attribute if present
                        #    element_copy.set(key, str(value))
                        element_copy.set(key, str(value))

                    # Copy text content, if available
                    if element.text:
                        element_copy.text = element.text

                    # Rename reference attributes in the child
                    for dep_attr in ["type", "ref", "base"]:
                        if dep_attr in element_copy.attrib:
                            dep_ref = element_copy.attrib[dep_attr]
                            if ":" not in dep_ref and dep_ref not in excluded_items:  # Local reference
                                new_ref = f"{prefix}{dep_ref}"
                                element_copy.attrib[dep_attr] = new_ref
                                if debuglevel >= 2:
                                    print(f"DEBUG: Updated child attribute '{dep_attr}' from '{dep_ref}' to '{new_ref}'")

                    # Rename 'name' attribute if the child itself is a definition
                    if "name" in element_copy.attrib and element.attrib["name"] not in excluded_items:
                        original_name = element.attrib["name"]
                        renamed_name = f"{prefix}{original_name}"
                        element_copy.attrib["name"] = renamed_name
                        if debuglevel >= 2:
                            print(f"DEBUG: Renamed child definition from '{original_name}' to '{renamed_name}'")

                    # Append the copied child to the parent
                    parent.append(element_copy)

                    # Recursively handle the element's children
                    for child in element:
                        recursive_rename(child, element_copy)

                # Handle the root element's children
                for child in definition:
                    recursive_rename(child, definition_copy)

                renamed_definitions.append(definition_copy)
            else:
                print(f"WARNING: Expected an XML element, but got a different type for reference '{ref}'")

    return renamed_definitions



def create_sub_include(main_xsd_file, sub_xsd_file, sub_include_file, prefix, debuglevel,excluded_items):
    """Create sub_include.xsd with only the definitions needed by main.xsd."""
    # Parse main and sub XSDs
    main_tree = ET.parse(main_xsd_file)
    main_root = main_tree.getroot()
    sub_tree = ET.parse(sub_xsd_file)
    sub_root = sub_tree.getroot()

    xs_ns = main_root.nsmap.get("xs", "http://www.w3.org/2001/XMLSchema")

    # Collect initial references from main.xsd
    references = set()
    for type_elem in main_root.findall(".//*[@type]", namespaces={"xs": xs_ns}):
        ref = type_elem.get("type")
        if ref and ref.startswith(f"{prefix[:-1]}:"):  # Matches the sub namespace
            local_name = ref.split(":")[1]
            references.add((local_name, "simpleType"))
            references.add((local_name, "complexType"))

    for ref_elem in main_root.findall(".//*[@ref]", namespaces={"xs": xs_ns}):
        ref = ref_elem.get("ref")
        if ref and ref.startswith(f"{prefix[:-1]}:"):  # Matches the sub namespace
            references.add((ref.split(":")[1], "element"))  # Extract local name, element type

    for attr_elem in main_root.findall(".//xs:attribute[@ref]", namespaces={"xs": xs_ns}):
        ref = attr_elem.get("ref")
        if ref and ref.startswith(f"{prefix[:-1]}:"):
            references.add((ref.split(":")[1], "attribute"))

    if debuglevel >= 2:
        print("DEBUG: ***References: ***", sorted(references))

    # Resolve all dependencies recursively
    required_definitions = resolve_dependencies(sub_tree, references, xs_ns, debuglevel)
    if debuglevel >= 2:
        print("DEBUG: ***Required definitions: ***", required_definitions.keys())

    # Ensure all top-level elements and types are also included
#    for element in sub_root.findall(".//xs:*[@name]", namespaces={"xs": xs_ns}):
#        element_name = element.get("name")
#        element_type = element.tag.split("}")[-1]  # Get the local part of the tag
#        element_type_plural = f"{element_type}s"
#
#        # Only include if element type matches what we are handling
#        if element_name and element_type_plural in required_definitions:
#            if element_name not in required_definitions[element_type_plural]:
#                print(f"Including additional top-level definition: {element_name}")
#                required_definitions[element_type_plural][element_name] = element
#        else:
#            print(f"Warning: Unexpected element type '{element_type}' encountered.")

    # Rename and copy definitions with the prefix
    renamed_definitions = rename_and_copy_definitions(required_definitions, prefix, xs_ns, debuglevel,excluded_items)

    # Create a new sub_include.xsd with only required definitions
    # Set nsmap only at the root level, excluding unnecessary namespaces
    new_root_nsmap = {k: v for k, v in sub_root.nsmap.items() if k in ["xs"]}  # Retain only xs namespace
    new_root = ET.Element("{" + xs_ns + "}schema", nsmap=new_root_nsmap)
    new_root.attrib["elementFormDefault"] = sub_root.attrib.get("elementFormDefault", "qualified")
    # Remove targetNamespace for the included schema to avoid conflicts
    if "targetNamespace" in new_root.attrib:
        del new_root.attrib["targetNamespace"]

    for definition in renamed_definitions:
        new_root.append(definition)

    # Ensure all references in the new schema are resolved
    for ref, ref_type in references:
        ref_plural = f"{ref_type}s"
        if ref_plural in required_definitions and ref not in required_definitions[ref_plural]:
            print(f"WARNING: Reference '{ref}' ({ref_type}) is missing in the included definitions.")

    # Save the new sub_include.xsd
    new_tree = ET.ElementTree(new_root)
    new_tree.write(sub_include_file, pretty_print=True, xml_declaration=True, encoding="UTF-8")
    if debuglevel:
        print(f"INFO: Created selective included XSD: {sub_include_file}")


def update_main_xsd(main_xsd_file, sub_include_file, output_main_xsd, prefix, debuglevel, excluded_items):
    """Replace xs:import with xs:include in the main XSD, update references, and preserve comments."""
    tree = ET.parse(main_xsd_file)
    root = tree.getroot()
    xs_ns = root.nsmap.get("xs", "http://www.w3.org/2001/XMLSchema")

    # Collect comments and their positions
    comments = []
    for parent in root.iter():
        for child in parent:
            if isinstance(child, ET._Comment):
                comments.append((parent, child.getprevious(), child.text))
                parent.remove(child)  # Temporarily remove comment

    # Update references in main.xsd

    for ref_elem in root.findall(".//*[@ref]", namespaces={"xs": xs_ns}):
        old_ref = ref_elem.get("ref")
        if old_ref and old_ref.startswith(f"{prefix[:-1]}:"):
            ref_local_name = old_ref.split(":", 1)[1]
            if ref_local_name in excluded_items:
                new_ref = ref_local_name  # Keep original name without prefix
            else:
                new_ref = f"{prefix}{ref_local_name}"  # Add prefix
            ref_elem.set("ref", new_ref)
            if debuglevel >= 2:
                print(f"DEBUG: Updated reference: {old_ref} -> {new_ref}")
            # Log all attributes to ensure they are preserved
            #attributes = ref_elem.attrib  # Get all attributes
            #print(f"Element attributes: {attributes}")

    for type_elem in root.findall(".//*[@type]", namespaces={"xs": xs_ns}):
        old_type = type_elem.get("type")
        if old_type and old_type.startswith(f"{prefix[:-1]}:"):
            new_type = f"{prefix}{old_type.split(':', 1)[1]}"
            type_elem.set("type", new_type)
            if debuglevel >= 2:
                print(f"DEBUG: Updated type: {old_type} -> {new_type}")

    for base_elem in root.findall(".//*[@base]", namespaces={"xs": xs_ns}):
        old_base = base_elem.get("base")  # Get the current value of the base attribute
        if old_base and old_base.startswith(f"{prefix[:-1]}:"):  # Check if it starts with the namespace prefix
            new_base = f"{prefix}{old_base.split(':', 1)[1]}"  # Replace prefix with the updated one
            base_elem.set("base", new_base)  # Update the base attribute
            if debuglevel >= 2:
                print(f"DEBUG: Updated base: {old_base} -> {new_base}")

    # Replace each top-level <xs:import> with <xs:include>
    for imp in root.findall("./xs:import", namespaces={"xs": xs_ns}):
        if debuglevel:
            print("DEBUG: Rewriting import to include:", ET.tostring(imp, pretty_print=True).decode().strip())
        # Change tag
        imp.tag = f"{{{xs_ns}}}include"
        # Drop the namespace attribute
        imp.attrib.pop("namespace", None)
        # Point to the new flattened sub-schema
        imp.attrib["schemaLocation"] = sub_include_file


    # Reattach comments with proper handling
    attached_comments = set()
    for parent, previous, text in comments:
        if text not in attached_comments:  # Avoid duplicates
            comment = ET.Comment(text)
            attached_comments.add(text)

            # Insert the comment and ensure a newline follows it
            if previous is not None:
                parent.insert(parent.index(previous) + 1, comment)
            else:
                parent.insert(0, comment)

    # Save the modified main.xsd
    tree.write(output_main_xsd, pretty_print=True, xml_declaration=True, encoding="UTF-8")
    print(f"INFO: Processed {main_xsd_file} saved as: {output_main_xsd}")


def xsd_import2include(main_xsd_file,exclude_file,debuglevel):
    excluded_items = read_exclude_file(exclude_file)
    main_xsd_basename = os.path.basename(main_xsd_file)

    # Parse main.xsd to identify sub.xsd and determine prefix
    main_tree = ET.parse(main_xsd_file)
    main_root = main_tree.getroot()
    xs_ns = main_root.nsmap.get("xs", "http://www.w3.org/2001/XMLSchema")
    sub_ns = None
    sub_xsd_file = None
    prefix = None

    for imp in main_root.findall(".//xs:import", namespaces={"xs": xs_ns}):
        sub_ns = imp.get("namespace")
        sub_xsd_file = imp.get("schemaLocation")
        prefix = [p for p, ns in main_root.nsmap.items() if ns == sub_ns]
        prefix = prefix[0] + "_" if prefix else ""
        break

    if not sub_xsd_file or not prefix:
        print("INFO: No valid <xs:import> found in the main XSD.")
        return

    # Resolve sub_xsd_file full path
    sub_xsd_file = os.path.join(os.path.dirname(main_xsd_file), sub_xsd_file)
    sub_xsd_basename = os.path.basename(sub_xsd_file)

    # Set output filenames
    sub_include_file = os.path.join(os.path.dirname(sub_xsd_file), f"{sub_xsd_basename.replace('.xsd', '_include.xsd')}")
    output_main_xsd = os.path.join(os.path.dirname(main_xsd_file), f"{main_xsd_basename.replace('.xsd', '_processed.xsd')}")

    if debuglevel:
        print(f"INFO: Detected sub namespace: {sub_ns}")
        print(f"INFO: Using prefix: {prefix}")
        print(f"INFO: Sub XSD file: {sub_xsd_file}")

    # Process sub.xsd selectively
    create_sub_include(main_xsd_file, sub_xsd_file, sub_include_file, prefix, debuglevel, excluded_items)
    #create_sub_include(main_xsd_file, sub_xsd_file, sub_include_file, prefix, debuglevel)
    # Process main.xsd
    update_main_xsd(main_xsd_file, sub_include_file, output_main_xsd, prefix, debuglevel, excluded_items)

    return (output_main_xsd, sub_include_file)


def main():
    parser = argparse.ArgumentParser(description="Changes 'import' statements of an XSD file into 'include' statements.")
    parser.add_argument("mainxsd", help="Path to the XSD file to be processed.")
    parser.add_argument("-e", "--exclude", help="Path to the exclude file (optional).")

    # Create a mutually exclusive group for -v and -d
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-v', '--verbose', action='store_true', help="Increase output verbosity.")
    group.add_argument('-d', '--debug', action='store_true', help="Print debug information.")

    args = parser.parse_args()

    debuglevel = 0

    main_xsd_file = args.mainxsd
    if args.verbose:
        print("INFO: Verbose mode enabled.")
        debuglevel = 1
    elif args.debug:
        print("INFO: Debug mode enabled.")
        debuglevel = 2
        

    (output_main_xsd, sub_include_file) = xsd_import2include(main_xsd_file,args.exclude,debuglevel)
    print(f"INFO: Output Main XSD file: {output_main_xsd}")
    print(f"INFO: Sub Include file: {sub_include_file}")


if __name__ == "__main__":
    main()

