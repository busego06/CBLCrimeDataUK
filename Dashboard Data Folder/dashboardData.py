import glob
import json
from pathlib import Path
import numpy as np
import pandas as pd

# Paths of needed folders and files relative to where the this file is located
dashboardFolder = Path(__file__).resolve().parent
dataFolder = dashboardFolder / "data"

crimeDataFiles = dataFolder / "CrimeData"
deprecationFile = dataFolder / "PopulationDeprivationIndex.csv"
LSOAPredictFile = dataFolder / "officialModel2026LSOAPredictions.csv"

forecastYear = 2026

## Not real severity weights probably
# Severity Scores of Crime Types
severityWeights = {
    "Anti-social behaviour": 1.0,
    "Bicycle theft": 1.2,
    "Other theft": 1.5,
    "Shoplifting": 1.5,
    "Public order": 2.0,
    "Drugs": 2.0,
    "Other crime": 2.0,
    "Theft from the person": 2.0,
    "Vehicle crime": 2.5,
    "Criminal damage and arson": 2.5,
    "Burglary": 3.0,
    "Possession of weapons": 4.0,
    "Robbery": 4.5,
    "Violence and sexual offences": 5.0,
}

# Function to read the crime data into a dataframe variable.
def readCrimeData(path):
    # Needed columns from the crime data
    neededInfo = ["Month", "Longitude", "Latitude", "LSOA code", "LSOA name", "Crime type"]

    # Recursively add file data to a variable while outputing the ones that have been scanned
    files = glob.glob(str(path / "**/*.csv"), recursive=True)
    data = []
    for number, filepath in enumerate(sorted(files), start=1):
        print(f"[{number}/{len(files)}] reading {Path(filepath).name}")
        data.append(pd.read_csv(filepath, usecols=neededInfo, low_memory=False))
    crimeData = pd.concat(data, ignore_index=True)

    # Clean data and change the values to the right types
    crimeData = crimeData.dropna(subset=["LSOA code"])
    crimeData["Month"] = pd.to_datetime(crimeData["Month"])
    crimeData["Longitude"] = pd.to_numeric(crimeData["Longitude"], errors="coerce")
    crimeData["Latitude"] = pd.to_numeric(crimeData["Latitude"], errors="coerce")

    # Maps severity weights from the dictionary above and defined high harm incidents
    crimeData["severityWeight"] = crimeData["Crime type"].map(severityWeights).fillna(1.0)
    crimeData["highHarmIncident"] = (crimeData["severityWeight"] >= 4.0).astype(int)

    # Creates crimeSummary to be used for the dashboard data
    crimeSummary = crimeData.groupby(["LSOA code", "Month"], as_index=False).agg(
            LSOA_name=("LSOA name", "last"),
            incidents=("Crime type", "size"),
            severityWeight=("severityWeight", "sum"),
            highHarmIncident=("highHarmIncident", "sum"),
            longitude=("Longitude", "mean"),
            latitude=("Latitude", "mean"))
    
    crimeSummary = crimeSummary.sort_values(["LSOA code", "Month"])

    return crimeSummary

# Loads deprivation data for non-model dashboard stats 
def loadContext(path):

    # Load csv and rename columns for accessibility
    LSOAInfo = pd.read_csv(path)
    LSOAInfo.rename(columns={
        "LSOA code (2021)": "LSOA code",
        "LSOA name (2021)": "LSOA name",
        "Local Authority District name (2024)": "LAD name",
        "Index of Multiple Deprivation (IMD) Decile (where 1 is most deprived 10% of LSOAs)": "imdDecile",
        "Income Decile (where 1 is most deprived 10% of LSOAs)": "incomeDecile",
        "Employment Decile (where 1 is most deprived 10% of LSOAs)": "employmentDecile",
        "Education, Skills and Training Decile (where 1 is most deprived 10% of LSOAs)": "educationDecile",
        "Total population: mid 2022": "Population",
    }, inplace=True)

    # Remove not needed columns
    LSOAInfo = LSOAInfo[["LSOA code", "LSOA name", "LAD name", "imdDecile", "incomeDecile", "employmentDecile", "educationDecile", "Population"]]

    # Converts all relevant columns to numeric values
    numericColumns = ["imdDecile", "incomeDecile", "employmentDecile", "educationDecile", "Population"]
    for column in numericColumns:
        LSOAInfo[column] = pd.to_numeric(LSOAInfo[column], errors="coerce")

    return LSOAInfo


