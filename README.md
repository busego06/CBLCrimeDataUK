# CBL Crime Data UK

Repository for Group 10's project in **4CBLW020 Addressing real-world crime and security problems with data science**.

The course project asks:

> How can data-driven estimates of police demand be used to inform the effective organisation and allocation of policing resources in the United Kingdom?

Our work approaches this question through exploratory research, demand modelling, and dashboard prototypes for police planning stakeholders. The dashboards are intended as decision-support tools: they organise evidence into a clearer planning view, but they do not prescribe automatic deployment decisions.

## Repository Structure

```text
CBLCrimeDataUK/
  Dashboard Data Creation Folder/
    Scripts and source files used to generate the prediction dashboard data.

  Django Dashboard Folder/
    Django project containing the dashboard web applications.

  Research Folder/
    Exploratory analysis scripts used during the project.

  requirements.txt
    Python dependencies needed for the reproducible prediction workflow.
```

The current repository contains two dashboard routes:

```text
http://127.0.0.1:8000/predictionDashboard/
http://127.0.0.1:8000/clusterDashboard/
```



# I. Prediction Dashboard

The Prediction Dashboard is a decision-support prototype for non-technical police planning stakeholders. It does not make automatic deployment decisions. It gives planners a readable map and review list showing which local areas may deserve attention first.

The current prediction workflow is:

1. Use official police.uk recorded crime files.
2. Add severity weights from the Crime Severity Score source file.
3. Build a LAD-level prediction model using crime, education, income, homelessness and deprivation-related variables.
4. Disaggregate the predicted LAD crime count to LSOAs using local LSOA context weights.
5. Classify LSOAs into three planning tiers:
   - `Priority Patrol`
   - `Risk Addressing Patrol`
   - `Standard Patrol`
6. Export the result into a JavaScript data file used by the Django dashboard.



## Running the Prediction Dashboard

From the repository root, install the required Python packages:

```powershell
py -m pip install -r requirements.txt
```

Then start the Django server:

```powershell
cd "Django Dashboard Folder\DashboardHTML\bin\PyDash"
py .\manage.py runserver
```

Open the prediction dashboard at:

```text
http://127.0.0.1:8000/predictionDashboard/
```

If `py` is not available on your system, use:

```powershell
python .\manage.py runserver
```

The dashboard uses Leaflet with CARTO/OpenStreetMap basemap tiles, so an internet connection is required for the map background.



## Reproducing the Prediction Dashboard Data

The repository includes the generated prediction dashboard data, so the dashboard can be opened directly. To reproduce the analysis from source data, follow the steps below.

### 1. Install Python dependencies

From the repository root:

```powershell
py -m pip install -r requirements.txt
```

The data scripts need `pandas`, `numpy`, `scikit-learn`, `openpyxl`, `xlrd` and `odfpy`. Django is needed to serve the dashboard.

### 2. Add the external data files

Most model input files are already included under:

```text
Dashboard Data Creation Folder/data/ModelData/
```

Two data sources are too large or unsuitable to keep directly in GitHub and must be downloaded manually:

#### A. police.uk recorded crime CSV files

Download the police.uk open data files from:

```text
https://data.police.uk/data/
```

Use the following download settings:

```text
Date range: January 2024 to December 2025
Forces: All forces
```

Extract the downloaded files and place the crime CSV files anywhere under:

```text
Dashboard Data Creation Folder/data/CrimeData/
```

Subfolders are accepted because the scripts search recursively:

```text
Dashboard Data Creation Folder/data/CrimeData/
  2024-01/
    2024-01-west-midlands-street.csv
    ...
  2024-02/
    2024-02-west-midlands-street.csv
    ...
```

The required columns are:

```text
Month, Longitude, Latitude, LSOA code, LSOA name, Crime type
```

#### B. LSOA to LAD lookup

Download the LSOA to LAD lookup file from the ONS Geoportal page:

```text
https://geoportal.statistics.gov.uk/datasets/c01336febabe4c76ac14fbe71dbb99e1/about
```

Place the downloaded CSV here, with this exact filename:

```text
Dashboard Data Creation Folder/data/ModelData/LSOALAD.csv
```

The code expects at least these two columns:

```text
lsoa21cd, ladcd
```

### 3. Generate the severity weights

Run the script from the repository root:

```powershell
py "Dashboard Data Creation Folder\crimeseverityscore.py"
```

This reads:

```text
Dashboard Data Creation Folder/data/ModelData/crimeseverityscore.xls
```

and writes:

```text
Dashboard Data Creation Folder/data/severityWeights.csv
```

The script maps Crime Severity Score categories to police.uk crime categories, then rescales them to a readable 1 to 5 severity scale.

### 4. Run the prediction model

Run the script from the repository root:

```powershell
py "Dashboard Data Creation Folder\officialmodelfinal.py"
```

This writes:

```text
Dashboard Data Creation Folder/data/officialModel2026LSOAPredictions.csv
```

The model is a LAD-level linear regression. It predicts crime rate using:

- persistent school absence
- mean income
- crime-related deprivation rank
- homelessness rate

The predicted LAD crime count is then distributed to LSOAs. The LSOA share is based on a mean of four normalized local weights:

- LSOA crime rank
- LSOA income rank
- LSOA health deprivation and disability rank
- population density

This step combines the crime history with selected social context variables.

### 5. Build the dashboard data file

Run the script from the repository root:

```powershell
py "Dashboard Data Creation Folder\dashboardData.py"
```

This reads:

```text
Dashboard Data Creation Folder/data/CrimeData/
Dashboard Data Creation Folder/data/PopulationDeprivationIndex.csv
Dashboard Data Creation Folder/data/officialModel2026LSOAPredictions.csv
Dashboard Data Creation Folder/data/severityWeights.csv
```

and writes:

```text
Dashboard Data Creation Folder/output/dashboardForecast.csv
Django Dashboard Folder/DashboardHTML/bin/PyDash/predictionDashboard/static/prediction/data/dashboardData.js
```

The dashboard tiers are assigned from the predicted LSOA crime count:

- top 10 percent: `Priority Patrol`
- 75th to 90th percentile: `Risk Addressing Patrol`
- below 75th percentile: `Standard Patrol`

The dashboard also shows recent serious-crime share and deprivation context. However, those are used for interpretation rather than automatic deployment.

### 6. Run the dashboard

```powershell
cd "Django Dashboard Folder\DashboardHTML\bin\PyDash"
py .\manage.py runserver
```

Then open:

```text
http://127.0.0.1:8000/predictionDashboard/
```



## Notes on Scope

- The prediction dashboard is designed for planning review, not automatic enforcement or deployment.
- Reproduced outputs can vary if different police.uk months or force files are used.
- Some areas may be excluded from the final dashboard data if they cannot be matched to the required context files.



## Common problems

If a package is missing: `ModuleNotFoundError: openpyxl`, `xlrd` or `odf`. Run from the repository root:

```powershell
py -m pip install -r requirements.txt
```

If `LSOALAD.csv` is missing, download it from the ONS Geoportal link above and place it in:

```text
Dashboard Data Creation Folder/data/ModelData/LSOALAD.csv
```

If no police.uk files are found, check that extracted CSV files are inside:

```text
Dashboard Data Creation Folder/data/CrimeData/
```

If the dashboard opens but the map background does not load, check the internet connection.



# II. Cluster Dashboard



