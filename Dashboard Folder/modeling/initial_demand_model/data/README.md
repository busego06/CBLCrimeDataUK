# Data download instructions

The raw crime data used for this initial model is not committed to GitHub.

Reason: the official police.uk ZIP is large and can be downloaded from the source, so the repository should keep code and reproducible outputs instead of duplicating raw public data.

## Official source

- Website: https://data.police.uk/data/
- Publisher: Single Online Home National Digital Team / data.police.uk
- Dataset type: street-level crime CSVs, aggregated by police force and 2021 LSOA
- Force used in this pilot: West Midlands Police
- Date range used in this pilot: April 2023 to March 2026
- Data type selected: crime data

## How to reproduce the input file

1. Go to https://data.police.uk/data/
2. Select:
   - From: April 2023
   - To: March 2026
   - Force: West Midlands Police
   - Include crime data: yes
   - Outcomes and stop-and-search: not needed for this first model
3. Generate and download the ZIP file.
4. Rename or save the file as:

```text
data/police_west_midlands_2023_04_to_2026_03.zip
```

5. Run the model from the parent folder:

```bash
python build_police_demand_model.py
```

You can also pass a custom file path:

```bash
python build_police_demand_model.py --zip-path path/to/official_police_uk_download.zip
```