# Loads the model csv and 
def loadModelForecast(path, panel):

    # Load model prediction csv and rename columns
    forecast = pd.read_csv(path)
    forecast = forecast.rename(columns={
        "LSOA": "LSOA code",
        "LAD": "LAD code",
        "LSOA Share": "lsoaShare",
        "LSOA Predicted Count": "predictedCrimeCount"
    })

    # Convert relevant values to numeric values
    forecast["predictedCrimeCount"] = pd.to_numeric(forecast["predictedCrimeCount"], errors="coerce").fillna(0)
    forecast["lsoaShare"] = pd.to_numeric(forecast["lsoaShare"], errors="coerce").fillna(0)

    # Link forecast LSOAs with crime data coordinates stored in the panel dataframe
    lsoaCoords = (panel.groupby("LSOA code", as_index=False).agg(
        latitude=("latitude", "median"), 
        longitude=("longitude", "median")))
    forecast = forecast.merge(lsoaCoords, on="LSOA code", how="left")

    # Calculate and use LAD median coords for any missing info on latitude or longitude
    ladCoords = forecast.dropna(subset=["latitude", "longitude"]).groupby("LAD code", as_index=False)
    ladCoords = ladCoords.agg(ladLatitude=("latitude", "median"), ladLongitude=("longitude", "median"))
    forecast = forecast.merge(ladCoords, on="LAD code", how="left")
    forecast["latitude"] = forecast["latitude"].fillna(forecast["ladLatitude"])
    forecast["longitude"] = forecast["longitude"].fillna(forecast["ladLongitude"])
    forecast = forecast.drop(columns=["ladLatitude", "ladLongitude"])

    ## Check to make a better response to what the model says

    # Calculate the priority of the LSOA/LAD according to the model
    q90 = forecast["predictedCrimeCount"].quantile(0.90)
    q75 = forecast["predictedCrimeCount"].quantile(0.75)

    forecast["allocationTier"] = "routine"
    forecast.loc[forecast["predictedCrimeCount"] >= q75, "allocationTier"] = "reserve"
    forecast.loc[forecast["predictedCrimeCount"] >= q90, "allocationTier"] = "priority"

    total = forecast["predictedCrimeCount"].sum()
    forecast["capacity"] = (forecast["predictedCrimeCount"] / total * 100) if total > 0 else 0.0

    return forecast

# Summarises recent data to let the dashboard provide more than just a predictive model
def summaryRecentData(panel, context):
    # Copy panel dataframe to not cause problems with it during future use
    panelDates = panel.copy()
    panelDates["Month"] = pd.to_datetime(panelDates["Month"])

    # Select crimes that were in the last 12 months
    recentMonth = 12
    latestMonths = sorted(panelDates["Month"].unique())[-recentMonth:]
    recent = panelDates[panelDates["Month"].isin(latestMonths)]

    recentSummary = recent.groupby("LSOA code", as_index=False).agg(
            RecentDemand=("severityWeight", "sum"),
            RecentIncidents=("incidents", "sum"),
            RecentHighHarm=("highHarmIncident", "sum"),
        )

    # Calculate the high harm crimes percentage for more data on the dashboard
    recentSummary["highHarmPercent"] = recentSummary["RecentHighHarm"] / recentSummary["RecentIncidents"].replace(0, np.nan).fillna(0)

    # Add population to the dataframe
    recentSummary = recentSummary.merge(context[["LSOA code", "Population"]], on="LSOA code", how="left")
    recentSummary["Population"] = recentSummary["Population"].fillna(0)

    return recentSummary

# Converts the data in python into a file readable by the javascript file
def JSDataPrep(forecast, context, recentSummary):
    # Merge all dataframes into an area data dataframe to make the conversion
    areaCoords = forecast
    areaSummary = areaCoords.merge(recentSummary, on="LSOA code", how="left")
    areaData = areaSummary.merge(context.drop(columns=["Population"], errors="ignore"), on="LSOA code", how="left")

    # Clean columns
    relevantDataColumns = ["Population", "RecentDemand", "RecentIncidents", "RecentHighHarm", "highHarmPercent"]
    for column in relevantDataColumns:
        areaData[column] = areaData[column].fillna(0)

    # Add values for new dashboard data and visualization points on the map
    areaData["predictedDemand"] = (areaData["predictedCrimeCount"] / areaData["Population"] * 1000).fillna(0)
    areaData["predictedRank"] = areaData["predictedCrimeCount"].rank(pct=True).fillna(0)
    predictedMax = max(areaData["predictedCrimeCount"].max(), 1)

    # Create the variable for data that is going to be added to the website and map columns to var names
    areas = []
    for _, row in areaData.iterrows():
        lsoaName = row["LSOA name"]
        ladName = row["LAD name"]

        if pd.notna(row["latitude"]):
            latitude = float(row["latitude"])
        else:
            latitude = None

        if pd.notna(row["longitude"]):
            longitude = float(row["longitude"])
        else:
            longitude = None

        areas.append({
            "lsoaCode": str(row["LSOA code"]),
            "name": str(lsoaName),
            "lsoaName": str(row.get("LSOA name", row["LSOA code"])),
            "ladName": str(ladName),
            "ladCode": str(row.get("LAD code", "")),
            "longitude": longitude,
            "latitude": latitude,

            "predictedDemand": round(float(row["predictedCrimeCount"]), 2),

            "lsoaShare": round(float(row.get("lsoaShare", 0)), 6),
            "allocatedCapacity": round(float(row.get("capacity", 0)), 2),
            "population": int(row.get("Population", 0)),

            "originalTier": str(row["allocationTier"]),

            "recentDemand": round(float(row.get("RecentDemand", 0)), 2),
            "recentIncidents": round(float(row.get("RecentIncidents", 0)), 0),
            "recentHighHarm": round(float(row.get("RecentHighHarm", 0)), 0),
            "highHarmShare": round(float(row.get("highHarmPercent", 0)), 4),

            "demandRank": round(float(row["predictedRank"]), 5),

            "imdDecile": int(row["imdDecile"]) if pd.notna(row.get("imdDecile")) else 0,
            "incomeDecile": int(row["incomeDecile"]) if pd.notna(row.get("incomeDecile")) else 0,
            "employmentDecile": int(row["employmentDecile"]) if pd.notna(row.get("employmentDecile")) else 0,
            "educationDecile": int(row["educationDecile"]) if pd.notna(row.get("educationDecile")) else 0,

            "contextAvailable": bool(row.get("Population", 0) > 0),
            "sizeScore": round(float(row["predictedCrimeCount"]) / predictedMax, 5),
        })

    return areas

