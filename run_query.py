from sqlalchemy import create_engine, text
from generation.generate_sql import generate_sql

# Connect to the same SQLite database
engine = create_engine("sqlite:///data/chinook.db")


def run_sql(sql):
    """Execute a SQL query and return (columns, rows) or (None, error_message)."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            rows = result.fetchall()
            columns = list(result.keys())
            return columns, rows
    except Exception as e:
        return None, str(e)


def ask(question):
    """Full pipeline: question -> model -> (SQL + result) OR clarification."""
    print(f"QUESTION: {question}")

    # The model now returns a dict: either a SQL answer or a clarification.
    result = generate_sql(question)

    # Case 1: the question was ambiguous -> show the clarification request
    if result["type"] == "clarification":
        print("NEEDS CLARIFICATION:")
        print(f"  {result['question']}")
        for opt in result["options"]:
            print(f"   - {opt}")
        print("-" * 60)
        return

    # Case 2: we got SQL -> run it and show the result
    sql = result["sql"]
    print(f"SQL:\n{sql}")

    columns, rows = run_sql(sql)
    if columns is None:
        print(f"ERROR: {rows}")
    else:
        print(f"COLUMNS: {columns}")
        for row in rows:
            print(row)
    print("-" * 60)


if __name__ == "__main__":
    ask("How many customers are there?")
    ask("Which 3 countries generate the most revenue?")
    ask("Who is our best customer?")  # should show clarification, not run SQL