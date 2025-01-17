import argparse
import os
from xsd_import2include import xsd_import2include
from sort_xsd import sort_xsd
from flatten_include import flatten_xsd

def flatten_xsd_pipeline(input_xsd, output_xsd, debuglevel, exclude_file):
    """
    Executes the XSD flattening pipeline:
    1. Convert <xs:import> to <xs:include>.
    2. Sort the included XSD and replace it in the main file.
    3. Flatten the main XSD into a single self-contained file.
    
    Args:
        input_xsd (str): Path to the input XSD file.
        output_xsd (str): Path to the final output XSD file.
        debuglevel (int): Debug verbosity level.
    """
    # Step 1: Convert <xs:import> to <xs:include>
    processed_main_xsd, included_xsd = xsd_import2include(input_xsd, exclude_file, debuglevel)

    if not processed_main_xsd or not included_xsd:
        raise FileNotFoundError("Processing <xs:import> to <xs:include> failed.")

    # Step 2: Sort the included XSD
    sorted_xsd = included_xsd.replace('.xsd', '_sorted.xsd')
    sort_xsd(included_xsd, sorted_xsd)

    # Replace the original included XSD with the sorted one
    os.rename(sorted_xsd, included_xsd)

    # Step 3: Flatten the processed main XSD
    flatten_xsd(processed_main_xsd, output_xsd)
    if debuglevel >= 1:
        print(f"INFO: Flattened XSD saved to: {output_xsd}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Flatten an XSD file from a file containing an import statement.")
    parser.add_argument("input_xsd", help="Path to the input XSD file.")
    parser.add_argument("output_xsd", help="Path to the final flattened XSD file.")
    parser.add_argument("-e", "--exclude", help="Path to the exclude file (optional).")

    # Debug flags
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-v", "--verbose", action="store_true", help="Enable verbose mode (debuglevel=1).")
    group.add_argument("-d", "--debug", action="store_true", help="Enable debug mode (debuglevel=2).")

    args = parser.parse_args()

    # Set debug level
    debuglevel = 0
    if args.verbose:
        debuglevel = 1
    elif args.debug:
        debuglevel = 2

    try:
        flatten_xsd_pipeline(args.input_xsd, args.output_xsd, debuglevel, args.exclude)
    except Exception as e:
        print(f"Error: {e}")

