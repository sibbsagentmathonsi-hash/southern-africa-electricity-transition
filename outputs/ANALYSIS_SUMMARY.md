# Southern Africa Electricity Access & Energy Transition

## Scope

World Bank annual estimates for 2000–2025 across South Africa, Botswana, Namibia, Zambia, and Mozambique. Electricity-access estimates currently run through 2024, renewable-energy-consumption estimates through 2021, and population estimates through 2025. Latest years therefore differ by indicator.

## Electricity access and estimated population without access

| country | electricity_access_latest_year | electricity_access_latest_value | people_without_electricity_latest_value |
| --- | --- | --- | --- |
| South Africa | 2024 | 90.20 | 6,272,704 |
| Botswana | 2024 | 80.20 | 499,186 |
| Namibia | 2024 | 59.30 | 1,233,263 |
| Zambia | 2024 | 53.60 | 9,890,140 |
| Mozambique | 2024 | 36.90 | 21,852,644 |

Estimated people without access is calculated as population × (100 − electricity access percentage) / 100, using the latest available values of each input. It is an approximate population-level estimate, not a household enumeration; input years may differ. The accompanying data includes each component and year so this estimate can be checked.

## Renewable energy consumption

| country | renewable_energy_latest_year | renewable_energy_latest_value |
| --- | --- | --- |
| South Africa | 2021 | 9.70 |
| Botswana | 2021 | 27.40 |
| Namibia | 2021 | 30.00 |
| Zambia | 2021 | 83.00 |
| Mozambique | 2021 | 76.90 |

The indicator measures renewable energy consumption as a share of **total final energy consumption**. It is not the renewable share of electricity generation and should not be read as a direct counterpart to electricity access.

## South Africa association (descriptive only)

Across 22 paired annual observations, the Pearson correlation between electricity access and renewable energy consumption share is **-0.84**. This describes co-movement only. It does not show that electricity access causes renewable-energy use or vice versa.

## Data sources and attribution

- `EG.ELC.ACCS.ZS` — Access to electricity (% of population); API updated 2026-10-08; country coverage: ZAF 2000–2024, BWA 2000–2024, NAM 2000–2024, ZMB 2000–2024, MOZ 2000–2024.
- `EG.FEC.RNEW.ZS` — Renewable energy consumption (% of total final energy consumption); API updated 2026-10-08; country coverage: ZAF 2000–2021, BWA 2000–2021, NAM 2000–2021, ZMB 2000–2021, MOZ 2000–2021.
- `SP.POP.TOTL` — Population, total; API updated 2026-10-08; country coverage: ZAF 2000–2025, BWA 2000–2025, NAM 2000–2025, ZMB 2000–2025, MOZ 2000–2025.

Source: [World Bank Indicators API](https://datahelpdesk.worldbank.org/knowledgebase/articles/889386). Indicator pages: [electricity access](https://data.worldbank.org/indicator/EG.ELC.ACCS.ZS), [renewable energy consumption](https://data.worldbank.org/indicator/EG.FEC.RNEW.ZS), and [population](https://data.worldbank.org/indicator/SP.POP.TOTL). World Bank open data generally references [CC BY 4.0](https://datacatalog.worldbank.org/public-licenses#cc-by); cite the World Bank and any original sources shown on the indicator pages.

## Methods and caveats

- **Electricity access (`EG.ELC.ACCS.ZS`):** estimated share of population with access; it does not measure reliability, affordability, connection quality, or hours supplied.
- **Renewable energy (`EG.FEC.RNEW.ZS`):** renewables as a percentage of total final energy consumption, not electricity-generation mix.
- **People without access:** derived from population and access estimates. Differences in estimate vintages and uncertainty can affect the count.
- **Access change:** year-over-year change in percentage points, not percent growth.
- Missing indicator values remain missing, never replaced with zero. Comparisons and correlations use only available paired observations.
- Correlations are descriptive, unadjusted annual associations between electricity access and renewable energy consumption. They do not address confounding, statistical significance, timing lags, measurement uncertainty, common time trends, or causation.
- The project retrieves the API when rerun; response URLs, update dates, and nonmissing coverage are stored in `outputs/source_metadata.json`.
