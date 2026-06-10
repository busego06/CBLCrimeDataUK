import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

dashboardFolder = Path(__file__).resolve().parent

crimeDataFile = dashboardFolder + "/data/police_uk_archive_2026_03.zip"
deprecationFile = dashboardFolder + "/data/File_7_IoD2025_All_Ranks_Scores_Deciles_Population_Denominators.csv"
LSOAPredictFile = dashboardFolder + "/data/officialmodel_2026_lsoa_predictions.csv"

forecastYear = 2026

## Not real severity weights probably
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


def readCrimeData(path):
    usecols = ["Month", "Longitude", "Latitude", "LSOA code", "LSOA name", "Crime type"]
    monthly_parts = []
    crime_type_parts = []
    incident_rows = 0

    with zipfile.ZipFile(path) as archive:
        street_files = sorted(
            name for name in archive.namelist()
            if Path(name).name.endswith("-street.csv")
        )

        for number, filename in enumerate(street_files, start=1):
            print(f"[{number}/{len(street_files)}] reading {Path(filename).name}")

            with archive.open(filename) as file:
                for chunk in pd.read_csv(file, usecols=usecols, chunksize=250_000, low_memory=False):
                    chunk = chunk.dropna(subset=["LSOA code"]).copy()
                    if chunk.empty:
                        continue

                    chunk["Month"] = pd.PeriodIndex(chunk["Month"], freq="M").astype(str)
                    chunk["Longitude"] = pd.to_numeric(chunk["Longitude"], errors="coerce")
                    chunk["Latitude"] = pd.to_numeric(chunk["Latitude"], errors="coerce")
                    chunk["severity_weight"] = chunk["Crime type"].map(severityWeights).fillna(1.0)
                    chunk["high_harm_incident"] = (chunk["severity_weight"] >= 4.0).astype(int)
                    incident_rows += len(chunk)

                    monthly_parts.append(
                        chunk.groupby(["LSOA code", "LSOA name", "Month"], as_index=False)
                        .agg(
                            incidents=("Crime type", "size"),
                            demand_points=("severity_weight", "sum"),
                            high_harm_incidents=("high_harm_incident", "sum"),
                            longitude=("Longitude", "mean"),
                            latitude=("Latitude", "mean"),
                        )
                    )

                    crime_type_parts.append(
                        chunk.groupby("Crime type", as_index=False)
                        .agg(
                            incidents=("Crime type", "size"),
                            demand_points=("severity_weight", "sum"),
                            severity_weight=("severity_weight", "first"),
                        )
                    )

    monthly_raw = pd.concat(monthly_parts, ignore_index=True)

    panel = (
        monthly_raw.groupby(["LSOA code", "Month"], as_index=False)
        .agg(
            LSOA_name=("LSOA name", "last"),
            incidents=("incidents", "sum"),
            demand_points=("demand_points", "sum"),
            high_harm_incidents=("high_harm_incidents", "sum"),
            longitude=("longitude", "mean"),
            latitude=("latitude", "mean"),
        )
        .sort_values(["LSOA code", "Month"])
    )

    crime_type_summary = (
        pd.concat(crime_type_parts, ignore_index=True)
        .groupby("Crime type", as_index=False)
        .agg(
            incidents=("incidents", "sum"),
            demand_points=("demand_points", "sum"),
            severity_weight=("severity_weight", "first"),
        )
        .sort_values("demand_points", ascending=False)
    )

    monthly_summary = (
        panel.groupby("Month", as_index=False)
        .agg(
            incidents=("incidents", "sum"),
            demand_points=("demand_points", "sum"),
            high_harm_incidents=("high_harm_incidents", "sum"),
        )
        .sort_values("Month")
    )

    return panel, crime_type_summary, monthly_summary, incident_rows


def load_context(path: Path) -> pd.DataFrame:
    columns = {
        "LSOA code (2021)": "LSOA code",
        "LSOA name (2021)": "official_lsoa_name",
        "Local Authority District name (2024)": "local_authority",
        "Index of Multiple Deprivation (IMD) Score": "imd_score",
        "Index of Multiple Deprivation (IMD) Decile (where 1 is most deprived 10% of LSOAs)": "imd_decile",
        "Income Score (rate)": "income_score",
        "Income Decile (where 1 is most deprived 10% of LSOAs)": "income_decile",
        "Employment Score (rate)": "employment_score",
        "Employment Decile (where 1 is most deprived 10% of LSOAs)": "employment_decile",
        "Education, Skills and Training Score": "education_score",
        "Education, Skills and Training Decile (where 1 is most deprived 10% of LSOAs)": "education_decile",
        "Income Deprivation Affecting Children Index (IDACI) Score (rate)": "child_income_score",
        "Income Deprivation Affecting Children Index (IDACI) Decile (where 1 is most deprived 10% of LSOAs)": "child_income_decile",
        "Total population: mid 2022": "population",
    }

    context = pd.read_csv(path, usecols=list(columns.keys())).rename(columns=columns)

    numeric_cols = [c for c in context.columns if c not in ["LSOA code", "official_lsoa_name", "local_authority"]]
    context[numeric_cols] = context[numeric_cols].apply(pd.to_numeric, errors="coerce")

    return context


