# CBLCrimeDataUK

Course code 4CBLW020

This repository contains data science work for the course project **Addressing real-world crime and security problems with data science**.

Project question:

> How can data-driven estimates of police demand be used to inform the effective organisation and allocation of policing resources in the United Kingdom?

## Current Models

### Police Demand Planning Dashboard

Location:

```text
dashboard/police_demand_allocation_dashboard/
```

This is an interactive decision-support dashboard for non-technical police resource planners. The upgraded version combines the existing police.uk demand model with official GOV.UK English Indices of Deprivation 2025 context data, including population, income, employment and education indicators.

Open the dashboard locally:

```text
dashboard/police_demand_allocation_dashboard/index.html
```



### Initial police demand model

Location:

```text
modeling/initial_demand_model/
```

This folder contains the first reproducible model for estimating police demand from official police.uk crime data. It includes:

- a Python modelling script;
- instructions for downloading the official police.uk input data;
- model evaluation outputs;
- April 2026 LSOA-level priority forecasts;
- figures for presentations and reports;
- a README file explaining the assumptions, results and limitations

Start here:

[modeling/initial_demand_model/README.md](modeling/initial_demand_model/README.md)

## Data note

Raw police.uk ZIP downloads are not committed to this repository. They should be downloaded from the official source and placed locally as described in the model README.
