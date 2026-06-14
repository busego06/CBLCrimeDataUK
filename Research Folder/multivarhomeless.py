import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import glob
from scipy import stats
from sklearn.linear_model import LinearRegression

## HOMELESSNESS

homelessFile = "./SSA7/csv/homesless.ods"

homeless = pd.read_excel(homelessFile, engine="odf", sheet_name="A1", header=4)

homelessClean = homeless[["Unnamed: 0", "Households assessed as homelessper (000s)"]]
homelessClean.rename(columns={
    "Unnamed: 0": "LAD",
    "Households assessed as homelessper (000s)": "Homeless Rate"
}, inplace=True)

homelessClean["Homeless Rate"] = pd.to_numeric(homelessClean["Homeless Rate"], errors="coerce")
homelessClean.dropna(inplace=True)

## DEPREVATION

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
    IMD = ("Index of Multiple Deprivation (IMD) Rank", "median"),
    Income = ("Income Rank", "median"),
    Employment = ("Employment Rank", "median"),
    Education = ("Education, Skills and Training Rank", "median"),
    Health = ("Health Deprivation and Disability Rank", "median"),
    Crime = ("Crime Rank", 'median')
).reset_index()

imdByLAD.rename(columns={"Local Authority District code (2024)": "LAD"}, inplace=True)

imdByLAD["IMD"] = pd.to_numeric(imdByLAD["IMD"], errors="coerce")

imdByLAD["Income"] = pd.to_numeric(imdByLAD["Income"], errors="coerce")

imdByLAD["Employment"] = pd.to_numeric(imdByLAD["Employment"], errors="coerce")

imdByLAD["Education"] = pd.to_numeric(imdByLAD["Education"], errors="coerce")

imdByLAD["Health"] = pd.to_numeric(imdByLAD["Health"], errors="coerce")

imdByLAD["Crime"] = pd.to_numeric(imdByLAD["Crime"], errors="coerce")

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
incomeData = incomeData.rename(columns={"Code": "LAD", "Median": "Median Income", 25: "Q1", 75: "Q3", "Year": "Year"}).reset_index(drop=True)

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
crimeByLAD = crimeByLAD.rename(columns={"ladcd": "LAD", "Crime Count": "Crime Count", "Year": 'Year'})
## POPULATION DATA

populationData = pd.read_excel("./SSA4/csv/sapemsoaquinaryage20222024.xlsx", sheet_name="Mid-2024 MSOA 2021", header=3)

populationLADData = populationData.groupby("LAD 2023 Code")["Total"].sum().reset_index()

populationLADData = populationLADData[["LAD 2023 Code", "Total"]]

populationLADData = populationLADData.rename(columns={"LAD 2023 Code": "LAD", "Total": "Total Population"})

mergedCrime = pd.merge(crimeByLAD, populationLADData, on="LAD")

mergedCrime["Crime Rate"] = (mergedCrime["Crime Count"] / mergedCrime["Total Population"]) * 100000

fileEducation = "./SSA2/csv/edudata/persistentabsence.csv"
eduData = pd.read_csv(fileEducation)

eduData = eduData[(eduData["education_phase"] == "Secondary")]

eduData = eduData[eduData["time_identifier"].str.match(r"Week \d+", na=False)].copy()

eduData["week_num"] = eduData["time_identifier"].str.extract(r"(\d+)").astype(int)

eduData["academic_year_start"] = eduData["time_period"].astype(int) - 1

eduData["sep1"] = pd.to_datetime(eduData["academic_year_start"].astype(str) + "-09-01")
eduData["first_monday"] = eduData["sep1"] + pd.to_timedelta((7 - eduData["sep1"].dt.dayofweek) % 7, unit="D")

eduData["date"]       = eduData["first_monday"] + pd.to_timedelta((eduData["week_num"] - 1) * 7, unit="D")
eduData["month"]      = eduData["date"].dt.month
eduData["year"]       = eduData["date"].dt.year
eduData["month_name"] = eduData["date"].dt.strftime("%B")