def load_ssa7_forecast(path: Path, panel: pd.DataFrame) -> pd.DataFrame:
    forecast = pd.read_csv(path)
    forecast = forecast[forecast["Year"] == forecastYear].copy()

    forecast = forecast.rename(columns={
        "LSOA": "LSOA code",
        "LAD": "lad_code",
        "LSOA Share": "lsoa_share",
        "LSOA Predicted Count": "predicted_demand_points",
    })

    forecast["predicted_demand_points"] = pd.to_numeric(forecast["predicted_demand_points"], errors="coerce").fillna(0)
    forecast["lsoa_share"] = pd.to_numeric(forecast["lsoa_share"], errors="coerce").fillna(0)

    # fill coordinates from panel
    lsoa_coords = (
        panel.groupby("LSOA code", as_index=False)
        .agg(latitude=("latitude", "median"), longitude=("longitude", "median"))
    )
    forecast = forecast.merge(lsoa_coords, on="LSOA code", how="left")

    # fallback to LAD median for any still missing
    lad_coords = (
        forecast.dropna(subset=["latitude", "longitude"])
        .groupby("lad_code", as_index=False)
        .agg(lat_fill=("latitude", "median"), lon_fill=("longitude", "median"))
    )
    forecast = forecast.merge(lad_coords, on="lad_code", how="left")
    forecast["latitude"] = forecast["latitude"].fillna(forecast["lat_fill"])
    forecast["longitude"] = forecast["longitude"].fillna(forecast["lon_fill"])
    forecast = forecast.drop(columns=["lat_fill", "lon_fill"])

    q90 = forecast["predicted_demand_points"].quantile(0.90)
    q75 = forecast["predicted_demand_points"].quantile(0.75)

    forecast["allocation_tier"] = "Routine baseline coverage"
    forecast.loc[forecast["predicted_demand_points"] >= q75, "allocation_tier"] = "Reserve / spike watch"
    forecast.loc[forecast["predicted_demand_points"] >= q90, "allocation_tier"] = "Priority patrol and problem-solving"

    total = forecast["predicted_demand_points"].sum()
    forecast["capacity_units_per_100"] = (forecast["predicted_demand_points"] / total * 100) if total > 0 else 0.0

    return forecast


def percentile_rank(series: pd.Series) -> pd.Series:
    return series.rank(pct=True, method="average").fillna(0)


def create_recent_summary(panel: pd.DataFrame, context: pd.DataFrame) -> pd.DataFrame:
    panel_dates = panel.copy()
    panel_dates["Month"] = pd.to_datetime(panel_dates["Month"])

    latest_months = sorted(panel_dates["Month"].unique())[-12:]
    recent = panel_dates[panel_dates["Month"].isin(latest_months)]

    summary = (
        recent.groupby("LSOA code", as_index=False)
        .agg(
            recent_12m_demand=("demand_points", "sum"),
            recent_12m_incidents=("incidents", "sum"),
            recent_12m_high_harm=("high_harm_incidents", "sum"),
        )
    )

    summary["high_harm_share"] = (
        summary["recent_12m_high_harm"] / summary["recent_12m_incidents"].replace(0, np.nan)
    ).fillna(0)

    summary = summary.merge(context[["LSOA code", "population"]], on="LSOA code", how="left")
    summary["population"] = summary["population"].fillna(0)
    summary["recent_demand_rate_1000"] = (
        summary["recent_12m_demand"] / summary["population"].replace(0, np.nan) * 1000
    ).fillna(0)

    return summary


