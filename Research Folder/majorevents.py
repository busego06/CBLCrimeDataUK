import pandas as pd
import matplotlib.pyplot as plt
import glob

filesCrime = glob.glob("./SSA5/csv/majorevents/**/*.csv", recursive=True)

dfs = []
for file in filesCrime:
    df = pd.read_csv(file)

    dfs.append(df)

crimeData = pd.concat(dfs, ignore_index=True)

crimeData["Month"] = pd.to_datetime(crimeData["Month"])

crimeData = crimeData[crimeData["Location"].str.contains(
    "Olympic Way|Engineers Way|South Way|Wembley|Empire Way|Fulton Road|High Road|Harrow Road",
    na=False
)]

crimeData = crimeData[crimeData["Crime type"] != "Criminal damage and arson"]

total_crime = crimeData.groupby("Month").size().reset_index(name="Count")

plt.plot(total_crime["Month"], total_crime["Count"])

pythonfig, ax = plt.subplots(figsize=(12, 6))

colors = {2023: "blue", 2024: "orange", 2025: "green"}

crimeData["Year"] = crimeData["Month"].dt.year
crimeData["MonthNum"] = crimeData["Month"].dt.month

crimeData = crimeData[crimeData["Year"].isin([2023, 2024, 2025])]

for year, group in crimeData.groupby("Year"):
    monthly = group.groupby("MonthNum").size().reset_index(name="Count")
    ax.plot(monthly["MonthNum"], monthly["Count"], 
            label=str(year), color=colors.get(year), marker="o")

# highlight June
ax.axvspan(5.5, 6.5, alpha=0.1, color="red", label="June")

ax.set_xticks(range(1, 13))
ax.set_xticklabels(["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"])
ax.set_title("Crime Trends Around Wembley Stadium 2023–2025")
ax.set_xlabel("Month")
ax.set_ylabel("Crime Count")
ax.legend()
ax.grid(True)

plt.tight_layout()
plt.savefig("./SSA5/TSConcertCrimeWembley.png")