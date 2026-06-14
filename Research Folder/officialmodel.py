from sklearn.linear_model import LinearRegression
import pandas as pd
import matplotlib.pyplot as plt
import glob

## DEPRIVATION

depFile = "./SSA5/csv/deprevation.xlsx"

imdData = pd.read_excel(depFile, sheet_name="IoD2025 Domains")

imdData.rename(columns={
    "Index of Multiple Deprivation (IMD) Rank (where 1 is most deprived)": "Index of Multiple Deprivation (IMD) Rank", 
    "Income Rank (where 1 is most deprived)": "Income Rank",
    "Employment Rank (where 1 is most deprived)": "Employment Rank",
    "Education, Skills and Training Rank (where 1 is most deprived)": "Education, Skills and Training Rank",
    "Health Deprivation and Disability Rank (where 1 is most deprived)": "Health Deprivation and Disability Rank",
    "Crime Rank (where 1 is most deprived)" : "Crime Rank"
}, inplace=True)

imdByLAD = imdData.groupby("Local Authority District code (2024)").agg(
    IMD        = ("Index of Multiple Deprivation (IMD) Rank", "median"),
    Income     = ("Income Rank", "median"),
    Employment = ("Employment Rank", "median"),
    Education  = ("Education, Skills and Training Rank", "median"),
    Health     = ("Health Deprivation and Disability Rank", "median"),
    Crime = ("Crime Rank", 'median')
).reset_index()

imdByLAD.rename(columns={"Local Authority District code (2024)": "LAD"}, inplace=True)

for col in ["IMD", "Income", "Employment", "Education", "Health"]:
    imdByLAD[col] = pd.to_numeric(imdByLAD[col], errors="coerce")

## INCOME DATA

files = glob.glob("./SSA4/csv/economy/income_*.xlsx")
dfs = []

for file in files:
    df = pd.read_excel(file, sheet_name="Full-Time", header=4)
    year = file.split("_")[-1].replace(".xlsx", "")
    df["Year"] = int(year)
    dfs.append(df)

incomeData = pd.concat(dfs, ignore_index=True)
incomeData = incomeData[["Code", "Median", "Mean", 25, 75, "Year"]]
incomeData = incomeData.rename(columns={"Code": "LAD", "Median": "Median Income", "Mean": "Mean Income", 25: "Q1", 75: "Q3"}).reset_index(drop=True)

incomeData["Q1"] = pd.to_numeric(incomeData["Q1"].astype(str).str.replace(",", "").str.replace("£", ""), errors="coerce")
incomeData["Q3"] = pd.to_numeric(incomeData["Q3"].astype(str).str.replace(",", "").str.replace("£", ""), errors="coerce")
incomeData["IQR"] = incomeData["Q3"] - incomeData["Q1"]

## CRIME DATA

filesCrime = glob.glob("./SSA4/csv/crimeecon/**/*.csv", recursive=True)
dfs = []

for file in filesCrime:
    df = pd.read_csv(file)
    dfs.append(df)

crimeData = pd.concat(dfs, ignore_index=True)
crimeData["Month"] = pd.to_datetime(crimeData["Month"])
crimeData = crimeData[["LSOA code", "Crime type", "Month"]]
crimeData = crimeData.rename(columns={"LSOA code": "LSOA", "Crime type": "Crime type"})
crimeData["Year"] = crimeData["Month"].dt.year
crimeData = crimeData[["LSOA", "Crime type", "Year"]]

crimeByLSOA = crimeData.groupby(["LSOA", "Year"]).size().reset_index(name="Crime Count")

lsoalad = pd.read_csv("./SSA4/csv/LSOALAD.csv", low_memory=False)
lsoalad = lsoalad[["lsoa21cd", "ladcd"]].drop_duplicates()