def create_area_records(forecast, panel, context, recent_summary):
    coordinates = (
        panel.groupby("LSOA code", as_index=False)
        .agg(LSOA_name=("LSOA_name", "last"), longitude=("longitude", "mean"), latitude=("latitude", "mean"))
    )

    area_data = (
        forecast
        .merge(coordinates, on="LSOA code", how="left")
        .merge(recent_summary, on="LSOA code", how="left")
        .merge(context.drop(columns=["population"], errors="ignore"), on="LSOA code", how="left")
    )

    for col in ["population", "recent_12m_demand", "recent_12m_incidents",
                "recent_12m_high_harm", "high_harm_share", "recent_demand_rate_1000"]:
        area_data[col] = area_data[col].fillna(0)

    area_data["predicted_demand_rate_1000"] = (
        area_data["predicted_demand_points"] / area_data["population"].replace(0, np.nan) * 1000
    ).fillna(0)

    area_data["predicted_rank"] = percentile_rank(area_data["predicted_demand_points"])
    area_data["balanced_review_score"] = area_data["predicted_rank"]
    max_predicted = max(area_data["predicted_demand_points"].max(), 1)

    areas = []
    for _, row in area_data.iterrows():
        lsoa_name = row["official_lsoa_name"] if pd.notna(row.get("official_lsoa_name")) else row.get("LSOA_name", row["LSOA code"])
        local_authority = row["local_authority"] if pd.notna(row.get("local_authority")) else row.get("lad_code", "Unknown LAD")

        # use forecast coordinates if panel coordinates are missing
        lat = row.get("latitude_x") or row.get("latitude") or row.get("latitude_y")
        lon = row.get("longitude_x") or row.get("longitude") or row.get("longitude_y")

        longitude = None if pd.isna(lon) else float(lon)
        latitude = None if pd.isna(lat) else float(lat)

        areas.append({
            "code": str(row["LSOA code"]),
            "name": str(lsoa_name),
            "shortName": str(row.get("LSOA_name", row["LSOA code"])),
            "localAuthority": str(local_authority),
            "ladCode": str(row.get("lad_code", "")),
            "longitude": longitude,
            "latitude": latitude,
            "predictedDemand": round(float(row["predicted_demand_points"]), 2),
            "originalPredictedDemand": round(float(row["predicted_demand_points"]), 2),
            "contextPredictedDemand": round(float(row["predicted_demand_points"]), 2),
            "lsoaShare": round(float(row.get("lsoa_share", 0)), 6),
            "demandRate1000": round(float(row["predicted_demand_rate_1000"]), 2),
            "recentDemandRate1000": round(float(row.get("recent_demand_rate_1000", 0)), 2),
            "population": int(row.get("population", 0)),
            "recentMean": 0,
            "uplift": 0,
            "spikeZ": 0,
            "originalTier": str(row["allocation_tier"]),
            "recent12Demand": round(float(row.get("recent_12m_demand", 0)), 2),
            "recent12Incidents": round(float(row.get("recent_12m_incidents", 0)), 0),
            "recent12HighHarm": round(float(row.get("recent_12m_high_harm", 0)), 0),
            "highHarmShare": round(float(row.get("high_harm_share", 0)), 4),
            "recentTopDecileMonths": 0,
            "repeatAttentionRisk": "Low",
            "historicPercentile": 0,
            "balancedScore": round(float(row["balanced_review_score"]), 5),
            "demandRank": round(float(row["predicted_rank"]), 5),
            "rateRank": 0,
            "contextRank": 0,
            "imdScore": round(float(row["imd_score"]), 2) if pd.notna(row.get("imd_score")) else 0,
            "imdDecile": int(row["imd_decile"]) if pd.notna(row.get("imd_decile")) else 0,
            "incomeScore": round(float(row["income_score"]), 3) if pd.notna(row.get("income_score")) else 0,
            "incomeDecile": int(row["income_decile"]) if pd.notna(row.get("income_decile")) else 0,
            "employmentScore": round(float(row["employment_score"]), 3) if pd.notna(row.get("employment_score")) else 0,
            "employmentDecile": int(row["employment_decile"]) if pd.notna(row.get("employment_decile")) else 0,
            "educationScore": round(float(row["education_score"]), 2) if pd.notna(row.get("education_score")) else 0,
            "educationDecile": int(row["education_decile"]) if pd.notna(row.get("education_decile")) else 0,
            "childIncomeScore": round(float(row["child_income_score"]), 3) if pd.notna(row.get("child_income_score")) else 0,
            "childIncomeDecile": int(row["child_income_decile"]) if pd.notna(row.get("child_income_decile")) else 0,
            "contextAvailable": bool(row.get("population", 0) > 0),
            "contextAlerts": [],
            "sizeScore": round(float(row["predicted_demand_points"]) / max_predicted, 5),
        })

    return areas


