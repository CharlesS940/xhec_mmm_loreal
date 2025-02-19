# -*- coding: utf-8 -*-
"""online_MMM_attemps.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1Iy4DIzokAuNSbamT7PEbXYe7wGML7WTG
"""

!apt-get install graphviz -y
!pip install pydot

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import holidays

import networkx as nx
import pydot
from networkx.drawing.nx_pydot import graphviz_layout

import statsmodels.api as sm
from statsmodels.stats.stattools import durbin_watson
from statsmodels.stats.outliers_influence import variance_inflation_factor

from scipy.optimize import minimize
from scipy.optimize import nnls

"""### Loading and preparing data"""

# Load dataset
file_path = "merged_data.csv"
df = pd.read_csv(file_path)

print(df.tail())

print(df.info())

print(df.describe())

df["Starting Week"] = pd.to_datetime(df["Starting Week"])
df = df.sort_values("Starting Week")
print(df["Starting Week"].min(), df["Starting Week"].max())

non_numeric_cols = df.select_dtypes(exclude=['number']).columns

for col in non_numeric_cols:
    print(f"Unique values in column '{col}':")
    print(df[col].unique())

if (df["Year_x"] == df["Year_y"]).all():
    print("✅ `Year_x` and `Year_y` are the same. Deleting `Year_y`.")
    df = df.drop(columns=["Year_y"])
    df = df.rename(columns={"Year_x": "Year"})
else:
    print("⚠️ `Year_x` and `Year_y` are not the same.")
    print(df[["Year_x", "Year_y"]].drop_duplicates())

"""### Data viz and extracting dataset for online"""

# Extract unique relationships between growth driver levels
edges = df[["growth_driver_l1", "growth_driver_l2", "growth_driver_l3", "growth_driver_l4", "growth_driver_l5"]].drop_duplicates()

# Replace underscores with spaces for readability
edges = edges.applymap(lambda x: x.replace("_", " ") if pd.notna(x) else x)

# Initialize directed graph
G = nx.DiGraph()

# Add edges to the graph
for _, row in edges.iterrows():
    for i in range(4):  # Connecting L1 → L2 → L3 → L4 → L5
        if pd.notna(row[i]) and pd.notna(row[i + 1]):
            G.add_edge(row[i], row[i + 1])

# Define improved colors for different levels
level_colors = {
    0: "#FFD700",  # Gold (L1)
    1: "#FF6347",  # Tomato (L2)
    2: "#4682B4",  # Steel Blue (L3)
    3: "#32CD32",  # Lime Green (L4)
    4: "#8A2BE2"   # Blue Violet (L5)
}

# Assign colors based on hierarchy depth
node_colors = []
for node in G.nodes():
    depth = next((i for i, col in enumerate(["growth_driver_l1", "growth_driver_l2", "growth_driver_l3", "growth_driver_l4", "growth_driver_l5"]) if node in df[col].unique()), 0)
    node_colors.append(level_colors.get(depth, "#A9A9A9"))  # Default to Dark Gray if unknown

# Use graphviz layout for clearer spacing
plt.figure(figsize=(15, 8))
pos = graphviz_layout(G, prog="dot")  # "dot" ensures top-down tree structure

# Draw the tree with larger spacing and adjusted label positioning
nx.draw(
    G, pos, with_labels=True, node_color=node_colors, node_size=3500,
    edge_color="gray", font_size=10, font_weight="bold", arrows=True
)

# Rotate labels slightly to prevent overlap
for label in pos:
    x, y = pos[label]
    plt.text(x, y, label, fontsize=9, ha='center', va='center', bbox=dict(facecolor='white', edgecolor='black', boxstyle='round,pad=0.3'))

plt.title("Improved Growth Drivers Tree Structure", fontsize=14)
plt.show()

plt.figure(figsize=(10, 5))
sns.boxplot(x=df["metric"], y=df["execution"])
plt.yscale("log")
plt.title("Distribution of 'execution' by metric type (log scale)")
plt.xticks(rotation=45)
plt.show()