crimeByLAD = crimeByLSOA.merge(lsoalad, left_on="LSOA", right_on="lsoa21cd")
crimeByLAD = crimeByLAD.groupby(["ladcd", "Year"])["Crime Count"].sum().reset_index()
crimeByLAD = crimeByLAD.rename(columns={"ladcd": "LAD"})

## POPULATION DATA

populationData = pd.read_excel("./SSA4/csv/sapemsoaquinaryage20222024.xlsx", sheet_name="Mid-2024 MSOA 2021", header=3)
populationLADData = populationData.groupby("LAD 2023 Code")["Total"].sum().reset_index()
populationLADData = populationLADData.rename(columns={"LAD 2023 Code": "LAD", "Total": "Total Population"})

mergedCrime = pd.merge(crimeByLAD, populationLADData, on="LAD")
mergedCrime["Crime Rate"] = (mergedCrime["Crime Count"] / mergedCrime["Total Population"]) * 100000

## EDUCATION DATA

fileEducation = "./SSA2/csv/edudata/persistentabsence.csv"
eduData = pd.read_csv(fileEducation)
eduData = eduData[eduData["education_phase"] == "Secondary"]
eduData = eduData[eduData["time_identifier"].str.match(r"Week \d+", na=False)].copy()
eduData["week_num"] = eduData["time_identifier"].str.extract(r"(\d+)").astype(int)
eduData["academic_year_start"] = eduData["time_period"].astype(int) - 1
eduData["sep1"] = pd.to_datetime(eduData["academic_year_start"].astype(str) + "-09-01")
eduData["first_monday"] = eduData["sep1"] + pd.to_timedelta((7 - eduData["sep1"].dt.dayofweek) % 7, unit="D")
eduData["date"] = eduData["first_monday"] + pd.to_timedelta((eduData["week_num"] - 1) * 7, unit="D")
eduData["year"] = eduData["date"].dt.year
eduData["persistent_absence_percent"] = pd.to_numeric(eduData["persistent_absence_percent"], errors="coerce")

absenceData = eduData.groupby(["new_la_code", "year"])["persistent_absence_percent"].mean().reset_index()
absenceData.rename(columns={"new_la_code": "LAD", "year": "Year"}, inplace=True)

## MERGE

crimeAndIQR = pd.merge(mergedCrime, incomeData, on=["LAD", "Year"], how="inner").dropna()
for col in ["IQR", "Median Income", "Mean Income", "Crime Rate"]:
    crimeAndIQR[col] = pd.to_numeric(crimeAndIQR[col], errors="coerce")

crimeIQRAbsence = crimeAndIQR.merge(absenceData, on=["LAD", "Year"], how="left").dropna(subset=["persistent_absence_percent"])
merged = crimeIQRAbsence.merge(imdByLAD, on="LAD", how="left")
merged = merged[merged["Crime Rate"] >= 1000]

## LAD REGRESSION MODEL

variables = ["persistent_absence_percent", "Mean Income", "IMD"]
labels    = ["Absence Rate", "Mean Income", "IMD Rank"]

models = {}

for year in [2024, 2025]:
    data = merged[merged["Year"] == year].dropna(subset=variables + ["Crime Rate"])
    X = data[variables].values
    y = data["Crime Rate"].values
    model = LinearRegression().fit(X, y)
    models[year] = model
    r2 = model.score(X, y)
    print(f"\n{year} — R²: {r2:.3f}")
    for var, coef in zip(variables, model.coef_):
        print(f"  {var:<35} coef: {coef:.4f}")
    print(f"  Intercept: {model.intercept_:.2f}")

## ACTUAL VS PREDICTED (LAD LEVEL)

