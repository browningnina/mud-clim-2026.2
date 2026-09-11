
"""
Synthetic daily precipitation generator for Rio de Janeiro (1986-01-01 to 2025-12-31)

Author: AI assistant using Copilot CLI runtime in VS Code
Seed: 42

Sections (as requested):
1. Imports
2. Configurações
3. Período da série
4. Características climáticas mensais
5. Parâmetros dos extremos
6. Variabilidade interanual
7. Geração da ocorrência de precipitação
8. Geração da intensidade
9. Eventos extremos
10. Criação do DataFrame
11. Exportação para CSV
12. Estatísticas da série
13. Gráficos

Notes:
- The model is synthetic and uses plausible approximate parameters for Rio de Janeiro's seasonality
- Uses a first-order Markov chain for occurrence with monthly-varying transition probs
- Intensities (on wet days) follow a Gamma distribution with monthly-varying mean
- Each year has a lognormal multiplier around 1 for interannual variability
- Occasional extremes are generated from a Generalized Pareto Distribution (GPD) above ~50 mm

This script requires: numpy, pandas, scipy, matplotlib
Run directly in VSCode or Jupyter. Results saved to Serie_Precip_Marina.csv
"""
#%%
# 1. Imports
import numpy as np
import pandas as pd
from scipy import stats
import matplotlib.pyplot as plt
from typing import List, Tuple

# openpyxl is used to write .xlsx files via pandas.to_excel
# If not installed in the environment, install with: pip install openpyxl

#%%
# 2. Configurações
SEED = 42
rng = np.random.default_rng(SEED)

#%%
# 3. Período da série de 40 anos (1986-01-01 a 2025-12-31)
START_DATE = "1986-01-01"
END_DATE = "2025-12-31"
DATES = pd.date_range(start=START_DATE, end=END_DATE, freq='D')
OUTPUT_CSV = "Serie_Precip_Marina.csv"
OUTPUT_XLSX = "Serie_Precip_Marina.xlsx"

#%%
# 4. Características climáticas mensais
# Rio de Janeiro: wetter in austral summer (~Nov-Mar), drier in austral winter (~Jun-Aug)
# Define monthly probabilities for the 1st-order Markov chain transitions:
# p01: probability of rain today given yesterday was dry
# p11: probability of rain today given yesterday was rainy (persistence)
# Values are plausible, approximate, and vary month-to-month to represent seasonality

# Index 0 = January ... 11 = December
p01_month = np.array([
    0.20,  # Jan (wet)
    0.18,  # Feb
    0.17,  # Mar
    0.12,  # Apr
    0.10,  # May
    0.06,  # Jun (drier)
    0.05,  # Jul (driest)
    0.07,  # Aug
    0.10,  # Sep
    0.14,  # Oct
    0.18,  # Nov (getting wet)
    0.20   # Dec (wet)
])

# Persistence: rainy day followed by another rainy day probability
p11_month = np.array([
    0.60,  # Jan
    0.58,  # Feb
    0.55,  # Mar
    0.45,  # Apr
    0.40,  # May
    0.30,  # Jun
    0.28,  # Jul
    0.32,  # Aug
    0.40,  # Sep
    0.48,  # Oct
    0.56,  # Nov
    0.60   # Dec
])

"""
Gamma distribution parameters for rainy-day amounts. Instead of setting shape/scale directly,
it's often intuitive to set the mean precipitation on rainy days by month (mm) and a shape parameter
that controls skewness. Then scale = mean / shape.
"""
# Monthly mean precipitation on rainy days (plausible values; higher in summer months):

mean_gamma_mm = np.array([
    25.0,  # Jan
    24.0,  # Feb
    22.0,  # Mar
    18.0,  # Apr
    14.0,  # May
    10.0,  # Jun
    9.0,   # Jul
    10.0,  # Aug
    12.0,  # Sep
    16.0,  # Oct
    20.0,  # Nov
    24.0   # Dec
])

