# Loblaw Bio: Immune Cell Population Analysis

Analysis of immune cell populations from Bob Loblaw's clinical trial (`cell-count.csv`): a SQLite database, a reproducible analysis pipeline, and an interactive dashboard.

**Dashboard:** http://localhost:8501, started with `make dashboard` (in Codespaces, open the forwarded port 8501 from the pop-up or the **Ports** tab).

## Quick start (GitHub Codespaces)

Open the repository in a Codespace, then run:

```bash
make setup       # install Python dependencies from requirements.txt
make pipeline    # build the database and run the full analysis (Parts 1-4)
make dashboard   # start the dashboard on port 8501
```

Plain `make` runs `setup` and `pipeline` together. `make clean` removes the database and generated outputs.

To run without `make` (each script runs directly, with no arguments):

```bash
pip install -r requirements.txt
python load_data.py
python analysis.py
python dashboard.py
```

## What the pipeline does

| Step | Script | Result |
|---|---|---|
| Part 1: Data management | `load_data.py` | Creates `cell_counts.db` and loads every row of `cell-count.csv` |
| Part 2: Data overview | `analysis.py` | Relative frequency of each cell population in each sample |
| Part 3: Statistical analysis | `analysis.py` | Responders vs non-responders (melanoma, miraclib, PBMC): boxplots and significance tests |
| Part 4: Data subset analysis | `analysis.py` | Baseline melanoma/miraclib/PBMC samples, counted by project, response and sex |

### Outputs (`outputs/`)

| File | Contents |
|---|---|
| `cell_frequencies.csv` | Part 2 summary table: `sample, total_count, population, count, percentage` |
| `responder_statistics.csv` | Part 3 medians, p-values, adjusted p-values and significance per population |
| `responder_boxplots.png` | Part 3 boxplots, one panel per population |
| `summary.txt` | Part 4 counts, plus the average B cell count for male melanoma responders at time 0 |

## Dashboard

`dashboard.py` (Streamlit + Plotly) reads `cell_counts.db` through the same functions as `analysis.py`, so it always matches the files in `outputs/`. Port and theme are set in `.streamlit/config.toml`.

- **Part 2: Cell frequencies.** The summary table, searchable by sample ID and filterable by population, with CSV download. Any sample can be looked up by patient or by ID to see its details and a donut chart of its composition.
- **Part 3: Responders vs non-responders.** Boxplots per population with hover details, the statistics table (Mann-Whitney U, Benjamini-Hochberg adjusted p-values), and a plain-language conclusion.
- **Part 4: Baseline subset.** Samples per project, responders vs non-responders and males vs females as bar charts, the average B cell count for male melanoma responders at day 0, and the list of baseline samples.

## Database schema

Each patient's details (condition, age, sex, treatment, response) repeat on every one of their rows in the CSV. The schema stores them once by splitting the data into three tables:

```
subjects ──< samples ──< cell_counts
```

| Table | One row per | Columns |
|---|---|---|
| `subjects` | patient | `subject_id` (PK), `project_id`, `condition`, `age`, `sex`, `treatment`, `response` |
| `samples` | biological sample | `sample_id` (PK), `subject_id` (FK), `sample_type`, `time_from_treatment_start` |
| `cell_counts` | sample × cell population | `sample_id` (FK), `population`, `count`; PK (`sample_id`, `population`) |

- **Long format for cell counts.** One row per population instead of five columns, so per-population calculations are a single `GROUP BY` / `PARTITION BY` query and a new population needs no schema change.
- **Patient vs sample attributes.** Patient details live in `subjects`; sample type and time point live in `samples`. Filters such as "melanoma + miraclib + PBMC + day 0" join the two.

## Code structure

```
.
├── load_data.py       # Part 1: schema + CSV loader -> cell_counts.db
├── analysis.py        # Parts 2-4: queries, statistics, plots; writes outputs/
├── dashboard.py       # Streamlit dashboard for Parts 2-4
├── .streamlit/        # Dashboard port and theme (config.toml)
├── cell-count.csv     # Input data
├── requirements.txt   # Python dependencies
├── Makefile           # setup / pipeline / dashboard targets
└── outputs/           # Generated results
```

- **`load_data.py`** rebuilds the database on every run, so the pipeline is repeatable and never duplicates rows.
- **`analysis.py`** runs Part 2 → Part 3 → Part 4. Each part has its SQL queries, functions that return pandas DataFrames, and a `run_partN()` function that prints and saves the results.
- **`dashboard.py`** imports the same functions, so the dashboard and the saved outputs always show the same numbers.
