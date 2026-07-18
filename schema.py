from sqlalchemy import create_engine, inspect

# Connect SQLAlchemy directly to the SQLite database
engine = create_engine("sqlite:///data/chinook.db")
inspector = inspect(engine)


def build_schema_text():
    """Read the database structure and return it as CREATE TABLE style text.
    This text is what we will feed to the language model as context."""

    schema_lines = []

    for table in inspector.get_table_names():
        # Start a CREATE TABLE block for this table
        schema_lines.append(f"CREATE TABLE {table} (")

        # Collect column definitions
        col_defs = []
        for col in inspector.get_columns(table):
            col_defs.append(f"    {col['name']} {col['type']}")

        # Join columns with commas
        schema_lines.append(",\n".join(col_defs))
        schema_lines.append(");")

        # Add foreign key relationships as readable comments below the table
        fks = inspector.get_foreign_keys(table)
        for fk in fks:
            local_col = fk["constrained_columns"][0]
            ref_table = fk["referred_table"]
            ref_col = fk["referred_columns"][0]
            schema_lines.append(
                f"-- {table}.{local_col} refers to {ref_table}.{ref_col}"
            )

        # Empty line between tables for readability
        schema_lines.append("")

    return "\n".join(schema_lines)


# Run it and print the result so we can see what the model will receive
if __name__ == "__main__":
    schema_text = build_schema_text()
    print(schema_text)