import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import glob


filesCrime = glob.glob("./SSA3/csv/wembley25/**/*.csv", recursive=True)

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

total_crime = crimeData.groupby("Month").size().reset_index(name="Count")

plt.figure(figsize=(12,6))

plt.plot(total_crime["Month"], total_crime["Count"])

plt.axvspan(pd.to_datetime("2025-08-21"),
            pd.to_datetime("2025-09-8"),
            alpha=0.3)


plt.title("Crime Trends Around Wembley Stadium in 2025")
plt.xlabel("Month")
plt.ylabel("Crime Count")

plt.gca().xaxis.set_major_locator(mdates.MonthLocator(interval=1))
plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))

plt.xticks(rotation=45)

plt.grid(True)

plt.savefig("./SSA3/ColdplayConcertCrimeMetropolitan.png")