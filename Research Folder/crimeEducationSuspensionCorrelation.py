import pandas as pd
import matplotlib.pyplot as plt

fileEducation = "./SSA2/csv/edudata/suspensiondata.csv"

eduData = pd.read_csv(fileEducation)

nationalEduData = eduData[eduData["geographic_level"] == "National"].reset_index(drop=True)

ax = plt.plot(nationalEduData["susp_rate"].head(6))

plt.title("Rate of Suspension in UK Schools Over Time")
plt.xlabel("Academic Years")
plt.ylabel("Rate of Suspension")
plt.grid(True)
plt.tight_layout()
plt.savefig("SuspensionOverTime.png")