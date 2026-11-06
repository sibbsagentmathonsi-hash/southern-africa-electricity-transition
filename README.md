# Southern Africa Electricity Access & Energy Transition

A reproducible World Bank data analysis of electricity access and renewable energy across **South Africa, Botswana, Namibia, Zambia, and Mozambique**. It combines World Bank access, renewable energy consumption, and population indicators to explore regional trends and produce a careful, transparent estimate of the population without electricity access.

The analysis downloads the latest available observations from the official [World Bank Indicators API](https://datahelpdesk.worldbank.org/knowledgebase/articles/889386), aligns country/year series, preserves missing observations, and generates an Excel workbook, charts, CSV files, source metadata, and a methods summary.

## Analysis coverage

- Electricity-access trends and annual changes in percentage points.
- Renewable-energy consumption as a share of total final energy consumption.
- Approximate people without electricity access, calculated from population and access estimates.
- Regional country comparisons and indexed access trends.
- Descriptive pairwise correlations with paired-year counts.
- Excel overview/dashboard, filterable annual data and summary tables, formula-derived access changes, charts, and data definitions.
- API URLs, indicator IDs, last-updated metadata, country coverage, and attribution guidance.

## Run it

Python 3.10+ and internet access are required. No World Bank API key is needed.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python analytics.py
```

By default, the request covers 2000–2025. To use another period:

```powershell
python analytics.py --start-year 1995 --end-year 2025
```

The pipeline fetches country/indicator API requests concurrently with retries. Outputs are created under `outputs/`; rerunning the analysis refreshes the API observations and replaces those files.

## Main outputs

| Output | Contents |
|---|---|
| `outputs/southern_africa_electricity_transition.xlsx` | Overview dashboard, annual data, country summary, correlation results, missing-values register, API source/methodology sheet, Excel formula, and chart |
| `outputs/ANALYSIS_SUMMARY.md` | Latest observations, missing-data explanation, derived count estimates, indicator definitions, results, and caveats |
| `outputs/annual_energy_access.csv` | Combined annual observations and derived measures; unavailable values are explicitly marked `Not reported` |
| `outputs/country_summary.csv` | Latest available values and changes by country, with years shown for each indicator |
| `outputs/correlations.csv` | Pairwise descriptive correlations and paired-year counts |
| `outputs/missing_values.csv` | Country-year-field register with a reason for every missing source or derived value |
| `outputs/source_metadata.json` | Indicator IDs, API URLs, retrieval date, update dates, and year coverage |
| `outputs/charts/*.png` | Electricity access, renewable consumption, estimated population without access, and correlation heatmap |

## Indicators, calculations, and interpretation

- **Electricity access:** World Bank indicator `EG.ELC.ACCS.ZS`, *Access to electricity (% of population)*. This is an access estimate; it does not mean power is reliable, affordable, or continuously available.
- **Renewable energy consumption:** `EG.FEC.RNEW.ZS`, *Renewable energy consumption (% of total final energy consumption)*. It is **not** renewable electricity generation as a share of the power grid.
- **Population:** `SP.POP.TOTL`, *Population, total*.
- **Estimated people without access:** `population × (100 − access percentage) ÷ 100`. This is a derived approximation using separate estimates, not an observed headcount. API estimate vintages may not align exactly.
- **Access change:** annual change in access percentage points, not a percent growth rate.
- **Correlations:** Pearson association for available paired years. These are exploratory descriptive statistics, not causal evidence or forecasts.

The indicators have different release schedules. In the 2026 API snapshot, electricity access is available through 2024, renewable-energy consumption through 2021, and population through 2025. The annual CSV explicitly marks unavailable values as `Not reported`, the workbook uses descriptive missing-value labels, and the missing-values register lists country, year, field, and reason. The Excel access-change formula is in its own final column and does not overwrite the estimated-population data. Missing values are never silently imputed or converted to zero. To restore numeric missing values in pandas, load with `na_values=["Not reported"]`.

## Source and attribution

- [World Bank API documentation](https://datahelpdesk.worldbank.org/knowledgebase/articles/889386)
- [Electricity access](https://data.worldbank.org/indicator/EG.ELC.ACCS.ZS)
- [Renewable energy consumption](https://data.worldbank.org/indicator/EG.FEC.RNEW.ZS)
- [Population](https://data.worldbank.org/indicator/SP.POP.TOTL)
- [World Bank public license information](https://datacatalog.worldbank.org/public-licenses#cc-by)

World Bank open data generally references CC BY 4.0. Attribute the World Bank and any original data providers identified on the indicator pages when you reuse the observations. Exact API URLs and metadata are retained in the generated metadata file.
