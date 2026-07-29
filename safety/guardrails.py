import sqlparse

# --- Configurable rules (easy to tune or expose via API later) ---

# Only these statement types are allowed to run. Everything else is blocked.
ALLOWED_STATEMENT_TYPES = {"SELECT"}

# Keywords that must never appear, even inside an otherwise SELECT-looking query
# (defense against tricks like "SELECT ... ; DROP ..." or hidden writes).
FORBIDDEN_KEYWORDS = {
    "DROP", "DELETE", "INSERT", "UPDATE", "ALTER",
    "CREATE", "TRUNCATE", "REPLACE", "ATTACH", "PRAGMA", "GRANT", "REVOKE",
}

# If the query has no LIMIT, we add this one automatically.
DEFAULT_ROW_LIMIT = 1000

# Reject queries nested deeper than this (very deep subqueries are a red flag).
MAX_SUBQUERY_DEPTH = 3


# --- Simple audit log: every blocked query is recorded here ---
BLOCKED_LOG = []


def _log_blocked(sql, reason):
    """Record a blocked query with the reason, for auditability."""
    BLOCKED_LOG.append({"sql": sql, "reason": reason})


def _statement_type(sql):
    """Return the SQL statement type (SELECT, DROP, ...) using sqlparse."""
    statements = [s for s in sqlparse.parse(sql) if str(s).strip()]
    if not statements:
        return None
    return statements[0].get_type()


def _count_statements(sql):
    """Count how many separate SQL statements the string contains.
    More than one is a classic injection pattern (stacked queries)."""
    return len([s for s in sqlparse.parse(sql) if str(s).strip()])


def _max_paren_depth(sql):
    """Rough nesting depth by counting parentheses.
    A proxy for how deeply subqueries are nested."""
    depth = 0
    max_depth = 0
    for char in sql:
        if char == "(":
            depth += 1
            max_depth = max(max_depth, depth)
        elif char == ")":
            depth -= 1
    return max_depth


def _contains_forbidden_keyword(sql):
    """Check for forbidden keywords as whole words (case-insensitive)."""
    upper_tokens = sql.upper().replace("(", " ").replace(")", " ").split()
    for kw in FORBIDDEN_KEYWORDS:
        if kw in upper_tokens:
            return kw
    return None


def _enforce_row_limit(sql):
    """Add a LIMIT clause if the query doesn't already have one.
    Keeps result sets bounded so a huge query can't overwhelm the system."""
    if "LIMIT" in sql.upper():
        return sql
    # Remove a trailing semicolon, add LIMIT, put semicolon back.
    stripped = sql.rstrip().rstrip(";")
    return f"{stripped}\nLIMIT {DEFAULT_ROW_LIMIT};"


def check_query(sql):
    """Run all guardrail rules on a SQL string.

    Returns a dict:
      {"allowed": True,  "sql": <possibly with LIMIT added>, "reason": "OK"}
      {"allowed": False, "sql": <original>, "reason": <why it was blocked>}
    """

    # Rule 1: must be a single statement (no stacked queries)
    if _count_statements(sql) != 1:
        reason = "Only a single SQL statement is allowed"
        _log_blocked(sql, reason)
        return {"allowed": False, "sql": sql, "reason": reason}

    # Rule 2: statement type must be allowed (SELECT only)
    stmt_type = _statement_type(sql)
    if stmt_type not in ALLOWED_STATEMENT_TYPES:
        reason = f"Statement type '{stmt_type}' is not allowed (read-only SELECT only)"
        _log_blocked(sql, reason)
        return {"allowed": False, "sql": sql, "reason": reason}

    # Rule 3: no forbidden keywords anywhere (belt-and-suspenders with Rule 2)
    bad_kw = _contains_forbidden_keyword(sql)
    if bad_kw:
        reason = f"Forbidden keyword detected: {bad_kw}"
        _log_blocked(sql, reason)
        return {"allowed": False, "sql": sql, "reason": reason}

    # Rule 4: reject overly deep nesting
    if _max_paren_depth(sql) > MAX_SUBQUERY_DEPTH:
        reason = f"Query nesting too deep (> {MAX_SUBQUERY_DEPTH} levels)"
        _log_blocked(sql, reason)
        return {"allowed": False, "sql": sql, "reason": reason}

    # Passed all checks: enforce a row limit and allow it.
    safe_sql = _enforce_row_limit(sql)
    return {"allowed": True, "sql": safe_sql, "reason": "OK"}


# Quick test: a mix of safe and dangerous queries
if __name__ == "__main__":
    test_queries = [
        "SELECT COUNT(*) FROM Customer;",                       # safe
        "SELECT Name FROM Track;",                              # safe, no LIMIT
        "DROP TABLE Album;",                                    # dangerous: DROP
        "DELETE FROM Customer WHERE CustomerId = 1;",           # dangerous: DELETE
        "INSERT INTO Genre (Name) VALUES ('Hacked');",          # dangerous: INSERT
        "SELECT * FROM Customer; DROP TABLE Album;",            # stacked injection
        "UPDATE Invoice SET Total = 0;",                        # dangerous: UPDATE
    ]

    for q in test_queries:
        result = check_query(q)
        status = "ALLOWED" if result["allowed"] else "BLOCKED "
        print(f"[{status}] {q}")
        if not result["allowed"]:
            print(f"           reason: {result['reason']}")
        elif result["sql"] != q:
            print(f"           -> LIMIT added")
        print()

    print("=" * 60)
    print(f"Total blocked queries logged: {len(BLOCKED_LOG)}")