# Creates the package that the javascript file uses to create the website
def JSDataConversion(crimeSummary, context, forecast):
    recentSummary = summaryRecentData(crimeSummary, context)
    areas = JSDataPrep(forecast, context, recentSummary)

    # Creates metadata for the website
    return {
        "meta": {
            "title": "Police Demand Review Map",
            "subtitle": "Dashboard based on the LAD-to-LSOA socioeconomic crime model",
            "courseQuestion": "How can socioeconomic indicators be used to estimate crime and support policing resource planning?",
            "modelEquation": "Predicted LAD Crime Rate = intercept + β1(Persistent Absence) + β2(Mean Income) + β3(Crime Rank) + β4(Homelessness Rate)",
            "stakeholder": "UK police resource planners and policing decision-makers",
            "dataFrom": "England & Wales Crime Archive",
            "dateRange": "2024-2025",
            "forecastMonth": str(forecastYear),
            "publisher": "data.police.uk",
            "downloadPage": "https://data.police.uk/data/",
            "contextSource": "GOV.UK English Indices of Deprivation 2025, File 7",
            "contextDownload": "https://www.gov.uk/government/statistics/english-indices-of-deprivation-2025",
            "lsoas": len(areas),
            "months": int(crimeSummary["Month"].nunique()),
            "contextCoverage": sum(1 for area in areas if area["contextAvailable"]),
            "sourceNote": "The dashboard uses police.uk data for recent crime context and coordinates. The prediction shown comes from the SSA7 LAD-to-LSOA model.",
            "modelCaution": "This is a decision-support prototype, not an automatic deployment system or staffing calculator.",
        },
        "areas": areas,
        "metrics": [{
            "model": "LAD-to-LSOA socioeconomic allocation model",
            "testMonths": "2026",
            "note": "Uses the LAD regression output and distributes LAD predicted crime to LSOAs using the LSOA share weights.",
        }],
        "localAuthorities": sorted({area["ladName"] for area in areas if area["ladName"]}),
        "seriesByArea": {},
        "method": [
            {"step": "Estimate LAD crime", "plainText": "A linear regression model estimates LAD-level crime rate using persistent absence, mean income, crime deprivation rank and homelessness rate."},
            {"step": "Convert rate to count", "plainText": "The predicted LAD crime rate is converted into a predicted LAD crime count using the LAD population."},
            {"step": "Allocate to LSOAs", "plainText": "The predicted LAD crime count is distributed to LSOAs using LSOA share weights based on crime rank, income rank, health deprivation and population density."},
            {"step": "Add IoD context only", "plainText": "IoD variables are shown in the dashboard for interpretation, but they do not change the SSA7 prediction or priority ranking."},
        ],
    }

# Creates the outputs, including the payload and the dashboard forecast csv
def write_outputs(payload, forecast):
    forecast.to_csv(dataFolder / "dashboardForecast.csv", index=False)

    with open(dataFolder / "dashboardData.js", "w", encoding="utf-8") as file:
        file.write("window.DASHBOARDDATA = ")
        json.dump(payload, file, ensure_ascii=False, separators=(",", ":"))
        file.write(";")


def main():
    # Load files
    crimeSummary = readCrimeData(crimeDataFiles)
    context = loadContext(deprecationFile)
    forecast = loadModelForecast(LSOAPredictFile, crimeSummary)
    print("Forecast rows:", len(forecast))
    print("Unique LSOAs:", forecast["LSOA code"].nunique())

    # Create package for website javascript file
    package = JSDataConversion(
        crimeSummary=crimeSummary,
        context=context,
        forecast=forecast,
    )

    # Create outputs
    write_outputs(package, forecast)

    print(json.dumps({
        "areas": len(package["areas"]),
        "contextCoverage": package["meta"]["contextCoverage"],
        "dashboardFile": str(dataFolder / "dashboardData.js"),
    }, indent=2))


if __name__ == "__main__":
    main()