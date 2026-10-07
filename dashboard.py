"""
dashboard.py

Streamlit dashboard presenting the Part 2-4 results from cell_counts.db,
using the functions in analysis.py. Settings and theme: .streamlit/config.toml.

Run with:
    make dashboard
or:
    python dashboard.py
"""

import html
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots
from streamlit import runtime
from streamlit.web import cli as streamlit_cli

import analysis

# ---------------------------------------------------------------------------
# Start the web server when run as `python dashboard.py`
# ---------------------------------------------------------------------------
if __name__ == "__main__" and not runtime.exists():
    sys.argv = ["streamlit", "run", str(Path(__file__).resolve())]
    sys.exit(streamlit_cli.main())

st.set_page_config(
    page_title="Loblaw Bio · Immune Cell Dashboard",
    page_icon="🧬",
    layout="wide",
)


# ---------------------------------------------------------------------------
# Look and feel
# ---------------------------------------------------------------------------
POPULATION_COLORS = {
    "b_cell": "#2a78d6",
    "cd4_t_cell": "#eb6834",
    "cd8_t_cell": "#1baf7a",
    "monocyte": "#eda100",
    "nk_cell": "#e87ba4",
}
POPULATION_LABELS = {
    "b_cell": "B cells",
    "cd4_t_cell": "CD4 T cells",
    "cd8_t_cell": "CD8 T cells",
    "monocyte": "Monocytes",
    "nk_cell": "NK cells",
}

GROUP_COLORS = {analysis.RESPONDER: "#4a3aa7", analysis.NON_RESPONDER: "#8a6d00"}
RESPONSE_LABEL_COLORS = {"Responder": GROUP_COLORS[analysis.RESPONDER],
                         "Non-responder": GROUP_COLORS[analysis.NON_RESPONDER]}

BAR_COLOR = "#7d8da3"
TEXT_COLOR = "#1b2433"
MUTED_TEXT = "#5b6575"
GRID_COLOR = "#e9edf3"
HIGHLIGHT_TEXT = "#9a5b00"

SEX_LABELS = {"M": "Male", "F": "Female"}

