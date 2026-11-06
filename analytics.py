#!/usr/bin/env python3
"""Analyze World Bank electricity access and energy transition indicators."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from openpyxl import Workbook
from openpyxl.chart import LineChart, Reference
from openpyxl.formatting.rule import ColorScaleRule, DataBarRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.table import Table, TableStyleInfo


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "outputs"
CHART_DIR = OUTPUT_DIR / "charts"
FIRST_YEAR = 2000
LAST_YEAR = 2025
COUNTRIES = {
    "ZAF": "South Africa",
    "BWA": "Botswana",
    "NAM": "Namibia",
    "ZMB": "Zambia",
    "MOZ": "Mozambique",
}
COUNTRY_ORDER = list(COUNTRIES)
INDICATORS = {
    "EG.ELC.ACCS.ZS": (
        "electricity_access_pct",
        "Access to electricity (% of population)",
    ),
    "EG.FEC.RNEW.ZS": (
        "renewable_energy_consumption_pct",
        "Renewable energy consumption (% of total final energy consumption)",
    ),
    "SP.POP.TOTL": ("population", "Population, total"),
}
COLORS = {
    "ZAF": "#2878B5",
    "BWA": "#35A7A0",
    "NAM": "#F2B134",
    "ZMB": "#D9685D",
    "MOZ": "#7656A6",
}


def fetch_country_indicator(
    country_code: str, indicator_id: str, start_year: int, end_year: int
) -> tuple[pd.DataFrame, dict]:
    url = (
        f"https://api.worldbank.org/v2/country/{country_code}/indicator/{indicator_id}?"
        + urllib.parse.urlencode(
            {
                "format": "json",
                "date": f"{start_year}:{end_year}",
                "per_page": 100,
            }
        )
    )
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Southern-Africa-Electricity-Transition/1.0", "Accept": "application/json"},
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                payload = json.load(response)
            break
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            if attempt == 2:
                raise RuntimeError(
                    f"World Bank API request failed for {country_code}/{indicator_id}: {url}"
                ) from error
            time.sleep(2**attempt)

    if not isinstance(payload, list) or len(payload) < 2:
        raise ValueError(f"Unexpected World Bank response for {country_code}/{indicator_id}: {payload!r}")
    metadata, observations = payload[0], payload[1] or []
    column, indicator_name = INDICATORS[indicator_id]
    rows = [
        {
            "country_code": country_code,
            "country": COUNTRIES[country_code],
            "year": int(row["date"]),
            column: row.get("value"),
        }
        for row in observations
        if row.get("countryiso3code") == country_code
    ]
    frame = pd.DataFrame(rows, columns=["country_code", "country", "year", column])
    frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame, {
        "country_code": country_code,
        "country": COUNTRIES[country_code],
        "indicator_id": indicator_id,
        "indicator_name": indicator_name,
        "api_url": url,
        "api_last_updated": metadata.get("lastupdated"),
        "rows_returned": len(frame),
        "nonmissing_observations": int(frame[column].notna().sum()),
        "first_nonmissing_year": int(frame.loc[frame[column].notna(), "year"].min())
        if frame[column].notna().any()
        else None,
        "last_nonmissing_year": int(frame.loc[frame[column].notna(), "year"].max())
        if frame[column].notna().any()
        else None,
    }


def fetch_all(start_year: int, end_year: int) -> tuple[pd.DataFrame, list[dict]]:
    tasks = [
        (country_code, indicator_id)
        for indicator_id in INDICATORS
        for country_code in COUNTRY_ORDER
    ]
    responses: dict[tuple[str, str], tuple[pd.DataFrame, dict]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(
                fetch_country_indicator, country_code, indicator_id, start_year, end_year
            ): (country_code, indicator_id)
            for country_code, indicator_id in tasks
        }
        for future in concurrent.futures.as_completed(futures):
            task = futures[future]
            try:
                responses[task] = future.result()
            except Exception as error:
                raise RuntimeError(f"Failed to fetch required data for {task[0]} {task[1]}") from error

    frames = []
    sources = []
    for indicator_id in INDICATORS:
        parts = []
        for country_code in COUNTRY_ORDER:
            frame, metadata = responses[(country_code, indicator_id)]
            parts.append(frame)
            sources.append(metadata)
        frames.append(pd.concat(parts, ignore_index=True))

    combined = frames[0]
    for frame in frames[1:]:
        combined = combined.merge(
            frame,
            on=["country_code", "country", "year"],
            how="outer",
            validate="one_to_one",
        )
    grid = pd.MultiIndex.from_product(
        [COUNTRY_ORDER, range(start_year, end_year + 1)],
        names=["country_code", "year"],
    ).to_frame(index=False)
    combined = grid.merge(
        combined.drop(columns="country"),
        on=["country_code", "year"],
        how="left",
        validate="one_to_one",
    )
    combined["country"] = combined["country_code"].map(COUNTRIES)
    combined["electricity_access_change_pp"] = np.nan
    combined["estimated_people_without_electricity"] = np.nan
    combined["electricity_access_index_2000_100"] = np.nan
    for _, indices in combined.groupby("country_code", sort=False).groups.items():
        group = combined.loc[indices].sort_values("year")
        combined.loc[group.index, "electricity_access_change_pp"] = group[
            "electricity_access_pct"
        ].diff()
        valid = (
            group["population"].notna()
            & group["electricity_access_pct"].between(0, 100, inclusive="both")
        )
        combined.loc[group.index[valid], "estimated_people_without_electricity"] = (
            group.loc[valid, "population"]
            * (100 - group.loc[valid, "electricity_access_pct"])
            / 100
        )
        baseline = group.loc[
            group["year"].eq(start_year), "electricity_access_pct"
        ].dropna()
        if not baseline.empty and baseline.iloc[0] != 0:
            combined.loc[group.index, "electricity_access_index_2000_100"] = (
                group["electricity_access_pct"] / float(baseline.iloc[0]) * 100
            )
    return combined.sort_values(["country_code", "year"]).reset_index(drop=True), sources


def country_summary(data: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for code in COUNTRY_ORDER:
        group = data.loc[data["country_code"].eq(code)].sort_values("year")
        record = {"country_code": code, "country": COUNTRIES[code]}
        for column, stem in [
            ("electricity_access_pct", "electricity_access"),
            ("renewable_energy_consumption_pct", "renewable_energy"),
            ("estimated_people_without_electricity", "people_without_electricity"),
        ]:
            available = group.dropna(subset=[column])
            if available.empty:
                record[f"{stem}_latest_year"] = None
                record[f"{stem}_latest_value"] = np.nan
                record[f"{stem}_first_year"] = None
                record[f"{stem}_first_value"] = np.nan
                record[f"{stem}_change"] = np.nan
            else:
                first = available.iloc[0]
                latest = available.iloc[-1]
                record[f"{stem}_latest_year"] = int(latest["year"])
                record[f"{stem}_latest_value"] = float(latest[column])
                record[f"{stem}_first_year"] = int(first["year"])
                record[f"{stem}_first_value"] = float(first[column])
                record[f"{stem}_change"] = float(latest[column] - first[column])
        access = group.dropna(subset=["electricity_access_pct"])
        renewable = group.dropna(subset=["renewable_energy_consumption_pct"])
        record["electricity_access_observations"] = len(access)
        record["renewable_energy_observations"] = len(renewable)
        rows.append(record)
    return pd.DataFrame(rows)


def paired_correlations(data: pd.DataFrame) -> pd.DataFrame:
    comparisons = [
        (
            "electricity_access_pct",
            "renewable_energy_consumption_pct",
            "Electricity access vs renewable energy consumption share",
        )
    ]
    rows = []
    for code in COUNTRY_ORDER:
        country_data = data.loc[data["country_code"].eq(code)]
        for left, right, label in comparisons:
            paired = country_data[[left, right]].dropna()
            rows.append(
                {
                    "country_code": code,
                    "country": COUNTRIES[code],
                    "comparison": label,
                    "correlation": paired[left].corr(paired[right]) if len(paired) >= 3 else np.nan,
                    "paired_years": len(paired),
                }
            )
    return pd.DataFrame(rows)


def style_sheet(sheet, table_name: str | None = None) -> None:
    sheet.sheet_view.showGridLines = False
    sheet.freeze_panes = "A2"
    if sheet.max_row:
        for cell in sheet[1]:
            cell.font = Font(color="FFFFFF", bold=True)
            cell.fill = PatternFill("solid", fgColor="17324D")
            cell.alignment = Alignment(vertical="center", wrap_text=True)
        sheet.row_dimensions[1].height = 32
    for column_cells in sheet.columns:
        cells = list(column_cells)
        width = max((len(str(cell.value or "")) for cell in cells[:150]), default=0)
        sheet.column_dimensions[cells[0].column_letter].width = min(max(width + 2, 12), 40)
    if table_name and sheet.max_row > 1:
        table = Table(displayName=table_name, ref=sheet.dimensions)
        table.tableStyleInfo = TableStyleInfo(
            name="TableStyleMedium2",
            showFirstColumn=False,
            showLastColumn=False,
            showRowStripes=True,
            showColumnStripes=False,
        )
        sheet.add_table(table)


def write_table(workbook: Workbook, name: str, frame: pd.DataFrame, table_name: str):
    sheet = workbook.create_sheet(name)
    sheet.append([str(column) for column in frame.columns])
    for row in frame.itertuples(index=False, name=None):
        sheet.append(
            [
                None
                if pd.isna(value)
                else value.item()
                if isinstance(value, np.generic)
                else value
                for value in row
            ]
        )
    style_sheet(sheet, table_name)
    for column_cells in sheet.columns:
        heading = str(column_cells[0].value).lower()
        if "pct" in heading or "change_pp" in heading:
            for cell in list(column_cells)[1:]:
                cell.number_format = "0.00"
        elif "people_without" in heading or heading == "population":
            for cell in list(column_cells)[1:]:
                cell.number_format = "#,##0"
    return sheet


def create_workbook(
    path: Path,
    data: pd.DataFrame,
    summary: pd.DataFrame,
    correlations: pd.DataFrame,
    sources: list[dict],
) -> None:
    workbook = Workbook()
    overview = workbook.active
    overview.title = "Overview"
    overview.sheet_view.showGridLines = False
    overview["A1"] = "SOUTHERN AFRICA | ELECTRICITY ACCESS & ENERGY TRANSITION"
    overview["A1"].font = Font(size=16, bold=True, color="FFFFFF")
    overview["A1"].fill = PatternFill("solid", fgColor="17324D")
    overview.merge_cells("A1:F1")
    overview["A2"] = "World Bank annual indicators | South Africa, Botswana, Namibia, Zambia, Mozambique"
    overview.merge_cells("A2:F2")
    overview["A2"].font = Font(italic=True, color="536579")
    sa = summary.loc[summary["country_code"].eq("ZAF")].iloc[0]
    latest_access = sa["electricity_access_latest_value"]
    latest_access_year = sa["electricity_access_latest_year"]
    latest_renewable = sa["renewable_energy_latest_value"]
    latest_renewable_year = sa["renewable_energy_latest_year"]
    kpis = [
        (
            "A4",
            "South Africa electricity access",
            "A5",
            float(latest_access),
            '0.00"%"',
            f"Year: {int(latest_access_year)}",
        ),
        (
            "C4",
            "South Africa renewable energy share",
            "C5",
            float(latest_renewable),
            '0.00"%"',
            f"Year: {int(latest_renewable_year)}",
        ),
        (
            "E4",
            "South Africa people without access (estimate)",
            "E5",
            float(
                sa.loc[
                    "people_without_electricity_latest_value"
                ]
            ),
            "#,##0",
            f"Year: {int(sa['people_without_electricity_latest_year'])}",
        ),
    ]
    for label_cell, label, value_cell, value, number_format, sublabel in kpis:
        overview[label_cell] = label
        overview[label_cell].font = Font(bold=True, color="FFFFFF")
        overview[label_cell].fill = PatternFill("solid", fgColor="2878B5")
        overview[value_cell] = value
        overview[value_cell].font = Font(bold=True, size=15, color="17324D")
        overview[value_cell].number_format = number_format
        subcell = overview.cell(6, overview[label_cell].column)
        subcell.value = sublabel
        subcell.font = Font(italic=True, color="536579")
    overview["A8"] = "Important interpretation"
    overview["A8"].font = Font(bold=True, color="17324D", size=12)
    notes = [
        "Electricity access is an estimated share of population with access to electricity, not supply reliability, affordability, or hours of service.",
        "Estimated people without access = population × (100 − electricity access %) / 100. This is a derived estimate, not a direct household headcount.",
        "Renewable energy consumption is a share of total final energy consumption; it is not the share of electricity generated from renewables.",
        "Electricity access data currently run through 2024; renewable energy shares currently run through 2021. Compare the year displayed for each indicator.",
        "Correlations are descriptive and not causal. Check missingness and indicator definitions before interpretation.",
    ]
    for row, note in enumerate(notes, start=9):
        overview.cell(row, 1, note)
        overview.merge_cells(start_row=row, start_column=1, end_row=row, end_column=7)
        overview.cell(row, 1).alignment = Alignment(wrap_text=True, vertical="top")
        overview.row_dimensions[row].height = 32

    annual_sheet = write_table(workbook, "Annual Data", data, "AnnualData")
    write_table(workbook, "Country Summary", summary, "CountrySummary")
    correlations_sheet = write_table(workbook, "Correlations", correlations, "Correlations")
    write_table(workbook, "Methodology", pd.DataFrame(sources), "SourceMetadata")

    chart_data = workbook.create_sheet("Chart Data")
    chart_data.append(["Year", *[COUNTRIES[code] for code in COUNTRY_ORDER]])
    access_wide = data.pivot(
        index="year", columns="country_code", values="electricity_access_pct"
    )
    for year in range(int(data["year"].min()), int(data["year"].max()) + 1):
        chart_data.append(
            [
                year,
                *[
                    None
                    if pd.isna(access_wide.loc[year, code])
                    else float(access_wide.loc[year, code])
                    for code in COUNTRY_ORDER
                ],
            ]
        )
    style_sheet(chart_data)
    chart_data.sheet_state = "hidden"

    annual_sheet.cell(1, 8, "Excel access change (pp)")
    for cell in annual_sheet[1]:
        cell.font = Font(color="FFFFFF", bold=True)
        cell.fill = PatternFill("solid", fgColor="17324D")
    for row in range(2, annual_sheet.max_row + 1):
        if (
            row > 2
            and annual_sheet.cell(row, 1).value == annual_sheet.cell(row - 1, 1).value
        ):
            annual_sheet.cell(row, 8, f'=IFERROR(D{row}-D{row - 1},"")')
        annual_sheet.cell(row, 8).number_format = "0.00"
    annual_sheet.tables["AnnualData"].ref = f"A1:H{annual_sheet.max_row}"

    overview_chart = LineChart()
    overview_chart.title = "Electricity access (% of population)"
    overview_chart.y_axis.title = "Access (%)"
    overview_chart.x_axis.title = "Year"
    overview_chart.y_axis.scaling.min = 0
    overview_chart.y_axis.scaling.max = 100
    overview_chart.add_data(
        Reference(
            chart_data,
            min_col=2,
            max_col=chart_data.max_column,
            min_row=1,
            max_row=chart_data.max_row,
        ),
        titles_from_data=True,
    )
    overview_chart.set_categories(
        Reference(chart_data, min_col=1, min_row=2, max_row=chart_data.max_row)
    )
    overview_chart.height = 9
    overview_chart.width = 18
    overview.add_chart(overview_chart, "A16")

    if correlations_sheet.max_row > 1:
        correlations_sheet.conditional_formatting.add(
            f"D2:D{correlations_sheet.max_row}",
            ColorScaleRule(
                start_type="num",
                start_value=-1,
                start_color="F8696B",
                mid_type="num",
                mid_value=0,
                mid_color="FFEB84",
                end_type="num",
                end_value=1,
                end_color="63BE7B",
            ),
        )
    summary_sheet = workbook["Country Summary"]
    summary_sheet.conditional_formatting.add(
        f"F2:F{summary_sheet.max_row}",
        DataBarRule(start_type="min", end_type="max", color="35A7A0"),
    )
    for column, width in {"A": 40, "B": 20, "C": 34, "D": 16, "E": 4, "F": 25, "G": 18}.items():
        overview.column_dimensions[column].width = width
    for sheet in workbook.worksheets:
        sheet.sheet_view.zoomScale = 90
    workbook.calculation.fullCalcOnLoad = True
    workbook.calculation.forceFullCalc = True
    workbook.save(path)


def create_charts(data: pd.DataFrame, correlations: pd.DataFrame) -> None:
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid")

    fig, ax = plt.subplots(figsize=(11, 6))
    for code in COUNTRY_ORDER:
        subset = data.loc[data["country_code"].eq(code)].dropna(
            subset=["electricity_access_pct"]
        )
        sns.lineplot(
            data=subset,
            x="year",
            y="electricity_access_pct",
            label=COUNTRIES[code],
            color=COLORS[code],
            marker="o",
            ax=ax,
        )
    ax.set(
        title="Access to electricity",
        xlabel="Year",
        ylabel="% of population",
        ylim=(0, 100),
    )
    fig.tight_layout()
    fig.savefig(CHART_DIR / "electricity_access.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(11, 6))
    for code in COUNTRY_ORDER:
        subset = data.loc[data["country_code"].eq(code)].dropna(
            subset=["renewable_energy_consumption_pct"]
        )
        sns.lineplot(
            data=subset,
            x="year",
            y="renewable_energy_consumption_pct",
            label=COUNTRIES[code],
            color=COLORS[code],
            ax=ax,
        )
    ax.set(
        title="Renewable energy consumption",
        xlabel="Year",
        ylabel="% of total final energy consumption",
    )
    fig.tight_layout()
    fig.savefig(CHART_DIR / "renewable_energy_share.png", dpi=180)
    plt.close(fig)

    latest = data.sort_values("year").groupby("country_code", as_index=False).tail(1)
    latest = latest.dropna(subset=["estimated_people_without_electricity"]).sort_values(
        "estimated_people_without_electricity"
    )
    fig, ax = plt.subplots(figsize=(9, 5))
    sns.barplot(
        data=latest,
        x="estimated_people_without_electricity",
        y="country",
        color="#2878B5",
        ax=ax,
    )
    ax.set(
        title="Estimated people without electricity (latest available year)",
        xlabel="Estimated people",
        ylabel="",
    )
    fig.tight_layout()
    fig.savefig(CHART_DIR / "people_without_electricity.png", dpi=180)
    plt.close(fig)

    pivot = correlations.pivot(index="country", columns="comparison", values="correlation")
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.heatmap(pivot, annot=True, fmt=".2f", cmap="vlag", center=0, vmin=-1, vmax=1, ax=ax)
    ax.set(title="Descriptive correlations (not causal)", xlabel="", ylabel="")
    fig.tight_layout()
    fig.savefig(CHART_DIR / "correlation_heatmap.png", dpi=180)
    plt.close(fig)


def markdown_table(frame: pd.DataFrame) -> str:
    headers = [str(column) for column in frame.columns]
    rows = [[str(value) for value in row] for row in frame.itertuples(index=False, name=None)]
    return "\n".join(
        ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
        + ["| " + " | ".join(row) + " |" for row in rows]
    )


def write_report(
    path: Path,
    data: pd.DataFrame,
    summary: pd.DataFrame,
    correlations: pd.DataFrame,
    sources: list[dict],
) -> None:
    latest_access = summary[
        [
            "country",
            "electricity_access_latest_year",
            "electricity_access_latest_value",
            "people_without_electricity_latest_value",
        ]
    ].copy()
    latest_access["electricity_access_latest_value"] = latest_access[
        "electricity_access_latest_value"
    ].map(lambda value: f"{value:.2f}")
    latest_access["people_without_electricity_latest_value"] = latest_access[
        "people_without_electricity_latest_value"
    ].map(lambda value: f"{value:,.0f}")
    latest_renewable = summary[
        ["country", "renewable_energy_latest_year", "renewable_energy_latest_value"]
    ].copy()
    latest_renewable["renewable_energy_latest_value"] = latest_renewable[
        "renewable_energy_latest_value"
    ].map(lambda value: f"{value:.2f}")
    source_lines = []
    for indicator_id in INDICATORS:
        indicator_sources = [
            source for source in sources if source["indicator_id"] == indicator_id
        ]
        source = indicator_sources[0]
        coverage = ", ".join(
            f"{item['country_code']} {item['first_nonmissing_year']}–{item['last_nonmissing_year']}"
            for item in indicator_sources
        )
        source_lines.append(
            f"- `{indicator_id}` — {source['indicator_name']}; API updated {source['api_last_updated']}; country coverage: {coverage}."
        )
    sources_text = "\n".join(source_lines)
    south_africa_corr = correlations.loc[
        correlations["country_code"].eq("ZAF")
        & correlations["comparison"].eq(
            "Electricity access vs renewable energy consumption share"
        )
    ].iloc[0]
    report = f"""# Southern Africa Electricity Access & Energy Transition

