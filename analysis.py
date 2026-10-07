"""
analysis.py

Parts 2-4 of the analysis. Reads cell_counts.db (built by load_data.py),
prints the results and saves them to outputs/.

Run with:
    python analysis.py
"""

import sqlite3
from pathlib import Path

import pandas as pd
from matplotlib.figure import Figure
from scipy.stats import false_discovery_control, mannwhitneyu

ROOT_DIR = Path(__file__).parent
DB_PATH = ROOT_DIR / "cell_counts.db"
OUTPUT_DIR = ROOT_DIR / "outputs"

RESPONDER = "yes"
NON_RESPONDER = "no"


def open_database(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Open the database read-only (fails instead of creating an empty file if missing)."""
    return sqlite3.connect(f"{db_path.as_uri()}?mode=ro", uri=True)


# ---------------------------------------------------------------------------
# Part 2: relative frequency of each cell population in each sample
# ---------------------------------------------------------------------------
CELL_FREQUENCY_SQL = """
SELECT
    sample_id                                          AS sample,
    SUM(count) OVER (PARTITION BY sample_id)           AS total_count,
    population,
    count,
    ROUND(100.0 * count / NULLIF(SUM(count) OVER (PARTITION BY sample_id), 0), 4)
                                                       AS percentage
FROM cell_counts
ORDER BY sample_id, population
"""


def get_cell_frequencies(conn: sqlite3.Connection) -> pd.DataFrame:
    """One row per (sample, population): sample, total_count, population, count, percentage."""
    return pd.read_sql_query(CELL_FREQUENCY_SQL, conn)


SAMPLE_DETAILS_SQL = """
SELECT
    s.sample_id                  AS sample,
    s.subject_id                 AS subject,
    sub.project_id               AS project,
    sub.condition,
    sub.treatment,
    sub.response,
    sub.sex,
    sub.age,
    s.sample_type,
    s.time_from_treatment_start
FROM samples s
JOIN subjects sub ON sub.subject_id = s.subject_id
ORDER BY s.sample_id
"""


def get_sample_details(conn: sqlite3.Connection) -> pd.DataFrame:
    """One row per sample with its subject and sample metadata."""
    return pd.read_sql_query(SAMPLE_DETAILS_SQL, conn)


def run_part2(conn: sqlite3.Connection) -> None:
    """Print the Part 2 summary table and save it to outputs/cell_frequencies.csv."""
    frequencies = get_cell_frequencies(conn)

    out_path = OUTPUT_DIR / "cell_frequencies.csv"
    frequencies.to_csv(out_path, index=False)

    print("Part 2: Relative frequency of each cell population per sample")
    print(frequencies.head(10).to_string(index=False, float_format="%.4f"))
    print(f"... {len(frequencies)} rows total "
          f"({frequencies['sample'].nunique()} samples x "
          f"{frequencies['population'].nunique()} populations)")
    print(f"Full table saved to {out_path.relative_to(ROOT_DIR)}")


# ---------------------------------------------------------------------------
# Cohort shared by Parts 3 and 4 (expects aliases `s` = samples, `sub` = subjects)
# ---------------------------------------------------------------------------
COHORT_FILTER_SQL = """
    sub.condition = 'melanoma'
    AND sub.treatment = 'miraclib'
    AND s.sample_type = 'PBMC'
"""


# ---------------------------------------------------------------------------
# Part 3: responders vs non-responders
# ---------------------------------------------------------------------------
RESPONSE_FREQUENCY_SQL = f"""
WITH freq AS ({CELL_FREQUENCY_SQL})
SELECT
    freq.*,
    sub.subject_id,
    sub.response
FROM freq
JOIN samples  s   ON s.sample_id    = freq.sample
JOIN subjects sub ON sub.subject_id = s.subject_id
WHERE {COHORT_FILTER_SQL}
  AND sub.response IN ('{RESPONDER}', '{NON_RESPONDER}')
ORDER BY freq.sample, freq.population
"""

SIGNIFICANCE_LEVEL = 0.05

GROUP_COLORS = {RESPONDER: "#2a78d6", NON_RESPONDER: "#eb6834"}
GROUP_LABELS = {RESPONDER: "Responders", NON_RESPONDER: "Non-responders"}


def get_response_frequencies(conn: sqlite3.Connection) -> pd.DataFrame:
    """Part 2 frequencies for the Part 3 cohort, with subject_id and response."""
    return pd.read_sql_query(RESPONSE_FREQUENCY_SQL, conn)


def compare_responders(response_freq: pd.DataFrame) -> pd.DataFrame:
    """
    Per population: two-sided Mann-Whitney U test, responders vs non-responders,
    with Benjamini-Hochberg adjustment across populations.
    """
    rows = []
    for population, group in response_freq.groupby("population"):
        responders = group.loc[group["response"] == RESPONDER, "percentage"].dropna()
        non_responders = group.loc[group["response"] == NON_RESPONDER, "percentage"].dropna()

        if len(responders) > 0 and len(non_responders) > 0:
            p_value = mannwhitneyu(responders, non_responders, alternative="two-sided").pvalue
        else:
            p_value = float("nan")

        rows.append({
            "population": population,
            "n_responders": len(responders),
            "n_non_responders": len(non_responders),
            "responder_median": responders.median(),
            "non_responder_median": non_responders.median(),
            "p_value": p_value,
        })

    stats = pd.DataFrame(rows, columns=[
        "population", "n_responders", "n_non_responders",
        "responder_median", "non_responder_median", "p_value",
    ])

    stats["p_adjusted"] = float("nan")
    tested = stats["p_value"].notna()
    if tested.any():
        stats.loc[tested, "p_adjusted"] = false_discovery_control(
            stats.loc[tested, "p_value"], method="bh"
        )
    stats["significant"] = stats["p_adjusted"] < SIGNIFICANCE_LEVEL
    return stats


def plot_response_boxplots(response_freq: pd.DataFrame, stats: pd.DataFrame) -> Figure:
    """One boxplot panel per population: responders vs non-responders."""
    if stats.empty:
        raise ValueError("No populations to plot: the statistics table is empty.")

    populations = list(stats["population"])
    stats_by_population = stats.set_index("population")
    groups = (RESPONDER, NON_RESPONDER)

    fig = Figure(figsize=(3.2 * len(populations), 4.8), layout="constrained")
    axes = fig.subplots(1, len(populations), squeeze=False)[0]

    for ax, population in zip(axes, populations):
        group = response_freq[response_freq["population"] == population]
        data = [group.loc[group["response"] == r, "percentage"].dropna() for r in groups]

        boxes = ax.boxplot(
            data,
            tick_labels=[GROUP_LABELS[r] for r in groups],
            patch_artist=True,
            widths=0.55,
            medianprops={"color": "#1a1a19", "linewidth": 2},
            flierprops={"marker": "o", "markersize": 3, "alpha": 0.4},
        )
        for patch, r in zip(boxes["boxes"], groups):
            patch.set_facecolor(GROUP_COLORS[r])
            patch.set_alpha(0.75)

        row = stats_by_population.loc[population]
        ax.set_title(
            f"{population}\np = {row['p_value']:.3f}  (adj. {row['p_adjusted']:.3f})",
            fontsize=10,
        )
        ax.grid(axis="y", color="#e0e0e0", linewidth=0.8)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)

    axes[0].set_ylabel("Relative frequency (%)")
    fig.suptitle(
        "Melanoma, miraclib, PBMC: cell population frequencies by response",
        fontsize=12,
    )
    return fig


def run_part3(conn: sqlite3.Connection) -> None:
    """Print the responder statistics and save the statistics CSV and boxplot PNG."""
    response_freq = get_response_frequencies(conn)
    stats = compare_responders(response_freq)

    stats_path = OUTPUT_DIR / "responder_statistics.csv"
    stats.to_csv(stats_path, index=False)
    plot_path = OUTPUT_DIR / "responder_boxplots.png"
    plot_response_boxplots(response_freq, stats).savefig(plot_path, dpi=150)

    n_patients = response_freq.groupby("response")["subject_id"].nunique()
    print("Part 3: Responders vs non-responders (melanoma, miraclib, PBMC)")
    print(f"Responders: {n_patients.get(RESPONDER, 0)} patients, "
          f"non-responders: {n_patients.get(NON_RESPONDER, 0)} patients")
    print("Test: Mann-Whitney U, Benjamini-Hochberg adjusted p-values")
    print(stats.to_string(index=False, float_format="%.4f"))

    significant = stats.loc[stats["significant"], "population"].tolist()
    if significant:
        print(f"Significant difference (adjusted p < {SIGNIFICANCE_LEVEL}): "
              + ", ".join(significant))
    else:
        print(f"No population is significant after adjustment (adjusted p < {SIGNIFICANCE_LEVEL}).")
        nominal = stats.loc[stats["p_value"] < SIGNIFICANCE_LEVEL, "population"].tolist()
        if nominal:
            print(f"Significant before adjustment (p < {SIGNIFICANCE_LEVEL}): "
                  + ", ".join(nominal))
    print(f"Saved {stats_path.relative_to(ROOT_DIR)} and {plot_path.relative_to(ROOT_DIR)}")


# ---------------------------------------------------------------------------
# Part 4: baseline subset (cohort above, time_from_treatment_start = 0)
# ---------------------------------------------------------------------------
BASELINE_SAMPLES_SQL = f"""
SELECT
    s.sample_id     AS sample,
    s.subject_id    AS subject,
    sub.project_id  AS project,
    sub.response,
    sub.sex
FROM samples s
JOIN subjects sub ON sub.subject_id = s.subject_id
WHERE {COHORT_FILTER_SQL}
  AND s.time_from_treatment_start = 0
ORDER BY s.sample_id
"""

# LEFT JOIN from all projects so projects without matching samples report 0.
BASELINE_SAMPLES_PER_PROJECT_SQL = f"""
WITH
    baseline     AS ({BASELINE_SAMPLES_SQL}),
    all_projects AS (SELECT DISTINCT project_id FROM subjects)
SELECT
    p.project_id           AS project,
    COUNT(baseline.sample) AS n_samples
FROM all_projects p
LEFT JOIN baseline ON baseline.project = p.project_id
GROUP BY p.project_id
ORDER BY p.project_id
"""

BASELINE_SUBJECTS_BY_RESPONSE_SQL = f"""
WITH baseline AS ({BASELINE_SAMPLES_SQL})
SELECT
    CASE response WHEN '{RESPONDER}'     THEN 'responder'
                  WHEN '{NON_RESPONDER}' THEN 'non-responder'
                  ELSE 'unknown' END AS response,
    COUNT(DISTINCT subject) AS n_subjects
FROM baseline
GROUP BY baseline.response
ORDER BY baseline.response DESC
"""

BASELINE_SUBJECTS_BY_SEX_SQL = f"""
WITH baseline AS ({BASELINE_SAMPLES_SQL})
SELECT
    CASE sex WHEN 'M' THEN 'male' WHEN 'F' THEN 'female' END AS sex,
    COUNT(DISTINCT subject) AS n_subjects
FROM baseline
GROUP BY baseline.sex
ORDER BY baseline.sex DESC
"""


# All sample types and treatments (not limited to the miraclib/PBMC cohort).
MELANOMA_MALE_RESPONDER_BASELINE_B_CELL_AVG_SQL = f"""
SELECT AVG(cc.count) AS avg_b_cell
FROM cell_counts cc
JOIN samples  s   ON s.sample_id    = cc.sample_id
JOIN subjects sub ON sub.subject_id = s.subject_id
WHERE sub.condition = 'melanoma'
  AND sub.sex = 'M'
  AND sub.response = '{RESPONDER}'
  AND s.time_from_treatment_start = 0
  AND cc.population = 'b_cell'
"""


MELANOMA_MALE_RESPONDER_BASELINE_B_CELL_N_SQL = f"""
SELECT COUNT(cc.count) AS n_samples
FROM cell_counts cc
JOIN samples  s   ON s.sample_id    = cc.sample_id
JOIN subjects sub ON sub.subject_id = s.subject_id
WHERE sub.condition = 'melanoma'
  AND sub.sex = 'M'
  AND sub.response = '{RESPONDER}'
  AND s.time_from_treatment_start = 0
  AND cc.population = 'b_cell'
"""


def get_baseline_samples(conn: sqlite3.Connection) -> pd.DataFrame:
    """Baseline melanoma/miraclib/PBMC samples: sample, subject, project, response, sex."""
    return pd.read_sql_query(BASELINE_SAMPLES_SQL, conn)


def count_baseline_samples_per_project(conn: sqlite3.Connection) -> pd.DataFrame:
    """Number of baseline samples per project."""
    return pd.read_sql_query(BASELINE_SAMPLES_PER_PROJECT_SQL, conn)


def count_baseline_subjects_by_response(conn: sqlite3.Connection) -> pd.DataFrame:
    """Number of baseline subjects who were responders / non-responders."""
    return pd.read_sql_query(BASELINE_SUBJECTS_BY_RESPONSE_SQL, conn)


def count_baseline_subjects_by_sex(conn: sqlite3.Connection) -> pd.DataFrame:
    """Number of baseline subjects who are male / female."""
    return pd.read_sql_query(BASELINE_SUBJECTS_BY_SEX_SQL, conn)


def average_b_cells_melanoma_male_responders_baseline(conn: sqlite3.Connection) -> float:
    """Average B cell count for male melanoma responders at time 0."""
    (average,) = conn.execute(MELANOMA_MALE_RESPONDER_BASELINE_B_CELL_AVG_SQL).fetchone()
    return average


def count_b_cell_samples_melanoma_male_responders_baseline(conn: sqlite3.Connection) -> int:
    """Number of samples behind the average B cell count above."""
    (n_samples,) = conn.execute(MELANOMA_MALE_RESPONDER_BASELINE_B_CELL_N_SQL).fetchone()
    return n_samples


def run_part4(conn: sqlite3.Connection) -> None:
    """Print the Part 4 results and save them to outputs/summary.txt."""
    baseline = get_baseline_samples(conn)

    report = [
        "Part 4: Melanoma PBMC samples at baseline (day 0) from miraclib-treated patients",
        f"{len(baseline)} samples from {baseline['subject'].nunique()} subjects",
        "",
        "Samples per project:",
        count_baseline_samples_per_project(conn).to_string(index=False),
        "",
        "Subjects by response:",
        count_baseline_subjects_by_response(conn).to_string(index=False),
        "",
        "Subjects by sex:",
        count_baseline_subjects_by_sex(conn).to_string(index=False),
        "",
        "Melanoma males (all sample types and treatments), responders, time 0:",
        f"Average B cell count: {average_b_cells_melanoma_male_responders_baseline(conn):.2f}",
    ]
    print("\n".join(report))

    out_path = OUTPUT_DIR / "summary.txt"
    out_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"\nSaved to {out_path.relative_to(ROOT_DIR)}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    """Run Parts 2, 3 and 4."""
    if not DB_PATH.exists():
        raise SystemExit(f"{DB_PATH.name} not found. Run `python load_data.py` first.")

    OUTPUT_DIR.mkdir(exist_ok=True)
    conn = open_database()
    try:
        run_part2(conn)
        print()
        run_part3(conn)
        print()
        run_part4(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        main()
    except PermissionError as error:
        raise SystemExit(f"Could not write {error.filename}.\n"
                         "Is it open in Excel? Close it and run this script again.")