# Filter only rows related to Online Growth Drivers
online_df = df.copy()

# Keep relevant Online KPIs
online_df = online_df[
    [
        "Starting Week",
        "Year",
        "growth_driver_l1",
        "growth_driver_l2",
        "growth_driver_l3",
        "growth_driver_l4",
        "growth_driver_l5",
        "metric",
        "investment (in pound)",
        "execution",
        "UK L'Oreal Paris Haircare Online Average Price (in pound)",
        "UK L'Oreal Paris Haircare Total Weigheted Promotion Distribution (%)",
        "UK L'Oreal Paris Haircare Total Online Sellout Units"
    ]
]

# Convert date to datetime format
online_df["Starting Week"] = pd.to_datetime(online_df["Starting Week"])

# Sort by date
online_df = online_df.sort_values("Starting Week")

# Check unique values in metric
print("Unique Metrics in Online Data:", online_df["metric"].unique())

# Save for later use
online_df.to_csv("online_dataset.csv", index=False)

online_df.info()

# Count occurrences of each date
date_counts = online_df["Starting Week"].value_counts().reset_index()
date_counts.columns = ["Starting Week", "Count"]

# Show dates where we have duplicates
date_counts = date_counts[date_counts["Count"] > 1]
print("Dates with multiple entries:\n", date_counts)
date_counts.describe()

# Pick a random duplicate date
example_date = date_counts.iloc[0]["Starting Week"]  # First date with duplicates

# Show all rows for that date
print(f"Entries for {example_date}:")
display(online_df[online_df["Starting Week"] == example_date])

# Drop Level 1 growth driver since it's constant
online_df = online_df.drop(columns=["growth_driver_l1"], errors="ignore")

# Create a unique identifier for each growth driver combination
online_df["growth_driver_combination"] = (
    online_df["growth_driver_l2"] + " | " +
    online_df["growth_driver_l3"] + " | " +
    online_df["growth_driver_l4"] + " | " +
    online_df["growth_driver_l5"]
)

# Store metric mapping in a dictionary
metric_mapping = online_df.groupby("growth_driver_combination")["metric"].unique().to_dict()

# Identify the columns that remain constant for each date
constant_columns = [
    "UK L'Oreal Paris Haircare Online Average Price (in pound)",
    "UK L'Oreal Paris Haircare Total Weigheted Promotion Distribution (%)",
    "UK L'Oreal Paris Haircare Total Online Sellout Units"
]

# Keep only one unique row per date for these constant columns
constant_data = online_df[["Starting Week", "Year"] + constant_columns].drop_duplicates()

# Pivot execution & investment by growth driver combination
pivot_df = online_df.pivot_table(
    index=["Starting Week", "Year"],
    columns="growth_driver_combination",
    values=["execution", "investment (in pound)"],
    aggfunc="sum",
    fill_value=0
)

# Flatten MultiIndex column names
pivot_df.columns = [f"{col[0]} - {col[1]}" for col in pivot_df.columns]
pivot_df = pivot_df.reset_index()

# Merge back the constant columns
final_df = pd.merge(pivot_df, constant_data, on=["Starting Week", "Year"], how="left")

# Save the cleaned dataset
final_df.to_csv("online_dataset_cleaned.csv", index=False)

final_df.info()

final_df.head()

"""### EDA of online data"""

# Load the cleaned dataset
df = pd.read_csv("online_dataset_cleaned.csv")

# Convert date column to datetime
df["Starting Week"] = pd.to_datetime(df["Starting Week"])

# Set the figure style
sns.set_style("whitegrid")

# ---------------- 1️⃣ BASIC OVERVIEW ----------------
print("\n🔹 Dataset Overview:")
print(f"Shape: {df.shape}")
print("\n🔹 Column Types:")
print(df.dtypes)

# Missing values
print("\n🔹 Missing Values:")
print(df.isnull().sum())

