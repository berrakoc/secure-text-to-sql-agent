from sqlalchemy import create_engine, inspect, text

# Connect SQLAlchemy directly to the SQLite database
engine = create_engine("sqlite:///data/chinook.db")
inspector = inspect(engine)


def get_sample_values(table, column, limit=5):
    """Fetch a few distinct values from a column, to help the model
    use real values (e.g. 'USA' instead of guessing 'United States')."""
    try:
        with engine.connect() as conn:
            query = text(
                f"SELECT DISTINCT {column} FROM {table} "
                f"WHERE {column} IS NOT NULL LIMIT {limit}"
            )
            rows = conn.execute(query).fetchall()
            # Each row is a tuple like ('USA',); take the first element
            return [r[0] for r in rows]
    except Exception:
        return []


# Only these columns get sample values — real category columns where the
# user might type the value directly (e.g. "customers in Brazil").
# Free text, IDs, emails, phones, addresses are deliberately excluded.
CATEGORICAL_COLUMNS = {
    ("Customer", "Country"),
    ("Invoice", "BillingCountry"),
    ("Employee", "Title"),
    ("Genre", "Name"),
    ("MediaType", "Name"),
    ("Playlist", "Name"),
}


def build_schema_text():
    """Read the database structure and return it as CREATE TABLE style text,
    including sample values for categorical columns."""

    schema_lines = []

    for table in inspector.get_table_names():
        schema_lines.append(f"CREATE TABLE {table} (")

        col_defs = []
        for col in inspector.get_columns(table):
            col_defs.append(f"    {col['name']} {col['type']}")
        schema_lines.append(",\n".join(col_defs))
        schema_lines.append(");")

        # Foreign key hints
        for fk in inspector.get_foreign_keys(table):
            local_col = fk["constrained_columns"][0]
            ref_table = fk["referred_table"]
            ref_col = fk["referred_columns"][0]
            schema_lines.append(
                f"-- {table}.{local_col} refers to {ref_table}.{ref_col}"
            )

        # Sample values only for whitelisted categorical columns
        for col in inspector.get_columns(table):
            if (table, col["name"]) in CATEGORICAL_COLUMNS:
                samples = get_sample_values(table, col["name"])
                if samples:
                    sample_str = ", ".join(repr(s) for s in samples)
                    schema_lines.append(
                        f"-- Example values for {table}.{col['name']}: {sample_str}"
                    )

        schema_lines.append("")

    return "\n".join(schema_lines)


if __name__ == "__main__":
    print(build_schema_text())