st.markdown(
    """
    <style>
    .block-container { padding-top: 2rem; max-width: 1400px; }

    .hero {
        background: linear-gradient(120deg, #0d2c54 0%, #1c5cab 100%);
        color: #ffffff; padding: 1.4rem 2rem; border-radius: 14px;
        margin-bottom: 1.2rem;
    }
    .hero h1 { color: #ffffff; font-size: 1.9rem; margin: 0; padding: 0; }
    .hero p  { color: #c9dcf5; margin: .35rem 0 0 0; font-size: .95rem; }
    .view-note { color: #5b6575; font-size: .92rem; margin: -.3rem 0 .6rem 0; }

    div[data-testid="stMetric"] {
        background: #ffffff; border: 1px solid #e3e8ef; border-radius: 12px;
        padding: 14px 18px; box-shadow: 0 1px 2px rgba(16, 24, 40, .05);
    }
    div[data-testid="stMetricLabel"] p { color: #5b6575; font-weight: 600; }

    div[class*="st-key-card"] {
        background: #ffffff; box-shadow: 0 1px 3px rgba(16, 24, 40, .06);
    }

    .info-grid {
        display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
        gap: .6rem .9rem; margin: .2rem 0 1rem 0;
    }
    .info-grid .label {
        color: #5b6575; font-size: .72rem; text-transform: uppercase;
        letter-spacing: .04em;
    }
    .info-grid .value { color: #1b2433; font-weight: 600; font-size: .98rem; }
    .section-note { color: #5b6575; font-size: .92rem; margin-top: -.4rem; }
    .big-number { font-size: 2.4rem; font-weight: 600; color: #1b2433; line-height: 1.2; }

    @media (max-width: 900px) {
        div[class*="st-key-stack"] div[data-testid="stHorizontalBlock"],
        div[class*="st-key-metrics"] div[data-testid="stHorizontalBlock"] {
            flex-wrap: wrap;
        }
        div[class*="st-key-stack"] div[data-testid="stColumn"] {
            min-width: 100% !important; flex: 1 1 100% !important;
        }
        div[class*="st-key-metrics"] div[data-testid="stColumn"] {
            min-width: calc(50% - 1rem) !important; flex: 1 1 calc(50% - 1rem) !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def style_figure(fig: go.Figure, height: int, margin: dict | None = None) -> go.Figure:
    """Shared Plotly styling: transparent background, quiet grid, readable text."""
    fig.update_layout(
        height=height,
        margin={"l": 10, "r": 10, "t": 50, "b": 10, **(margin or {})},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "sans-serif", "color": TEXT_COLOR, "size": 13},
        hoverlabel={"bgcolor": "#ffffff", "bordercolor": "#c9d2de",
                    "font": {"color": TEXT_COLOR}},
    )
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor="#c9d2de")
    fig.update_yaxes(gridcolor=GRID_COLOR, zeroline=False, linecolor="#c9d2de")
    return fig


def show_chart(fig: go.Figure, filename: str) -> None:
    """Render a Plotly chart; the toolbar's camera icon saves a 2x PNG named `filename`."""
    st.plotly_chart(fig, theme=None, config={
        "displaylogo": False,
        "modeBarButtonsToRemove": ["select2d", "lasso2d", "autoScale2d"],
        "toImageButtonOptions": {"format": "png", "scale": 2, "filename": filename},
    })


def info_grid(items: dict) -> None:
    """Label/value pairs as a grid (values HTML-escaped)."""
    cells = "".join(
        f"<div><div class='label'>{html.escape(str(k))}</div>"
        f"<div class='value'>{html.escape(str(v))}</div></div>"
        for k, v in items.items()
    )
    st.markdown(f"<div class='info-grid'>{cells}</div>", unsafe_allow_html=True)


def note(text: str) -> None:
    """Muted note under a heading."""
    st.markdown(f"<p class='section-note'>{text}</p>", unsafe_allow_html=True)


def csv_download(label: str, table: pd.DataFrame, file_name: str, key: str) -> None:
    """CSV download button for `table`."""
    st.download_button(label, table.to_csv(index=False), file_name=file_name,
                       mime="text/csv", key=key, icon=":material/download:")


# ---------------------------------------------------------------------------
# Remembering choices
# ---------------------------------------------------------------------------
PERSISTENT_KEYS = [
    "p2_mode", "p2_f_condition", "p2_f_treatment", "p2_f_response_label",
    "p2_f_project", "p2_patient", "p2_sample", "p2_search", "p2_search_pick",
    "p2_populations", "p2_table_search",
    "p3_all_points",
]
for _key in PERSISTENT_KEYS:
    if _key in st.session_state:
        st.session_state[_key] = st.session_state[_key]


def remember(key: str, value) -> None:
    """Set a widget's initial value in session state (only if not already set)."""
    if key not in st.session_state:
        st.session_state[key] = value


def keep_a_selection(key: str) -> None:
    """on_change callback: restore the previous choice when a control is deselected."""
    if st.session_state[key] is None:
        st.session_state[key] = st.session_state.get(f"{key}_last")


# ---------------------------------------------------------------------------
# Loading data
# ---------------------------------------------------------------------------
def run_query(query_function):
    """Run one analysis function on a fresh read-only connection."""
    conn = analysis.open_database()
    try:
        return query_function(conn)
    finally:
        conn.close()


@st.cache_data
def load_cell_frequencies() -> pd.DataFrame:
    return run_query(analysis.get_cell_frequencies)


@st.cache_data
def load_sample_details() -> pd.DataFrame:
    details = run_query(analysis.get_sample_details)
    details["response_label"] = details["response"].map(
        {analysis.RESPONDER: "Responder", analysis.NON_RESPONDER: "Non-responder"}
    ).fillna("Not applicable")
    return details


@st.cache_data
def load_response_frequencies() -> pd.DataFrame:
    return run_query(analysis.get_response_frequencies)


@st.cache_data
def load_baseline_results() -> dict:
    return {
        "samples": run_query(analysis.get_baseline_samples),
        "per_project": run_query(analysis.count_baseline_samples_per_project),
        "by_response": run_query(analysis.count_baseline_subjects_by_response),
        "by_sex": run_query(analysis.count_baseline_subjects_by_sex),
        "b_cell_avg": run_query(analysis.average_b_cells_melanoma_male_responders_baseline),
        "b_cell_n": run_query(analysis.count_b_cell_samples_melanoma_male_responders_baseline),
    }


if not analysis.DB_PATH.exists():
    st.error("Database not found. Run `make pipeline` (or `python load_data.py`) first.")
    st.stop()


# ---------------------------------------------------------------------------
# Box summaries (used by the Part 3 tooltips)
# ---------------------------------------------------------------------------
def box_summary(values: pd.Series) -> dict:
    """Quartiles, median, mean and whisker ends (1.5 x IQR rule) of `values`."""
    q1, median, q3 = values.quantile([0.25, 0.5, 0.75])
    iqr = q3 - q1
    low = values[values >= q1 - 1.5 * iqr].min()
    high = values[values <= q3 + 1.5 * iqr].max()
    return {"n": len(values), "q1": q1, "median": median, "q3": q3,
            "mean": values.mean(), "low": low, "high": high}


def add_hover_column(fig: go.Figure, x_label: str, s: dict, tooltip: str,
                     row: int | None = None, col: int | None = None,
                     legendgroup: str | None = None) -> None:
    """Invisible markers spanning a box's whiskers, so hovering anywhere on it shows `tooltip`."""
    fig.add_trace(
        go.Scatter(
            x=[x_label] * 40,
            y=np.linspace(s["low"], s["high"], 40),
            mode="markers",
            marker={"size": 28, "opacity": 0},
            hovertemplate=tooltip + "<extra></extra>",
            hoverlabel={"align": "left"},
            legendgroup=legendgroup,
            showlegend=False,
        ),
        row=row, col=col,
    )


# ---------------------------------------------------------------------------
# Header and navigation
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="hero">
      <h1>Immune Cell Population Analysis</h1>
      <p>Loblaw Bio clinical trial · immune cell counts per sample</p>
    </div>
    """,
    unsafe_allow_html=True,
)

VIEWS = {
    "overview": "Part 2 · Cell frequencies",
    "response": "Part 3 · Responders vs non-responders",
    "baseline": "Part 4 · Baseline subset",
}
VIEW_NOTES = {
    "overview": "The share of each of the 5 immune populations in every sample. "
                "Look up any sample or patient, or search and download the full table.",
    "response": "Do melanoma patients on miraclib who respond have different immune cell "
                "frequencies from those who don't?",
    "baseline": "Who is in the day-0 (baseline) melanoma / miraclib / PBMC subset, and the "
                "average B cell count for male melanoma responders.",
}

if "view" not in st.session_state:
    requested = st.query_params.get("view", "overview")
    st.session_state["view"] = requested if requested in VIEWS else "overview"
st.segmented_control(
    "View",
    options=list(VIEWS),
    format_func=VIEWS.get,
    key="view",
    on_change=keep_a_selection, args=("view",),
    label_visibility="collapsed",
)
view = st.session_state["view"]
st.session_state["view_last"] = view
st.query_params["view"] = view
st.markdown(f"<p class='view-note'>{VIEW_NOTES[view]}</p>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Part 2: relative frequency of each population in each sample
# ---------------------------------------------------------------------------
PATIENT_FILTERS = [
    ("condition", "Indication"),
    ("treatment", "Treatment"),
    ("response_label", "Response"),
    ("project", "Project"),
]


def pick_sample_by_patient(details: pd.DataFrame) -> str | None:
    """Cascading filters -> patient -> sample. Returns the chosen sample ID."""
    subset = details
    reset = []
    for col, (column, label) in zip(st.columns(4), PATIENT_FILTERS):
        key = f"p2_f_{column}"
        options = ["All"] + sorted(subset[column].unique())
        remember(key, "All")
        if st.session_state[key] not in options:
            reset.append(f"{label} “{st.session_state[key]}”")
            st.session_state[key] = "All"
        choice = col.selectbox(label, options, key=key)
        if choice != "All":
            subset = subset[subset[column] == choice]
    if reset:
        st.caption(f"Reset to All: {', '.join(reset)}, because no patient matches it "
                   "together with the filters to its left.")

    patients = subset.drop_duplicates("subject").set_index("subject")

    def patient_label(subject: str) -> str:
        p = patients.loc[subject]
        return (f"{subject}  ·  {p['condition']}  ·  {p['treatment']}  ·  "
                f"{p['sex']}, {p['age']}  ·  {p['project']}")

    if st.session_state.get("p2_patient") not in patients.index:
        st.session_state["p2_patient"] = patients.index[0]
    subject = st.selectbox(
        f"Patient ({len(patients):,} matching, type to search)",
        patients.index,
        format_func=patient_label,
        key="p2_patient",
    )

    patient_samples = details[details["subject"] == subject].sort_values(
        ["time_from_treatment_start", "sample_type"]
    ).set_index("sample")
    if st.session_state.get("p2_sample") not in patient_samples.index:
        st.session_state["p2_sample"] = patient_samples.index[0]
    chosen = st.pills(
        "Sample",
        patient_samples.index,
        format_func=lambda s: (f"Day {patient_samples.loc[s, 'time_from_treatment_start']}"
                               f" · {patient_samples.loc[s, 'sample_type']}"),
        key="p2_sample",
        on_change=keep_a_selection, args=("p2_sample",),
    )
    st.session_state["p2_sample_last"] = chosen
    return chosen


def find_samples(text: str, all_samples: pd.Series) -> list[str]:
    """Sample IDs containing `text`; an exact sample-number match (e.g. "42") comes first."""
    matches = all_samples[all_samples.str.contains(text, case=False, regex=False)].tolist()
    number = re.fullmatch(r"(?:sample)?\s*(\d+)", text, flags=re.IGNORECASE)
    if number:
        exact = f"sample{int(number.group(1)):05d}"
        if exact in set(all_samples):
            matches = [exact] + [m for m in matches if m != exact]
    return matches


def pick_sample_by_id(details: pd.DataFrame) -> str | None:
    """Search by sample ID. Returns the chosen sample ID, or None."""
    text = st.text_input("Sample ID", key="p2_search",
                         placeholder="e.g. 42 or sample00042, then press Enter").strip()
    if not text:
        st.caption("Type any part of a sample ID and press Enter.")
        return None
    matches = find_samples(text, details["sample"])
    if not matches:
        st.warning(f"No sample ID contains “{text}”.")
        return None
    if len(matches) == 1:
        return matches[0]
    if st.session_state.get("p2_search_pick") not in matches:
        st.session_state["p2_search_pick"] = matches[0]
    return st.selectbox(f"{len(matches):,} matching samples", matches, key="p2_search_pick")


def composition_donut(one_sample: pd.DataFrame) -> go.Figure:
    """Donut chart of one sample's population shares."""
    fig = go.Figure(go.Pie(
        labels=[POPULATION_LABELS[p] for p in one_sample["population"]],
        values=one_sample["count"],
        marker={"colors": [POPULATION_COLORS[p] for p in one_sample["population"]],
                "line": {"color": "#ffffff", "width": 2}},
        hole=0.62,
        sort=False,
        direction="clockwise",
        texttemplate="%{percent:.1%}",
        textfont={"size": 13, "color": "#ffffff"},
        hovertemplate="<b>%{label}</b><br>Count: %{value:,}<br>Share: %{percent:.2%}<extra></extra>",
    ))
    total = int(one_sample["total_count"].iloc[0])
    fig.add_annotation(
        text=f"<b>{total:,}</b><br><span style='font-size:12px;color:{MUTED_TEXT}'>total cells</span>",
        showarrow=False, font={"size": 22, "color": TEXT_COLOR},
    )
    fig.update_layout(legend={"orientation": "h", "y": -0.08, "x": 0.5, "xanchor": "center"})
    return style_figure(fig, height=400, margin={"t": 20})


def show_sample(sample_id: str, details: pd.DataFrame, frequencies: pd.DataFrame) -> None:
    """Metadata, population table and donut chart for one sample."""
    info = details.set_index("sample").loc[sample_id]
    one_sample = frequencies[frequencies["sample"] == sample_id]

    with st.container(key="stack_sample"):
        left, right = st.columns([1, 1.1], gap="large")
    with left:
        st.markdown(f"##### {sample_id}")
        info_grid({
            "Patient": info["subject"],
            "Project": info["project"],
            "Indication": info["condition"],
            "Treatment": info["treatment"],
            "Response": info["response_label"],
            "Sex / age": f"{SEX_LABELS.get(info['sex'], info['sex'])} / {info['age']}",
            "Sample type": info["sample_type"],
            "Day": info["time_from_treatment_start"],
        })
        st.dataframe(
            one_sample.assign(population=one_sample["population"].map(POPULATION_LABELS)),
            hide_index=True,
            column_order=["population", "count", "percentage"],
            column_config={
                "population": "Population",
                "count": st.column_config.NumberColumn("Count", format="localized"),
                "percentage": st.column_config.NumberColumn("% of total", format="%.2f%%"),
            },
        )
        csv_download("Download this sample (CSV)", one_sample, f"{sample_id}.csv",
                     key="dl_sample")

    with right:
        show_chart(composition_donut(one_sample), f"{sample_id}_composition")


TABLE_COLUMN_CONFIG = {
    "sample": "Sample",
    "total_count": st.column_config.NumberColumn("Total cells", format="localized"),
    "population": "Population",
    "count": st.column_config.NumberColumn("Count", format="localized"),
    "percentage": st.column_config.NumberColumn("% of total", format="%.2f%%"),
}
GRADED_COLUMNS = ["sample", "total_count", "population", "count", "percentage"]


def render_full_table(populations: list[str]) -> None:
    """Filterable Part 2 summary table with CSV download."""
    table = load_cell_frequencies()

    f1, f2 = st.columns([2, 1])
    remember("p2_populations", populations)
    chosen_populations = f1.multiselect(
        "Populations", populations, key="p2_populations",
        format_func=POPULATION_LABELS.get,
    )
    sample_search = f2.text_input("Sample ID contains", key="p2_table_search",
                                  placeholder="e.g. sample0001, then press Enter").strip()

    if not chosen_populations:
        st.info("Select at least one population.")
        return
    table = table[table["population"].isin(chosen_populations)]
    if sample_search:
        table = table[table["sample"].str.contains(sample_search, case=False, regex=False)]
    if table.empty:
        st.info("No rows match these filters.")
        return

    columns = GRADED_COLUMNS
    st.caption(f"{len(table):,} rows · click a column header to sort")
    st.dataframe(
        table.assign(population=table["population"].map(POPULATION_LABELS)),
        hide_index=True,
        height=420,
        column_order=columns,
        column_config=TABLE_COLUMN_CONFIG,
    )
    csv_download("Download filtered table (CSV)", table[columns],
                 "cell_frequencies_filtered.csv", key="dl_full_table")


def render_part2() -> None:
    frequencies = load_cell_frequencies()
    details = load_sample_details()
    populations = sorted(frequencies["population"].unique())

    st.subheader("Relative frequency of each cell population per sample")
    note("For each sample, <b>total cells</b> is the sum of the five population counts and "
         "<b>% of total</b> is each population's share of that total.")

    with st.container(key="metrics_part2"):
        c1, c2, c3, c4 = st.columns(4)
    c1.metric("Samples", f"{frequencies['sample'].nunique():,}")
    c2.metric("Patients", f"{details['subject'].nunique():,}")
    c3.metric("Cell populations", len(populations))
    c4.metric("Summary table rows", f"{len(frequencies):,}")

    with st.container(border=True, key="card_sample_explorer"):
        st.markdown("#### Explore a sample")
        remember("p2_mode", "Browse by patient")
        mode = st.segmented_control(
            "Find a sample by",
            ["Browse by patient", "Search by sample ID"],
            key="p2_mode",
            on_change=keep_a_selection, args=("p2_mode",),
        )
        st.session_state["p2_mode_last"] = mode
        if mode == "Browse by patient":
            sample_id = pick_sample_by_patient(details)
        else:
            sample_id = pick_sample_by_id(details)

        if sample_id:
            st.divider()
            show_sample(sample_id, details, frequencies)

    with st.container(border=True, key="card_full_table"):
        st.markdown("#### Full summary table")
        render_full_table(populations)


# ---------------------------------------------------------------------------
# Part 3: responders vs non-responders
# ---------------------------------------------------------------------------
def both_groups_tooltip(population: str, summaries: dict, test_row: pd.Series) -> str:
    """Tooltip text comparing both groups for one population."""
    muted = f"<span style='color:{MUTED_TEXT}'>"
    lines = [f"<b>{POPULATION_LABELS.get(population, population)}</b>"]
    for response, s in summaries.items():
        color = GROUP_COLORS[response]
        lines += [
            "",
            f"<span style='color:{color}'>■</span> <b>{analysis.GROUP_LABELS[response]}</b> "
            f"{muted}· {s['n']:,} samples</span>",
            f"Median <b>{s['median']:.2f}%</b> · mean {s['mean']:.2f}%",
            f"Middle 50%: {s['q1']:.2f} – {s['q3']:.2f}%",
        ]
    lines += ["", f"{muted}Mann-Whitney p = {test_row['p_value']:.3f} · "
                  f"adjusted p = {test_row['p_adjusted']:.3f}</span>"]
    return "<br>".join(lines)


def response_boxplots(response_freq: pd.DataFrame, stats: pd.DataFrame,
                      show_all_points: bool) -> go.Figure:
    """Interactive boxplots, one panel per population, responders vs non-responders."""
    populations = list(stats["population"])
    stats_by_pop = stats.set_index("population")

    titles = []
    for p in populations:
        row = stats_by_pop.loc[p]
        star = " ★" if row["significant"] else ""
        if row["p_value"] < analysis.SIGNIFICANCE_LEVEL:
            style = f"font-size:11px;color:{HIGHLIGHT_TEXT};font-weight:bold"
        else:
            style = f"font-size:11px;color:{MUTED_TEXT}"
        titles.append(
            f"<b>{POPULATION_LABELS.get(p, p)}{star}</b><br>"
            f"<span style='{style}'>p = {row['p_value']:.3f}<br>"
            f"adj. p = {row['p_adjusted']:.3f}</span>"
        )

    fig = make_subplots(rows=1, cols=len(populations), subplot_titles=titles,
                        horizontal_spacing=0.045)
    for i, population in enumerate(populations, start=1):
        group = response_freq[response_freq["population"] == population]
        summaries = {}
        for response in (analysis.RESPONDER, analysis.NON_RESPONDER):
            rows = group[(group["response"] == response) & group["percentage"].notna()]
            label = analysis.GROUP_LABELS[response]
            summaries[response] = box_summary(rows["percentage"])
            fig.add_trace(
                go.Box(
                    y=rows["percentage"],
                    name=label,
                    legendgroup=response,
                    showlegend=(i == 1),
                    marker={"color": GROUP_COLORS[response], "size": 4, "opacity": 0.6},
                    line={"width": 1.5},
                    fillcolor=GROUP_COLORS[response],
                    opacity=0.8,
                    boxmean=True,
                    boxpoints="all" if show_all_points else "outliers",
                    jitter=0.35,
                    pointpos=0,
                    hoveron="points",
                    customdata=rows[["sample", "subject_id"]].to_numpy(),
                    hovertemplate=(f"<b>{label}</b><br>%{{customdata[0]}} · "
                                   "patient %{customdata[1]}<br>%{y:.2f}%<extra></extra>"),
                ),
                row=1, col=i,
            )

        tooltip = both_groups_tooltip(population, summaries, stats_by_pop.loc[population])
        for response in (analysis.RESPONDER, analysis.NON_RESPONDER):
            add_hover_column(fig, analysis.GROUP_LABELS[response], summaries[response],
                             tooltip, row=1, col=i, legendgroup=response)
        fig.update_xaxes(showticklabels=False, row=1, col=i)
    fig.update_yaxes(automargin=True)
    fig.update_yaxes(title_text="Relative frequency (%)", title_standoff=8, row=1, col=1)
    fig.update_layout(
        legend={"orientation": "h", "y": -0.06, "x": 0.5, "xanchor": "center"},
        boxgap=0.25,
    )
    fig.update_annotations(font={"size": 14, "color": TEXT_COLOR})
    return style_figure(fig, height=560, margin={"l": 60, "t": 110})


def render_part3() -> None:
    response_freq = load_response_frequencies()
    stats = analysis.compare_responders(response_freq)
    level = analysis.SIGNIFICANCE_LEVEL

    n_patients = response_freq.groupby("response")["subject_id"].nunique()
    n_samples = response_freq.groupby("response")["sample"].nunique()
    responders = analysis.RESPONDER
    non_responders = analysis.NON_RESPONDER

    st.subheader("Responders vs non-responders")
    note(f"Melanoma patients treated with miraclib, PBMC samples only "
         f"({n_samples.get(responders, 0):,} responder and "
         f"{n_samples.get(non_responders, 0):,} non-responder samples). "
         "Each population is compared with a Mann-Whitney U test; p-values are adjusted "
         "for testing five populations.")

    with st.container(key="metrics_part3"):
        c1, c2, c3, c4 = st.columns(4)
    c1.metric("Responder patients", f"{n_patients.get(responders, 0):,}",
              help=f"{n_samples.get(responders, 0):,} samples (days 0, 7 and 14)")
    c2.metric("Non-responder patients", f"{n_patients.get(non_responders, 0):,}",
              help=f"{n_samples.get(non_responders, 0):,} samples (days 0, 7 and 14)")
    if stats["p_adjusted"].notna().any():
        best = stats.loc[stats["p_adjusted"].idxmin()]
        c3.metric(f"Lowest adjusted p · {POPULATION_LABELS.get(best['population'])}",
                  f"{best['p_adjusted']:.3f}",
                  help=f"Significant means adjusted p below {level}.")
    else:
        c3.metric("Lowest adjusted p", "n/a")
    c4.metric(f"Significant (adj. p < {level})",
              f"{int(stats['significant'].sum())} of {len(stats)}")

    significant = [POPULATION_LABELS.get(p, p) for p in stats.loc[stats["significant"], "population"]]
    nominal = [POPULATION_LABELS.get(p, p) for p in stats.loc[stats["p_value"] < level, "population"]]
    if significant:
        st.success(f"**Significant after correction:** {', '.join(significant)}.")
    elif nominal:
        st.warning(
            f"**No population is significant after correction** (adjusted p < {level}). "
            f"Significant before correction: **{', '.join(nominal)}**. "
            "A candidate for follow-up, not a confirmed predictor of response."
        )
    else:
        st.info("No population differs significantly between responders and non-responders.")

    with st.container(border=True, key="card_boxplots"):
        head, toggle = st.columns([3, 1])
        head.markdown("#### Relative frequencies by response")
        show_all_points = toggle.toggle("Show every sample", key="p3_all_points")
        st.caption("Hover over a box to compare both groups' medians and quartiles; hover over "
                   "a dot to see its sample and patient. Click a legend entry to hide a group. "
                   "The camera icon (top right of the chart) saves it as a PNG.")
        show_chart(response_boxplots(response_freq, stats, show_all_points),
                   "responders_boxplots")

    with st.container(border=True, key="card_stats"):
        st.markdown("#### Statistical results")
        table = stats.assign(
            population=stats["population"].map(POPULATION_LABELS),
            median_difference=stats["responder_median"] - stats["non_responder_median"],
            significant=stats["significant"].map({True: "Yes", False: "No"}),
        )
        st.dataframe(
            table,
            hide_index=True,
            column_order=["population", "responder_median", "non_responder_median",
                          "median_difference", "p_adjusted", "significant", "p_value"],
            column_config={
                "population": "Population",
                "responder_median": st.column_config.NumberColumn(
                    "Responders (median %)", format="%.2f",
                    help="Median relative frequency in responder samples."),
                "non_responder_median": st.column_config.NumberColumn(
                    "Non-resp. (median %)", format="%.2f",
                    help="Median relative frequency in non-responder samples."),
                "median_difference": st.column_config.NumberColumn(
                    "Difference (pp)", format="%+.2f",
                    help="Difference in medians: responder minus non-responder, in "
                         "percentage points."),
                "p_adjusted": st.column_config.NumberColumn(
                    "Adjusted p (BH)", format="%.3f",
                    help="p-value adjusted for 5 tests (Benjamini-Hochberg)."),
                "significant": st.column_config.TextColumn(
                    "Significant", help=f"Adjusted p-value below {level}."),
                "p_value": st.column_config.NumberColumn(
                    "p-value (unadjusted)", format="%.3f",
                    help="Mann-Whitney U p-value before adjusting for 5 tests."),
            },
        )
        with st.expander("How to read these statistics"):
            example = ""
            if stats["p_adjusted"].notna().any():
                closest = stats.loc[stats["p_adjusted"].idxmin()]
                verdict = "significant" if closest["significant"] else "suggestive, not proven"
                example = (f"- **{POPULATION_LABELS.get(closest['population'])}** have "
                           f"p = {closest['p_value']:.3f} before adjustment and "
                           f"{closest['p_adjusted']:.3f} after: {verdict}.\n")
            st.markdown(
                "- The **Mann-Whitney U test** asks whether one group's values tend to be "
                "higher than the other's. It does not assume the values follow a bell curve.\n"
                "- Testing **5 populations** at once raises the chance that one looks different "
                "just by luck, so the p-values are **adjusted** (Benjamini-Hochberg).\n"
                f"- A population counts as **significant** if its adjusted p-value is below {level}.\n"
                + example +
                "- Each patient gave up to three samples (days 0, 7, 14), so samples are not "
                "fully independent; averaging each patient's samples first gives the same "
                "conclusion."
            )
        d1, d2 = st.columns(2)
        with d1:
            csv_download("Download statistics (CSV)",
                         stats.assign(median_difference_pp=table["median_difference"]),
                         "responder_statistics.csv", key="dl_stats")
        with d2:
            csv_download("Download per-sample frequencies (CSV)", response_freq,
                         "responder_sample_frequencies.csv", key="dl_response_freq")


# ---------------------------------------------------------------------------
# Part 4: baseline subset
# ---------------------------------------------------------------------------
COUNT_LABELS = {"responder": "Responder", "non-responder": "Non-responder",
                "unknown": "Unknown", "male": "Male", "female": "Female"}


def count_bars(table: pd.DataFrame, x: str, y: str, unit: str,
               colors: dict | None = None, empty_notes: dict | None = None) -> go.Figure:
    """Bar chart labelled "count (share)"; `empty_notes` annotates zero-height bars."""
    total = max(table[y].sum(), 1)
    labels = ["" if c in (empty_notes or {}) else f"{v:,} ({v / total:.1%})"
              for c, v in zip(table[x], table[y])]
    fig = go.Figure(go.Bar(
        x=table[x], y=table[y],
        marker={"color": [(colors or {}).get(c, BAR_COLOR) for c in table[x]],
                "cornerradius": 4},
        text=labels, textposition="outside", cliponaxis=False,
        textfont={"color": TEXT_COLOR},
        hovertemplate=f"<b>%{{x}}</b><br>%{{y:,}} {unit}<extra></extra>",
        width=0.55,
    ))
    for category, text in (empty_notes or {}).items():
        fig.add_annotation(x=category, y=table[y].max() * 0.12, showarrow=False,
                           text=text, font={"size": 12, "color": MUTED_TEXT},
                           bordercolor="#c9d2de", borderpad=6)
    style_figure(fig, height=280, margin={"t": 10, "b": 30})
    fig.update_yaxes(visible=False, range=[0, max(table[y].max(), 1) * 1.2])
    fig.update_xaxes(tickfont={"size": 13}, automargin=True)
    return fig


def empty_project_reasons(per_project: pd.DataFrame) -> dict:
    """Explanation for each project with no baseline samples."""
    details = load_sample_details()
    reasons = {}
    for project in per_project.loc[per_project["n_samples"] == 0, "project"]:
        sample_types = sorted(details.loc[details["project"] == project, "sample_type"].unique())
        if "PBMC" not in sample_types:
            reasons[project] = (f"**{project}** shows 0 because it has no PBMC samples "
                                f"(its samples are all {', '.join(sample_types)}).")
        else:
            reasons[project] = f"**{project}** has no samples matching all of the subset's filters."
    return reasons


def baseline_sample_table(samples: pd.DataFrame) -> pd.DataFrame:
    """Baseline samples with readable labels and population percentages."""
    shares = load_cell_frequencies().pivot_table(
        index="sample", columns="population", values="percentage")
    shares.columns = [f"{POPULATION_LABELS.get(p, p)} (%)" for p in shares.columns]
    return samples.assign(
        response=samples["response"].map({analysis.RESPONDER: "Responder",
                                          analysis.NON_RESPONDER: "Non-responder"}),
        sex=samples["sex"].map(SEX_LABELS),
    ).merge(shares, left_on="sample", right_index=True, how="left")


def render_part4() -> None:
    baseline = load_baseline_results()
    per_project = baseline["per_project"]
    by_response = baseline["by_response"].assign(
        response=lambda t: t["response"].map(COUNT_LABELS).fillna(t["response"]))
    by_sex = baseline["by_sex"].assign(sex=lambda t: t["sex"].map(COUNT_LABELS).fillna(t["sex"]))

    st.subheader("Baseline subset")
    note("Melanoma patients treated with miraclib, PBMC samples, at baseline "
         "(day 0, before treatment).")

    n_samples = len(baseline["samples"])
    responders = by_response.loc[by_response["response"] == "Responder", "n_subjects"].sum()
    n_subjects = baseline["samples"]["subject"].nunique()
    with st.container(key="metrics_part4"):
        c1, c2, c3, c4 = st.columns(4)
    c1.metric("Baseline samples", f"{n_samples:,}")
    c2.metric("Patients", f"{n_subjects:,}")
    c3.metric("Projects with samples",
              f"{(per_project['n_samples'] > 0).sum()} of {len(per_project)}")
    c4.metric("Responders", f"{responders:,} ({responders / max(n_subjects, 1):.1%})")

    reasons = empty_project_reasons(per_project)
    charts = [
        ("Samples per project", per_project, "project", "n_samples", "samples", None,
         {p: "no PBMC<br>samples" for p in reasons}),
        ("Patients by response", by_response, "response", "n_subjects", "patients",
         RESPONSE_LABEL_COLORS, None),
        ("Patients by sex", by_sex, "sex", "n_subjects", "patients", None, None),
    ]
    with st.container(key="stack_part4"):
        columns = st.columns(3)
    for col, (title, table, x, y, unit, colors, empty_notes) in zip(columns, charts):
        with col, st.container(border=True, key=f"card_{x}"):
            st.markdown(f"#### {title}")
            show_chart(count_bars(table, x, y, unit, colors, empty_notes), f"baseline_{x}")
            if x == "project":
                for reason in reasons.values():
                    st.caption(reason)

    with st.container(border=True, key="card_b_cell"):
        st.markdown("#### Average B cell count: male melanoma responders at day 0")
        st.markdown(f"<div class='big-number'>{baseline['b_cell_avg']:,.2f}</div>",
                    unsafe_allow_html=True)
        st.caption(f"All sample types, all treatments · n = {baseline['b_cell_n']:,} samples. "
                   "Unlike the charts above, this is not limited to miraclib or PBMC.")

    counts = pd.concat([
        per_project.rename(columns={"project": "group", "n_samples": "count"})
        .assign(table="samples_per_project"),
        by_response.rename(columns={"response": "group", "n_subjects": "count"})
        .assign(table="subjects_by_response"),
        by_sex.rename(columns={"sex": "group", "n_subjects": "count"})
        .assign(table="subjects_by_sex"),
    ])[["table", "group", "count"]]
    csv_download("Download counts (CSV)", counts, "baseline_counts.csv", key="dl_counts")

    with st.expander(f"Show all {n_samples:,} baseline samples"):
        samples = baseline_sample_table(baseline["samples"])
        st.dataframe(
            samples, hide_index=True,
            column_config={
                "sample": "Sample", "subject": "Patient", "project": "Project",
                "response": "Response", "sex": "Sex",
                **{c: st.column_config.NumberColumn(c, format="%.2f")
                   for c in samples.columns if c.endswith("(%)")},
            },
        )
        st.caption("Population columns are each sample's % of total cells at day 0.")
        csv_download("Download baseline samples (CSV)", samples, "baseline_samples.csv",
                      key="dl_baseline_samples")


# ---------------------------------------------------------------------------
# Show the chosen view
# ---------------------------------------------------------------------------
if view == "overview":
    render_part2()
elif view == "response":
    render_part3()
else:
    render_part4()
