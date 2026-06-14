import pandas as pd
import matplotlib.pyplot as plt
import glob

filesCrime = glob.glob("./SSA2/csv/crimedataedu/**/*.csv", recursive=True)

dfs = []
for file in filesCrime:
    df = pd.read_csv(file)

    dfs.append(df)

crimeData = pd.concat(dfs, ignore_index=True)

total_crime = crimeData.groupby("Month").size().reset_index(name="Count")

plt.figure(figsize=(12,6))

plt.plot(total_crime["Month"], total_crime["Count"])

plt.title("Total Crime Over Time")
plt.xlabel("Month")
plt.ylabel("Number of Crimes")
plt.grid(True)

plt.tight_layout()
plt.savefig("eduCrimeData.png")