import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import glob
from scipy import stats

## INCOME DATA

econFile = "./SSA4/csv/MSOAecon.xlsx"

incomeData = pd.read_excel(econFile, header=0)

incomeData = incomeData[["AREACD", "Disposable (net) annual income before housing costs (£ thousands)"]]
incomeData = incomeData.rename(columns={"AREACD": "MSOA", "Disposable (net) annual income before housing costs (£ thousands)": "Annual Income"}).reset_index(drop=True)

## CRIME DATA

filesCrime = glob.glob("./SSA4/csv/crime2023/**/*.csv", recursive=True)

dfs = []

for file in filesCrime:
    df = pd.read_csv(file)
    dfs.append(df)

crimeData = pd.concat(dfs, ignore_index=True)

crimeData = crimeData[["LSOA code", "Crime type"]]
crimeData = crimeData.rename(columns={"LSOA code": "LSOA", "Crime type": "Crime type"})

crimeByLSOA = crimeData.groupby(["LSOA"]).size().reset_index(name="Crime Count")

lsoalad = pd.read_csv("./SSA4/csv/LSOALAD.csv", low_memory=False)
lsoalad = lsoalad[["lsoa21cd", "msoa21cd"]].drop_duplicates()

crimeByMSOA = crimeByLSOA.merge(lsoalad, left_on="LSOA", right_on="lsoa21cd")
crimeByMSOA = crimeByMSOA.groupby(["msoa21cd"])["Crime Count"].sum().reset_index()
crimeByMSOA = crimeByMSOA.rename(columns={"msoa21cd": "MSOA", "Crime Count": "Crime Count"})

## POPULATION DATA

populationData = pd.read_excel("./SSA4/csv/sapemsoaquinaryage20222024.xlsx", sheet_name="Mid-2024 MSOA 2021", header=3)

populationData = populationData[["MSOA 2021 Code", "Total"]]

populationData = populationData.rename(columns={"MSOA 2021 Code": "MSOA", "Total": "Total Population"})

mergedCrime = pd.merge(crimeByMSOA, populationData, on="MSOA")

mergedCrime["Crime Rate"] = (mergedCrime["Crime Count"] / mergedCrime["Total Population"]) * 100000

final = pd.merge(mergedCrime, incomeData, on=["MSOA"], how="inner")

final["Annual Income"] = pd.to_numeric(final["Annual Income"], errors="coerce")

final["Crime Rate"] = pd.to_numeric(final["Crime Rate"], errors="coerce")

final = final[final["Annual Income"] <= 90]

final = final[(final["Crime Rate"] > 1000) & (final["Crime Rate"] <= 80000)]

x = final["Annual Income"]
y = final["Crime Rate"]

# clean
mask = np.isfinite(x) & np.isfinite(y)
x, y = x[mask], y[mask]

# fit
coeffs = np.polyfit(x, y, deg=2)
poly = np.poly1d(coeffs)

r, p = stats.pearsonr(x, y)

def conclusion(r, p):
    return "keep" if (abs(r) >= 0.15 and p < 0.05) else "drop"

print(f"Pearson r: {r:.3f}, R²: {r**2:.3f}, p: {p:.4f} → {conclusion(r, p)}")

plt.figure(figsize=(10,6))
plt.scatter(x, y, alpha=0.7, label="2023", color="blue")
plt.plot(np.sort(x), poly(np.sort(x)), color="red")

plt.title("Crime Rate vs Income IQR")
plt.xlabel("Annual Income")
plt.ylabel("Crime Rate")
plt.legend()
plt.savefig("./SSA4/quadAnnualIncome.png")