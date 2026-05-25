# Police Demand Review Map

This is a stakeholder-facing dashboard prototype for one practical planning question:

> Which local areas should be reviewed first this month?

The output is a single combined review result:

- **Priority review:** areas to check first.
- **Reserve watch:** areas with possible emerging pressure.
- **Routine coverage:** areas not selected for extra review in this month.



The map uses Leaflet with CARTO basemap tiles based on OpenStreetMap data, so planners can drag, zoom, inspect scale, and click individual areas. The selected-area panel shows the demand result together with income, employment, education and deprivation context.

The score combines:

- recent and historical police.uk recorded demand;
- crime severity weighting;
- recent change or uplift;
- official income, employment, and education context from GOV.UK IoD 2025.

## Data sources

### Crime and demand

- Source: https://data.police.uk/data/
- Publisher: Single Online Home National Digital Team / data.police.uk
- Current pilot force: West Midlands Police
- Period: April 2023 to March 2026
- Spatial unit: LSOA-level approximate locations

### Context variables

- Source: GOV.UK English Indices of Deprivation 2025
- File used: File 7, ranks, scores, deciles and population denominators
- URL: https://www.gov.uk/government/statistics/english-indices-of-deprivation-2025

The demand-score logic is also informed by the ONS Crime Severity Score idea:

- https://www.ons.gov.uk/peoplepopulationandcommunity/crimeandjustice/articles/researchoutputsdevelopingacrimeseverityscoreforenglandandwalesusingdataoncrimesrecordedbythepolice/2016-11-29
