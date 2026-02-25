# TAIDE Law Converters

This project contains scripts for converting `.docx` files into structured JSON and Markdown formats. Follow the steps below to set up the environment and run the scripts.

## Requirements

1. Python packages:
   - `python-docx`
   - `pypandoc`

   Install them using:
   ```bash
   pip install -r requirements.txt
   ```

2. Pandoc:
   - Ensure Pandoc is installed on your system. You can download it from [Pandoc's official website](https://pandoc.org/installing.html).

## Usage

1. Place your `.docx` files in the `rawdata` folder.
2. Run the respective script:
   - For JSON conversion:
     ```bash
     python converters/docx_to_json.py
     ```
   - For Markdown conversion:
     ```bash
     python converters/dock_to_md.py
     ```
3. The output files will be saved in the `processed_data` folder.

## Notes
- Ensure the `rawdata` and `processed_data` folders exist before running the scripts.
- The scripts automatically create the `processed_data` folder if it doesn't exist.
