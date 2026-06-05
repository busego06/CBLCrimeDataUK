from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUTPUTS = ROOT / "modeling" / "initial_demand_model" / "outputs"
DATA_DIR = Path(__file__).resolve().parent / "data"
LOCAL_FALLBACK_OUTPUTS = ROOT.parents[1] / "outputs"
IOD_FILE = DATA_DIR / "File_7_IoD2025_All_Ranks_Scores_Deciles_Population_Denominators.csv"


LAG_FEATURES = [
    "lag_1",
    "lag_2",
    "lag_3",
    "roll_3",
    "roll_6",
    "lag_12",
    "prev_mean",
    "recent_trend",
    "month_sin",
    "month_cos",
]

CONTEXT_FEATURES = [
    "log_population",
    "income_score",
    "employment_score",
    "education_score",
    "children_score",
    "adult_skills_score",
]

MODEL_FEATURES = LAG_FEATURES + CONTEXT_FEATURES


def output_file(name: str) -> Path:
    repo_path = OUTPUTS / name
    if repo_path.exists():
        return repo_path
    fallback_path = LOCAL_FALLBACK_OUTPUTS / name
    if fallback_path.exists():
        return fallback_path
    raise FileNotFoundError(f"Could not find {name} in {OUTPUTS} or {LOCAL_FALLBACK_OUTPUTS}")


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: object, default: int = 0) -> int:
    try:
        if pd.isna(value):
            return default
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def _pct_rank(series: pd.Series) -> pd.Series:
    return series.rank(pct=True, method="average").fillna(0.0)


def load_context() -> pd.DataFrame:
    if not IOD_FILE.exists():
        raise FileNotFoundError(
            f"Missing {IOD_FILE.name}. Download it from the official GOV.UK English Indices of Deprivation 2025 release."
        )

    usecols = [
        "LSOA code (2021)",
        "LSOA name (2021)",
        "Local Authority District name (2024)",
        "Index of Multiple Deprivation (IMD) Score",
        "Index of Multiple Deprivation (IMD) Decile (where 1 is most deprived 10% of LSOAs)",
        "Income Score (rate)",
        "Income Decile (where 1 is most deprived 10% of LSOAs)",
        "Employment Score (rate)",
        "Employment Decile (where 1 is most deprived 10% of LSOAs)",
        "Education, Skills and Training Score",
        "Education, Skills and Training Decile (where 1 is most deprived 10% of LSOAs)",
        "Income Deprivation Affecting Children Index (IDACI) Score (rate)",
        "Income Deprivation Affecting Children Index (IDACI) Decile (where 1 is most deprived 10% of LSOAs)",
        "Children and Young People Sub-domain Score",
        "Adult Skills Sub-domain Score",
        "Total population: mid 2022",
        "Dependent Children aged 0-15: mid 2022",
        "Older population aged 60 and over: mid 2022",
        "Working age population 18-66 (for use with Employment Deprivation Domain): mid 2022",
    ]
    df = pd.read_csv(IOD_FILE, usecols=usecols)
    df = df.rename(
        columns={
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
            "Children and Young People Sub-domain Score": "children_score",
            "Adult Skills Sub-domain Score": "adult_skills_score",
            "Total population: mid 2022": "population",
            "Dependent Children aged 0-15: mid 2022": "children_population",
            "Older population aged 60 and over: mid 2022": "older_population",
            "Working age population 18-66 (for use with Employment Deprivation Domain): mid 2022": "working_age_population",
        }
    )
    numeric_cols = [c for c in df.columns if c not in {"LSOA code", "official_lsoa_name", "local_authority"}]
    df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors="coerce")
    df["log_population"] = np.log1p(df["population"].clip(lower=0))
    df["deprivation_pressure"] = 11 - df["imd_decile"]
    df["income_pressure"] = 11 - df["income_decile"]
    df["education_pressure"] = 11 - df["education_decile"]
    df["child_income_pressure"] = 11 - df["child_income_decile"]
    return df


