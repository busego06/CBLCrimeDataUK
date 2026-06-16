# Model input data

This folder contains the smaller input files used by the prediction pipeline.

One file is not included:

```text
LSOALAD.csv
```

Download it from the ONS Geoportal page:

```text
https://geoportal.statistics.gov.uk/datasets/c01336febabe4c76ac14fbe71dbb99e1/about
```

Then place it in this folder with the exact filename:

```text
Dashboard Data Creation Folder/data/ModelData/LSOALAD.csv
```

The scripts use the `lsoa21cd` and `ladcd` columns to connect LSOAs to local authority districts.
