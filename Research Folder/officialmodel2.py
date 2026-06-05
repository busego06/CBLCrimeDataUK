import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import glob
import os
from scipy import stats
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score
import sys

## POPULATION DENSITY

densityFile = "./SSA7/csv/density.xlsx"

density = pd.read_excel(densityFile, sheet_name="Mid-2022 to mid-2024 LSOA", header=3)

density = density[["LSOA 2021 Code", "Mid-2024: People per Sq Km"]].rename(columns={
    "LSOA 2021 Code": "LSOA",
    "Mid-2024: People per Sq Km": "Population Density"
})


## HOMELESSNESS

homelessFile = "./SSA7/csv/homesless.ods"

homeless = pd.read_excel(homelessFile, engine="odf", sheet_name="A1", header=4)

homelessClean = homeless[["Unnamed: 0", "Households assessed as homelessper (000s)"]]
homelessClean.rename(columns={
    "Unnamed: 0": "LAD",
    "Households assessed as homelessper (000s)": "Homeless Rate"
}, inplace=True)

homelessClean["Homeless Rate"] = pd.to_numeric(homelessClean["Homeless Rate"], errors="coerce")
homelessClean.dropna(inplace=True)

## DEPREVATION

depFile = "./SSA5/csv/deprevation.xlsx"

imdData = pd.read_excel(depFile, sheet_name="IoD2025 Domains")

imdData.rename(columns={
    "Index of Multiple Deprivation (IMD) Rank (where 1 is most deprived)": "Index of Multiple Deprivation (IMD) Rank", 
    "Income Rank (where 1 is most deprived)": "Income Rank",
    "Employment Rank (where 1 is most deprived)": "Employment Rank",
    "Education, Skills and Training Rank (where 1 is most deprived)": "Education, Skills and Training Rank",
    "Health Deprivation and Disability Rank (where 1 is most deprived)": "Health Deprivation and Disability Rank",
    "Crime Rank (where 1 is most deprived)" : "Crime Rank"
}, inplace=True)

imdByLAD = imdData.groupby("Local Authority District code (2024)").agg(
    IMD = ("Index of Multiple Deprivation (IMD) Rank", "median"),
    Income = ("Income Rank", "median"),
    Employment = ("Employment Rank", "median"),
    Education = ("Education, Skills and Training Rank", "median"),
    Health = ("Health Deprivation and Disability Rank", "median"),
    Crime = ("Crime Rank", 'median')
).reset_index()

imdByLAD.rename(columns={"Local Authority District code (2024)": "LAD"}, inplace=True)

imdByLAD["IMD"] = pd.to_numeric(imdByLAD["IMD"], errors="coerce")
imdByLAD["Income"] = pd.to_numeric(imdByLAD["Income"], errors="coerce")
imdByLAD["Employment"] = pd.to_numeric(imdByLAD["Employment"], errors="coerce")
imdByLAD["Education"] = pd.to_numeric(imdByLAD["Education"], errors="coerce")
imdByLAD["Health"] = pd.to_numeric(imdByLAD["Health"], errors="coerce")
imdByLAD["Crime"] = pd.to_numeric(imdByLAD["Crime"], errors="coerce")

## INCOME DATA

files = glob.glob("./SSA4/csv/economy/income_*.xlsx")

dfs = []

for file in files:
    df = pd.read_excel(file, sheet_name="Full-Time", header=4)
    year = file.split("_")[-1].replace(".xlsx", "")
    df["Year"] = int(year)
    dfs.append(df)

incomeData = pd.concat(dfs, ignore_index=True)

incomeData = incomeData[["Code", "Median", "Mean", 25, 75, "Year"]]
incomeData = incomeData.rename(columns={"Code": "LAD", "Median": "Median Income", 25: "Q1", 75: "Q3", "Year": "Year"}).reset_index(drop=True)

incomeData["Q1"] = pd.to_numeric(incomeData["Q1"].astype(str).str.replace(",", "").str.replace("£", ""), errors="coerce")
incomeData["Q3"] = pd.to_numeric(incomeData["Q3"].astype(str).str.replace(",", "").str.replace("£", ""), errors="coerce")
incomeData["IQR"] = incomeData["Q3"] - incomeData["Q1"]

## CRIME DATA

filesCrime = glob.glob("./SSA4/csv/crimeecon/**/*.csv", recursive=True)

dfs = []

for file in filesCrime:
    df = pd.read_csv(file)
    dfs.append(df)

crimeData = pd.concat(dfs, ignore_index=True)

crimeData["Month"] = pd.to_datetime(crimeData["Month"])
crimeData = crimeData[["LSOA code", "Crime type", "Month"]]
crimeData = crimeData.rename(columns={"LSOA code": "LSOA", "Crime type": "Crime type"})

crimeData["Year"] = crimeData["Month"].dt.year
crimeData = crimeData[["LSOA", "Crime type", "Year"]]

crimeByLSOA = crimeData.groupby(["LSOA", "Year"]).size().reset_index(name="Crime Count")