# Check for duplicates
print("\n🔹 Duplicates:", df.duplicated().sum())

# ---------------- 2️⃣ DESCRIPTIVE STATISTICS ----------------
print("\n🔹 Summary Statistics (Numerical Variables):")
print(df.describe())

# ---------------- 3️⃣ TIME SERIES ANALYSIS ----------------
plt.figure(figsize=(12,5))
plt.plot(df["Starting Week"], df["UK L'Oreal Paris Haircare Total Online Sellout Units"], marker="o", linestyle="-", label="Online Sales")
plt.xlabel("Date")
plt.ylabel("Units Sold")
plt.title("📈 Online Sales Over Time")
plt.legend()
plt.xticks(rotation=45)
plt.show()

# ---------------- 4️⃣ CORRELATION ANALYSIS ----------------
corr_matrix = df.corr()

plt.figure(figsize=(12, 6))
sns.heatmap(corr_matrix, annot=True, cmap="coolwarm", fmt=".2f", linewidths=0.5)
plt.title("🔗 Correlation Heatmap")
plt.show()

# ---------------- 5️⃣ DISTRIBUTIONS OF KEY VARIABLES ----------------
numeric_cols = [
    "UK L'Oreal Paris Haircare Online Average Price (in pound)",
    "UK L'Oreal Paris Haircare Total Weigheted Promotion Distribution (%)",
    "UK L'Oreal Paris Haircare Total Online Sellout Units"
]

for col in numeric_cols:
    plt.figure(figsize=(8,4))
    sns.histplot(df[col], bins=30, kde=True)
    plt.title(f"📊 Distribution of {col}")
    plt.xlabel(col)
    plt.show()

# ---------------- 6️⃣ GROWTH DRIVER IMPACT ANALYSIS ----------------
# Find all execution & investment columns
execution_cols = [col for col in df.columns if "execution" in col]
investment_cols = [col for col in df.columns if "investment" in col]

# Plot execution vs sales
plt.figure(figsize=(12,5))
for col in execution_cols[:5]:  # Limit to first 5 to avoid clutter
    plt.plot(df["Starting Week"], df[col], linestyle="--", alpha=0.7, label=col)

plt.plot(df["Starting Week"], df["UK L'Oreal Paris Haircare Total Online Sellout Units"], color="black", linewidth=2, label="Online Sales")
plt.xlabel("Date")
plt.ylabel("Execution Volume")
plt.title("📊 Execution Impact Over Time")
plt.legend()
plt.xticks(rotation=45)
plt.show()

# Plot investment vs sales
plt.figure(figsize=(12,5))
for col in investment_cols[:5]:  # Limit to first 5
    plt.plot(df["Starting Week"], df[col], linestyle="--", alpha=0.7, label=col)

plt.plot(df["Starting Week"], df["UK L'Oreal Paris Haircare Total Online Sellout Units"], color="black", linewidth=2, label="Online Sales")
plt.xlabel("Date")
plt.ylabel("Investment (£)")
plt.title("💰 Investment Impact Over Time")
plt.legend()
plt.xticks(rotation=45)
plt.show()

print("✅ Full EDA Completed!")

"""### Feature eng"""

# Load dataset
df = pd.read_csv("online_dataset_cleaned.csv")

# Convert date column to datetime
df["Starting Week"] = pd.to_datetime(df["Starting Week"])

# Drop investment columns (we'll use them later for ROI)
df = df.drop(columns=[col for col in df.columns if "investment" in col])

# Set date as index
df = df.set_index("Starting Week")

# ---------------- 1️⃣ TIME-BASED FEATURES ----------------
df["Year"] = df.index.year
df["Month"] = df.index.month
df["Week"] = df.index.isocalendar().week

# UK Holidays (binary feature)
uk_holidays = holidays.country_holidays('GB')
df["Is_Holiday"] = df.index.to_series().apply(lambda x: 1 if x in uk_holidays else 0)

