# FlattenXSD: Flattening and Processing XML Schema Definitions

This repository contains four Python scripts designed to handle various tasks related to XML Schema Definitions (XSD). The tools enable users to convert `<xs:import>` statements to `<xs:include>`, "flatten" the included files in a single file, sort XSD definitions, and process files to create self-contained schemas. The scripts are:

1. **xsd_import2include.py**
2. **flatten_include.py**
3. **sort_xsd.py**
4. **flattenxsd.py**

## Description of Scripts

### 1. `xsd_import2include.py`
This script converts `<xs:import>` statements in an XSD file to `<xs:include>`. Additionally, it allows the user to exclude specific elements, attributes, or types from being renamed during processing, using an **exclude file**.

#### Usage:
```bash
python xsd_import2include.py <main_xsd> [-e <exclude_file>] [-v | -d]
```

- `<main_xsd>`: Path to the main XSD file.
- `-e <exclude_file>`: (Optional) Path to a file containing a list of items (one per line) to exclude from renaming.
- `-v`: Enable verbose mode for basic information.
- `-d`: Enable debug mode for detailed processing information.

When copied from the imported file to the included file, objects (e.g. elements, attributes) are renamed by prepending the namespace used in the import as a prefix. So for instance if the namespace is "ns" and an element in the imported file is called "Book", the copied element in the included file will be called "ns\_Book". This avoids potential conflicts in the final result.

The "exclude file" can be used to avoid renaming some of the elements of the imported file.

### 2. `flatten_include.py`
This script resolves `<xs:include>` elements in an XSD file, incorporating all included content into a single file. The resulting file is a self-contained XSD.

#### Usage:
```bash
python flatten_include.py <input_file> [-o <output_file>]
```

- `<input_file>`: Path to the input XSD file.
- `-o <output_file>`: (Optional) Path to save the flattened XSD file. Defaults to appending `_flattened` to the input file name.

### 3. `sort_xsd.py`
This script sorts XSD definitions alphabetically. By default the sorting is done first by kind (e.g., `element`, `complexType`) and then by name; this order can be reversed. This ensures consistent organization of schema definitions.

#### Usage:
```bash
python sort_xsd.py <file> [--output <output_file>] [--name-first]
```

- `<file>`: Path to the input XSD file.
- `--output <output_file>`: (Optional) Path to save the sorted XSD file. Defaults to appending `_sorted` to the input file name.
- `--name-first`: Sort by name first, then by kind.

### 4. `flattenxsd.py`
This is the main orchestration script that combines the functionality of the other three scripts. It performs the following pipeline:

1. Converts `<xs:import>` statements to `<xs:include>` using `xsd_import2include.py`.
2. Sorts the resulting included XSD using `sort_xsd.py`.
3. Flattens the processed main XSD into a single self-contained file using `flatten_include.py`.

#### Usage:
```bash
python flattenxsd.py <input_xsd> <output_xsd> [-e <exclude_file>] [-v | -d]
```

- `<input_xsd>`: Path to the main input XSD file.
- `<output_xsd>`: Path to save the final flattened XSD file.
- `-e <exclude_file>`: (Optional) Path to a file with a list of items to exclude from renaming.
- `-v`: Enable verbose mode for pipeline progress.
- `-d`: Enable debug mode for detailed logs.

## The Exclude File
The **exclude file** allows users to specify items (one per line) that should not be renamed during processing. This applies to elements, attributes, and types referenced in the schema. When provided, the script will retain the original names for these items, even if a prefix is applied to other definitions.

### Example Exclude File:
```
MyElement
MyComplexType
myAttribute
```

## Example Workflow
Assume you have an XSD file, `example.xsd`, and want to produce a self-contained, flattened version, `example_flattened.xsd`, while excluding certain definitions from being renamed.

#### Step 1: Run the Flattening Pipeline
```bash
python flattenxsd.py example.xsd example_flattened.xsd -e exclude.txt -v
```

- Converts imports to includes (`xsd_import2include.py`).
- Sorts the included XSD (`sort_xsd.py`).
- Flattens the XSD (`flatten_include.py`).

#### Output:
- `example_flattened.xsd`: The final self-contained XSD.
- Intermediate files, such as sorted or processed XSDs, may also be saved depending on the steps.

## Requirements
- Python 3.6 or later
- `lxml` library (for `flatten_include.py` and `xsd_import2include.py`)

Install required libraries:
```bash
pip install lxml
```

## License
This repository is distributed under the GNU License.


