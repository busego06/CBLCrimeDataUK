import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import glob
import os

def clean_force(name):
    name = name.lower().strip()
    for word in [" police service", " constabulary", " police"]:
        name = name.replace(word, "")
    name = name.replace("&", "and")
    return name

## INCOME DATA

incomeToPolice = {
    "London": "Metropolitan Police Service",
    "Inner London": "Metropolitan Police Service",
    "Outer London": "Metropolitan Police Service",
    "Greater Manchester Met County": "Greater Manchester Police",
    "Merseyside Met County": "Merseyside Police",
    "West Midlands Met County": "West Midlands Police",
    "West Yorkshire Met County": "West Yorkshire Police",
    "South Yorkshire Met County": "South Yorkshire Police",
    "Tyne and Wear Met County": "Northumbria Police",
    "Cardiff / Caerdydd": "South Wales Police",
    "Swansea / Abertawe": "South Wales Police",
    "Newport / Casnewydd": "Gwent Police",
}

files = glob.glob("./SSA3/csv/economy/income_*.xlsx")

dfs = []

for file in files:
    df = pd.read_excel(file, sheet_name="Full-Time", header=4)
    year = file.split("_")[-1].replace(".xlsx", "")
    df["Year"] = int(year)
    dfs.append(df)

incomeData = pd.concat(dfs, ignore_index=True)
incomeData = incomeData[["Description", "Median", "Year"]]
incomeData = incomeData.rename(columns={"Description": "Region", "Median": "Median Income", "Year": "Year"})
incomeData["Police Force"] = incomeData["Region"].map(incomeToPolice)
incomeData = incomeData.dropna(subset=["Police Force"]).reset_index(drop=True)

incomeByForce = incomeData.groupby("Police Force")["Median Income"].median().reset_index()

## CRIME DATA

filesCrime = glob.glob("./SSA3/csv/crimeecon/**/*.csv", recursive=True)

dfs = []

for file in filesCrime:
    df = pd.read_csv(file)
    dfs.append(df)

crimeData = pd.concat(dfs, ignore_index=True)

crimeData["Month"] = pd.to_datetime(crimeData["Month"])
crimeData = crimeData[["Reported by", "Crime type", "Month"]]
crimeData = crimeData.rename(columns={"Reported by": "Police Force", "Crime type": "Crime type"})

crimeData["Year"] = crimeData["Month"].dt.year
crimeData = crimeData[["Police Force", "Crime type", "Year"]]

crimeByForce = crimeData.groupby("Police Force").size().reset_index(name="Crime Count")

## POPULATION DATA

populationData = pd.read_excel("./SSA3/csv/population2024.xlsx", sheet_name="Mid-2021 to Mid-2024", header=3)

populationData = populationData[populationData["Year"] == 2024]

pop_cols = [col for col in populationData.columns if col.startswith("M") or col.startswith("F")]

populationData["Total Population"] = populationData[pop_cols].sum(axis=1)

populationData = populationData[["PFA 2023 Name", "Total Population"]].reset_index(drop=True)

populationData = populationData.rename(columns={"PFA 2023 Name": "Police Force", "Total Population": "Total Population"})

crimeByForce["Police Force"] = crimeByForce["Police Force"].str.lower().str.strip()
incomeByForce["Police Force"] = incomeByForce["Police Force"].str.lower().str.strip()
populationData["Police Force"] = populationData["Police Force"].str.lower().str.strip()

forceMap = {
    "avon and somerset constabulary": "avon and somerset",
    "bedfordshire police": "bedfordshire",
    "cambridgeshire constabulary": "cambridgeshire",
    "cheshire constabulary": "cheshire",
    "cleveland police": "cleveland",
    "cumbria constabulary": "cumbria",
    "derbyshire constabulary": "derbyshire",
    "devon & cornwall police": "devon & cornwall",
    "dorset police": "dorset",
    "durham constabulary": "durham",
    "essex police": "essex",
    "gloucestershire constabulary": "gloucestershire",
    "gwent police": "gwent",
    "hampshire constabulary": "hampshire",
    "hertfordshire constabulary": "hertfordshire",
    "humberside police": "humberside",
    "kent police": "kent",
    "lancashire constabulary": "lancashire",
    "leicestershire police": "leicestershire",
    "lincolnshire police": "lincolnshire",
    "merseyside police": "merseyside",
    "metropolitan police service": "metropolitan",
    "norfolk constabulary": "norfolk",
    "north wales police": "north wales",
    "north yorkshire police": "north yorkshire",
    "northamptonshire police": "northamptonshire",
    "northumbria police": "northumbria",
    "nottinghamshire police": "nottinghamshire",
    "south wales police": "south wales",
    "south yorkshire police": "south yorkshire",
    "staffordshire police": "staffordshire",
    "suffolk constabulary": "suffolk",
    "surrey police": "surrey",
    "sussex police": "sussex",
    "thames valley police": "thames valley",
    "warwickshire police": "warwickshire",
    "west mercia police": "west mercia",
    "west midlands police": "west midlands",
    "west yorkshire police": "west yorkshire",
    "wiltshire police": "wiltshire"
}

crimeByForce["Police Force"] = crimeByForce["Police Force"].replace(forceMap)

print(crimeByForce)
print(populationData)
print(incomeByForce)

mergedCrime = pd.merge(crimeByForce, populationData, on="Police Force")

mergedCrime["Crime Rate"] = (mergedCrime["Crime Count"] / mergedCrime["Total Population"]) * 100000

mergedCrime["Police Force"] = mergedCrime["Police Force"].apply(standardise)
incomeByForce["Police Force"] = incomeByForce["Police Force"].apply(standardise)

final = pd.merge(mergedCrime, incomeByForce, on="Police Force", how="inner")

final["Median Income"] = (
    final["Median Income"]
    .astype(str)
    .str.replace(",", "")
    .str.replace("£", "")
)

final["Median Income"] = pd.to_numeric(final["Median Income"], errors="coerce")

final["Crime Rate"] = pd.to_numeric(final["Crime Rate"], errors="coerce")
x = final["Median Income"].values
y = final["Crime Rate"].values

coeffs = np.polyfit(x, y, deg=2)
poly = np.poly1d(coeffs)

x_sorted = np.sort(x)

plt.figure(figsize=(10,6))
plt.scatter(x, y, alpha=0.7)
plt.plot(x_sorted, poly(x_sorted), color="red")

plt.title("Polynomial Fit (Degree 2): Crime Rate vs Income")
plt.xlabel("Median Income")
plt.ylabel("Crime Rate")
plt.savefig("./SSA3/degree2.png")