lsoalad = pd.read_csv("./SSA4/csv/LSOALAD.csv", low_memory=False)
lsoalad = lsoalad[["lsoa21cd", "ladcd"]].drop_duplicates()

crimeByLAD = crimeByLSOA.merge(lsoalad, left_on="LSOA", right_on="lsoa21cd")
crimeByLAD = crimeByLAD.groupby(["ladcd", "Year"])["Crime Count"].sum().reset_index()
crimeByLAD = crimeByLAD.rename(columns={"ladcd": "LAD", "Crime Count": "Crime Count", "Year": 'Year'})

## POPULATION DATA

populationData = pd.read_excel("./SSA4/csv/sapemsoaquinaryage20222024.xlsx", sheet_name="Mid-2024 MSOA 2021", header=3)

populationLADData = populationData.groupby("LAD 2023 Code")["Total"].sum().reset_index()

populationLADData = populationLADData[["LAD 2023 Code", "Total"]]

populationLADData = populationLADData.rename(columns={"LAD 2023 Code": "LAD", "Total": "Total Population"})

mergedCrime = pd.merge(crimeByLAD, populationLADData, on="LAD")

mergedCrime["Crime Rate"] = (mergedCrime["Crime Count"] / mergedCrime["Total Population"]) * 100000

fileEducation = "./SSA2/csv/edudata/persistentabsence.csv"
eduData = pd.read_csv(fileEducation)

eduData = eduData[(eduData["education_phase"] == "Secondary")]

eduData = eduData[eduData["time_identifier"].str.match(r"Week \d+", na=False)].copy()

eduData["week_num"] = eduData["time_identifier"].str.extract(r"(\d+)").astype(int)

eduData["academic_year_start"] = eduData["time_period"].astype(int) - 1

eduData["sep1"] = pd.to_datetime(eduData["academic_year_start"].astype(str) + "-09-01")
eduData["first_monday"] = eduData["sep1"] + pd.to_timedelta((7 - eduData["sep1"].dt.dayofweek) % 7, unit="D")

eduData["date"]       = eduData["first_monday"] + pd.to_timedelta((eduData["week_num"] - 1) * 7, unit="D")
eduData["month"]      = eduData["date"].dt.month
eduData["year"]       = eduData["date"].dt.year
eduData["month_name"] = eduData["date"].dt.strftime("%B")

eduData["persistent_absence_percent"] = pd.to_numeric(eduData["persistent_absence_percent"], errors="coerce")

absenceData = eduData.groupby(["new_la_code", "year"])["persistent_absence_percent"].mean().reset_index()
absenceData.rename(columns={"new_la_code": "LAD", "year": "Year"}, inplace=True)

crimeAndIQR = pd.merge(mergedCrime, incomeData, on=["LAD", "Year"], how="inner")
crimeAndIQR = crimeAndIQR.dropna()

crimeAndIQR["IQR"] = pd.to_numeric(crimeAndIQR["IQR"], errors="coerce")
crimeAndIQR["Median Income"] = pd.to_numeric(crimeAndIQR["Median Income"], errors="coerce")
crimeAndIQR["Mean"] = pd.to_numeric(crimeAndIQR["Mean"], errors="coerce")
crimeAndIQR["Crime Rate"] = pd.to_numeric(crimeAndIQR["Crime Rate"], errors="coerce")

crimeIQRAbsence = crimeAndIQR.merge(absenceData, on=["LAD", "Year"], how="left")
crimeIQRAbsence = crimeIQRAbsence.dropna(subset=["persistent_absence_percent"])

crimeIQRAbsenceHomeless = crimeIQRAbsence.merge(homelessClean, on=["LAD"], how="left")

merged = crimeIQRAbsenceHomeless.merge(imdByLAD, on=["LAD"], how="left")
merged = merged[merged["Crime Rate"] >= 1000]


## LAD REGRESSION MODEL

variables = ["persistent_absence_percent", "Mean", "Crime", "Homeless Rate"]
labels = ["Persistent Absence (%)", "Mean Income", "Crime Rank", "Homeless Rate"]

models = {}

for year in [2024, 2025]:
    data = merged[merged["Year"] == year].dropna(subset=variables + ["Crime Rate"])
    X = data[variables].values
    y = data["Crime Rate"].values
    model = LinearRegression().fit(X, y)
    models[year] = model
    r2 = model.score(X, y)
    print(f"\n{year} — R²: {r2:.3f}")
    for var, coef in zip(variables, model.coef_):
        print(f"  {var:<35} coef: {coef:.4f}")
    print(f"  Intercept: {model.intercept_:.2f}")

# LOG MODEL
merged["Log Crime Rate"] = np.log(merged["Crime Rate"])

log_models = {}