# Choose monthly shape parameters (k). Lower k => heavier tail. Use modest k (1.2 - 2.5)
shape_gamma_k = np.array([
    1.6,  # Jan
    1.6,  # Feb
    1.7,  # Mar
    1.8,  # Apr
    2.0,  # May
    2.2,  # Jun
    2.3,  # Jul
    2.2,  # Aug
    2.0,  # Sep
    1.9,  # Oct
    1.7,  # Nov
    1.6   # Dec
])

# Derive scales for gamma: scale = mean / k
scale_gamma_theta = mean_gamma_mm / shape_gamma_k

#%%
# 5. Parâmetros dos extremos (GPD)
# Use threshold (u) around 50 mm/day to define extremes
GPD_THRESHOLD = 50.0  # mm/day
# GPD parameters - shape xi and scale sigma. Small positive xi produces heavy but realistic tails.
GPD_XI = 0.12
GPD_SCALE = 18.0  # mm - moderate scale for exceedances

# Probability that a rainy day is an extreme override (monthly-varying to reflect seasonality)
# We'll make this small: higher in wet months
base_extreme_prob = np.array([
    0.015,  # Jan
    0.013,  # Feb
    0.012,  # Mar
    0.008,  # Apr
    0.006,  # May
    0.004,  # Jun
    0.003,  # Jul
    0.004,  # Aug
    0.005,  # Sep
    0.007,  # Oct
    0.010,  # Nov
    0.014   # Dec
])

#%%
# 6. Variabilidade interanual
# Each year receives a positive multiplier sampled from a Lognormal with mean ~1
# Choose lognormal sigma to produce moderate interannual variability
annual_sigma = 0.18
annual_mu = -0.5 * (annual_sigma ** 2)  # so that mean = exp(mu + sigma^2 / 2) = 1

# Generate annual multipliers for years in the period
years = np.arange(DATES[0].year, DATES[-1].year + 1)
n_years = len(years)
annual_factors = rng.lognormal(mean=annual_mu, sigma=annual_sigma, size=n_years)
# Map year -> factor
year_to_factor = dict(zip(years, annual_factors))

#%%
# 7. Geração da ocorrência de precipitação (1st-order Markov chain)

def generate_occurrence(dates: pd.DatetimeIndex,
                        p01_month: np.ndarray,
                        p11_month: np.ndarray,
                        rng: np.random.Generator) -> np.ndarray:
    """Generate boolean array indicating wet (True) or dry (False) days.

    The transition probabilities p01_month and p11_month are arrays length-12 for months Jan..Dec.
    """
    n = len(dates)
    occ = np.zeros(n, dtype=bool)

    # Initialize first day based on the stationary probability for that month
    m0 = dates[0].month - 1
    p01 = p01_month[m0]
    p11 = p11_month[m0]
    # Stationary probability for being wet: pi = p01 / (p01 + (1 - p11))
    denom = p01 + (1.0 - p11)
    pi = p01 / denom if denom > 0 else 0.1
    occ[0] = rng.uniform() < pi

    # Iterate
    for i in range(1, n):
        month_idx = dates[i].month - 1
        if occ[i - 1]:
            prob = p11_month[month_idx]
        else:
            prob = p01_month[month_idx]

        occ[i] = rng.uniform() < prob

    return occ

#%%
# 8. Geração da intensidade (Gamma for wet days), applying annual factor

def generate_intensity(dates: pd.DatetimeIndex,
                       occurrence: np.ndarray,
                       shape_k: np.ndarray,
                       scale_theta: np.ndarray,
                       year_to_factor: dict,
                       rng: np.random.Generator) -> np.ndarray:
    """Generate precipitation amounts (mm) for all dates given occurrence mask.
    For dry days, amount is 0. For wet days, sample from Gamma(k, theta) and multiply by annual factor.
    """
    amounts = np.zeros(len(dates), dtype=float)

    for i, date in enumerate(dates):
        if not occurrence[i]:
            continue

        m = date.month - 1
        k = shape_k[m]
        theta = scale_theta[m]
        year_factor = year_to_factor[date.year]

        # Sample Gamma - rng.gamma uses shape, scale
        base_amount = rng.gamma(shape=k, scale=theta)

        # Apply annual multiplier
        amt = base_amount * year_factor

        # Ensure non-negative (should already be)
        amounts[i] = max(0.0, amt)

    return amounts

