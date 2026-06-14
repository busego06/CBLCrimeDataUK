import pandas as pd
import matplotlib.pyplot as plt

fileEducation = "./SSA2/csv/edudata/persistentabsence.csv"

eduData = pd.read_csv(fileEducation)

eduData["persistent_absence_percent"] = pd.to_numeric(eduData["persistent_absence_percent"],errors="coerce")

londonEduData = eduData[(eduData["education_phase"] == "Secondary")]

londonEduData = londonEduData.groupby(["time_period", "time_identifier"])["persistent_absence_percent"].median().reset_index()
print(londonEduData.head(10))
ax = plt.plot(londonEduData["persistent_absence_percent"])

plt.title("Median Percentages of Persistent Absences in UK Schools Over Time")
plt.xlabel("School Weeks")
plt.ylabel("Median Percentage of Persistent Absences")
plt.grid(True)
plt.xticks(range(0,19,2))
plt.tight_layout()
plt.savefig("AbsenceOverTime.png")