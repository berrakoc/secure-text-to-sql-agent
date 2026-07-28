from sqlalchemy import create_engine, text

# Read-only connection to SQLite.
# 'mode=ro' opens the database file in read-only mode at the driver level:
# even if a write query somehow slips through, the database refuses it.
# This is our second, independent line of defense (defense in depth).
READONLY_ENGINE = create_engine(
    "sqlite:///file:data/chinook.db?mode=ro&uri=true"
)


def run_readonly(sql):
    """Execute a SQL query on a strictly read-only connection.

    Returns a dict:
      {"success": True,  "columns": [...], "rows": [...]}
      {"success": False, "error": "<message>"}
    """
    try:
        with READONLY_ENGINE.connect() as conn:
            result = conn.execute(text(sql))
            columns = list(result.keys())
            rows = result.fetchall()
            return {"success": True, "columns": columns, "rows": rows}
    except Exception as e:
        # Any error (including a blocked write) lands here instead of crashing.
        return {"success": False, "error": str(e)}


# Quick test: a safe read, then prove writes are physically rejected.
if __name__ == "__main__":
    # 1. A normal read should work
    print("READ TEST:")
    result = run_readonly("SELECT COUNT(*) FROM Customer;")
    print(result)
    print()

    # 2. A write should be refused by the read-only connection itself,
    #    even though no guardrail is involved here.
    print("WRITE TEST (should fail at the connection level):")
    result = run_readonly("DELETE FROM Customer WHERE CustomerId = 1;")
    print(result)