# ---------------- 2️⃣ LAGS (PAST WEEKS EFFECT) ----------------
lag_features = [col for col in df.columns if "execution" in col]
for col in lag_features:
    for lag in range(1, 5):  # Create 1 to 4-week lags
        df[f"{col}_lag{lag}"] = df[col].shift(lag)

# ---------------- 3️⃣ DECAY (EXPONENTIAL WEIGHTED MOVING AVERAGE) ----------------
for col in lag_features:
    df[f"{col}_decay"] = df[col].ewm(span=4, adjust=False).mean()

# ---------------- 4️⃣ SATURATION (Diminishing Returns) ----------------
for col in lag_features:
    df[f"{col}_saturation"] = np.log1p(df[col])  # log transformation for diminishing returns

# ---------------- 5️⃣ ADSTOCK (CARRYOVER EFFECT) ----------------
def adstock(series, alpha=0.7):
    """Apply Adstock transformation with decay factor alpha."""
    result = np.zeros(len(series))
    for i in range(1, len(series)):
        result[i] = series.iloc[i] + alpha * result[i - 1]
    return result

for col in lag_features:
    df[f"{col}_adstock"] = adstock(df[col])

# ---------------- 6️⃣ FINAL TARGET & FEATURES ----------------
# Define target variable
y = df["UK L'Oreal Paris Haircare Total Online Sellout Units"]

# Define features (drop target variable)
X = df.drop(columns=["UK L'Oreal Paris Haircare Total Online Sellout Units"])

# Drop NaN values caused by lags
X = X.dropna()
y = y.loc[X.index]

X.head()

X.info()

from sklearn.ensemble import RandomForestRegressor
from sklearn.feature_selection import RFE
from sklearn.linear_model import LinearRegression


# ---------------- 1️⃣ REMOVE HIGHLY CORRELATED FEATURES ----------------
corr_matrix = X.corr().abs()

# Find features that are highly correlated
high_corr_pairs = np.where(corr_matrix > 0.9)
high_corr_pairs = [(corr_matrix.index[i], corr_matrix.columns[j])
                   for i, j in zip(*high_corr_pairs) if i != j]

# Drop one feature from each correlated pair
features_to_drop = set()
for f1, f2 in high_corr_pairs:
    if f1 not in features_to_drop and f2 not in features_to_drop:
        features_to_drop.add(f2)  # Arbitrarily drop the second feature

X_filtered = X.drop(columns=features_to_drop)
print(f"✅ Dropped {len(features_to_drop)} highly correlated features.")

# ---------------- 2️⃣ FEATURE IMPORTANCE (RANDOM FOREST) ----------------
rf = RandomForestRegressor(n_estimators=100, random_state=42)
rf.fit(X_filtered, y.values.ravel())  # Train Random Forest

# Get feature importances
feature_importance = pd.Series(rf.feature_importances_, index=X_filtered.columns)
feature_importance = feature_importance.sort_values(ascending=False)

# Plot top 20 most important features
plt.figure(figsize=(10,6))
sns.barplot(x=feature_importance[:20], y=feature_importance.index[:20])
plt.title("Top 20 Feature Importances (Random Forest)")
plt.xlabel("Importance Score")
plt.ylabel("Feature")
plt.show()

# Drop features with very low importance (< threshold)
low_importance_features = feature_importance[feature_importance < 0.01].index
X_filtered = X_filtered.drop(columns=low_importance_features)
print(f"✅ Dropped {len(low_importance_features)} low-importance features.")

# ---------------- 3️⃣ RECURSIVE FEATURE ELIMINATION (RFE) ----------------
rfe = RFE(estimator=LinearRegression(), n_features_to_select=20)  # Keep top 20 features
rfe.fit(X_filtered, y.values.ravel())

# Select only the best features
selected_features = X_filtered.columns[rfe.support_]
X_final = X_filtered[selected_features]

