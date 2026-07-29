import time
from sqlalchemy import create_engine, text

# Read-only connection to SQLite (second line of defense).
READONLY_ENGINE = create_engine(
    "sqlite:///file:data/chinook.db?mode=ro&uri=true"
)


def run_readonly(sql):
    """Execute a SQL query on a strictly read-only connection.
    Also measures execution time and captures the query plan (EXPLAIN).

    Returns a dict with success, columns, rows, row_count, elapsed_ms, plan
    (or success=False with an error message)."""
    try:
        with READONLY_ENGINE.connect() as conn:
            # Measure how long the query takes to run
            start = time.perf_counter()
            result = conn.execute(text(sql))
            columns = list(result.keys())
            # Convert SQLAlchemy Row objects into plain lists so the result
            # can be serialized to JSON (needed by the API layer).
            rows = [list(row) for row in result.fetchall()]
            elapsed_ms = (time.perf_counter() - start) * 1000

            # Capture the query plan (how SQLite will execute this query)
            plan = get_query_plan(conn, sql)

            return {
                "success": True,
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
                "elapsed_ms": round(elapsed_ms, 2),
                "plan": plan,
            }
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_query_plan(conn, sql):
    """Ask SQLite how it plans to run the query (its EXPLAIN QUERY PLAN).
    Useful for auditability and for spotting expensive full-table scans."""
    try:
        plan_rows = conn.execute(
            text(f"EXPLAIN QUERY PLAN {sql}")
        ).fetchall()
        # Each row's last field is a human-readable step description
        return [row[-1] for row in plan_rows]
    except Exception:
        return []


if __name__ == "__main__":
    print(run_readonly("SELECT COUNT(*) FROM Customer;"))