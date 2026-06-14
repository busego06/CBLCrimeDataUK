import sys
from scipy import stats
import matplotlib.pyplot as plt
import numpy as np

sys.path.append("./SSA7")

exec(open("./SSA7/pyfiles/officialmodel2.py").read())

## 2026 VALIDATION

crimeFiles2026 = glob.glob("./SSA7/csv/test/**/*.csv", recursive=True)

dfs2026 = []
for file in crimeFiles2026:
    df = pd.read_csv(file)
    dfs2026.append(df)

crimeData2026 = pd.concat(dfs2026, ignore_index=True)
crimeData2026["Month"] = pd.to_datetime(crimeData2026["Month"])
crimeData2026 = crimeData2026[["LSOA code", "Crime type", "Month"]]
crimeData2026 = crimeData2026.rename(columns={"LSOA code": "LSOA"})
crimeData2026["Year"] = crimeData2026["Month"].dt.year
crimeData2026 = crimeData2026[crimeData2026["Year"] == 2026]

crimeByLSOA2026 = crimeData2026.groupby(["LSOA"]).size().reset_index(name="Crime Count")

crimeByLAD2026 = crimeByLSOA2026.merge(lsoalad, left_on="LSOA", right_on="lsoa21cd")
crimeByLAD2026 = crimeByLAD2026.groupby("ladcd")["Crime Count"].sum().reset_index()
crimeByLAD2026.rename(columns={"ladcd": "LAD"}, inplace=True)

crimeByLAD2026["Crime Count Annualised"] = crimeByLAD2026["Crime Count"] * 4

crimeByLAD2026 = crimeByLAD2026.merge(populationLADData, on="LAD")
crimeByLAD2026["Crime Rate 2026"] = (crimeByLAD2026["Crime Count Annualised"] / crimeByLAD2026["Total Population"]) * 100000
crimeByLAD2026 = crimeByLAD2026[crimeByLAD2026["Crime Rate 2026"] >= 1000]

data2025 = merged[merged["Year"] == 2025].dropna(subset=variables + ["Crime Rate"]).copy()
data2025["Predicted 2026 Crime Rate"] = models[2025].predict(data2025[variables].values)

validation2026 = data2025[["LAD", "Predicted 2026 Crime Rate"]].merge(
    crimeByLAD2026[["LAD", "Crime Rate 2026"]],
    on="LAD", how="inner"
)

r, p = stats.pearsonr(validation2026["Crime Rate 2026"], validation2026["Predicted 2026 Crime Rate"])
mae  = (validation2026["Crime Rate 2026"] - validation2026["Predicted 2026 Crime Rate"]).abs().mean()

print(f"\n2026 Q1 Validation (annualised)")
print(f"  Pearson r: {r:.3f}")
print(f"  p-value:   {p:.4f}")
print(f"  MAE:       {mae:.1f}")
print(f"  LADs matched: {len(validation2026)}")

plt.figure(figsize=(8, 6))
plt.scatter(validation2026["Crime Rate 2026"], validation2026["Predicted 2026 Crime Rate"], alpha=0.5, s=20)
plt.plot([validation2026["Crime Rate 2026"].min(), validation2026["Crime Rate 2026"].max()],
         [validation2026["Crime Rate 2026"].min(), validation2026["Crime Rate 2026"].max()],
         color="red", linewidth=1.5, linestyle="--", label="Perfect prediction")
plt.xlabel("Actual 2026 Crime Rate (annualised)")
plt.ylabel("Predicted 2026 Crime Rate")
plt.title("2026 Q1 Validation (Annualised)")
plt.legend()
plt.tight_layout()
plt.savefig("./SSA7/validation_2026.png")

# generate 2026 LSOA predictions using annualised LAD predictions
data2025 = merged[merged["Year"] == 2025].dropna(subset=variables + ["Crime Rate", "Total Population"]).copy()
data2025["Predicted 2026 Crime Rate"] = models[2025].predict(data2025[variables].values)
data2025["Predicted 2026 Crime Count"] = data2025["Predicted 2026 Crime Rate"] / 100000 * data2025["Total Population"]

lsoa_2026 = lsoaIMD.merge(
    data2025[["LAD", "Predicted 2026 Crime Count"]],
    on="LAD", how="inner"
).copy()

lsoa_2026["Year"] = 2026
lsoa_2026["LSOA Predicted Count"] = lsoa_2026["LSOA Share"] * lsoa_2026["Predicted 2026 Crime Count"]

# validate against actual 2026 LSOA crime
crimeByLSOA2026 = crimeByLAD2026.merge(lsoalad, left_on="LAD", right_on="ladcd", how="left")

lsoa_val_2026 = lsoa_2026.merge(
    crimeByLSOA2026[["lsoa21cd", "Crime Count"]].rename(columns={
        "lsoa21cd": "LSOA",
        "Crime Count": "Actual Count"
    }),
    on="LSOA", how="inner"
)

lsoa_val_2026["Actual Count Annualised"] = lsoa_val_2026["Actual Count"] * 4

r, p = stats.pearsonr(lsoa_val_2026["Actual Count Annualised"], lsoa_val_2026["LSOA Predicted Count"])
mae  = (lsoa_val_2026["Actual Count Annualised"] - lsoa_val_2026["LSOA Predicted Count"]).abs().mean()

print(f"\n2026 LSOA Validation (annualised)")
print(f"  Pearson r: {r:.3f}")
print(f"  p-value:   {p:.4f}")
print(f"  MAE:       {mae:.1f}")

lsoa_2026[["LSOA", "LAD", "Year", "LSOA Share", "LSOA Predicted Count"]].to_csv("./SSA7/lsoa_predicted_2026.csv", index=False)