## Scope

World Bank annual estimates for 2000–2025 across South Africa, Botswana, Namibia, Zambia, and Mozambique. Electricity-access estimates currently run through 2024, renewable-energy-consumption estimates through 2021, and population estimates through 2025. Latest years therefore differ by indicator.

## Electricity access and estimated population without access

{markdown_table(latest_access)}

Estimated people without access is calculated as population × (100 − electricity access percentage) / 100, using the latest available values of each input. It is an approximate population-level estimate, not a household enumeration; input years may differ. The accompanying data includes each component and year so this estimate can be checked.

## Renewable energy consumption

{markdown_table(latest_renewable)}

The indicator measures renewable energy consumption as a share of **total final energy consumption**. It is not the renewable share of electricity generation and should not be read as a direct counterpart to electricity access.

## South Africa association (descriptive only)

Across {int(south_africa_corr['paired_years'])} paired annual observations, the Pearson correlation between electricity access and renewable energy consumption share is **{south_africa_corr['correlation']:.2f}**. This describes co-movement only. It does not show that electricity access causes renewable-energy use or vice versa.

## Data sources and attribution

{sources_text}

Source: [World Bank Indicators API](https://datahelpdesk.worldbank.org/knowledgebase/articles/889386). Indicator pages: [electricity access](https://data.worldbank.org/indicator/EG.ELC.ACCS.ZS), [renewable energy consumption](https://data.worldbank.org/indicator/EG.FEC.RNEW.ZS), and [population](https://data.worldbank.org/indicator/SP.POP.TOTL). World Bank open data generally references [CC BY 4.0](https://datacatalog.worldbank.org/public-licenses#cc-by); cite the World Bank and any original sources shown on the indicator pages.

## Methods and caveats

- **Electricity access (`EG.ELC.ACCS.ZS`):** estimated share of population with access; it does not measure reliability, affordability, connection quality, or hours supplied.
- **Renewable energy (`EG.FEC.RNEW.ZS`):** renewables as a percentage of total final energy consumption, not electricity-generation mix.
- **People without access:** derived from population and access estimates. Differences in estimate vintages and uncertainty can affect the count.
- **Access change:** year-over-year change in percentage points, not percent growth.
- Missing indicator values remain missing, never replaced with zero. Comparisons and correlations use only available paired observations.
- Correlations are descriptive, unadjusted annual associations between electricity access and renewable energy consumption. They do not address confounding, statistical significance, timing lags, measurement uncertainty, common time trends, or causation.
- The project retrieves the API when rerun; response URLs, update dates, and nonmissing coverage are stored in `outputs/source_metadata.json`.
"""
    path.write_text(report, encoding="utf-8")


def run_analysis(start_year: int = FIRST_YEAR, end_year: int = LAST_YEAR) -> pd.DataFrame:
    if start_year < 1960 or end_year < start_year:
        raise ValueError(f"Invalid year range {start_year}:{end_year}; choose start >= 1960 and end >= start.")
    data, sources = fetch_all(start_year, end_year)
    summary = country_summary(data)
    correlations = paired_correlations(data)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    data.to_csv(OUTPUT_DIR / "annual_energy_access.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(OUTPUT_DIR / "country_summary.csv", index=False, encoding="utf-8-sig")
    correlations.to_csv(OUTPUT_DIR / "correlations.csv", index=False, encoding="utf-8-sig")
    metadata = {
        "retrieved_at_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "requested_years": [start_year, end_year],
        "countries": COUNTRIES,
        "indicators": sources,
        "api_documentation": "https://datahelpdesk.worldbank.org/knowledgebase/articles/889386",
        "license_reference": "https://datacatalog.worldbank.org/public-licenses#cc-by",
        "data_rows": len(data),
    }
    (OUTPUT_DIR / "source_metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    create_charts(data, correlations)
    create_workbook(
        OUTPUT_DIR / "southern_africa_electricity_transition.xlsx",
        data,
        summary,
        correlations,
        sources,
    )
    write_report(
        OUTPUT_DIR / "ANALYSIS_SUMMARY.md", data, summary, correlations, sources
    )
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-year", type=int, default=FIRST_YEAR)
    parser.add_argument("--end-year", type=int, default=LAST_YEAR)
    args = parser.parse_args()
    data = run_analysis(args.start_year, args.end_year)
    print(
        f"Analysis complete: {len(data)} country-year rows, "
        f"{int(data['electricity_access_pct'].notna().sum())} electricity-access observations, "
        f"{int(data['renewable_energy_consumption_pct'].notna().sum())} renewable-energy observations."
    )
    print(f"Outputs: {OUTPUT_DIR.resolve()}")


if __name__ == "__main__":
    main()
