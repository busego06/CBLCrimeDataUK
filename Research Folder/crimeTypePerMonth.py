import pandas as pd
import matplotlib.pyplot as plt
import glob

filesCrime = glob.glob("./SSA2/csv/crimedata/**/*.csv", recursive=True)
fileGDP = "./SSA2/csv/economydata/GDPUK.csv"
fileEducation = "./SSA2/csv/"


dfs = []
for file in filesCrime:
    df = pd.read_csv(file)

    dfs.append(df)

crimeData = pd.concat(dfs, ignore_index=True)

crimeData["Crime type"] = crimeData["Crime type"].astype(str)

crimeTrend = crimeData.groupby(["Month", "Crime type"]).size().reset_index(name="Count")

plt.figure(figsize=(14, 6))

for crime in crimeTrend["Crime type"].unique():
    subset = crimeTrend[crimeTrend["Crime type"] == crime]
    
    plt.plot(
        subset["Month"],
        subset["Count"],
        label=crime,
        alpha=0.7
    )

plt.title("Crime Type Trends Over Time")
plt.xlabel("Month")
plt.ylabel("Number of Crimes")
plt.grid(True)
plt.legend(bbox_to_anchor=(1.05, 1), loc="upper left")

plt.tight_layout()

plt.savefig("crimeTrends.png")