for year in [2024, 2025]:
    data = merged[merged["Year"] == year].dropna(subset=variables + ["Log Crime Rate"])
    X = data[variables].values
    y = data["Log Crime Rate"].values
    log_model = LinearRegression().fit(X, y)
    log_models[year] = log_model
    r2 = log_model.score(X, y)
    print(f"\n{year} — Log Model R²: {r2:.3f}")
    for var, coef in zip(variables, log_model.coef_):
        print(f"  {var:<35} coef: {coef:.6f}")
    print(f"  Intercept: {log_model.intercept_:.4f}")

## ACTUAL VS PREDICTED (LAD LEVEL)

for year in [2024, 2025]:
    data = merged[merged["Year"] == year].dropna(subset=variables + ["Crime Rate"]).copy()
    data["Predicted Crime Rate"] = models[year].predict(data[variables].values)
    data["Residual"] = data["Crime Rate"] - data["Predicted Crime Rate"]

    plt.figure(figsize=(8, 6))
    plt.scatter(data["Crime Rate"], data["Predicted Crime Rate"], alpha=0.5, s=20)
    plt.plot([data["Crime Rate"].min(), data["Crime Rate"].max()],
             [data["Crime Rate"].min(), data["Crime Rate"].max()],
             color="red", linewidth=1.5, linestyle="--", label="Perfect prediction")
    plt.xlabel("Actual Crime Rate")
    plt.ylabel("Predicted Crime Rate")
    plt.title(f"Actual vs Predicted Crime Rate ({year})")
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"./SSA7/actual_vs_predicted_{year}.png")

## LSOA DISAGGREGATION

lsoaIMD = imdData[[
    "LSOA code (2021)",
    "Local Authority District code (2024)",
    "Crime Rank",
    "Income Rank",
    "Health Deprivation and Disability Rank"
]].copy()

lsoaIMD.rename(columns={
    "LSOA code (2021)": "LSOA",
    "Local Authority District code (2024)": "LAD",
    "Crime Rank": "LSOA Crime Rank",
    "Income Rank": "LSOA Income Rank",
    "Health Deprivation and Disability Rank": "LSOA Health Deprivation and Disability Rank"
}, inplace=True)

lsoaIMD = lsoaIMD.merge(density, on="LSOA", how="left")

lsoaIMD["LSOA Crime Rank"] = pd.to_numeric(lsoaIMD["LSOA Crime Rank"], errors="coerce")
lsoaIMD["LSOA Income Rank"] = pd.to_numeric(lsoaIMD["LSOA Income Rank"], errors="coerce")
lsoaIMD["LSOA Health Deprivation and Disability Rank"] = pd.to_numeric(lsoaIMD["LSOA Health Deprivation and Disability Rank"], errors="coerce")
lsoaIMD["Population Density"] = pd.to_numeric(lsoaIMD["Population Density"], errors="coerce")
lsoaIMD = lsoaIMD.dropna(subset=["LSOA Crime Rank", "LSOA Income Rank", "LSOA Health Deprivation and Disability Rank", "Population Density"])

n = len(lsoaIMD)

lsoaIMD["Crime Weight"]    = 1 - (lsoaIMD["LSOA Crime Rank"] / n)
lsoaIMD["Income Weight"]   = 1 - (lsoaIMD["LSOA Income Rank"] / n)
lsoaIMD["Health Deprivation and Disability Weight"] = 1 - (lsoaIMD["LSOA Health Deprivation and Disability Rank"] / n)
lsoaIMD["Density Weight"]  = lsoaIMD["Population Density"] / lsoaIMD["Population Density"].max()

weight_cols = ["Crime Weight", "Income Weight", "Health Deprivation and Disability Weight", "Density Weight"]

lsoaIMD["Weight"] = lsoaIMD[weight_cols].mean(axis=1)

lad_weight_total = lsoaIMD.groupby("LAD")["Weight"].sum().reset_index()
lad_weight_total.rename(columns={"Weight": "LAD Weight Total"}, inplace=True)
lsoaIMD = lsoaIMD.merge(lad_weight_total, on="LAD")
lsoaIMD["LSOA Share"] = lsoaIMD["Weight"] / lsoaIMD["LAD Weight Total"]

lsoa_results = []

for year in [2024, 2025]:
    data = merged[merged["Year"] == year].dropna(subset=variables + ["Crime Rate", "Total Population"]).copy()
    data["Predicted Crime Rate"]  = models[year].predict(data[variables].values)
    data["Predicted Crime Count"] = data["Predicted Crime Rate"] / 100000 * data["Total Population"]

    lsoa_year = lsoaIMD.merge(
        data[["LAD", "Predicted Crime Count"]],
        on="LAD", how="inner"
    ).copy()

    lsoa_year["Year"] = year
    lsoa_year["LSOA Predicted Count"] = lsoa_year["LSOA Share"] * lsoa_year["Predicted Crime Count"]
    lsoa_results.append(lsoa_year)

lsoaPredicted = pd.concat(lsoa_results, ignore_index=True)

print(lsoaPredicted[["LSOA", "LAD", "Year", "LSOA Share", "LSOA Predicted Count"]].head(10))
lsoaPredicted.to_csv("./SSA7/lsoa_predicted_crime.csv", index=False)