print(f"✅ Selected {len(selected_features)} best features with RFE.")

# Save final dataset
X_final.to_csv("X_features_selected.csv")
print("✅ Feature selection complete. Final dataset saved as 'X_features_selected.csv'.")

"""### Training"""

y.info()

X_final.info()

X_final.describe()

X_final.head()

# Load the full dataset
X = X_final.copy()

# Ensure index is datetime
X.index = pd.to_datetime(X.index)
y.index = pd.to_datetime(y.index)

# Align datasets (avoid index mismatches)
X, y = X.align(y, join="inner", axis=0)

# ---------------- 1️⃣ Fit OLS Model on Full Dataset ----------------
X_ols = sm.add_constant(X)  # Add intercept
ols_model = sm.OLS(y, X_ols).fit()  # Fit OLS on full data

# ---------------- 2️⃣ Model Diagnostics ----------------
# R² Score (Goodness of Fit)
r2_ols = ols_model.rsquared

# Durbin-Watson Test (Autocorrelation Check)
dw_ols = durbin_watson(ols_model.resid)

# Variance Inflation Factor (Multicollinearity Check)
vif_data = pd.DataFrame()
vif_data["Feature"] = X.columns
vif_data["VIF"] = [variance_inflation_factor(X.values, i) for i in range(X.shape[1])]

# ---------------- 3️⃣ Print Results ----------------
print("\n🔹 OLS Regression Results:")
print(f"R² Score (Full Dataset): {r2_ols:.4f}")
print(f"Durbin-Watson: {dw_ols:.4f}")

print("\n🔹 Variance Inflation Factor (VIF):")
print(vif_data)

print("\n🔹 OLS Model Summary:")
print(ols_model.summary())

# Compute VIF
vif_data = pd.DataFrame()
vif_data["Feature"] = X.columns
vif_data["VIF"] = [variance_inflation_factor(X.values, i) for i in range(X.shape[1])]

# Drop highly collinear features
high_vif_features = vif_data[vif_data["VIF"] > 10]["Feature"].tolist()
X = X.drop(columns=high_vif_features)

print(f"\n✅ Dropped {len(high_vif_features)} multicollinear features")
print(vif_data)

X.describe()

# ---------------- 1️⃣ Fit OLS Model on Full Dataset ----------------
X_ols = sm.add_constant(X)  # Add intercept
ols_model = sm.OLS(y, X_ols).fit()  # Fit OLS on full data

# ---------------- 2️⃣ Model Diagnostics ----------------
# R² Score (Goodness of Fit)
r2_ols = ols_model.rsquared

# Durbin-Watson Test (Autocorrelation Check)
dw_ols = durbin_watson(ols_model.resid)

# Variance Inflation Factor (Multicollinearity Check)
vif_data = pd.DataFrame()
vif_data["Feature"] = X.columns
vif_data["VIF"] = [variance_inflation_factor(X.values, i) for i in range(X.shape[1])]

# ---------------- 3️⃣ Print Results ----------------
print("\n🔹 OLS Regression Results:")
print(f"R² Score (Full Dataset): {r2_ols:.4f}")
print(f"Durbin-Watson: {dw_ols:.4f}")

print("\n🔹 Variance Inflation Factor (VIF):")
print(vif_data)

print("\n🔹 OLS Model Summary:")
print(ols_model.summary())

# Add lagged sales as a feature
X["sales_lag1"] = y.shift(1)
X["sales_lag2"] = y.shift(2)

# Drop first few rows (due to NaN from lags)
X, y = X.iloc[2:], y.iloc[2:]

# Recompute Durbin-Watson
dw_stat = durbin_watson(ols_model.resid)
print(f"\n🔹 Durbin-Watson after adding lags: {dw_stat:.4f}")

# ---------------- 1️⃣ Fit OLS Model on Full Dataset ----------------
X_ols = sm.add_constant(X)  # Add intercept
ols_model = sm.OLS(y, X_ols).fit()  # Fit OLS on full data

