import pandas as pd
import numpy as np
from pathlib import Path

dashboardDataFolder = Path(__file__).resolve().parent

# Load severity score file
severityScoreFile = dashboardDataFolder / "data/ModelData/crimeseverityscore.xls"

severityScores = pd.read_excel(severityScoreFile, sheet_name="List of weights", header=6)
severityScores.columns = severityScores.columns.astype(str).str.strip()

# Narrow down the columns needed
severityScores = severityScores[["Offence category", "Weight"]].dropna()
severityScores["Offence category"] = severityScores["Offence category"].astype(str)
severityScores["Weight"] = pd.to_numeric(severityScores["Weight"], errors="coerce")
severityScores = severityScores.dropna(subset=["Weight"])

categoryWeights = severityScores.groupby("Offence category")["Weight"].median()

# Map severity scores to crime types
rawSeverityWeights = {
    "Violence and sexual offences": categoryWeights[
        categoryWeights.index.str.contains(
            "assault|sexual|rape|homicide|murder|wounding|death|injury",
            case=False,
            regex=True,
        )
    ].mean(),

    "Robbery": categoryWeights[
        categoryWeights.index.str.contains(
            "robbery",
            case=False,
            regex=True,
        )
    ].mean(),

    "Burglary": categoryWeights[
        categoryWeights.index.str.contains(
            "burglary",
            case=False,
            regex=True,
        )
    ].mean(),

    "Possession of weapons": categoryWeights[
        categoryWeights.index.str.contains(
            "weapon|firearm|blade",
            case=False,
            regex=True,
        )
    ].mean(),

    "Vehicle crime": categoryWeights[
        categoryWeights.index.str.contains(
            "vehicle",
            case=False,
            regex=True,
        )
    ].mean(),

    "Criminal damage and arson": categoryWeights[
        categoryWeights.index.str.contains(
            "criminal damage|arson",
            case=False,
            regex=True,
        )
    ].mean(),

    "Drugs": categoryWeights[
        categoryWeights.index.str.contains(
            "drug|cannabis",
            case=False,
            regex=True,
        )
    ].mean(),

    "Public order": categoryWeights[
        categoryWeights.index.str.contains(
            "public",
            case=False,
            regex=True,
        )
    ].mean(),

    "Shoplifting": categoryWeights[
        categoryWeights.index.str.contains(
            "shoplifting",
            case=False,
            regex=True,
        )
    ].mean(),

    "Other theft": categoryWeights[
        categoryWeights.index.str.contains(
            "theft",
            case=False,
            regex=True,
        )
    ].mean(),

    "Theft from the person": categoryWeights[
        categoryWeights.index.str.contains(
            "theft from the person|person",
            case=False,
            regex=True,
        )
    ].mean(),


    "Bicycle theft": categoryWeights[
        categoryWeights.index.str.contains(
            "pedal cycle|bicycle",
            case=False,
            regex=True,
        )
    ].mean(),
}

# Anti social behavior not in the csv
rawSeverityWeights["Anti-social behaviour"] = min(value for value in rawSeverityWeights.values() if pd.notna(value))

rawSeries = pd.Series(rawSeverityWeights)

# Make scores a number 1-5
logValues = np.log(rawSeries)
scaledSeverity = 1 + ((logValues - logValues.min()) / (logValues.max() - logValues.min())) * 4

severityWeights = scaledSeverity.round(1).to_dict()

# Make csv and save it
severityWeightsFile = pd.DataFrame({
    "Crime type": severityWeights.keys(),
    "Severity weight": severityWeights.values(),
    "Raw CSS weight": [rawSeverityWeights[crimeType] for crimeType in severityWeights.keys()],
})

severityWeightsFile = severityWeightsFile.sort_values("Severity weight", ascending=False)

severityWeightsFile.to_csv(dashboardDataFolder / "data/severityWeights.csv", index=False)