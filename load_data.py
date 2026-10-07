"""
load_data.py

Creates the SQLite database cell_counts.db in the repository root and loads
every row of cell-count.csv into it.

Run with:
    python load_data.py

Schema:
    subjects     one row per subject (patient), including its project
    samples      one row per sample, linked to its subject
    cell_counts  one row per (sample, cell population), linked to its sample
"""

import csv
import sqlite3
from pathlib import Path

ROOT_DIR = Path(__file__).parent
CSV_PATH = ROOT_DIR / "cell-count.csv"
DB_PATH = ROOT_DIR / "cell_counts.db"

CELL_POPULATIONS = ["b_cell", "cd8_t_cell", "cd4_t_cell", "nk_cell", "monocyte"]

SCHEMA = """
CREATE TABLE subjects (
    subject_id  TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL,              -- e.g. prj1
    condition   TEXT NOT NULL,              -- indication, e.g. melanoma, carcinoma, healthy
    age         INTEGER NOT NULL,
    sex         TEXT NOT NULL CHECK (sex IN ('M', 'F')),
    treatment   TEXT NOT NULL,              -- e.g. miraclib, phauximab, none
    response    TEXT CHECK (response IN ('yes', 'no'))  -- NULL when not applicable
);

CREATE TABLE samples (
    sample_id                  TEXT PRIMARY KEY,
    subject_id                 TEXT NOT NULL REFERENCES subjects(subject_id),
    sample_type                TEXT NOT NULL,     -- e.g. PBMC, WB
    time_from_treatment_start  INTEGER NOT NULL   -- days
);

CREATE TABLE cell_counts (
    sample_id   TEXT NOT NULL REFERENCES samples(sample_id),
    population  TEXT NOT NULL,
    count       INTEGER NOT NULL CHECK (count >= 0),
    PRIMARY KEY (sample_id, population)
);

-- Indexes speed up the filters the later analysis parts will use most.
CREATE INDEX idx_subjects_project   ON subjects(project_id);
CREATE INDEX idx_subjects_condition ON subjects(condition, treatment);
CREATE INDEX idx_samples_subject    ON samples(subject_id);
"""


def create_database(db_path):
    """Delete any existing database file and create a fresh one with the schema."""
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def load_csv(conn, csv_path):
    """Read the CSV and insert its rows into the three tables in one transaction."""
    subjects = {}
    samples = []
    cell_counts = []

    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            subjects[row["subject"]] = (
                row["subject"],
                row["project"],
                row["condition"],
                int(row["age"]),
                row["sex"],
                row["treatment"],
                row["response"] or None,
            )

            samples.append((
                row["sample"],
                row["subject"],
                row["sample_type"],
                int(row["time_from_treatment_start"]),
            ))

            for population in CELL_POPULATIONS:
                cell_counts.append((row["sample"], population, int(row[population])))

    with conn:
        conn.executemany(
            "INSERT INTO subjects (subject_id, project_id, condition, age, sex, treatment, response) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            subjects.values(),
        )
        conn.executemany(
            "INSERT INTO samples (sample_id, subject_id, sample_type, time_from_treatment_start) "
            "VALUES (?, ?, ?, ?)",
            samples,
        )
        conn.executemany(
            "INSERT INTO cell_counts (sample_id, population, count) VALUES (?, ?, ?)",
            cell_counts,
        )


def main():
    conn = create_database(DB_PATH)
    try:
        load_csv(conn, CSV_PATH)

        print(f"Created {DB_PATH.name}")
        for table in ["subjects", "samples", "cell_counts"]:
            (n,) = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            print(f"  {table:<12} {n:>6} rows")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