# ---------------- 2️⃣ Model Diagnostics ----------------
# R² Score (Goodness of Fit)
r2_ols = ols_model.rsquared

# Durbin-Watson Test (Autocorrelation Check)
dw_ols = durbin_watson(ols_model.resid)

# Variance Inflation Factor (Multicollinearity Check)
vif_data = pd.DataFrame()
vif_data["Feature"] = X.columns
vif_data["VIF"] = [variance_inflation_factor(X.values, i) for i in range(X.shape[1])]

# ---------------- 3️⃣ Print Results ----------------
print("\n🔹 OLS Regression Results:")
print(f"R² Score (Full Dataset): {r2_ols:.4f}")
print(f"Durbin-Watson: {dw_ols:.4f}")

print("\n🔹 Variance Inflation Factor (VIF):")
print(vif_data)

print("\n🔹 OLS Model Summary:")
print(ols_model.summary())

# ---------------- 1️⃣ Fit OLS Model with Non-Negative Coefficients ----------------
X_ols = sm.add_constant(X)  # Add intercept

# Use Non-Negative Least Squares (NNLS) to enforce positive coefficients
beta_nnls, _ = nnls(X_ols, y)

# Manually compute model predictions and residuals
y_pred = X_ols @ beta_nnls
residuals = y - y_pred

# ---------------- 2️⃣ Model Diagnostics ----------------
# R² Score (Goodness of Fit)
ss_total = np.sum((y - np.mean(y))**2)
ss_residual = np.sum(residuals**2)
r2_nnls = 1 - (ss_residual / ss_total)

# Adjusted R² Score
n, p = X.shape
adj_r2_nnls = 1 - (1 - r2_nnls) * (n - 1) / (n - p - 1)

# Durbin-Watson Test (Autocorrelation Check)
dw_nnls = durbin_watson(residuals)

# Variance Inflation Factor (Multicollinearity Check)
vif_data = pd.DataFrame()
vif_data["Feature"] = X.columns
vif_data["VIF"] = [variance_inflation_factor(X.values, i) for i in range(X.shape[1])]

# ---------------- 3️⃣ Print Results ----------------
print("\n🔹 OLS Regression Results with Non-Negative Coefficients:")
print(f"R² Score (Full Dataset): {r2_nnls:.4f}")
print(f"Adjusted R² Score: {adj_r2_nnls:.4f}")
print(f"Durbin-Watson: {dw_nnls:.4f}")

print("\n🔹 Variance Inflation Factor (VIF):")
print(vif_data)

print("\n🔹 Model Coefficients:")
coef_df = pd.DataFrame({"Feature": ["Intercept"] + list(X.columns), "Coefficient": beta_nnls})
print(coef_df)

"""Fully optimized attempt in terms of R2 - too much loss of durbin watson"""

lags = [6]
spans = [6]
alphas = [0.3]
cors = [0.97]
imps = [0.003]
sels = [35]

best_r2 = 0
best_lag_range = 0
best_sp = 0
best_alph = 0
best_cor = 0
best_imp = 0
best_sel = 0

n=0


# Load dataset
df = pd.read_csv("online_dataset_cleaned.csv")

# Convert date column to datetime
df["Starting Week"] = pd.to_datetime(df["Starting Week"])
df = df.set_index("Starting Week")

# LAG, DECAY, ADSTOCK
lag_features = [col for col in df.columns if "execution" in col]
for col in lag_features:
    for lag in range(1, lag_range):
        df[f"{col}_lag{lag}"] = df[col].shift(lag)

    df[f"{col}_decay"] = df[col].ewm(span=sp, adjust=False).mean()
    df[f"{col}_saturation"] = np.log1p(df[col])

def adstock(series, alpha=alph):
    result = np.zeros(len(series))
    for i in range(1, len(series)):
        result[i] = series.iloc[i] + alpha * result[i - 1]
    return result

