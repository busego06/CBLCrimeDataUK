# Model Input Data

This folder contains the smaller input files used by the prediction model.

However, the file which links LSOA's to LAD's is not included and should be downloaded from the ONS Geoportal page:

```text
https://geoportal.statistics.gov.uk/datasets/c01336febabe4c76ac14fbe71dbb99e1/about
```

Then place it in the path with the exact filename:

```text
Dashboard Data Creation Folder/data/ModelData/LSOALAD.csv
```

The python scripts use the `lsoa21cd` and `ladcd` columns to link LSOAs to local authority districts.
