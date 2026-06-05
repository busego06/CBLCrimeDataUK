from __future__ import annotations

import argparse
import csv
import json
import math
import os
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
DEFAULT_ZIP_PATH = ROOT / "data" / "police_west_midlands_2023_04_to_2026_03.zip"
OUT = ROOT / "outputs"


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


FEATURES = [
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


@dataclass
class Standardiser:
    mean: np.ndarray
    std: np.ndarray

    def transform(self, x: np.ndarray) -> np.ndarray:
        return (x - self.mean) / self.std


def ensure_output_dir() -> None:
    OUT.mkdir(exist_ok=True)


def read_crime_zip(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Expected official police.uk ZIP at {path}")

    usecols = [
        "Month",
        "Longitude",
        "Latitude",
        "LSOA code",
        "LSOA name",
        "Crime type",
        "Last outcome category",
    ]
    frames = []
    with zipfile.ZipFile(path) as zf:
        for name in sorted(zf.namelist()):
            if name.endswith("-street.csv"):
                frames.append(pd.read_csv(zf.open(name), usecols=usecols))
    df = pd.concat(frames, ignore_index=True)
    df = df[df["LSOA code"].notna()].copy()
    df["Month"] = pd.PeriodIndex(df["Month"], freq="M").astype(str)
    df["severity_weight"] = df["Crime type"].map(SEVERITY_WEIGHTS).fillna(1.0)
    df["high_harm_flag"] = df["severity_weight"].ge(4.0).astype(int)
    return df


def build_lsoa_panel(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    monthly = (
        df.groupby(["LSOA code", "LSOA name", "Month"], as_index=False)
        .agg(
            incidents=("Crime type", "size"),
            demand_points=("severity_weight", "sum"),
            high_harm_incidents=("high_harm_flag", "sum"),
            longitude=("Longitude", "mean"),
            latitude=("Latitude", "mean"),
        )
    )

    months = pd.period_range(df["Month"].min(), df["Month"].max(), freq="M").astype(str)
    lsoa_meta = (
        monthly.sort_values("Month")
        .groupby("LSOA code", as_index=False)
        .agg(
            LSOA_name=("LSOA name", "last"),
            longitude=("longitude", "mean"),
            latitude=("latitude", "mean"),
        )
    )
    full_index = pd.MultiIndex.from_product(
        [lsoa_meta["LSOA code"], months], names=["LSOA code", "Month"]
    ).to_frame(index=False)
    panel = full_index.merge(lsoa_meta, on="LSOA code", how="left")
    panel = panel.merge(
        monthly[
            [
                "LSOA code",
                "Month",
                "incidents",
                "demand_points",
                "high_harm_incidents",
            ]
        ],
        on=["LSOA code", "Month"],
        how="left",
    )
    for col in ["incidents", "demand_points", "high_harm_incidents"]:
        panel[col] = panel[col].fillna(0.0)

    crime_type_summary = (
        df.groupby("Crime type", as_index=False)
        .agg(
            incidents=("Crime type", "size"),
            demand_points=("severity_weight", "sum"),
            severity_weight=("severity_weight", "first"),
        )
        .sort_values("demand_points", ascending=False)
    )

    force_month = (
        panel.groupby("Month", as_index=False)
        .agg(
            incidents=("incidents", "sum"),
            demand_points=("demand_points", "sum"),
            high_harm_incidents=("high_harm_incidents", "sum"),
        )
        .sort_values("Month")
    )
    return panel, crime_type_summary, force_month


def add_features(panel: pd.DataFrame) -> pd.DataFrame:
    panel = panel.sort_values(["LSOA code", "Month"]).copy()
    g = panel.groupby("LSOA code", group_keys=False)
    for lag in [1, 2, 3, 12]:
        panel[f"lag_{lag}"] = g["demand_points"].shift(lag)
    shifted = g["demand_points"].shift(1)
    panel["roll_3"] = shifted.groupby(panel["LSOA code"]).rolling(3, min_periods=1).mean().reset_index(level=0, drop=True)
    panel["roll_6"] = shifted.groupby(panel["LSOA code"]).rolling(6, min_periods=1).mean().reset_index(level=0, drop=True)
    panel["prev_mean"] = (
        shifted.groupby(panel["LSOA code"]).expanding(min_periods=1).mean().reset_index(level=0, drop=True)
    )
    panel["recent_trend"] = panel["lag_1"] - panel["lag_3"]
    month_no = pd.PeriodIndex(panel["Month"], freq="M").month
    panel["month_sin"] = np.sin(2 * np.pi * month_no / 12.0)
    panel["month_cos"] = np.cos(2 * np.pi * month_no / 12.0)
    panel[FEATURES] = panel[FEATURES].fillna(0.0)
    return panel


def wape(actual: np.ndarray, pred: np.ndarray) -> float:
    denom = np.maximum(np.sum(np.abs(actual)), 1e-9)
    return float(np.sum(np.abs(actual - pred)) / denom)


def rmse(actual: np.ndarray, pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((actual - pred) ** 2)))


def mae(actual: np.ndarray, pred: np.ndarray) -> float:
    return float(np.mean(np.abs(actual - pred)))


def hotspot_recall(frame: pd.DataFrame, pred_col: str, actual_col: str = "demand_points", q: float = 0.90) -> float:
    recalls = []
    for _, month_df in frame.groupby("Month"):
        n = max(1, int(math.ceil(len(month_df) * (1 - q))))
        actual_top = set(month_df.nlargest(n, actual_col)["LSOA code"])
        pred_top = set(month_df.nlargest(n, pred_col)["LSOA code"])
        recalls.append(len(actual_top & pred_top) / len(actual_top))
    return float(np.mean(recalls))


def calibration_factor(actual: np.ndarray, pred: np.ndarray) -> float:
    factor = np.sum(actual) / max(np.sum(pred), 1e-9)
    return float(np.clip(factor, 0.75, 1.25))


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
    xtx = design.T @ design + penalty
    xty = design.T @ y
    try:
        beta = np.linalg.solve(xtx, xty)
    except np.linalg.LinAlgError:
        beta = np.linalg.pinv(xtx) @ xty
    # Cap only beyond the largest training observation to prevent impossible
    # extrapolations while preserving genuine high-demand LSOAs.
    log_cap = float(np.log1p(train["demand_points"].max() * 1.20))
    return beta, scaler, log_cap


def transformed_features(frame: pd.DataFrame) -> np.ndarray:
    transformed = frame[FEATURES].copy()
    for col in DEMAND_SCALE_FEATURES:
        transformed[col] = np.log1p(transformed[col].clip(lower=0.0))
    transformed["recent_trend"] = np.sign(transformed["recent_trend"]) * np.log1p(
        np.abs(transformed["recent_trend"])
    )
    return transformed.to_numpy(dtype=float)


def predict_ridge(frame: pd.DataFrame, beta: np.ndarray, scaler: Standardiser, log_cap: float | None = None) -> np.ndarray:
    x = transformed_features(frame)
    xs = scaler.transform(x)
    design = np.column_stack([np.ones(len(xs)), xs])
    log_pred = design @ beta
    if log_cap is not None:
        log_pred = np.clip(log_pred, 0.0, log_cap)
    return np.maximum(np.expm1(log_pred), 0.0)


def evaluate_models(featured: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, float, float, float, tuple[np.ndarray, Standardiser, float, float, float], pd.DataFrame]:
    usable = featured[featured["Month"] >= "2023-10"].copy()
    tune_train = usable[(usable["Month"] >= "2023-10") & (usable["Month"] <= "2025-03")]
    validation = usable[(usable["Month"] >= "2025-04") & (usable["Month"] <= "2025-09")].copy()
    model_train = usable[(usable["Month"] >= "2023-10") & (usable["Month"] <= "2025-09")]
    test = usable[(usable["Month"] >= "2025-10") & (usable["Month"] <= "2026-03")].copy()

    alpha_results = []
    best_alpha = None
    best_score = float("inf")
    best_calibration = 1.0
    actual_validation = validation["demand_points"].to_numpy(dtype=float)
    for alpha in [0.0, 0.1, 1.0, 10.0, 50.0, 100.0, 250.0]:
        beta, scaler, log_cap = fit_ridge_log_model(tune_train, alpha)
        validation_pred_raw = predict_ridge(validation, beta, scaler, log_cap)
        factor = calibration_factor(actual_validation, validation_pred_raw)
        validation_pred = validation_pred_raw * factor
        score = wape(actual_validation, validation_pred)
        alpha_results.append({"alpha": alpha, "calibration_factor": factor, "validation_wape": score})
        if score < best_score:
            best_score = score
            best_alpha = alpha
            best_calibration = factor

    tune_beta, tune_scaler, tune_log_cap = fit_ridge_log_model(tune_train, float(best_alpha))
    validation_ridge = predict_ridge(validation, tune_beta, tune_scaler, tune_log_cap) * best_calibration
    validation_roll = validation["roll_3"].to_numpy(dtype=float)
    blend_results = []
    best_blend = None
    best_blend_score = float("inf")
    for ridge_weight in [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
        pred = ridge_weight * validation_ridge + (1.0 - ridge_weight) * validation_roll
        score = wape(actual_validation, pred)
        blend_results.append(
            {
                "alpha": best_alpha,
                "ridge_weight": ridge_weight,
                "validation_wape": score,
            }
        )
        if score < best_blend_score:
            best_blend_score = score
            best_blend = ridge_weight

    beta, scaler, log_cap = fit_ridge_log_model(model_train, float(best_alpha))
    test["ridge_pred"] = predict_ridge(test, beta, scaler, log_cap) * best_calibration
    test["rolling_3_pred"] = test["roll_3"].clip(lower=0)
    test["seasonal_naive_pred"] = np.where(test["lag_12"] > 0, test["lag_12"], test["roll_3"]).clip(min=0)
    test["hybrid_pred"] = (
        float(best_blend) * test["ridge_pred"] + (1.0 - float(best_blend)) * test["rolling_3_pred"]
    )

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
    metrics_df = pd.DataFrame(metrics)
    alpha_df = pd.concat([pd.DataFrame(alpha_results), pd.DataFrame(blend_results)], ignore_index=True, sort=False)
    return (
        metrics_df,
        test,
        float(best_alpha),
        float(best_blend),
        float(best_calibration),
        (beta, scaler, log_cap, float(best_blend), float(best_calibration)),
        alpha_df,
    )


def forecast_next_month(panel: pd.DataFrame, model: tuple[np.ndarray, Standardiser, float, float, float]) -> pd.DataFrame:
    beta, scaler, log_cap, ridge_weight, calibration = model
    lsoa_meta = panel[["LSOA code", "LSOA_name", "longitude", "latitude"]].drop_duplicates("LSOA code")
    future = lsoa_meta.copy()
    future["Month"] = "2026-04"
    future["incidents"] = np.nan
    future["demand_points"] = np.nan
    future["high_harm_incidents"] = np.nan

    appended = pd.concat([panel, future], ignore_index=True, sort=False)
    featured = add_features(appended)
    future_featured = featured[featured["Month"] == "2026-04"].copy()
    future_featured["ridge_predicted_demand_points"] = (
        predict_ridge(future_featured, beta, scaler, log_cap) * calibration
    )
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
        future_featured["predicted_demand_points"]
        / future_featured["recent_12m_mean"].replace(0, np.nan)
        - 1
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
    future_featured.loc[
        future_featured["predicted_demand_points"] >= q90,
        "allocation_tier",
    ] = "Priority patrol and problem-solving"

    future_featured["capacity_units_per_100"] = (
        future_featured["predicted_demand_points"]
        / future_featured["predicted_demand_points"].sum()
        * 100.0
    )
    cols = [
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
    return future_featured[cols].sort_values("predicted_demand_points", ascending=False)


def allocation_summary(forecast: pd.DataFrame) -> pd.DataFrame:
    summary = (
        forecast.groupby("allocation_tier", as_index=False)
        .agg(
            lsoas=("LSOA code", "size"),
            predicted_demand_points=("predicted_demand_points", "sum"),
            capacity_units_per_100=("capacity_units_per_100", "sum"),
            mean_uplift_vs_recent=("uplift_vs_recent_mean", "mean"),
        )
    )
    summary["share_of_lsoas"] = summary["lsoas"] / summary["lsoas"].sum()
    summary["share_of_predicted_demand"] = (
        summary["predicted_demand_points"] / summary["predicted_demand_points"].sum()
    )
    order = {
        "Priority patrol and problem-solving": 0,
        "Reserve / spike watch": 1,
        "Routine baseline coverage": 2,
    }
    summary["order"] = summary["allocation_tier"].map(order)
    return summary.sort_values("order").drop(columns="order")


def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def draw_text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, size: int = 24, fill=(25, 31, 38), bold=False) -> None:
    draw.text(xy, text, fill=fill, font=get_font(size, bold=bold))


def save_line_chart(force_month: pd.DataFrame) -> None:
    img = Image.new("RGB", (1400, 720), "white")
    draw = ImageDraw.Draw(img)
    margin = 90
    top = 110
    width = 1180
    height = 470
    draw_text(draw, (70, 38), "West Midlands monthly police demand index", 34, bold=True)
    draw_text(draw, (70, 78), "Official police.uk incidents weighted by transparent provisional severity score", 19, fill=(82, 93, 105))

    y = force_month["demand_points"].to_numpy(float)
    x = np.arange(len(y))
    ymin, ymax = y.min() * 0.96, y.max() * 1.04

    for i in range(6):
        yy = top + height - i * height / 5
        draw.line([(margin, yy), (margin + width, yy)], fill=(226, 232, 240), width=1)
        val = ymin + i * (ymax - ymin) / 5
        draw_text(draw, (15, int(yy - 10)), f"{val:,.0f}", 16, fill=(82, 93, 105))
    draw.line([(margin, top), (margin, top + height), (90, top + height), (margin + width, top + height)], fill=(96, 111, 128), width=2)

    pts = []
    for xi, yi in zip(x, y):
        px = margin + xi * width / (len(y) - 1)
        py = top + height - (yi - ymin) * height / (ymax - ymin)
        pts.append((px, py))
    draw.line(pts, fill=(25, 118, 210), width=4)
    for p in pts:
        draw.ellipse((p[0] - 4, p[1] - 4, p[0] + 4, p[1] + 4), fill=(25, 118, 210))

    months = force_month["Month"].tolist()
    for idx in [0, 5, 11, 17, 23, 29, 35]:
        px = margin + idx * width / (len(y) - 1)
        draw_text(draw, (int(px - 35), top + height + 18), months[idx], 16, fill=(82, 93, 105))

    draw.rectangle((margin + 30 * width / 35, top, margin + width, top + height), outline=(217, 119, 6), width=3)
    draw_text(draw, (int(margin + 30 * width / 35 + 10), top + 12), "held-out test", 18, fill=(217, 119, 6), bold=True)
    img.save(OUT / "fig_monthly_demand.png")


def save_test_performance_chart(test: pd.DataFrame) -> None:
    monthly = (
        test.groupby("Month", as_index=False)
        .agg(
            actual=("demand_points", "sum"),
            rolling=("rolling_3_pred", "sum"),
            hybrid=("hybrid_pred", "sum"),
        )
        .sort_values("Month")
    )
    img = Image.new("RGB", (1400, 720), "white")
    draw = ImageDraw.Draw(img)
    draw_text(draw, (70, 38), "Held-out forecast performance by month", 34, bold=True)
    draw_text(draw, (70, 78), "October 2025-March 2026 was not used for fitting the final model", 19, fill=(82, 93, 105))
    margin = 90
    top = 120
    width = 1180
    height = 430
    vals = monthly[["actual", "rolling", "hybrid"]].to_numpy(float).ravel()
    ymin, ymax = vals.min() * 0.97, vals.max() * 1.03
    colors = {"actual": (30, 41, 59), "rolling": (217, 119, 6), "hybrid": (64, 164, 109)}
    labels = {"actual": "Actual", "rolling": "Rolling baseline", "hybrid": "Final model"}
    for i in range(6):
        yy = top + height - i * height / 5
        draw.line([(margin, yy), (margin + width, yy)], fill=(226, 232, 240), width=1)
        draw_text(draw, (18, int(yy - 10)), f"{ymin + i * (ymax-ymin)/5:,.0f}", 16, fill=(82, 93, 105))
    draw.line([(margin, top), (margin, top + height), (margin + width, top + height)], fill=(96, 111, 128), width=2)
    xs = np.arange(len(monthly))
    for col in ["actual", "hybrid", "rolling"]:
        pts = []
        for xi, yi in zip(xs, monthly[col].to_numpy(float)):
            px = margin + xi * width / (len(monthly) - 1)
            py = top + height - (yi - ymin) * height / (ymax - ymin)
            pts.append((px, py))
        draw.line(pts, fill=colors[col], width=4)
        for p in pts:
            draw.ellipse((p[0] - 4, p[1] - 4, p[0] + 4, p[1] + 4), fill=colors[col])
    for idx, month in enumerate(monthly["Month"]):
        px = margin + idx * width / (len(monthly) - 1)
        draw_text(draw, (int(px - 35), top + height + 18), month, 16, fill=(82, 93, 105))
    legend_x = 900
    for i, col in enumerate(["actual", "hybrid", "rolling"]):
        y0 = 42 + i * 28
        draw.line([(legend_x, y0 + 10), (legend_x + 35, y0 + 10)], fill=colors[col], width=4)
        draw_text(draw, (legend_x + 45, y0), labels[col], 18, fill=(30, 41, 59))
    img.save(OUT / "fig_model_performance.png")


def save_crime_mix_chart(crime_type_summary: pd.DataFrame) -> None:
    top = crime_type_summary.sort_values("demand_points", ascending=True).tail(10)
    img = Image.new("RGB", (1400, 820), "white")
    draw = ImageDraw.Draw(img)
    draw_text(draw, (70, 38), "Weighted demand contribution by crime type", 34, bold=True)
    draw_text(draw, (70, 78), "Incident counts are multiplied by the provisional severity weights used in the model", 19, fill=(82, 93, 105))
    x0, y0 = 470, 130
    bar_w, bar_h, gap = 780, 42, 25
    max_val = top["demand_points"].max()
    for i, (_, row) in enumerate(top.iterrows()):
        y = y0 + i * (bar_h + gap)
        label = row["Crime type"]
        val = row["demand_points"]
        fill = (25, 118, 210) if row["severity_weight"] >= 3 else (64, 164, 109)
        draw_text(draw, (70, y + 8), str(label), 20, fill=(30, 41, 59))
        draw.rectangle((x0, y, x0 + bar_w, y + bar_h), fill=(235, 240, 245))
        draw.rectangle((x0, y, x0 + bar_w * val / max_val, y + bar_h), fill=fill)
        draw_text(draw, (x0 + bar_w + 20, y + 8), f"{val:,.0f}", 19, fill=(30, 41, 59))
    img.save(OUT / "fig_crime_mix.png")


def save_priority_map(forecast: pd.DataFrame) -> None:
    img = Image.new("RGB", (1200, 900), "white")
    draw = ImageDraw.Draw(img)
    draw_text(draw, (55, 32), "April 2026 LSOA allocation tiers", 34, bold=True)
    draw_text(draw, (55, 73), "Approximate LSOA centroids estimated from official police.uk incident coordinates", 18, fill=(82, 93, 105))
    data = forecast.dropna(subset=["longitude", "latitude"]).copy()
    min_lon, max_lon = data["longitude"].min(), data["longitude"].max()
    min_lat, max_lat = data["latitude"].min(), data["latitude"].max()
    plot = (80, 130, 1030, 820)
    colors = {
        "Priority patrol and problem-solving": (203, 64, 66),
        "Reserve / spike watch": (217, 119, 6),
        "Routine baseline coverage": (89, 132, 179),
    }
    order = [
        "Routine baseline coverage",
        "Reserve / spike watch",
        "Priority patrol and problem-solving",
    ]
    draw.rectangle(plot, outline=(203, 213, 225), width=2)
    for tier in order:
        subset = data[data["allocation_tier"] == tier]
        for _, row in subset.iterrows():
            px = plot[0] + (row["longitude"] - min_lon) / (max_lon - min_lon) * (plot[2] - plot[0])
            py = plot[3] - (row["latitude"] - min_lat) / (max_lat - min_lat) * (plot[3] - plot[1])
            r = 2 if tier == "Routine baseline coverage" else 4
            draw.ellipse((px - r, py - r, px + r, py + r), fill=colors[tier])
    lx, ly = 820, 138
    for i, tier in enumerate(order[::-1]):
        y = ly + i * 40
        draw.rectangle((lx, y, lx + 22, y + 22), fill=colors[tier])
        draw_text(draw, (lx + 34, y - 2), tier, 18, fill=(30, 41, 59))
    draw_text(draw, (55, 842), "Note: This is not a street-address map; police.uk coordinates are anonymised before publication.", 17, fill=(82, 93, 105))
    img.save(OUT / "fig_allocation_map.png")


def save_outputs(
    df: pd.DataFrame,
    panel: pd.DataFrame,
    crime_type_summary: pd.DataFrame,
    force_month: pd.DataFrame,
    metrics: pd.DataFrame,
    test: pd.DataFrame,
    best_alpha: float,
    best_blend: float,
    best_calibration: float,
    alpha_df: pd.DataFrame,
    forecast: pd.DataFrame,
    allocation: pd.DataFrame,
) -> None:
    panel.to_csv(OUT / "lsoa_month_panel.csv", index=False)
    crime_type_summary.to_csv(OUT / "crime_type_summary.csv", index=False)
    force_month.to_csv(OUT / "monthly_force_summary.csv", index=False)
    metrics.to_csv(OUT / "model_metrics.csv", index=False)
    alpha_df.to_csv(OUT / "ridge_alpha_tuning.csv", index=False)
    forecast.to_csv(OUT / "april_2026_lsoa_priority_forecast.csv", index=False)
    allocation.to_csv(OUT / "allocation_tier_summary.csv", index=False)

    top_10_share = forecast.head(math.ceil(len(forecast) * 0.10))["predicted_demand_points"].sum() / forecast["predicted_demand_points"].sum()
    top_20_share = forecast.head(math.ceil(len(forecast) * 0.20))["predicted_demand_points"].sum() / forecast["predicted_demand_points"].sum()
    hybrid_row = metrics.loc[metrics["model"] == "Hybrid demand model"].iloc[0].to_dict()
    ridge_row = metrics.loc[metrics["model"] == "Ridge lag model"].iloc[0].to_dict()
    baseline_row = metrics.loc[metrics["model"] == "Rolling 3-month baseline"].iloc[0].to_dict()
    summary = {
        "source": {
            "publisher": "Single Online Home National Digital Team / data.police.uk",
            "download_page": "https://data.police.uk/data/",
            "force": "West Midlands Police",
            "date_range": "2023-04 to 2026-03",
            "download_job_url": "https://data.police.uk/data/fetch/2ca85ca1-9c24-4910-847b-a8fd9b91fbc5/",
        },
        "dataset": {
            "incident_rows": int(len(df)),
            "months": int(panel["Month"].nunique()),
            "lsoas": int(panel["LSOA code"].nunique()),
            "crime_types": int(df["Crime type"].nunique()),
            "total_weighted_demand_points": float(panel["demand_points"].sum()),
        },
        "model": {
            "best_ridge_alpha": best_alpha,
            "ridge_weight_in_hybrid": best_blend,
            "validation_calibration_factor": best_calibration,
            "features": FEATURES,
            "test_period": "2025-10 to 2026-03",
            "hybrid_metrics": hybrid_row,
            "ridge_metrics": ridge_row,
            "rolling_baseline_metrics": baseline_row,
        },
        "forecast": {
            "forecast_month": "2026-04",
            "top_10pct_lsoa_share_predicted_demand": float(top_10_share),
            "top_20pct_lsoa_share_predicted_demand": float(top_20_share),
            "priority_lsoas": int((forecast["allocation_tier"] == "Priority patrol and problem-solving").sum()),
            "reserve_lsoas": int((forecast["allocation_tier"] == "Reserve / spike watch").sum()),
        },
        "severity_weights": SEVERITY_WEIGHTS,
    }
    with open(OUT / "model_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    save_line_chart(force_month)
    save_test_performance_chart(test)
    save_crime_mix_chart(crime_type_summary)
    save_priority_map(forecast)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the initial West Midlands police demand model from an official police.uk ZIP download."
    )
    parser.add_argument(
        "--zip-path",
        type=Path,
        default=DEFAULT_ZIP_PATH,
        help="Path to the official police.uk custom download ZIP. Default: data/police_west_midlands_2023_04_to_2026_03.zip",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUT,
        help="Directory where model tables and figures are written. Default: outputs/",
    )
    return parser.parse_args()


def main() -> None:
    global OUT
    args = parse_args()
    OUT = args.output_dir
    ensure_output_dir()
    df = read_crime_zip(args.zip_path)
    panel, crime_type_summary, force_month = build_lsoa_panel(df)
    featured = add_features(panel)
    metrics, test, best_alpha, best_blend, best_calibration, model, alpha_df = evaluate_models(featured)
    forecast = forecast_next_month(featured, model)
    allocation = allocation_summary(forecast)
    save_outputs(
        df=df,
        panel=featured,
        crime_type_summary=crime_type_summary,
        force_month=force_month,
        metrics=metrics,
        test=test,
        best_alpha=best_alpha,
        best_blend=best_blend,
        best_calibration=best_calibration,
        alpha_df=alpha_df,
        forecast=forecast,
        allocation=allocation,
    )
    print(json.dumps(json.load(open(OUT / "model_summary.json", encoding="utf-8")), indent=2))


if __name__ == "__main__":
    main()
