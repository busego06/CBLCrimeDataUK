from __future__ import annotations

import argparse
import csv
import json
import math
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = Path(__file__).resolve().parent
DATA_DIR = DASHBOARD_DIR / "data"
DEFAULT_ARCHIVE = ROOT / "modeling" / "initial_demand_model" / "data" / "police_uk_archive_2026_03.zip"
DEFAULT_IOD = DATA_DIR / "File_7_IoD2025_All_Ranks_Scores_Deciles_Population_Denominators.csv"
DEFAULT_CENTRES = ROOT.parents[1] / "dataShort" / "input.csv"

START_MONTH = "2023-04"
END_MONTH = "2026-03"
FORECAST_MONTH = "2026-04"


SEVERITY_WEIGHTS = {
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

DEMAND_SCALE_FEATURES = [
    "lag_1",
    "lag_2",
    "lag_3",
    "roll_3",
    "roll_6",
    "lag_12",
    "prev_mean",
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


@dataclass
class Standardiser:
    mean: np.ndarray
    std: np.ndarray

    def transform(self, x: np.ndarray) -> np.ndarray:
        return (x - self.mean) / self.std


def safe_float(value: object, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: object, default: int = 0) -> int:
    try:
        if pd.isna(value):
            return default
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def pct_rank(series: pd.Series) -> pd.Series:
    return series.rank(pct=True, method="average").fillna(0.0)


def derive_area_name(lsoa_name: object) -> str:
    name = str(lsoa_name or "").strip()
    if not name or name.lower() == "nan":
        return "Context unmatched"
    cleaned = re.sub(r"\s+\d+[A-Z]?$", "", name).strip()
    return cleaned or name


def load_clustering_centres(path: Path) -> list[dict]:
    centres = []
    if not path.exists():
        return centres
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.reader(f):
            if len(row) < 3:
                continue
            try:
                centres.append(
                    {
                        "lat": float(row[0]),
                        "lon": float(row[1]),
                        "weight": float(row[2]),
                    }
                )
            except ValueError:
                continue
    return centres


def archive_street_members(zf: zipfile.ZipFile) -> list[str]:
    members = []
    for name in zf.namelist():
        base = Path(name).name
        if not base.endswith("-street.csv"):
            continue
        month = base[:7]
        if START_MONTH <= month <= END_MONTH:
            members.append(name)
    return sorted(members)


def read_archive_to_panel(path: Path, chunk_size: int = 250_000) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, int]:
    if not path.exists():
        raise FileNotFoundError(f"Missing official police.uk archive ZIP: {path}")

    usecols = [
        "Month",
        "Longitude",
        "Latitude",
        "LSOA code",
        "LSOA name",
        "Crime type",
    ]
    monthly_parts = []
    crime_parts = []
    incident_rows = 0

    with zipfile.ZipFile(path) as zf:
        members = archive_street_members(zf)
        if not members:
            raise ValueError(f"No street-level crime CSVs between {START_MONTH} and {END_MONTH} were found in {path}")

        for index, member in enumerate(members, start=1):
            print(f"[{index}/{len(members)}] aggregating {Path(member).name}")
            with zf.open(member) as f:
                for chunk in pd.read_csv(f, usecols=usecols, chunksize=chunk_size, low_memory=False):
                    chunk = chunk[chunk["LSOA code"].notna()].copy()
                    if chunk.empty:
                        continue
                    chunk["Month"] = pd.PeriodIndex(chunk["Month"], freq="M").astype(str)
                    chunk["Longitude"] = pd.to_numeric(chunk["Longitude"], errors="coerce")
                    chunk["Latitude"] = pd.to_numeric(chunk["Latitude"], errors="coerce")
                    chunk["severity_weight"] = chunk["Crime type"].map(SEVERITY_WEIGHTS).fillna(1.0)
                    chunk["high_harm_flag"] = chunk["severity_weight"].ge(4.0).astype(int)
                    valid_coord = chunk["Longitude"].notna() & chunk["Latitude"].notna()
                    chunk["coord_count"] = valid_coord.astype(int)
                    chunk["lon_sum"] = chunk["Longitude"].where(valid_coord, 0.0)
                    chunk["lat_sum"] = chunk["Latitude"].where(valid_coord, 0.0)
                    incident_rows += len(chunk)

                    monthly_parts.append(
                        chunk.groupby(["LSOA code", "LSOA name", "Month"], as_index=False).agg(
                            incidents=("Crime type", "size"),
                            demand_points=("severity_weight", "sum"),
                            high_harm_incidents=("high_harm_flag", "sum"),
                            lon_sum=("lon_sum", "sum"),
                            lat_sum=("lat_sum", "sum"),
                            coord_count=("coord_count", "sum"),
                        )
                    )
                    crime_parts.append(
                        chunk.groupby("Crime type", as_index=False).agg(
                            incidents=("Crime type", "size"),
                            demand_points=("severity_weight", "sum"),
                            severity_weight=("severity_weight", "first"),
                        )
                    )

    monthly_raw = pd.concat(monthly_parts, ignore_index=True)
    monthly = (
        monthly_raw.sort_values("Month")
        .groupby(["LSOA code", "Month"], as_index=False)
        .agg(
            LSOA_name=("LSOA name", "last"),
            incidents=("incidents", "sum"),
            demand_points=("demand_points", "sum"),
            high_harm_incidents=("high_harm_incidents", "sum"),
            lon_sum=("lon_sum", "sum"),
            lat_sum=("lat_sum", "sum"),
            coord_count=("coord_count", "sum"),
        )
    )
    monthly["longitude"] = np.where(monthly["coord_count"] > 0, monthly["lon_sum"] / monthly["coord_count"], np.nan)
    monthly["latitude"] = np.where(monthly["coord_count"] > 0, monthly["lat_sum"] / monthly["coord_count"], np.nan)

    months = pd.period_range(START_MONTH, END_MONTH, freq="M").astype(str)
    lsoa_meta = (
        monthly.sort_values("Month")
        .groupby("LSOA code", as_index=False)
        .agg(
            LSOA_name=("LSOA_name", "last"),
            longitude=("longitude", "mean"),
            latitude=("latitude", "mean"),
        )
    )
    full_index = pd.MultiIndex.from_product(
        [lsoa_meta["LSOA code"], months], names=["LSOA code", "Month"]
    ).to_frame(index=False)
    panel = full_index.merge(lsoa_meta, on="LSOA code", how="left")
    panel = panel.merge(
        monthly[["LSOA code", "Month", "incidents", "demand_points", "high_harm_incidents"]],
        on=["LSOA code", "Month"],
        how="left",
    )
    for col in ["incidents", "demand_points", "high_harm_incidents"]:
        panel[col] = panel[col].fillna(0.0)

    crime_type_summary = (
        pd.concat(crime_parts, ignore_index=True)
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


def add_features(panel: pd.DataFrame) -> pd.DataFrame:
    panel = panel.sort_values(["LSOA code", "Month"]).copy()
    g = panel.groupby("LSOA code", group_keys=False)
    for lag in [1, 2, 3, 12]:
        panel[f"lag_{lag}"] = g["demand_points"].shift(lag)
    shifted = g["demand_points"].shift(1)
    panel["roll_3"] = shifted.groupby(panel["LSOA code"]).rolling(3, min_periods=1).mean().reset_index(level=0, drop=True)
    panel["roll_6"] = shifted.groupby(panel["LSOA code"]).rolling(6, min_periods=1).mean().reset_index(level=0, drop=True)
    panel["prev_mean"] = shifted.groupby(panel["LSOA code"]).expanding(min_periods=1).mean().reset_index(level=0, drop=True)
    panel["recent_trend"] = panel["lag_1"] - panel["lag_3"]
    month_no = pd.PeriodIndex(panel["Month"], freq="M").month
    panel["month_sin"] = np.sin(2 * np.pi * month_no / 12.0)
    panel["month_cos"] = np.cos(2 * np.pi * month_no / 12.0)
    panel[LAG_FEATURES] = panel[LAG_FEATURES].fillna(0.0)
    return panel


def transformed_features(frame: pd.DataFrame) -> np.ndarray:
    transformed = frame[LAG_FEATURES].copy()
    for col in DEMAND_SCALE_FEATURES:
        transformed[col] = np.log1p(transformed[col].clip(lower=0.0))
    transformed["recent_trend"] = np.sign(transformed["recent_trend"]) * np.log1p(np.abs(transformed["recent_trend"]))
    return transformed.to_numpy(dtype=float)


def fit_ridge_log_model(train: pd.DataFrame, alpha: float) -> tuple[np.ndarray, Standardiser, float]:
    x = transformed_features(train)
    y = np.log1p(train["demand_points"].to_numpy(dtype=float))
    mean = x.mean(axis=0)
    std = x.std(axis=0)
    std[std == 0] = 1.0
    scaler = Standardiser(mean=mean, std=std)
    xs = scaler.transform(x)
    design = np.column_stack([np.ones(len(xs)), xs])
    penalty = np.eye(design.shape[1]) * alpha
    penalty[0, 0] = 0.0
    try:
        beta = np.linalg.solve(design.T @ design + penalty, design.T @ y)
    except np.linalg.LinAlgError:
        beta = np.linalg.pinv(design.T @ design + penalty) @ (design.T @ y)
    log_cap = float(np.log1p(train["demand_points"].max() * 1.20))
    return beta, scaler, log_cap


def predict_ridge(frame: pd.DataFrame, beta: np.ndarray, scaler: Standardiser, log_cap: float | None = None) -> np.ndarray:
    xs = scaler.transform(transformed_features(frame))
    design = np.column_stack([np.ones(len(xs)), xs])
    log_pred = design @ beta
    if log_cap is not None:
        log_pred = np.clip(log_pred, 0.0, log_cap)
    return np.maximum(np.expm1(log_pred), 0.0)


def wape(actual: np.ndarray, pred: np.ndarray) -> float:
    return float(np.sum(np.abs(actual - pred)) / max(np.sum(np.abs(actual)), 1e-9))


def mae(actual: np.ndarray, pred: np.ndarray) -> float:
    return float(np.mean(np.abs(actual - pred)))


def rmse(actual: np.ndarray, pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((actual - pred) ** 2)))


def hotspot_recall(frame: pd.DataFrame, pred_col: str, actual_col: str = "demand_points", q: float = 0.90) -> float:
    recalls = []
    for _, month_df in frame.groupby("Month"):
        n = max(1, int(math.ceil(len(month_df) * (1 - q))))
        actual_top = set(month_df.nlargest(n, actual_col)["LSOA code"])
        pred_top = set(month_df.nlargest(n, pred_col)["LSOA code"])
        recalls.append(len(actual_top & pred_top) / len(actual_top))
    return float(np.mean(recalls))


def calibration_factor(actual: np.ndarray, pred: np.ndarray) -> float:
    return float(np.clip(np.sum(actual) / max(np.sum(pred), 1e-9), 0.75, 1.25))


def evaluate_models(featured: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, tuple[np.ndarray, Standardiser, float, float, float], dict]:
    usable = featured[featured["Month"] >= "2023-10"].copy()
    tune_train = usable[(usable["Month"] >= "2023-10") & (usable["Month"] <= "2025-03")]
    validation = usable[(usable["Month"] >= "2025-04") & (usable["Month"] <= "2025-09")].copy()
    model_train = usable[(usable["Month"] >= "2023-10") & (usable["Month"] <= "2025-09")]
    test = usable[(usable["Month"] >= "2025-10") & (usable["Month"] <= "2026-03")].copy()

    actual_validation = validation["demand_points"].to_numpy(dtype=float)
    best = {"alpha": 0.0, "score": float("inf"), "calibration": 1.0}
    alpha_results = []
    for alpha in [0.0, 0.1, 1.0, 10.0, 50.0, 100.0, 250.0]:
        beta, scaler, log_cap = fit_ridge_log_model(tune_train, alpha)
        raw = predict_ridge(validation, beta, scaler, log_cap)
        factor = calibration_factor(actual_validation, raw)
        score = wape(actual_validation, raw * factor)
        alpha_results.append({"alpha": alpha, "calibration_factor": factor, "validation_wape": score})
        if score < best["score"]:
            best = {"alpha": alpha, "score": score, "calibration": factor}

    tune_beta, tune_scaler, tune_log_cap = fit_ridge_log_model(tune_train, float(best["alpha"]))
    validation_ridge = predict_ridge(validation, tune_beta, tune_scaler, tune_log_cap) * float(best["calibration"])
    validation_roll = validation["roll_3"].to_numpy(dtype=float)
    best_blend = {"ridge_weight": 0.0, "score": float("inf")}
    blend_results = []
    for ridge_weight in [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
        pred = ridge_weight * validation_ridge + (1.0 - ridge_weight) * validation_roll
        score = wape(actual_validation, pred)
        blend_results.append({"alpha": best["alpha"], "ridge_weight": ridge_weight, "validation_wape": score})
        if score < best_blend["score"]:
            best_blend = {"ridge_weight": ridge_weight, "score": score}

    beta, scaler, log_cap = fit_ridge_log_model(model_train, float(best["alpha"]))
    test["ridge_pred"] = predict_ridge(test, beta, scaler, log_cap) * float(best["calibration"])
    test["rolling_3_pred"] = test["roll_3"].clip(lower=0)
    test["seasonal_naive_pred"] = np.where(test["lag_12"] > 0, test["lag_12"], test["roll_3"]).clip(min=0)
    test["hybrid_pred"] = float(best_blend["ridge_weight"]) * test["ridge_pred"] + (
        1.0 - float(best_blend["ridge_weight"])
    ) * test["rolling_3_pred"]

    metrics = []
    for name, col in [
        ("Rolling 3-month baseline", "rolling_3_pred"),
        ("Same-month-last-year baseline", "seasonal_naive_pred"),
        ("Ridge lag model", "ridge_pred"),
        ("Hybrid demand model", "hybrid_pred"),
    ]:
        actual = test["demand_points"].to_numpy(dtype=float)
        pred = test[col].to_numpy(dtype=float)
        metrics.append(
            {
                "model": name,
                "test_months": "2025-10 to 2026-03",
                "MAE_LSOA_month": mae(actual, pred),
                "RMSE_LSOA_month": rmse(actual, pred),
                "WAPE": wape(actual, pred),
                "top_10pct_hotspot_recall": hotspot_recall(test, col),
            }
        )

    tuning = {
        "best_alpha": float(best["alpha"]),
        "best_blend": float(best_blend["ridge_weight"]),
        "best_calibration": float(best["calibration"]),
        "alpha_results": alpha_results,
        "blend_results": blend_results,
    }
    return pd.DataFrame(metrics), test, (
        beta,
        scaler,
        log_cap,
        float(best_blend["ridge_weight"]),
        float(best["calibration"]),
    ), tuning


def forecast_next_month(panel: pd.DataFrame, model: tuple[np.ndarray, Standardiser, float, float, float]) -> pd.DataFrame:
    beta, scaler, log_cap, ridge_weight, calibration = model
    lsoa_meta = panel[["LSOA code", "LSOA_name", "longitude", "latitude"]].drop_duplicates("LSOA code")
    future = lsoa_meta.copy()
    future["Month"] = FORECAST_MONTH
    future["incidents"] = np.nan
    future["demand_points"] = np.nan
    future["high_harm_incidents"] = np.nan

    appended = pd.concat([panel, future], ignore_index=True, sort=False)
    featured = add_features(appended)
    future_featured = featured[featured["Month"] == FORECAST_MONTH].copy()
    future_featured["ridge_predicted_demand_points"] = predict_ridge(future_featured, beta, scaler, log_cap) * calibration
    future_featured["rolling_3_predicted_demand_points"] = future_featured["roll_3"].clip(lower=0)
    future_featured["predicted_demand_points"] = (
        ridge_weight * future_featured["ridge_predicted_demand_points"]
        + (1.0 - ridge_weight) * future_featured["rolling_3_predicted_demand_points"]
    )

    history = panel[panel["Month"] >= "2025-04"].copy()
    recent = (
        history.groupby("LSOA code", as_index=False)
        .agg(
            recent_12m_mean=("demand_points", "mean"),
            recent_12m_sd=("demand_points", "std"),
            recent_12m_incidents=("incidents", "sum"),
        )
    )
    future_featured = future_featured.merge(recent, on="LSOA code", how="left")
    future_featured["recent_12m_sd"] = future_featured["recent_12m_sd"].fillna(0.0)
    future_featured["uplift_vs_recent_mean"] = (
        future_featured["predicted_demand_points"] / future_featured["recent_12m_mean"].replace(0, np.nan) - 1
    ).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    future_featured["spike_z"] = (
        (future_featured["predicted_demand_points"] - future_featured["recent_12m_mean"])
        / future_featured["recent_12m_sd"].replace(0, np.nan)
    ).replace([np.inf, -np.inf], np.nan).fillna(0.0)

    q90 = future_featured["predicted_demand_points"].quantile(0.90)
    q75 = future_featured["predicted_demand_points"].quantile(0.75)
    future_featured["allocation_tier"] = "Routine baseline coverage"
    future_featured.loc[
        (future_featured["predicted_demand_points"] >= q75)
        & (future_featured["uplift_vs_recent_mean"] >= 0.20),
        "allocation_tier",
    ] = "Reserve / spike watch"
    future_featured.loc[future_featured["predicted_demand_points"] >= q90, "allocation_tier"] = (
        "Priority patrol and problem-solving"
    )
    future_featured["capacity_units_per_100"] = (
        future_featured["predicted_demand_points"] / future_featured["predicted_demand_points"].sum() * 100.0
    )
    return future_featured[
        [
            "LSOA code",
            "LSOA_name",
            "longitude",
            "latitude",
            "predicted_demand_points",
            "rolling_3_predicted_demand_points",
            "ridge_predicted_demand_points",
            "recent_12m_mean",
            "uplift_vs_recent_mean",
            "spike_z",
            "allocation_tier",
            "capacity_units_per_100",
        ]
    ].sort_values("predicted_demand_points", ascending=False)


def load_context(path: Path) -> pd.DataFrame:
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
    ]
    df = pd.read_csv(path, usecols=usecols)
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
        }
    )
    numeric_cols = [c for c in df.columns if c not in {"LSOA code", "official_lsoa_name", "local_authority"}]
    df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors="coerce")
    df["log_population"] = np.log1p(df["population"].clip(lower=0))
    return df


