import sys
from scipy import stats
import matplotlib.pyplot as plt
import numpy as np
sys.path.append("./SSA7")

exec(open("./SSA7/pyfiles/officialmodel2.py").read())

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
plt.savefig("./SSA7/lsoa_validation.png")

for year in [2024, 2025]:
    val  = lsoa_validation[lsoa_validation["Year"] == year]
    r, p = stats.pearsonr(val["Actual Count"], val["LSOA Predicted Count"])
    mae  = (val["Actual Count"] - val["LSOA Predicted Count"]).abs().mean()
    print(f"\nLSOA Validation {year}")
    print(f"  Pearson r:           {r:.3f}")
    print(f"  p-value:             {p:.4f}")
    print(f"  Mean Absolute Error: {mae:.1f} crimes per LSOA")