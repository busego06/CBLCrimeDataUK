import sys
from scipy import stats
import matplotlib.pyplot as plt
import numpy as np
sys.path.append("./SSA6")

exec(open("./SSA6/officialmodel.py").read())

for year in [2024, 2025]:
    data = merged[merged["Year"] == year].dropna(subset=variables + ["Crime Rate", "Total Population"]).copy()
    data["Predicted Crime Rate"] = models[year].predict(data[variables].values)
    data["Predicted Crime Count"] = data["Predicted Crime Rate"] / 100000 * data["Total Population"]
    print(f"\n{year} — Predicted Crime Count sample:")
    print(data[["LAD", "Total Population", "Predicted Crime Rate", "Predicted Crime Count"]].head(10))

print("\nActual LSOA crime count distribution:")
print(crimeByLSOA["Crime Count"].describe())

print("\nActual LAD crime count distribution:")
print(merged[["LAD", "Year", "Crime Count"]].groupby("Year").describe())

## RESIDUAL ANALYSIS

for year in [2024, 2025]:
    data = merged[merged["Year"] == year].dropna(subset=variables + ["Crime Rate"]).copy()
    data["Predicted Crime Rate"] = models[year].predict(data[variables].values)
    data["Residual"] = data["Crime Rate"] - data["Predicted Crime Rate"]
    data["Abs Residual"] = data["Residual"].abs()

    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    axes[0].scatter(data["Predicted Crime Rate"], data["Residual"], alpha=0.5, s=20)
    axes[0].axhline(0, color="red", linewidth=1.5, linestyle="--")
    axes[0].set_xlabel("Predicted Crime Rate")
    axes[0].set_ylabel("Residual (Actual - Predicted)")
    axes[0].set_title(f"Residuals vs Predicted ({year})")

    axes[1].hist(data["Residual"], bins=30, edgecolor="black", color="steelblue")
    axes[1].axvline(0, color="red", linewidth=1.5, linestyle="--")
    axes[1].set_xlabel("Residual")
    axes[1].set_ylabel("Count")
    axes[1].set_title(f"Residual Distribution ({year})")

    plt.tight_layout()
    plt.savefig(f"./SSA6/residuals_{year}.png")

    print(f"\n{year} — Top 10 Overpredicted:")
    print(data.nlargest(10, "Residual")[["LAD", "Crime Rate", "Predicted Crime Rate", "Residual"]].to_string(index=False))

    print(f"\n{year} — Top 10 Underpredicted:")
    print(data.nsmallest(10, "Residual")[["LAD", "Crime Rate", "Predicted Crime Rate", "Residual"]].to_string(index=False))

## LSOA VALIDATION

lsoa_validation = lsoaPredicted.merge(
    crimeByLSOA.rename(columns={"Crime Count": "Actual Count"}),
    on=["LSOA", "Year"], how="inner"
).dropna(subset=["LSOA Predicted Count", "Actual Count"])

fig, axes = plt.subplots(1, 2, figsize=(16, 6))

for ax, year in zip(axes, [2024, 2025]):
    val  = lsoa_validation[lsoa_validation["Year"] == year]
    r, p = stats.pearsonr(val["Actual Count"], val["LSOA Predicted Count"])

    ax.scatter(val["Actual Count"], val["LSOA Predicted Count"], alpha=0.3, s=10)
    ax.plot([val["Actual Count"].min(), val["Actual Count"].max()],
            [val["Actual Count"].min(), val["Actual Count"].max()],
            color="red", linewidth=1.5, linestyle="--", label="Perfect prediction")
    ax.set_xlabel("Actual LSOA Crime Count")
    ax.set_ylabel("Predicted LSOA Crime Count")
    ax.set_title(f"LSOA Validation ({year})")
    ax.annotate(
        f"r = {r:.3f}   p = {p:.4f}",
        xy=(0.05, 0.90), xycoords="axes fraction",
        fontsize=10,
        bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="gray", alpha=0.8)
    )
    ax.legend()

plt.tight_layout()
plt.savefig("./SSA6/lsoa_validation.png")

for year in [2024, 2025]:
    val  = lsoa_validation[lsoa_validation["Year"] == year]
    r, p = stats.pearsonr(val["Actual Count"], val["LSOA Predicted Count"])
    mae  = (val["Actual Count"] - val["LSOA Predicted Count"]).abs().mean()
    print(f"\nLSOA Validation {year}")
    print(f"  Pearson r:           {r:.3f}")
    print(f"  p-value:             {p:.4f}")
    print(f"  Mean Absolute Error: {mae:.1f} crimes per LSOA")
