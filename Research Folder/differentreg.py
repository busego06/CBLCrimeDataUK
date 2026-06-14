import sys
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import Ridge, Lasso
sys.path.append("./SSA7")

exec(open("./SSA7/pyfiles/officialmodel2.py").read())
from sklearn.model_selection import cross_val_score

for year in [2024, 2025]:
    data = merged[merged["Year"] == year].dropna(subset=variables + ["Crime Rate"])
    X = data[variables].values
    y = data["Crime Rate"].values

    rf    = RandomForestRegressor(n_estimators=100, random_state=42)
    gb    = GradientBoostingRegressor(n_estimators=200, learning_rate=0.1, random_state=42)
    ridge = Ridge(alpha=1.0)
    lasso = Lasso(alpha=1.0)
    lr    = LinearRegression()

    print(f"\n{year} — Cross-validated R² (5-fold):")
    for name, model in [("Linear Regression", lr), ("Ridge", ridge),
                         ("Lasso", lasso), ("Random Forest", rf),
                         ("Gradient Boosting", gb)]:
        scores = cross_val_score(model, X, y, cv=5, scoring="r2")
        print(f"  {name:<25} mean R²: {scores.mean():.3f}  std: {scores.std():.3f}")

    rf.fit(X, y)
    importance = pd.Series(rf.feature_importances_, index=variables).sort_values(ascending=False)
    print(f"\n  Random Forest feature importance ({year}):")
    print(importance)