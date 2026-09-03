from pathlib import Path
import sqlite3
import pandas as pd


# ============================================================
# CHIA v0.1 — Normalize Primary HPSA Measures
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = PROJECT_ROOT / "Data" / "Model" / "chia_v01.sqlite"

METHODOLOGY_VERSION = "v0.1"
NORMALIZATION_METHOD = "county_percentile_rank_average"

VARIABLES_TO_NORMALIZE = [
    "PC_HPSA_GEOGRAPHIC_COVERAGE",
    "DENTAL_HPSA_GEOGRAPHIC_COVERAGE",
    "MH_HPSA_GEOGRAPHIC_COVERAGE",
]


def main():
    print("=" * 70)
    print("CHIA v0.1 NORMALIZATION")
    print("=" * 70)

    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Database not found:\n{DATABASE_PATH}"
        )

    connection = sqlite3.connect(DATABASE_PATH)

    try:
        connection.execute("PRAGMA foreign_keys = ON")

        # Confirm methodology exists.
        methodology = connection.execute(
            """
            SELECT methodology_version
            FROM methodology
            WHERE methodology_version = ?
            """,
            (METHODOLOGY_VERSION,),
        ).fetchone()

        if methodology is None:
            raise ValueError(
                f"Methodology {METHODOLOGY_VERSION!r} not found."
            )

        total_inserted = 0

        for variable_id in VARIABLES_TO_NORMALIZE:
            print(f"\nProcessing: {variable_id}")

            rows = connection.execute(
                """
                SELECT observation_id, raw_value
                FROM observation
                WHERE variable_id = ?
                ORDER BY observation_id
                """,
                (variable_id,),
            ).fetchall()

            if not rows:
                raise ValueError(
                    f"No observations found for {variable_id}."
                )

            df = pd.DataFrame(
                rows,
                columns=["observation_id", "raw_value"],
            )

            # Start with NULL for missing observations.
            df["normalized_value"] = None

            # Valid positive values receive average-tie percentile ranks.
            positive_mask = (
                df["raw_value"].notna()
                & (df["raw_value"] > 0)
            )

            positive_values = df.loc[
                positive_mask, "raw_value"
            ]

            if not positive_values.empty:
                df.loc[
                    positive_mask, "normalized_value"
                ] = positive_values.rank(
                    method="average",
                    pct=True,
                )

            # Valid zero values explicitly remain zero.
            zero_mask = (
                df["raw_value"].notna()
                & (df["raw_value"] == 0)
            )

            df.loc[zero_mask, "normalized_value"] = 0.0

            # Replace any existing v0.1 results for this variable.
            connection.execute(
                """
                DELETE FROM normalized_measure
                WHERE methodology_version = ?
                  AND observation_id IN (
                      SELECT observation_id
                      FROM observation
                      WHERE variable_id = ?
                  )
                """,
                (METHODOLOGY_VERSION, variable_id),
            )

            records = [
                (
                    int(row.observation_id),
                    METHODOLOGY_VERSION,
                    (
                        None
                        if pd.isna(row.normalized_value)
                        else float(row.normalized_value)
                    ),
                    NORMALIZATION_METHOD,
                )
                for row in df.itertuples(index=False)
            ]

            connection.executemany(
                """
                INSERT INTO normalized_measure (
                    observation_id,
                    methodology_version,
                    normalized_value,
                    normalization_method
                )
                VALUES (?, ?, ?, ?)
                """,
                records,
            )

            connection.commit()

            inserted = len(records)
            total_inserted += inserted

            missing = int(df["raw_value"].isna().sum())
            zeros = int(zero_mask.sum())
            positive = int(positive_mask.sum())

            print(f"    Observations: {inserted:,}")
            print(f"    Positive values normalized: {positive:,}")
            print(f"    Zero values preserved: {zeros:,}")
            print(f"    Missing values preserved: {missing:,}")

    finally:
        connection.close()

    print()
    print("=" * 70)
    print("NORMALIZATION COMPLETE")
    print("=" * 70)
    print(f"Normalized-measure records written: {total_inserted:,}")
    print("=" * 70)


if __name__ == "__main__":
    main()