for year in [2024, 2025]:
    data = merged[merged["Year"] == year].dropna(subset=variables + ["Crime Rate"]).copy()
    data["Predicted Crime Rate"] = models[year].predict(data[variables].values)
    data["Residual"] = data["Crime Rate"] - data["Predicted Crime Rate"]

    plt.figure(figsize=(8, 6))
    plt.scatter(data["Crime Rate"], data["Predicted Crime Rate"], alpha=0.5, s=20)
    plt.plot([data["Crime Rate"].min(), data["Crime Rate"].max()],
             [data["Crime Rate"].min(), data["Crime Rate"].max()],
             color="red", linewidth=1.5, linestyle="--", label="Perfect prediction")
    plt.xlabel("Actual Crime Rate")
    plt.ylabel("Predicted Crime Rate")
    plt.title(f"Actual vs Predicted Crime Rate ({year})")
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"./SSA6/actual_vs_predicted_{year}.png")

## LSOA DISAGGREGATION

lsoaIMD = imdData[[
    "LSOA code (2021)",
    "Local Authority District code (2024)",
    "Index of Multiple Deprivation (IMD) Rank",
    "Income Rank",
    "Health Deprivation and Disability Rank"
]].copy()

lsoaIMD.rename(columns={
    "LSOA code (2021)": "LSOA",
    "Local Authority District code (2024)": "LAD",
    "Index of Multiple Deprivation (IMD) Rank": "LSOA IMD Rank",
    "Income Rank": "LSOA Income Rank",
    "Health Deprivation and Disability Rank": "LSOA Health Deprivation and Disability Rank"
}, inplace=True)

lsoaIMD["LSOA IMD Rank"]    = pd.to_numeric(lsoaIMD["LSOA IMD Rank"], errors="coerce")
lsoaIMD["LSOA Income Rank"] = pd.to_numeric(lsoaIMD["LSOA Income Rank"], errors="coerce")
lsoaIMD["LSOA Health Deprivation and Disability Rank"] = pd.to_numeric(lsoaIMD["LSOA Health Deprivation and Disability Rank"], errors="coerce")
lsoaIMD = lsoaIMD.dropna(subset=["LSOA IMD Rank", "LSOA Income Rank"])

## Combined Weight
lsoaIMD["IMD Weight"]        = 1 / lsoaIMD["LSOA IMD Rank"]
lsoaIMD["Income Weight"]     = 1 / lsoaIMD["LSOA Income Rank"]
lsoaIMD["Health Deprivation and Disability Weight"] = 1 / lsoaIMD["LSOA Health Deprivation and Disability Rank"]
lsoaIMD["Weight"]            = (
    lsoaIMD["IMD Weight"] + 
    lsoaIMD["Income Weight"] + 
    lsoaIMD["Health Deprivation and Disability Weight"]
) / 3

lad_weight_total = lsoaIMD.groupby("LAD")["Weight"].sum().reset_index()
lad_weight_total.rename(columns={"Weight": "LAD Weight Total"}, inplace=True)
lsoaIMD = lsoaIMD.merge(lad_weight_total, on="LAD")
lsoaIMD["LSOA Share"] = lsoaIMD["Weight"] / lsoaIMD["LAD Weight Total"]

lsoa_results = []

for year in [2024, 2025]:
    data = merged[merged["Year"] == year].dropna(subset=variables + ["Crime Rate", "Total Population"]).copy()
    data["Predicted Crime Rate"]  = models[year].predict(data[variables].values)
    data["Predicted Crime Count"] = data["Predicted Crime Rate"] / 100000 * data["Total Population"]

    lsoa_year = lsoaIMD.merge(
        data[["LAD", "Predicted Crime Count"]],
        on="LAD", how="inner"
    ).copy()

    lsoa_year["Year"] = year
    lsoa_year["LSOA Predicted Count"] = lsoa_year["LSOA Share"] * lsoa_year["Predicted Crime Count"]
    lsoa_results.append(lsoa_year)

lsoaPredicted = pd.concat(lsoa_results, ignore_index=True)

print(lsoaPredicted[["LSOA", "LAD", "Year", "LSOA Share", "LSOA Predicted Count"]].head(10))
lsoaPredicted.to_csv("./SSA6/lsoa_predicted_crime.csv", index=False)