for col in lag_features:
    df[f"{col}_adstock"] = adstock(df[col])

# Define target variable
y = df["UK L'Oreal Paris Haircare Total Online Sellout Units"]
X = df.drop(columns=["UK L'Oreal Paris Haircare Total Online Sellout Units"])
X = X.dropna()
y = y.loc[X.index]

# Correlation Filtering
corr_matrix = X.corr().abs()
high_corr_pairs = np.where(corr_matrix > cor)
high_corr_pairs = [(corr_matrix.index[i], corr_matrix.columns[j])
                  for i, j in zip(*high_corr_pairs) if i != j]

features_to_drop = set()
for f1, f2 in high_corr_pairs:
    if f1 not in features_to_drop and f2 not in features_to_drop:
        features_to_drop.add(f2)

X_filtered = X.drop(columns=features_to_drop)

# print(f"✅ Dropped {len(features_to_drop)} highly correlated features.")
# print(f"Remaining features after correlation filter: {X_filtered.shape[1]}")

if X_filtered.shape[1] == 0:
    print("❌ No features left after correlation filtering! Skipping iteration...")
    continue

# Feature Importance Filtering
rf = RandomForestRegressor(n_estimators=100, random_state=42)
rf.fit(X_filtered, y.values.ravel())

feature_importance = pd.Series(rf.feature_importances_, index=X_filtered.columns)
low_importance_features = feature_importance[feature_importance < imp].index
X_filtered = X_filtered.drop(columns=low_importance_features)

# print(f"✅ Dropped {len(low_importance_features)} low-importance features.")
# print(f"Remaining features after importance filter: {X_filtered.shape[1]}")

if X_filtered.shape[1] == 0:
    print("❌ No features left after importance filtering! Skipping iteration...")
    continue

# RFE Selection
rfe = RFE(estimator=LinearRegression(), n_features_to_select=min(sel, X_filtered.shape[1]))
rfe.fit(X_filtered, y.values.ravel())

selected_features = X_filtered.columns[rfe.support_]
X_final = X_filtered[selected_features]

# print(f"✅ Selected {len(selected_features)} best features with RFE.")
# print(f"Remaining features after RFE: {X_final.shape[1]}")

if X_final.shape[1] == 0:
    print("❌ No features left after RFE! Skipping iteration...")
    continue

# Check if X is empty before proceeding
if X_final.shape[1] == 0:
    print("❌ No features left! Skipping iteration...")
    continue

# Compute VIF only if there are features left
vif_data = pd.DataFrame()
vif_data["Feature"] = X_final.columns
if X_final.shape[1] > 0:
    vif_data["VIF"] = [variance_inflation_factor(X_final.values, i) for i in range(X_final.shape[1])]
else:
    print("❌ No features left after VIF filtering! Skipping iteration...")
    continue

# Fit OLS Model
X_ols = sm.add_constant(X_final)
beta_nnls, _ = nnls(X_ols, y)
y_pred = X_ols @ beta_nnls
residuals = y - y_pred

r2_nnls = 1 - (np.sum(residuals**2) / np.sum((y - np.mean(y))**2))

if r2_nnls > best_r2:
    best_r2 = r2_nnls
    best_lag_range = lag_range
    best_sp = sp
    best_alph = alph
    best_cor = cor
    best_imp = imp
    best_sel = sel

n+=1

if n % 100 == 0:
  print(n)

print("\n🔹 OLS Regression Results with Non-Negative Coefficients:")
print(f"R² Score (Full Dataset): {r2_nnls:.4f}")
print(f"Adjusted R² Score: {adj_r2_nnls:.4f}")
print(f"Durbin-Watson: {dw_nnls:.4f}")

print("\n🔹 Variance Inflation Factor (VIF):")
print(vif_data)

print("\n🔹 Model Coefficients:")
coef_df = pd.DataFrame({"Feature": ["Intercept"] + list(X.columns), "Coefficient": beta_nnls})
print(coef_df)