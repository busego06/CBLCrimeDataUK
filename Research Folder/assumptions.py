from scipy import stats
import statsmodels.api as sm
import sys
from statsmodels.stats.diagnostic import linear_reset
from statsmodels.stats.outliers_influence import variance_inflation_factor

sys.path.append("./SSA7")

exec(open("./SSA7/pyfiles/officialmodel2.py").read())

## NORMAL CRIME RATE
for year in [2024, 2025]:
    data = merged[merged["Year"] == year].dropna(subset=variables + ["Crime Rate"]).copy()
    data["Predicted"] = models[year].predict(data[variables].values)
    data["Residual"]  = data["Crime Rate"] - data["Predicted"]

    # normality test
    stat, p = stats.shapiro(data["Residual"])
    print(f"\n{year} Shapiro-Wilk normality test: stat={stat:.3f}, p={p:.4f}")
    print("  Residuals normal" if p > 0.05 else "  Residuals NOT normal")

    # homoscedasticity, Breusch-Pagan
    Xconst = sm.add_constant(data[variables])
    bpTest = sm.stats.diagnostic.het_breuschpagan(data["Residual"], Xconst)
    print(f"  Breusch-Pagan p={bpTest[1]:.4f}")
    print("  Homoscedastic" if bpTest[1] > 0.05 else "  Heteroscedastic (unequal variance)")

    # RESET test for non-linearity / omitted variables
    olsModel = sm.OLS(data["Crime Rate"], Xconst).fit()
    resetResult = linear_reset(olsModel, power=2, use_f=True)

    print(f"  RESET test: F={resetResult.fvalue:.3f}, p={resetResult.pvalue:.4f}")
    print("  Linear specification OK" if resetResult.pvalue > 0.05 else "  Possible non-linearity or omitted variables")

    # Robust standard errors
    robustModel = sm.OLS(data["Crime Rate"], Xconst).fit(cov_type="HC3")
    print("\nOLS with HC3 robust standard errors")
    print(robustModel.summary())

    # multicollinearity, VIF
    vifData = pd.DataFrame()
    vifData["Variable"] = variables
    vifData["VIF"] = [variance_inflation_factor(data[variables].values, i) for i in range(len(variables))]
    print(f"\n  VIF scores ({year}):")
    print(vifData)
    print("  VIF > 10 indicates multicollinearity")