def make_april_features(panel: pd.DataFrame, context: pd.DataFrame) -> pd.DataFrame:
    rows = []
    apr_month = pd.Timestamp("2026-04-01")
    for code, group in panel.sort_values("Month").groupby("LSOA code"):
        s = group.set_index("Month")["demand_points"].sort_index()
        latest = group.sort_values("Month").iloc[-1]
        lags = {
            "lag_1": s.iloc[-1] if len(s) >= 1 else 0.0,
            "lag_2": s.iloc[-2] if len(s) >= 2 else 0.0,
            "lag_3": s.iloc[-3] if len(s) >= 3 else 0.0,
            "roll_3": s.tail(3).mean() if len(s) else 0.0,
            "roll_6": s.tail(6).mean() if len(s) else 0.0,
            "prev_mean": s.mean() if len(s) else 0.0,
            "recent_trend": (s.tail(3).mean() - s.iloc[-6:-3].mean()) if len(s) >= 6 else 0.0,
            "month_sin": np.sin(2 * np.pi * apr_month.month / 12),
            "month_cos": np.cos(2 * np.pi * apr_month.month / 12),
        }
        lag_12_month = pd.Timestamp("2025-04-01")
        lags["lag_12"] = float(s.get(lag_12_month, s.tail(12).mean() if len(s) else 0.0))
        rows.append(
            {
                "LSOA code": code,
                "LSOA_name": latest.get("LSOA_name", code),
                "longitude": latest.get("longitude", 0.0),
                "latitude": latest.get("latitude", 0.0),
                **lags,
            }
        )
    return pd.DataFrame(rows).merge(context, on="LSOA code", how="left")


def fit_contextual_ridge(panel_context: pd.DataFrame, april_features: pd.DataFrame) -> tuple[pd.Series, dict]:
    model_df = panel_context.dropna(subset=MODEL_FEATURES + ["demand_points"]).copy()
    model_df["Month"] = pd.to_datetime(model_df["Month"])
    train = model_df[(model_df["Month"] >= "2023-10-01") & (model_df["Month"] <= "2025-09-01")]
    test = model_df[(model_df["Month"] >= "2025-10-01") & (model_df["Month"] <= "2026-03-01")]

    X_train = train[MODEL_FEATURES].astype(float).to_numpy()
    y_train = train["demand_points"].astype(float).to_numpy()
    X_test = test[MODEL_FEATURES].astype(float).to_numpy()
    y_test = test["demand_points"].astype(float).to_numpy()
    X_april = april_features[MODEL_FEATURES].astype(float).to_numpy()

    mu = X_train.mean(axis=0)
    sigma = X_train.std(axis=0)
    sigma[sigma == 0] = 1.0
    X_train_z = (X_train - mu) / sigma
    X_test_z = (X_test - mu) / sigma
    X_april_z = (X_april - mu) / sigma

    # Manual ridge regression. The intercept column is not penalised.
    alpha = 250.0
    X_aug = np.column_stack([np.ones(len(X_train_z)), X_train_z])
    penalty = np.eye(X_aug.shape[1]) * alpha
    penalty[0, 0] = 0.0
    beta = np.linalg.solve(X_aug.T @ X_aug + penalty, X_aug.T @ y_train)

    pred_test = np.maximum(0.0, np.column_stack([np.ones(len(X_test_z)), X_test_z]) @ beta)
    pred_april = np.maximum(0.0, np.column_stack([np.ones(len(X_april_z)), X_april_z]) @ beta)

    mae = float(np.mean(np.abs(pred_test - y_test)))
    rmse = float(np.sqrt(np.mean((pred_test - y_test) ** 2)))
    wape = float(np.sum(np.abs(pred_test - y_test)) / max(1.0, np.sum(np.abs(y_test))))

    test_compare = test[["Month", "LSOA code", "demand_points"]].copy()
    test_compare["pred"] = pred_test
    recalls = []
    for _, month_rows in test_compare.groupby("Month"):
        n = max(1, int(round(len(month_rows) * 0.10)))
        actual_top = set(month_rows.nlargest(n, "demand_points")["LSOA code"])
        pred_top = set(month_rows.nlargest(n, "pred")["LSOA code"])
        recalls.append(len(actual_top & pred_top) / n)
    recall = float(np.mean(recalls))

    metrics = {
        "model": "Context-aware ridge model",
        "testMonths": "2025-10 to 2026-03",
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "wape": round(wape * 100, 1),
        "recall": round(recall * 100, 1),
        "note": "Uses lag, seasonality, population, income, employment and education context.",
    }
    return pd.Series(pred_april, index=april_features["LSOA code"]), metrics


