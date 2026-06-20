# Crime Addressing in the UK

Repository for Group 10's project for **4CBLW020 Addressing real-world crime and security problems with data science**.

## Repository Structure

```text
CBLCrimeDataUK/
  Dashboard Data Creation Folder/
    Contains files used to generate the prediction dashboard data.

  Django Dashboard Folder/
    Django project with everything needed to make the dashboard work.

  Research Folder/
    Data analysis scripts used during the project.

  requirements.txt
    Python dependencies needed for the project to be reproducible.
```

## Requirements

Install required packages through the terminal:

```powershell
py -m pip install -r requirements.txt
```

## Running the Dashboards

Start the Django server:

```powershell
cd "Django Dashboard Folder/DashboardHTML/bin/PyDash"
py .\manage.py runserver
```

If py is not available:

```powershell
python .\manage.py runserver
```

Next go to:
```text
http://127.0.0.1:8000/ -> The home page that links directly to the two dashboards
```

# I. Prediction Dashboard

Dashboard for viewing predicted police demand and LSOA review tiers.

## Running the Prediction Dashboard

From the already open homepage, use the landing page buttons to navigate to the Prediction Dashboard or open:

```text
http://127.0.0.1:8000/predictionDashboard/
```

The dashboard uses Leaflet with CARTO/OpenStreetMap, so an internet connection is required for the map background.

## Reproducing the Prediction Dashboard Data

The repository includes the prediction dashboard data:

```text
CBLCrimeDataUK/Django Dashboard Folder/DashboardHTML/bin/PyDash/predictionDashboard/static/prediction/data/dashboardData.js
```

So the dashboard already shows all the data. To reproduce the analysis from source data, follow the steps below.

### 1. Add the external data files

Most model input files are already included:

```text
Dashboard Data Creation Folder/data/ModelData/
```

Two data sources are too large to keep directly in GitHub and must be downloaded manually. How to download these two sources can be found in:

```text
CBLCrimeDataUK/Dashboard Data Creation Folder/data/CrimeData/README.md
CBLCrimeDataUK/Dashboard Data Creation Folder/data/ModelData/README.md
```

### 2. Generate the severity weights

From the repository root, run:

```powershell
py "Dashboard Data Creation Folder/crimeseverityscore.py"
```

Output:

```text
Dashboard Data Creation Folder/data/severityWeights.csv
```

The script maps Crime Severity Score categories to police.uk crime categories, then normalizes them to a 1 to 5 scale.

### 3. Run the prediction model

From the repository root, run:

```powershell
py "Dashboard Data Creation Folder/officialmodelfinal.py"
```

Output:

```text
Dashboard Data Creation Folder/data/officialModel2026LSOAPredictions.csv
```

### 4. Build the dashboard data file

From the repository root, run:

```powershell
py "Dashboard Data Creation Folder/dashboardData.py"
```

Read:

```text
Dashboard Data Creation Folder/data/CrimeData/
Dashboard Data Creation Folder/data/PopulationDeprivationIndex.csv
Dashboard Data Creation Folder/data/officialModel2026LSOAPredictions.csv
Dashboard Data Creation Folder/data/severityWeights.csv
```

Output:

```text
Dashboard Data Creation Folder/output/dashboardForecast.csv

Django Dashboard Folder/DashboardHTML/bin/PyDash/predictionDashboard/static/prediction/data/dashboardData.js
```

### 5. Reload the dashboard

Reload the webpage (Ctrl + F5) to load the newly generated dashboard data.

# II. Cluster Dashboard

Dashboard for exploring alternative authority clusters and coverage zones.

## Running the Cluster Dashboard

From the Prediction Dashboard, click on the hyperlink on the top right to ope the homepage again and use the landing page buttons to navigate to the Clustering Dashboard or open:

```text
http://127.0.0.1:8000/clusterDashboard/
```

The dashboard uses Leaflet with CARTO/OpenStreetMap, so an internet connection is required for the map background.


# Research Materials

The research files are found in:

```text
Research Folder/
```

To reproduce the research part of the project extract the zip folder and run the scripts from the parent directory of the SSA folders. The outputs will be in each output folder of each SSA. SSA2 is the earliest, SSA7 is the newest.
