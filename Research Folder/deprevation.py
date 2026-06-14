import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import glob
from scipy import stats

## DEPREVATION

depFile = "./SSA5/csv/deprevation.xlsx"

imdData = pd.read_excel(depFile, sheet_name="IoD2025 Domains")

imdData.rename(columns={
    "Index of Multiple Deprivation (IMD) Rank (where 1 is most deprived)": "Index of Multiple Deprivation (IMD) Rank", 
    "Income Rank (where 1 is most deprived)": "Income Rank",
    "Employment Rank (where 1 is most deprived)": "Employment Rank",
    "Education, Skills and Training Rank (where 1 is most deprived)": "Education, Skills and Training Rank",
    "Health Deprivation and Disability Rank (where 1 is most deprived)": "Health Deprivation and Disability Rank"
}, inplace=True)

imdByLAD = imdData.groupby("Local Authority District code (2024)").agg(
    IMD = ("Index of Multiple Deprivation (IMD) Rank", "median"),
    Income = ("Income Rank", "median"),
    Employment = ("Employment Rank", "median"),
    Education = ("Education, Skills and Training Rank", "median"),
    Health = ("Health Deprivation and Disability Rank", "median")
).reset_index()

imdByLAD.rename(columns={"Local Authority District code (2024)": "LAD"}, inplace=True)

imdByLAD["IMD"] = pd.to_numeric(imdByLAD["IMD"], errors="coerce")

imdByLAD["Income"] = pd.to_numeric(imdByLAD["Income"], errors="coerce")

imdByLAD["Employment"] = pd.to_numeric(imdByLAD["Employment"], errors="coerce")

imdByLAD["Education"] = pd.to_numeric(imdByLAD["Education"], errors="coerce")

imdByLAD["Health"] = pd.to_numeric(imdByLAD["Health"], errors="coerce")

## CRIME

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

## MERGE

merge = pd.merge(mergedCrime, imdByLAD, on=["LAD"], how="left")

merge = merge.dropna()

variables = ["IMD", "Income", "Employment", "Education", "Health"]
labels = ["IMD Rank", "Income Rank", "Employment Rank", "Education Rank", "Health Rank"]

print("=" * 60)
print(f"{'Variable':<20} {'Year':<6} {'r':>6} {'p':>10} {'Verdict'}")
print("=" * 60)

for var, label in zip(variables, labels):
    for year in [2024, 2025]:
        data = merge[merge["Year"] == year].dropna(subset=[var, "Crime Rate"])
        r, p = stats.pearsonr(data[var], data["Crime Rate"])
        print(f"{label:<20} {year:<6} {r:>6.3f} {p:>10.4f}")

fig, axes = plt.subplots(len(variables), 2, figsize=(16, 5 * len(variables)))

for row, (var, label) in enumerate(zip(variables, labels)):
    for col, year in enumerate([2024, 2025]):
        ax = axes[row][col]
        data = merge[merge["Year"] == year].dropna(subset=[var, "Crime Rate"])

        x = data[var].values
        y = data["Crime Rate"].values
        r, p = stats.pearsonr(x, y)

        ax.scatter(x, y, alpha=0.5, s=20, color="blue" if year == 2024 else "orange")
        m, b = np.polyfit(x, y, 1)
        ax.plot(np.sort(x), m * np.sort(x) + b, color="black", linewidth=1.5)

        ax.set_title(f"{label} vs Crime Rate ({year})")
        ax.set_xlabel(label)
        ax.set_ylabel("Crime Rate")
        ax.annotate(
            f"r = {r:.3f}   p = {p:.4f}\n",
            xy=(0.05, 0.90), xycoords="axes fraction",
            fontsize=10,
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="gray", alpha=0.8)
        )

plt.tight_layout()
plt.savefig("./SSA5/imd_correlation.png")