def make_april_features(panel: pd.DataFrame, context: pd.DataFrame) -> pd.DataFrame:
    rows = []
    april_month = pd.Timestamp(FORECAST_MONTH + "-01")
    for code, group in panel.sort_values("Month").groupby("LSOA code"):
        s = group.set_index("Month")["demand_points"].sort_index()
        latest = group.sort_values("Month").iloc[-1]
        rows.append(
            {
                "LSOA code": code,
                "LSOA_name": latest.get("LSOA_name", code),
                "longitude": latest.get("longitude", 0.0),
                "latitude": latest.get("latitude", 0.0),
                "lag_1": s.iloc[-1] if len(s) >= 1 else 0.0,
                "lag_2": s.iloc[-2] if len(s) >= 2 else 0.0,
                "lag_3": s.iloc[-3] if len(s) >= 3 else 0.0,
                "roll_3": s.tail(3).mean() if len(s) else 0.0,
                "roll_6": s.tail(6).mean() if len(s) else 0.0,
                "lag_12": float(s.get("2025-04", s.tail(12).mean() if len(s) else 0.0)),
                "prev_mean": s.mean() if len(s) else 0.0,
                "recent_trend": (s.tail(3).mean() - s.iloc[-6:-3].mean()) if len(s) >= 6 else 0.0,
                "month_sin": np.sin(2 * np.pi * april_month.month / 12),
                "month_cos": np.cos(2 * np.pi * april_month.month / 12),
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

    mu = X_train.mean(axis=0)
    sigma = X_train.std(axis=0)
    sigma[sigma == 0] = 1.0
    X_train_z = (X_train - mu) / sigma
    X_test_z = (X_test - mu) / sigma
    alpha = 250.0
    X_aug = np.column_stack([np.ones(len(X_train_z)), X_train_z])
    penalty = np.eye(X_aug.shape[1]) * alpha
    penalty[0, 0] = 0.0
    beta = np.linalg.solve(X_aug.T @ X_aug + penalty, X_aug.T @ y_train)

    pred_test = np.maximum(0.0, np.column_stack([np.ones(len(X_test_z)), X_test_z]) @ beta)
    pred_series = pd.Series(index=april_features["LSOA code"], dtype=float)
    complete = april_features[MODEL_FEATURES].notna().all(axis=1)
    X_april = april_features.loc[complete, MODEL_FEATURES].astype(float).to_numpy()
    if len(X_april):
        X_april_z = (X_april - mu) / sigma
        pred_series.loc[april_features.loc[complete, "LSOA code"]] = np.maximum(
            0.0, np.column_stack([np.ones(len(X_april_z)), X_april_z]) @ beta
        )

    test_compare = test[["Month", "LSOA code", "demand_points"]].copy()
    test_compare["pred"] = pred_test
    recalls = []
    for _, month_rows in test_compare.groupby("Month"):
        n = max(1, int(round(len(month_rows) * 0.10)))
        actual_top = set(month_rows.nlargest(n, "demand_points")["LSOA code"])
        pred_top = set(month_rows.nlargest(n, "pred")["LSOA code"])
        recalls.append(len(actual_top & pred_top) / n)

    return pred_series, {
        "model": "Context-aware ridge model",
        "testMonths": "2025-10 to 2026-03",
        "mae": round(mae(y_test, pred_test), 2),
        "rmse": round(rmse(y_test, pred_test), 2),
        "wape": round(wape(y_test, pred_test) * 100, 1),
        "recall": round(float(np.mean(recalls)) * 100, 1),
        "note": "Uses lag, seasonality, population, income, employment and education context where official IoD data are available.",
    }


def build_dashboard_payload(
    panel: pd.DataFrame,
    crime_type_summary: pd.DataFrame,
    monthly: pd.DataFrame,
    metrics: pd.DataFrame,
    forecast: pd.DataFrame,
    context: pd.DataFrame,
    contextual_metric: dict,
    contextual_pred: pd.Series,
    incident_rows: int,
    centres: list[dict],
) -> dict:
    panel_dates = panel.copy()
    panel_dates["Month"] = pd.to_datetime(panel_dates["Month"])
    latest_months = sorted(panel_dates["Month"].unique())[-12:]
    recent = panel_dates[panel_dates["Month"].isin(latest_months)].copy()
    recent_context = recent.merge(context[["LSOA code", "population"]], on="LSOA code", how="left")
    recent_summary = (
        recent_context.groupby("LSOA code")
        .agg(
            recent_12m_demand=("demand_points", "sum"),
            recent_12m_incidents=("incidents", "sum"),
            recent_12m_high_harm=("high_harm_incidents", "sum"),
            population=("population", "first"),
        )
        .reset_index()
    )
    recent_summary["high_harm_share"] = (
        recent_summary["recent_12m_high_harm"] / recent_summary["recent_12m_incidents"].replace(0, pd.NA)
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
    history = panel_dates.copy()
    history["history_rank_pct"] = history.groupby("Month")["demand_points"].rank(pct=True)
    history_pct = history.groupby("LSOA code").agg(mean_historic_percentile=("history_rank_pct", "mean")).reset_index()

    area_data = (
        forecast.merge(recent_summary, on="LSOA code", how="left")
        .merge(repeat, on="LSOA code", how="left")
        .merge(history_pct, on="LSOA code", how="left")
        .merge(context, on="LSOA code", how="left", suffixes=("", "_context"))
    )
    area_data["contextual_predicted_demand_points"] = area_data["LSOA code"].map(contextual_pred)
    area_data["context_available"] = area_data["contextual_predicted_demand_points"].notna()
    area_data["contextual_predicted_demand_points"] = area_data["contextual_predicted_demand_points"].fillna(
        area_data["predicted_demand_points"]
    )
    area_data["recommended_predicted_demand"] = np.where(
        area_data["context_available"],
        0.70 * area_data["predicted_demand_points"] + 0.30 * area_data["contextual_predicted_demand_points"],
        area_data["predicted_demand_points"],
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
        area_data[f"{col}_rank"] = pct_rank(area_data[col].astype(float))

    area_data["context_pressure_rank"] = (
        area_data["income_score_rank"] * 0.35
        + area_data["education_score_rank"] * 0.35
        + area_data["employment_score_rank"] * 0.30
    ).fillna(0.5)
    area_data["balanced_review_score"] = (
        area_data["recommended_predicted_demand_rank"] * 0.60
        + area_data["uplift_vs_recent_mean_rank"] * 0.20
        + area_data["context_pressure_rank"] * 0.20
    )

    max_pred = area_data["recommended_predicted_demand"].max()
    areas = []
    for _, row in area_data.iterrows():
        repeat_months = safe_int(row.get("recent_top_decile_months"))
        repeat_risk = "High" if repeat_months >= 8 else "Medium" if repeat_months >= 4 else "Low"
        imd_decile = safe_int(row.get("imd_decile"), 0)
        income_decile = safe_int(row.get("income_decile"), 0)
        employment_decile = safe_int(row.get("employment_decile"), 0)
        education_decile = safe_int(row.get("education_decile"), 0)
        context_alerts = []
        if 0 < imd_decile <= 2:
            context_alerts.append("high deprivation")
        if 0 < education_decile <= 2:
            context_alerts.append("education pressure")
        if 0 < income_decile <= 2:
            context_alerts.append("income pressure")

        local_authority = row.get("local_authority")
        if pd.isna(local_authority) or not str(local_authority).strip():
            local_authority = derive_area_name(row.get("LSOA_name"))

        official_name = row.get("official_lsoa_name")
        if pd.isna(official_name) or not str(official_name).strip():
            official_name = row.get("LSOA_name", row["LSOA code"])

        areas.append(
            {
                "code": str(row["LSOA code"]),
                "name": str(official_name),
                "shortName": str(row.get("LSOA_name", row["LSOA code"])),
                "localAuthority": str(local_authority),
                "longitude": safe_float(row.get("longitude")),
                "latitude": safe_float(row.get("latitude")),
                "predictedDemand": round(safe_float(row["recommended_predicted_demand"]), 2),
                "originalPredictedDemand": round(safe_float(row["predicted_demand_points"]), 2),
                "contextPredictedDemand": round(safe_float(row["contextual_predicted_demand_points"]), 2),
                "demandRate1000": round(safe_float(row["predicted_demand_rate_1000"]), 2),
                "recentDemandRate1000": round(safe_float(row.get("recent_demand_rate_1000")), 2),
                "population": safe_int(row.get("population")),
                "recentMean": round(safe_float(row.get("recent_12m_mean")), 2),
                "uplift": round(safe_float(row.get("uplift_vs_recent_mean")), 4),
                "spikeZ": round(safe_float(row.get("spike_z")), 3),
                "originalTier": str(row.get("allocation_tier", "")),
                "recent12Demand": round(safe_float(row.get("recent_12m_demand")), 2),
                "recent12Incidents": round(safe_float(row.get("recent_12m_incidents")), 0),
                "recent12HighHarm": round(safe_float(row.get("recent_12m_high_harm")), 0),
                "highHarmShare": round(safe_float(row.get("high_harm_share")), 4),
                "recentTopDecileMonths": repeat_months,
                "repeatAttentionRisk": repeat_risk,
                "historicPercentile": round(safe_float(row.get("mean_historic_percentile")), 4),
                "balancedScore": round(safe_float(row.get("balanced_review_score")), 5),
                "demandRank": round(safe_float(row.get("recommended_predicted_demand_rank")), 5),
                "rateRank": round(safe_float(row.get("predicted_demand_rate_1000_rank")), 5),
                "contextRank": round(safe_float(row.get("context_pressure_rank")), 5),
                "imdScore": round(safe_float(row.get("imd_score")), 2),
                "imdDecile": imd_decile,
                "incomeScore": round(safe_float(row.get("income_score")), 3),
                "incomeDecile": income_decile,
                "employmentScore": round(safe_float(row.get("employment_score")), 3),
                "employmentDecile": employment_decile,
                "educationScore": round(safe_float(row.get("education_score")), 2),
                "educationDecile": education_decile,
                "childIncomeScore": round(safe_float(row.get("child_income_score")), 3),
                "childIncomeDecile": safe_int(row.get("child_income_decile"), 0),
                "contextAvailable": bool(row.get("context_available")),
                "contextAlerts": context_alerts,
                "sizeScore": round(safe_float(row["recommended_predicted_demand"]) / max_pred, 5),
            }
        )

    monthly_records = [
        {
            "month": str(row["Month"]),
            "incidents": round(safe_float(row["incidents"]), 2),
            "demand": round(safe_float(row["demand_points"]), 2),
            "highHarm": round(safe_float(row["high_harm_incidents"]), 2),
        }
        for _, row in monthly.iterrows()
    ]
    crime_records = [
        {
            "type": str(row["Crime type"]),
            "incidents": safe_int(row["incidents"]),
            "demand": round(safe_float(row["demand_points"]), 2),
            "weight": round(safe_float(row["severity_weight"]), 2),
        }
        for _, row in crime_type_summary.sort_values("demand_points", ascending=False).iterrows()
    ]
    metric_records = [
        {
            "model": str(row["model"]),
            "testMonths": str(row["test_months"]),
            "mae": round(safe_float(row["MAE_LSOA_month"]), 2),
            "rmse": round(safe_float(row["RMSE_LSOA_month"]), 2),
            "wape": round(safe_float(row["WAPE"]) * 100, 1),
            "recall": round(safe_float(row["top_10pct_hotspot_recall"]) * 100, 1),
            "note": "Uses lag and seasonality only.",
        }
        for _, row in metrics.iterrows()
    ]
    metric_records.append(contextual_metric)
    local_authorities = sorted({a["localAuthority"] for a in areas if a["localAuthority"]})
    context_coverage = int(sum(1 for a in areas if a["contextAvailable"]))

    return {
        "meta": {
            "title": "Police Demand Review Map",
            "subtitle": "Monthly decision-support prototype for non-technical police resource planners",
            "courseQuestion": "How can data-driven estimates of police demand be used to inform the effective organisation and allocation of policing resources in the United Kingdom?",
            "stakeholder": "UK police resource planners and policing decision-makers",
            "force": "Police.uk all-force archive",
            "dateRange": f"{START_MONTH} to {END_MONTH}",
            "forecastMonth": FORECAST_MONTH,
            "publisher": "Single Online Home National Digital Team / data.police.uk",
            "downloadPage": "https://data.police.uk/data/archive/2026-03.zip",
            "contextSource": "GOV.UK English Indices of Deprivation 2025, File 7: ranks, scores, deciles and population denominators",
            "contextDownload": "https://www.gov.uk/government/statistics/english-indices-of-deprivation-2025",
            "incidentRows": incident_rows,
            "lsoas": len(areas),
            "months": int(panel["Month"].nunique()),
            "crimeTypes": int(len(crime_records)),
            "contextCoverage": context_coverage,
            "sourceNote": "Uses official police.uk recorded crime data. English social context is matched where GOV.UK IoD 2025 LSOA data are available; non-English areas keep the crime-history forecast without fabricated context.",
            "modelCaution": "This is a decision-support prototype, not an automatic deployment system or staffing calculator.",
            "modelUpgrade": "Forecasts combine tested local crime-history patterns with official income, employment and education context where available.",
            "clusteringCenters": centres,
        },
        "areas": areas,
        "monthly": monthly_records,
        "crimeTypes": crime_records,
        "metrics": metric_records,
        "localAuthorities": local_authorities,
        "seriesByArea": {},
        "method": [
            {
                "step": "Estimate demand",
                "plainText": "Recorded crimes are converted into severity-weighted demand points using crime type and transparent weights.",
            },
            {
                "step": "Forecast demand",
                "plainText": "Lag, rolling average and seasonal features estimate likely next-month demand for each LSOA.",
            },
            {
                "step": "Add context",
                "plainText": "Official income, employment and education context is added where matched, without inventing missing context for other areas.",
            },
            {
                "step": "Group coverage",
                "plainText": "Coverage zones use the teammate weighted-proximity method with fake centre LSOAs and crime-count weights.",
            },
        ],
    }


def write_outputs(payload: dict, metrics: pd.DataFrame, forecast: pd.DataFrame, monthly: pd.DataFrame) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    metrics.to_csv(DATA_DIR / "uk_model_metrics.csv", index=False)
    forecast.to_csv(DATA_DIR / "uk_april_2026_lsoa_priority_forecast.csv", index=False)
    monthly.to_csv(DATA_DIR / "uk_monthly_summary.csv", index=False)
    with open(DATA_DIR / "uk_model_summary.json", "w", encoding="utf-8") as f:
        json.dump(payload["meta"], f, indent=2)
    with open(DATA_DIR / "dashboard_data.js", "w", encoding="utf-8") as f:
        f.write("window.DASHBOARD_DATA = ")
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the UK-wide dashboard data from the official police.uk archive.")
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--iod-file", type=Path, default=DEFAULT_IOD)
    parser.add_argument("--centres", type=Path, default=DEFAULT_CENTRES)
    parser.add_argument("--chunk-size", type=int, default=250_000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    centres = load_clustering_centres(args.centres)
    panel, crime_type_summary, monthly, incident_rows = read_archive_to_panel(args.archive, args.chunk_size)
    featured = add_features(panel)
    metrics, test, model, tuning = evaluate_models(featured)
    forecast = forecast_next_month(featured, model)
    context = load_context(args.iod_file)
    panel_context = featured.merge(context, on="LSOA code", how="left")
    april_features = make_april_features(featured, context)
    contextual_pred, contextual_metric = fit_contextual_ridge(panel_context, april_features)
    payload = build_dashboard_payload(
        panel=featured,
        crime_type_summary=crime_type_summary,
        monthly=monthly,
        metrics=metrics,
        forecast=forecast,
        context=context,
        contextual_metric=contextual_metric,
        contextual_pred=contextual_pred,
        incident_rows=incident_rows,
        centres=centres,
    )
    write_outputs(payload, metrics, forecast, monthly)
    print(
        json.dumps(
            {
                "areas": len(payload["areas"]),
                "incidentRows": payload["meta"]["incidentRows"],
                "contextCoverage": payload["meta"]["contextCoverage"],
                "metrics": payload["metrics"],
                "tuning": tuning,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
