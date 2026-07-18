from sqlalchemy import create_engine, text
from generate_sql import generate_sql

# Connect to the same SQLite database
engine = create_engine("sqlite:///data/chinook.db")


def run_sql(sql):
    """Execute a SQL query and return the rows (or an error message)."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            rows = result.fetchall()
            columns = list(result.keys())
            return columns, rows
    except Exception as e:
        # If the SQL is invalid, return the error instead of crashing
        return None, str(e)


def ask(question):
    """Full pipeline: question -> SQL -> execution -> printed result."""
    print(f"QUESTION: {question}")

    # Step 1: model generates SQL
    sql = generate_sql(question)
    print(f"SQL:\n{sql}")

    # Step 2: run the SQL on the database
    columns, rows = run_sql(sql)

    # Step 3: show the result
    if columns is None:
        print(f"ERROR: {rows}")
    else:
        print(f"COLUMNS: {columns}")
        for row in rows:
            print(row)
    print("-" * 60)


if __name__ == "__main__":
    ask("How many customers are there?")
    ask("List the top 5 artists with the most albums.")
    ask("What is the total revenue from invoices in the USA?")