#%%
# 9. Eventos extremos (apply GPD to a small fraction of wet days)

def apply_extremes(dates: pd.DatetimeIndex,
                   amounts: np.ndarray,
                   occurrence: np.ndarray,
                   gpd_threshold: float,
                   gpd_xi: float,
                   gpd_scale: float,
                   extreme_prob_month: np.ndarray,
                   rng: np.random.Generator) -> np.ndarray:
    """Override some wet days with GPD exceedances above threshold.

    Strategy:
    - For each wet day, with probability extreme_prob_month[month] generate an extreme amount
      as threshold + GPD_excess (sampled via inverse CDF), replacing the gamma amount.
    - Otherwise keep the gamma amount. This ensures rare extremes and control over their frequency.
    """
    n = len(dates)
    out = amounts.copy()

    for i, date in enumerate(dates):
        if not occurrence[i]:
            continue

        month_idx = date.month - 1
        eprob = extreme_prob_month[month_idx]

        if rng.uniform() < eprob:
            # Sample excess from GPD with parameters xi and scale
            u = rng.uniform()
            xi = gpd_xi
            sigma = gpd_scale
            if xi == 0:
                excess = -sigma * np.log(1 - u)
            else:
                excess = (sigma / xi) * ((1 - u) ** (-xi) - 1)

            extreme_value = gpd_threshold + excess

            # Guard: avoid absurdly huge extremes by capping at, e.g., 600 mm/day
            extreme_value = min(extreme_value, 600.0)

            out[i] = extreme_value

        else:
            # If gamma sample is inexplicably above threshold, allow it (rare) but cap moderately
            if out[i] > 1000:
                out[i] = 1000.0

    # Safety: ensure no negative values
    out[out < 0] = 0.0
    return out

# Helper: build full series pipeline

def build_synthetic_series(dates: pd.DatetimeIndex,
                           rng: np.random.Generator) -> pd.DataFrame:
    occ = generate_occurrence(dates, p01_month, p11_month, rng)
    amounts = generate_intensity(dates, occ, shape_gamma_k, scale_gamma_theta, year_to_factor, rng)
    amounts_with_extremes = apply_extremes(dates, amounts, occ,
                                           GPD_THRESHOLD, GPD_XI, GPD_SCALE,
                                           base_extreme_prob, rng)

    # Ensure that days marked dry have exactly 0
    amounts_with_extremes[~occ] = 0.0

    df = pd.DataFrame({
        'date': dates,
        'precipitation_mm': np.round(amounts_with_extremes, 2)  # round to 2 decimals for neatness
    })

    return df

