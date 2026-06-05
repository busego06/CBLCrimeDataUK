# Police Demand Review Map

This is a stakeholder-facing dashboard prototype for one practical planning question:

> Which local areas should be reviewed first this month?

The output is a single combined review result:

- **Priority review:** areas to check first.
- **Reserve watch:** areas with possible emerging pressure.
- **Routine coverage:** areas not selected for extra review in this month.



The map uses Leaflet with CARTO basemap tiles based on OpenStreetMap data, so planners can drag, zoom, inspect scale, and click local authorities or individual LSOA points. The selected-area panel shows the demand result together with income, employment, education and deprivation context where official context data are available.

The UK-wide version uses an overview-to-drilldown visual structure. The default national view does not draw all 35,724 LSOA points at once. It first aggregates results into local-authority review-pressure circles, so non-technical stakeholders can see the national pattern without a cluttered point cloud. After a local authority is selected, the dashboard switches to the LSOA-level red/yellow/blue review points.

The teammate weighted-proximity clustering method was tested but is not shown as a main stakeholder layer in the current dashboard. With only three fake centre points in `dataShort/input.csv`, the UK-wide clusters become very large mathematical regions rather than clear operational planning units. The dashboard therefore keeps the clustering output as an experimental method record, but uses local authorities for the stakeholder-facing overview.

For the clustering experiment, the dashboard data uses `recent12Incidents` as the closest available equivalent to the C++ `cC` crime-count field. The C++ clustering output is precomputed and stored in `data/dashboard_data.js` as `teammateCluster`, but it is not used as the default stakeholder visualisation layer.

The score combines:

- recent and historical police.uk recorded demand;
- crime severity weighting;
- recent change or uplift;
- official income, employment, and education context from GOV.UK IoD 2025.

## Data sources

### Crime and demand

- Source: https://data.police.uk/data/
- Publisher: Single Online Home National Digital Team / data.police.uk
- Current version: police.uk all-force archive
- Period: April 2023 to March 2026
- Spatial unit: LSOA-level approximate locations
- Areas shown: 35,724 police.uk LSOA/area records
- Crime rows processed: 17,163,400 official police.uk records

### Context variables

- Source: GOV.UK English Indices of Deprivation 2025
- File used: File 7, ranks, scores, deciles and population denominators
- URL: https://www.gov.uk/government/statistics/english-indices-of-deprivation-2025
- Matched context areas: 32,863

The GOV.UK IoD 2025 context file covers English LSOAs. Non-English police.uk areas keep the crime-history forecast and are not given fabricated deprivation, income, employment or education values.

## Model check

The UK-wide model keeps the same modelling logic as the West Midlands version:

- convert recorded crime into severity-weighted monthly demand;
- create LSOA-month panel data;
- add lag, rolling-average, same-month-last-year and monthly trend features;
- compare simple baselines with ridge/context models;
- generate April 2026 predicted demand;
- assign tiers from the combined review score.

Held-out month checks for the UK-wide version:

- rolling 3-month baseline: WAPE 34.6%, hotspot recall 70.5%;
- same-month-last-year baseline: WAPE 44.0%, hotspot recall 62.2%;
- ridge lag model: WAPE 32.0%, hotspot recall 72.4%;
- context-aware model: WAPE 31.4%, hotspot recall 72.8%.

These numbers should be interpreted as decision-support evidence, not as proof that the dashboard can automatically allocate officers.

The demand-score logic is also informed by the ONS Crime Severity Score idea:

- https://www.ons.gov.uk/peoplepopulationandcommunity/crimeandjustice/articles/researchoutputsdevelopingacrimeseverityscoreforenglandandwalesusingdataoncrimesrecordedbythepolice/2016-11-29