def create_dashboard_payload(panel, crime_type_summary, monthly_summary, context, forecast, incident_rows):
    recent_summary = create_recent_summary(panel, context)
    areas = create_area_records(forecast, panel, context, recent_summary)

    monthly_records = [
        {"month": str(row["Month"]), "incidents": round(float(row["incidents"]), 2),
         "demand": round(float(row["demand_points"]), 2), "highHarm": round(float(row["high_harm_incidents"]), 2)}
        for _, row in monthly_summary.iterrows()
    ]

    crime_type_records = [
        {"type": str(row["Crime type"]), "incidents": int(row["incidents"]),
         "demand": round(float(row["demand_points"]), 2), "weight": round(float(row["severity_weight"]), 2)}
        for _, row in crime_type_summary.iterrows()
    ]

    return {
        "meta": {
            "title": "Police Demand Review Map",
            "subtitle": "Dashboard based on the SSA7 LAD-to-LSOA socioeconomic crime model",
            "courseQuestion": "How can socioeconomic indicators be used to estimate crime and support policing resource planning?",
            "modelEquation": "Predicted LAD Crime Rate = intercept + β1(Persistent Absence) + β2(Mean Income) + β3(Crime Rank) + β4(Homelessness Rate)",
            "stakeholder": "UK police resource planners and policing decision-makers",
            "force": "Police.uk all-force archive",
            "dateRange": "Police archive period",
            "forecastMonth": str(forecastYear),
            "publisher": "Single Online Home National Digital Team / data.police.uk",
            "downloadPage": "https://data.police.uk/data/archive/2026-03.zip",
            "contextSource": "GOV.UK English Indices of Deprivation 2025, File 7",
            "contextDownload": "https://www.gov.uk/government/statistics/english-indices-of-deprivation-2025",
            "incidentRows": incident_rows,
            "lsoas": len(areas),
            "months": int(panel["Month"].nunique()),
            "crimeTypes": len(crime_type_records),
            "contextCoverage": sum(1 for area in areas if area["contextAvailable"]),
            "sourceNote": "The dashboard uses police.uk data for recent crime context and coordinates. The prediction shown comes from the SSA7 LAD-to-LSOA model.",
            "modelCaution": "This is a decision-support prototype, not an automatic deployment system or staffing calculator.",
            "modelUpgrade": "The old crime-history forecasting model has been replaced with the SSA7 socioeconomic LAD regression and LSOA allocation model.",
            "clusteringCenters": [],
        },
        "areas": areas,
        "monthly": monthly_records,
        "crimeTypes": crime_type_records,
        "metrics": [{
            "model": "SSA7 LAD-to-LSOA socioeconomic allocation model",
            "testMonths": "2026",
            "mae": 0, "rmse": 0, "wape": 0, "recall": 0,
            "note": "Uses the SSA7 LAD regression output and distributes LAD predicted crime to LSOAs using the LSOA share weights.",
        }],
        "localAuthorities": sorted({area["localAuthority"] for area in areas if area["localAuthority"]}),
        "seriesByArea": {},
        "method": [
            {"step": "Estimate LAD crime", "plainText": "A linear regression model estimates LAD-level crime rate using persistent absence, mean income, crime deprivation rank and homelessness rate."},
            {"step": "Convert rate to count", "plainText": "The predicted LAD crime rate is converted into a predicted LAD crime count using the LAD population."},
            {"step": "Allocate to LSOAs", "plainText": "The predicted LAD crime count is distributed to LSOAs using LSOA share weights based on crime rank, income rank, health deprivation and population density."},
            {"step": "Add IoD context only", "plainText": "IoD variables are shown in the dashboard for interpretation, but they do not change the SSA7 prediction or priority ranking."},
        ],
    }


def write_outputs(payload, forecast, monthly_summary):
    DATA_DIR.mkdir(exist_ok=True)
    forecast.to_csv(DATA_DIR / "ssa7_dashboard_forecast.csv", index=False)
    monthly_summary.to_csv(DATA_DIR / "ssa7_monthly_summary.csv", index=False)

    with open(DATA_DIR / "dashboard_data.js", "w", encoding="utf-8") as file:
        file.write("window.DASHBOARD_DATA = ")
        json.dump(payload, file, ensure_ascii=False, separators=(",", ":"))
        file.write(";")


def main():
    panel, crime_type_summary, monthly_summary, incident_rows = readCrimeData(crimeDataFile)
    context = load_context(deprecationFile)
    forecast = load_ssa7_forecast(LSOAPredictFile, panel)

    payload = create_dashboard_payload(
        panel=panel,
        crime_type_summary=crime_type_summary,
        monthly_summary=monthly_summary,
        context=context,
        forecast=forecast,
        incident_rows=incident_rows,
    )

    write_outputs(payload, forecast, monthly_summary)

    print(json.dumps({
        "areas": len(payload["areas"]),
        "incidentRows": payload["meta"]["incidentRows"],
        "contextCoverage": payload["meta"]["contextCoverage"],
        "dashboardFile": str(DATA_DIR / "dashboard_data.js"),
    }, indent=2))


if __name__ == "__main__":
    main()