def build_dashboard_data() -> dict:
    forecast = pd.read_csv(output_file("april_2026_lsoa_priority_forecast.csv"))
    panel = pd.read_csv(output_file("lsoa_month_panel.csv"))
    monthly = pd.read_csv(output_file("monthly_force_summary.csv"))
    crime_types = pd.read_csv(output_file("crime_type_summary.csv"))
    metrics = pd.read_csv(output_file("model_metrics.csv"))
    context = load_context()
    with open(output_file("model_summary.json"), "r", encoding="utf-8") as f:
        summary = json.load(f)

    panel["Month"] = pd.to_datetime(panel["Month"])
    panel_context = panel.merge(context, on="LSOA code", how="left")
    april_features = make_april_features(panel, context)
    contextual_pred, contextual_metric = fit_contextual_ridge(panel_context, april_features)

    latest_months = sorted(panel["Month"].unique())[-12:]
    recent = panel[panel["Month"].isin(latest_months)].copy()
    recent_context = recent.merge(context[["LSOA code", "population"]], on="LSOA code", how="left")

    recent_summary = (
        recent_context.groupby("LSOA code")
        .agg(
            recent_12m_demand=("demand_points", "sum"),
            recent_12m_incidents=("incidents", "sum"),
            recent_12m_high_harm=("high_harm_incidents", "sum"),
            last_3m_demand=("demand_points", lambda s: s.tail(3).sum()),
            last_3m_incidents=("incidents", lambda s: s.tail(3).sum()),
            population=("population", "first"),
        )
        .reset_index()
    )

    recent_summary["high_harm_share"] = (
        recent_summary["recent_12m_high_harm"]
        / recent_summary["recent_12m_incidents"].replace(0, pd.NA)
    ).fillna(0)
    recent_summary["recent_demand_rate_1000"] = (
        recent_summary["recent_12m_demand"] / recent_summary["population"].replace(0, pd.NA) * 1000
    ).fillna(0)

    recent_ranked = recent.copy()
    recent_ranked["month_rank_pct"] = recent_ranked.groupby("Month")["demand_points"].rank(pct=True)
    repeat = (
        recent_ranked.assign(is_top_decile=recent_ranked["month_rank_pct"] >= 0.90)
        .groupby("LSOA code")
        .agg(recent_top_decile_months=("is_top_decile", "sum"))
        .reset_index()
    )

    history = panel.copy()
    history["history_rank_pct"] = history.groupby("Month")["demand_points"].rank(pct=True)
    history_pct = (
        history.groupby("LSOA code")
        .agg(mean_historic_percentile=("history_rank_pct", "mean"))
        .reset_index()
    )

    area_data = (
        forecast.merge(recent_summary, on="LSOA code", how="left")
        .merge(repeat, on="LSOA code", how="left")
        .merge(history_pct, on="LSOA code", how="left")
        .merge(context, on="LSOA code", how="left", suffixes=("", "_context"))
    )
    area_data["contextual_predicted_demand_points"] = area_data["LSOA code"].map(contextual_pred).fillna(
        area_data["predicted_demand_points"]
    )
    # Use a conservative hybrid: mostly the tested original forecast, with a
    # contextual model contribution that reflects population/economic/education
    # structure without letting static context dominate local history.
    area_data["recommended_predicted_demand"] = (
        0.70 * area_data["predicted_demand_points"]
        + 0.30 * area_data["contextual_predicted_demand_points"]
    )
    area_data["predicted_demand_rate_1000"] = (
        area_data["recommended_predicted_demand"] / area_data["population"].replace(0, pd.NA) * 1000
    ).fillna(0)

    for col in [
        "recommended_predicted_demand",
        "predicted_demand_rate_1000",
        "uplift_vs_recent_mean",
        "spike_z",
        "imd_score",
        "income_score",
        "employment_score",
        "education_score",
        "recent_demand_rate_1000",
    ]:
        area_data[f"{col}_rank"] = _pct_rank(area_data[col].astype(float))

    area_data["context_pressure_rank"] = (
        area_data["income_score_rank"] * 0.35
        + area_data["education_score_rank"] * 0.35
        + area_data["employment_score_rank"] * 0.30
    )
    area_data["balanced_review_score"] = (
        area_data["recommended_predicted_demand_rank"] * 0.60
        + area_data["uplift_vs_recent_mean_rank"] * 0.20
        + area_data["context_pressure_rank"] * 0.20
    )

    max_pred = area_data["recommended_predicted_demand"].max()
    areas = []
    for _, row in area_data.iterrows():
        repeat_months = _safe_int(row.get("recent_top_decile_months"))
        repeat_risk = "High" if repeat_months >= 8 else "Medium" if repeat_months >= 4 else "Low"
        context_alerts = []
        if _safe_int(row.get("imd_decile"), 10) <= 2:
            context_alerts.append("high deprivation")
        if _safe_int(row.get("education_decile"), 10) <= 2:
            context_alerts.append("education pressure")
        if _safe_int(row.get("income_decile"), 10) <= 2:
            context_alerts.append("income pressure")

        local_authority = row.get("local_authority", "Unknown")
        if pd.isna(local_authority) or str(local_authority).lower() == "nan":
            local_authority = "Context unmatched"

        official_name = row.get("official_lsoa_name")
        if pd.isna(official_name) or not str(official_name).strip():
            official_name = row.get("LSOA_name", row["LSOA code"])

        areas.append(
            {
                "code": str(row["LSOA code"]),
                "name": str(official_name),
                "shortName": str(row.get("LSOA_name", row["LSOA code"])),
                "localAuthority": str(local_authority),
                "longitude": _safe_float(row.get("longitude")),
                "latitude": _safe_float(row.get("latitude")),
                "predictedDemand": round(_safe_float(row["recommended_predicted_demand"]), 2),
                "originalPredictedDemand": round(_safe_float(row["predicted_demand_points"]), 2),
                "contextPredictedDemand": round(_safe_float(row["contextual_predicted_demand_points"]), 2),
                "demandRate1000": round(_safe_float(row["predicted_demand_rate_1000"]), 2),
                "recentDemandRate1000": round(_safe_float(row.get("recent_demand_rate_1000")), 2),
                "population": _safe_int(row.get("population")),
                "recentMean": round(_safe_float(row.get("recent_12m_mean")), 2),
                "uplift": round(_safe_float(row.get("uplift_vs_recent_mean")), 4),
                "spikeZ": round(_safe_float(row.get("spike_z")), 3),
                "originalTier": str(row.get("allocation_tier", "")),
                "recent12Demand": round(_safe_float(row.get("recent_12m_demand")), 2),
                "recent12Incidents": round(_safe_float(row.get("recent_12m_incidents")), 0),
                "recent12HighHarm": round(_safe_float(row.get("recent_12m_high_harm")), 0),
                "highHarmShare": round(_safe_float(row.get("high_harm_share")), 4),
                "recentTopDecileMonths": repeat_months,
                "repeatAttentionRisk": repeat_risk,
                "historicPercentile": round(_safe_float(row.get("mean_historic_percentile")), 4),
                "balancedScore": round(_safe_float(row.get("balanced_review_score")), 5),
                "demandRank": round(_safe_float(row.get("recommended_predicted_demand_rank")), 5),
                "rateRank": round(_safe_float(row.get("predicted_demand_rate_1000_rank")), 5),
                "contextRank": round(_safe_float(row.get("context_pressure_rank")), 5),
                "imdScore": round(_safe_float(row.get("imd_score")), 2),
                "imdDecile": _safe_int(row.get("imd_decile"), 10),
                "incomeScore": round(_safe_float(row.get("income_score")), 3),
                "incomeDecile": _safe_int(row.get("income_decile"), 10),
                "employmentScore": round(_safe_float(row.get("employment_score")), 3),
                "employmentDecile": _safe_int(row.get("employment_decile"), 10),
                "educationScore": round(_safe_float(row.get("education_score")), 2),
                "educationDecile": _safe_int(row.get("education_decile"), 10),
                "childIncomeScore": round(_safe_float(row.get("child_income_score")), 3),
                "childIncomeDecile": _safe_int(row.get("child_income_decile"), 10),
                "contextAlerts": context_alerts,
                "sizeScore": round(_safe_float(row["recommended_predicted_demand"]) / max_pred, 5),
            }
        )

    panel_small = panel.copy()
    panel_small["Month"] = panel_small["Month"].dt.strftime("%Y-%m")
    series_by_area = {}
    for code, rows in panel_small.groupby("LSOA code"):
        series_by_area[str(code)] = [
            {
                "month": str(r["Month"]),
                "incidents": round(_safe_float(r["incidents"]), 2),
                "demand": round(_safe_float(r["demand_points"]), 2),
                "highHarm": round(_safe_float(r["high_harm_incidents"]), 2),
            }
            for _, r in rows.sort_values("Month").iterrows()
        ]

    monthly_records = [
        {
            "month": str(row["Month"]),
            "incidents": round(_safe_float(row["incidents"]), 2),
            "demand": round(_safe_float(row["demand_points"]), 2),
            "highHarm": round(_safe_float(row["high_harm_incidents"]), 2),
        }
        for _, row in monthly.iterrows()
    ]

    crime_records = [
        {
            "type": str(row["Crime type"]),
            "incidents": _safe_int(row["incidents"]),
            "demand": round(_safe_float(row["demand_points"]), 2),
            "weight": round(_safe_float(row["severity_weight"]), 2),
        }
        for _, row in crime_types.sort_values("demand_points", ascending=False).iterrows()
    ]

    metric_records = [
        {
            "model": str(row["model"]),
            "testMonths": str(row["test_months"]),
            "mae": round(_safe_float(row["MAE_LSOA_month"]), 2),
            "rmse": round(_safe_float(row["RMSE_LSOA_month"]), 2),
            "wape": round(_safe_float(row["WAPE"]) * 100, 1),
            "recall": round(_safe_float(row["top_10pct_hotspot_recall"]) * 100, 1),
            "note": "Uses lag and seasonality only.",
        }
        for _, row in metrics.iterrows()
    ]
    metric_records.append(contextual_metric)

    local_authorities = sorted(
        {a["localAuthority"] for a in areas if a["localAuthority"] not in {"Unknown", "Context unmatched"}}
    )
    context_coverage = int(sum(1 for a in areas if a["population"] > 0))

    return {
        "meta": {
            "title": "Police Demand Planning Dashboard",
            "subtitle": "Monthly decision-support prototype for non-technical police resource planners",
            "courseQuestion": "How can data-driven estimates of police demand be used to inform the effective organisation and allocation of policing resources in the United Kingdom?",
            "stakeholder": "UK police resource planners and policing decision-makers",
            "force": summary["source"]["force"],
            "dateRange": summary["source"]["date_range"],
            "forecastMonth": summary["forecast"]["forecast_month"],
            "publisher": summary["source"]["publisher"],
            "downloadPage": summary["source"]["download_page"],
            "contextSource": "GOV.UK English Indices of Deprivation 2025, File 7: ranks, scores, deciles and population denominators",
            "contextDownload": "https://www.gov.uk/government/statistics/english-indices-of-deprivation-2025",
            "incidentRows": summary["dataset"]["incident_rows"],
            "lsoas": summary["dataset"]["lsoas"],
            "months": summary["dataset"]["months"],
            "crimeTypes": summary["dataset"]["crime_types"],
            "contextCoverage": context_coverage,
            "sourceNote": "Uses official police.uk recorded crime data and GOV.UK IoD 2025 context data. Coordinates are anonymised by police.uk and are not street-exact.",
            "modelCaution": "This is a decision-support prototype, not an automatic deployment system or staffing calculator.",
            "modelUpgrade": "Forecasts now combine tested local crime-history patterns with official population, income, employment and education context. Context is shown as plain-language local profile data for interpretation.",
        },
        "areas": areas,
        "monthly": monthly_records,
        "crimeTypes": crime_records,
        "metrics": metric_records,
        "localAuthorities": local_authorities,
        "seriesByArea": series_by_area,
        "method": [
            {
                "step": "Estimate demand",
                "plainText": "Recorded crimes are converted into severity-weighted demand points using crime type and transparent weights.",
            },
            {
                "step": "Add context",
                "plainText": "Official GOV.UK IoD 2025 variables add population, income, employment and education context so the forecast is not only a crime-history signal.",
            },
            {
                "step": "Plan attention",
                "plainText": "The dashboard combines demand, severity, recent change and local context into one priority, reserve or routine review tier.",
            },
            {
                "step": "Check context",
                "plainText": "The dashboard shows deprivation, income, employment and education indicators next to each area so planners can interpret results with local knowledge.",
            },
        ],
    }


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    data = build_dashboard_data()
    out = DATA_DIR / "dashboard_data.js"
    with open(out, "w", encoding="utf-8") as f:
        f.write("window.DASHBOARD_DATA = ")
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";")
    print(f"Wrote {out}")
    print(
        f"Areas: {len(data['areas'])}; months: {len(data['monthly'])}; context coverage: {data['meta']['contextCoverage']}"
    )


if __name__ == "__main__":
    main()
