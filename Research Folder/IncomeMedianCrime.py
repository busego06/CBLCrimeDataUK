import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import glob
from scipy import stats

## INCOME DATA

files = glob.glob("./SSA4/csv/economy/income_*.xlsx")

dfs = []

for file in files:
    df = pd.read_excel(file, sheet_name="Full-Time", header=4)
    year = file.split("_")[-1].replace(".xlsx", "")
    df["Year"] = int(year)
    dfs.append(df)

incomeData = pd.concat(dfs, ignore_index=True)
incomeData = incomeData[["Code", "Median", "Year"]]
incomeData = incomeData.rename(columns={"Code": "LAD", "Median": "Median Income", "Year": "Year"}).reset_index(drop=True)

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

print(crimeByLSOA.shape)
print(crimeByLAD.shape)
print(crimeByLAD["Crime Count"].describe())

print("Crime LSOAs:", crimeByLSOA["LSOA"].iloc[:5].values)
print("Lookup LSOAs:", lsoalad["lsoa21cd"].iloc[:5].values)

## POPULATION DATA

populationData = pd.read_excel("./SSA4/csv/sapemsoaquinaryage20222024.xlsx", sheet_name="Mid-2024 MSOA 2021", header=3)

populationLADData = populationData.groupby("LAD 2023 Code")["Total"].sum().reset_index()

populationLADData = populationLADData[["LAD 2023 Code", "Total"]]

populationLADData = populationLADData.rename(columns={"LAD 2023 Code": "LAD", "Total": "Total Population"})

mergedCrime = pd.merge(crimeByLAD, populationLADData, on="LAD")

mergedCrime["Crime Rate"] = (mergedCrime["Crime Count"] / mergedCrime["Total Population"]) * 100000

final = pd.merge(mergedCrime, incomeData, on=["LAD", "Year"], how="inner")

final["Median Income"] = (
    final["Median Income"]
    .astype(str)
    .str.replace(",", "")
    .str.replace("£", "")
)

final["Median Income"] = pd.to_numeric(final["Median Income"], errors="coerce")

final["Crime Rate"] = pd.to_numeric(final["Crime Rate"], errors="coerce")

final2024 = final[final["Year"] == 2024]
final2025 = final[final["Year"] == 2025]

final2024 = final2024[(final2024["Median Income"] <= 50000)]
final2025 = final2025[(final2025["Median Income"] <= 50000)]

final2024 = final2024[(final2024["Crime Rate"] >= 1000) & (final2024["Crime Rate"] <= 40000)]
final2025 = final2025[(final2025["Crime Rate"] >= 1000) & (final2025["Crime Rate"] <= 40000)]

x2024 = final2024["Median Income"].values
y2024 = final2024["Crime Rate"].values
x2025 = final2025["Median Income"].values
y2025 = final2025["Crime Rate"].values

# clean
mask2024 = np.isfinite(x2024) & np.isfinite(y2024)
mask2025 = np.isfinite(x2025) & np.isfinite(y2025)
x2024, y2024 = x2024[mask2024], y2024[mask2024]
x2025, y2025 = x2025[mask2025], y2025[mask2025]

# fit
coeffs2024 = np.polyfit(x2024, y2024, deg=1)
coeffs2025 = np.polyfit(x2025, y2025, deg=1)
poly2024 = np.poly1d(coeffs2024)
poly2025 = np.poly1d(coeffs2025)

r2024, p2024 = stats.pearsonr(x2024, y2024)
r2025, p2025 = stats.pearsonr(x2025, y2025)

def conclusion(r, p):
    return "keep" if (abs(r) >= 0.3 and p < 0.05) else "drop"

print(f"2024 — Pearson r: {r2024:.3f}, R²: {r2024**2:.3f}, p: {p2024:.4f} → {conclusion(r2024, p2024)}")
print(f"2025 — Pearson r: {r2025:.3f}, R²: {r2025**2:.3f}, p: {p2025:.4f} → {conclusion(r2025, p2025)}")

plt.figure(figsize=(10,6))
plt.scatter(x2024, y2024, alpha=0.7, label="2024", color="blue")
plt.scatter(x2025, y2025, alpha=0.7, label="2025", color="orange")
plt.plot(np.sort(x2024), poly2024(np.sort(x2024)), color="blue")
plt.plot(np.sort(x2025), poly2025(np.sort(x2025)), color="orange")

plt.title("Linear Fit: Crime Rate vs Median Income")
plt.xlabel("Median Income")
plt.ylabel("Crime Rate")
plt.legend()
plt.savefig("./SSA4/linearMedian.png")