eduData["persistent_absence_percent"] = pd.to_numeric(eduData["persistent_absence_percent"], errors="coerce")

absenceData = eduData.groupby(["new_la_code", "year"])["persistent_absence_percent"].mean().reset_index()
absenceData.rename(columns={"new_la_code": "LAD", "year": "Year"}, inplace=True)

crimeAndIQR = pd.merge(mergedCrime, incomeData, on=["LAD", "Year"], how="inner")
crimeAndIQR = crimeAndIQR.dropna()

crimeAndIQR["IQR"] = pd.to_numeric(crimeAndIQR["IQR"], errors="coerce")

crimeAndIQR["Median Income"] = pd.to_numeric(crimeAndIQR["Median Income"], errors="coerce")

crimeAndIQR["Mean"] = pd.to_numeric(crimeAndIQR["Mean"], errors="coerce")

crimeAndIQR["Crime Rate"] = pd.to_numeric(crimeAndIQR["Crime Rate"], errors="coerce")

crimeIQRAbsence = crimeAndIQR.merge(absenceData, on=["LAD", "Year"], how="left")

crimeIQRAbsence = crimeIQRAbsence.dropna(subset=["persistent_absence_percent"])

crimeIQRAbsenceHomeless = crimeIQRAbsence.merge(homelessClean, on=["LAD"], how="left")

merged = crimeIQRAbsenceHomeless.merge(imdByLAD, on=["LAD"], how="left")


variables = ["persistent_absence_percent", "Mean", "Crime", "Homeless Rate"]
labels = ["Persistent Absence (%)", "Mean Income", "Crime Rank", "Homeless Rate"]

fig, axes = plt.subplots(4, 2, figsize=(20, 16))

for year, col in zip([2024, 2025], [0, 1]):
    data = merged[merged["Year"] == year].dropna(subset=variables + ["Crime Rate"])
    
    for row, (var, label) in enumerate(zip(variables, labels)):
        ax = axes[row][col]
        
        x = data[var].values
        y = data["Crime Rate"].values
        
        r, p = stats.pearsonr(x, y)
        verdict = "keep" if (abs(r) >= 0.3 and p < 0.05) else "drop"
        
        ax.scatter(x, y, alpha=0.5, s=20, color="blue" if year == 2024 else "orange")
        
        # trend line
        m, b = np.polyfit(x, y, 1)
        ax.plot(np.sort(x), m * np.sort(x) + b, color="black", linewidth=1.5)
        
        ax.set_title(f"{label} vs Crime Rate ({year})")
        ax.set_xlabel(label)
        ax.set_ylabel("Crime Rate")
        ax.annotate(
            f"r = {r:.3f}   p = {p:.4f}\n→ {verdict}",
            xy=(0.05, 0.90), xycoords="axes fraction",
            fontsize=11,
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="gray", alpha=0.8)
        )

plt.tight_layout()
plt.savefig("./SSA7/multivariable_correlation_withhome2.png")

for year in [2024, 2025]:
    data = merged[merged["Year"] == year].dropna(subset=["persistent_absence_percent", "Crime Rate", "Mean", "Crime", "Homeless Rate"])
    
    X = data[["persistent_absence_percent", "Mean", "Crime", "Homeless Rate"]].values
    y = data["Crime Rate"].values
    
    model = LinearRegression().fit(X, y)
    r2 = model.score(X, y)
    yPrediction = model.predict(X)
    
    print(f"\n{year}")
    print(f"  R²: {r2:.3f}  — explains {r2*100:.1f}% of variance in Crime Rate")
    print(f"  Absence coefficient:   {model.coef_[0]:.4f}")
    print(f"  Mean Income coefficient:   {model.coef_[1]:.4f}")
    print(f"  Crime IMD coefficient:   {model.coef_[2]:.4f}")
    print(f"  Homeless coefficient:   {model.coef_[3]:.4f}")
    print(f"  Intercept:             {model.intercept_:.2f}")