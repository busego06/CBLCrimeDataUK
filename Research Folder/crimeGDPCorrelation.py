import pandas as pd
import matplotlib.pyplot as plt
import glob

filesCrime = glob.glob("./SSA2/csv/crimedata/**/*.csv", recursive=True)

dfs = []

for file in filesCrime:
    df = pd.read_csv(file)
    dfs.append(df)

crimeData = pd.concat(dfs, ignore_index=True)

totalCrime = crimeData.groupby("Month").size().reset_index(name="CrimeCount")
totalCrime["Month"] = pd.to_datetime(totalCrime["Month"])

fileGDP = "./csv/economydata/GDPUK.csv"
economyData = pd.read_csv(fileGDP)

economyData["Month"] = pd.to_datetime(economyData["Month/Year"], errors="coerce")
economyData["GDP"] = pd.to_numeric(economyData["GDP"], errors="coerce")

merged = pd.merge(totalCrime, economyData[["Month", "GDP"]], on="Month", how="inner")

merged["Crime_norm"] = (merged["CrimeCount"] - merged["CrimeCount"].mean()) / merged["CrimeCount"].std()
merged["GDP_norm"] = (merged["GDP"] - merged["GDP"].mean()) / merged["GDP"].std()

plt.figure(figsize=(12,6))
plt.plot(merged["Month"], merged["Crime_norm"], label="Crime")
plt.plot(merged["Month"], merged["GDP_norm"], label="GDP")
plt.legend()
plt.grid(True)
plt.title("Crime vs GDP")
plt.tight_layout()
plt.savefig("crime_gdp.png")

print(merged[["CrimeCount", "GDP"]].corr())