#%%
# 10. Criação do DataFrame
if __name__ == '__main__':
    df = build_synthetic_series(DATES, rng)

    # Final safety checks
    assert df['date'].min() == pd.to_datetime(START_DATE), "Start date mismatch"
    assert df['date'].max() == pd.to_datetime(END_DATE), "End date mismatch"
    assert (df['precipitation_mm'] >= 0).all(), "Negative precipitation values found"

    # 11. Exportação para CSV e conversão para XLSX
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"Saved synthetic series to: {OUTPUT_CSV}")

    # Read the generated CSV back and convert it to Excel (.xlsx)
    df_from_csv = pd.read_csv(OUTPUT_CSV)
    df_from_csv['date'] = pd.to_datetime(df_from_csv['date'])
    df_from_csv.to_excel(OUTPUT_XLSX, index=False, engine='openpyxl')
    print(f"Converted synthetic series to: {OUTPUT_XLSX}")

    # 13. Gráficos
    # Graph 1: full time series (plot as small vertical lines to show magnitude over long period)
    plt.figure(figsize=(14, 5))
    plt.vlines(df['date'], ymin=0, ymax=df['precipitation_mm'], color='tab:blue', alpha=0.6, linewidth=0.5)
    plt.xlabel('Ano')
    plt.ylabel('Precipitação (mm)')
    plt.title('Série de Precipitação Sintética - Rio de Janeiro')
    plt.tight_layout()
    plt.show()

    # Graph 2: monthly boxplot across all years
    df['month'] = df['date'].dt.month
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

    # Prepare data for boxplot: list of arrays for each month
    data_by_month = [df.loc[df['month'] == (m+1), 'precipitation_mm'].values for m in range(12)]

    plt.figure(figsize=(12, 6))
    bplot = plt.boxplot(data_by_month, labels=month_names, showfliers=True, patch_artist=True)
    plt.xlabel('Mês')
    plt.ylabel('Precipitação (mm)')
    plt.title('Distribuição Mensal da Série de Precipitação Sintética')

    # Style the boxes a bit
    for patch in bplot['boxes']:
        patch.set_facecolor('lightblue')

    plt.tight_layout()
    plt.show()

    # final quick verification printed
    print('\nVerification:')
    print(f"First date: {df['date'].min().date()}, Last date: {df['date'].max().date()}")
    print(f"All precipitation >= 0: {bool((df['precipitation_mm'] >= 0).all())}")

#%%
# 14. Nova série com redução gradual de 15% nos últimos 30 anos
# A redução é linear: começa em 0% em 1996 e chega a 15% em 2025.
REDUCTION_START_DATE = pd.Timestamp("1996-01-01")
REDUCTION_END_DATE = pd.Timestamp("2025-12-31")
REDUCED_OUTPUT_CSV = "Serie_Precip_Marina_reducao_15.csv"
REDUCED_OUTPUT_XLSX = "Serie_Precip_Marina_reducao_15.xlsx"

reduced_rng = np.random.default_rng(SEED)
df_reduced = build_synthetic_series(DATES, reduced_rng)

date_values = df_reduced["date"]
period_days = (REDUCTION_END_DATE - REDUCTION_START_DATE).days
elapsed_days = (date_values - REDUCTION_START_DATE).dt.days
reduction_progress = (
    elapsed_days.clip(lower=0, upper=period_days) / period_days
)
reduction_factor = 1.0 - (0.15 * reduction_progress)

df_reduced["precipitation_mm"] = np.round(
    df_reduced["precipitation_mm"] * reduction_factor, 2
)

df_reduced.to_csv(REDUCED_OUTPUT_CSV, index=False)
df_reduced.to_excel(REDUCED_OUTPUT_XLSX, index=False, engine="openpyxl")
print(f"Saved reduced synthetic series to: {REDUCED_OUTPUT_CSV}")
print(f"Saved reduced synthetic series to: {REDUCED_OUTPUT_XLSX}")

# Gráfico da série inteira
plt.figure(figsize=(14, 5))
plt.vlines(
    df_reduced["date"],
    ymin=0,
    ymax=df_reduced["precipitation_mm"],
    color="tab:green",
    alpha=0.6,
    linewidth=0.5,
)
plt.xlabel("Ano")
plt.ylabel("Precipitação (mm)")
plt.title("Série de Precipitação Sintética com Redução Gradual de 15%")
plt.tight_layout()
plt.show()

# Boxplot mensal
df_reduced["month"] = df_reduced["date"].dt.month
month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
data_by_month_reduced = [
    df_reduced.loc[
        df_reduced["month"] == (month + 1), "precipitation_mm"
    ].values
    for month in range(12)
]

plt.figure(figsize=(12, 6))
bplot_reduced = plt.boxplot(
    data_by_month_reduced,
    labels=month_names,
    showfliers=True,
    patch_artist=True,
)
plt.xlabel("Mês")
plt.ylabel("Precipitação (mm)")
plt.title("Distribuição Mensal com Redução Gradual de 15%")
for patch in bplot_reduced["boxes"]:
    patch.set_facecolor("lightgreen")
plt.tight_layout()
plt.show()
