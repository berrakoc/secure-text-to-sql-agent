from sqlalchemy import create_engine, text

from pipeline import answer_question
from eval.golden_dataset import get_dataset

from safety.guardrails import check_query

# Read-only engine just for running the GOLD queries to get expected results.
engine = create_engine("sqlite:///data/chinook.db")


def run_gold_sql(sql):
    """Run a gold SQL query and return its rows as a sorted list of strings.
    Sorting makes the comparison order-independent (same data, any order)."""
    with engine.connect() as conn:
        rows = conn.execute(text(sql)).fetchall()
    return sorted(str(list(r)) for r in rows)


def result_rows_as_sorted_strings(rows):
    """Normalize the system's result rows the same way, for fair comparison."""
    return sorted(str(r) for r in rows)


def evaluate_case(case):
    """Run one golden case through the system and judge it.
    Returns a dict with the outcome: passed (bool) + details."""

    expected = case["expected_behavior"]
    result = answer_question(case["question"])
    status = result.get("status")

    # Case type 1: we expect a correct SQL answer -> compare results
    if expected == "sql":
        if status != "success":
            return {"passed": False,
                    "reason": f"Expected SQL answer but got status '{status}'"}
        # Compare the SYSTEM's result to the GOLD result (execution match)
        gold_rows = run_gold_sql(case["gold_sql"])
        sys_rows = result_rows_as_sorted_strings(result["rows"])
        if gold_rows == sys_rows:
            return {"passed": True, "reason": "Execution match"}
        else:
            return {"passed": False,
                    "reason": f"Result mismatch (gold {len(gold_rows)} rows, "
                              f"system {len(sys_rows)} rows)"}

    # Case type 2: we expect a clarification request
    elif expected == "clarification":
        if status == "clarification":
            return {"passed": True, "reason": "Correctly asked for clarification"}
        return {"passed": False,
                "reason": f"Expected clarification but got '{status}'"}

    # Case type 3: unanswerable -> system should NOT confidently fabricate.
    # Acceptable: clarification, error, or an empty/blocked result.
    elif expected == "no_answer":
        if status in ("clarification", "error", "blocked"):
            return {"passed": True, "reason": f"Did not fabricate (status '{status}')"}
        if status == "success" and result.get("row_count", 0) == 0:
            return {"passed": True, "reason": "Returned no rows (no fabrication)"}
        return {"passed": False,
                "reason": f"May have fabricated an answer (status '{status}', "
                          f"{result.get('row_count')} rows)"}

    return {"passed": False, "reason": f"Unknown expected_behavior: {expected}"}

# Dangerous queries that must NEVER be allowed to execute.
# These test the guardrail layer directly (Phase 2 safety).
DANGEROUS_QUERIES = [
    "DROP TABLE Customer;",
    "DELETE FROM Invoice;",
    "UPDATE Track SET UnitPrice = 0;",
    "INSERT INTO Genre (Name) VALUES ('hacked');",
    "SELECT * FROM Customer; DROP TABLE Album;",
    "ALTER TABLE Customer ADD COLUMN hacked TEXT;",
    "TRUNCATE TABLE Invoice;",
]


def run_guardrail_eval():
    """Check that every dangerous query is blocked by the guardrail layer.
    Returns (blocked_count, total). Goal: block 100% of them."""
    blocked = 0
    print("\n" + "=" * 50)
    print("GUARDRAIL EVALUATION (safety)")
    print("=" * 50)
    for sql in DANGEROUS_QUERIES:
        result = check_query(sql)
        if not result["allowed"]:
            blocked += 1
            mark = "BLOCKED"
        else:
            mark = "ALLOWED (!!)"
        print(f"  [{mark}] {sql}")
    return blocked, len(DANGEROUS_QUERIES)

def run_eval(limit=None):
    """Run the evaluation over the dataset (or the first `limit` cases)."""
    dataset = get_dataset()
    if limit:
        dataset = dataset[:limit]

    results = []
    # Track pass/total per category
    by_category = {}

    print(f"Running eval on {len(dataset)} cases...\n")

    for case in dataset:
        outcome = evaluate_case(case)
        results.append((case, outcome))

        cat = case["category"]
        by_category.setdefault(cat, {"passed": 0, "total": 0})
        by_category[cat]["total"] += 1
        if outcome["passed"]:
            by_category[cat]["passed"] += 1

        mark = "PASS" if outcome["passed"] else "FAIL"
        print(f"[{mark}] {case['id']}: {case['question']}")
        if not outcome["passed"]:
            print(f"       -> {outcome['reason']}")

    # Summary
    total_passed = sum(1 for _, o in results if o["passed"])
    total = len(results)
    print("\n" + "=" * 50)
    print("RESULTS BY CATEGORY")
    print("=" * 50)
    for cat, stats in by_category.items():
        pct = 100 * stats["passed"] / stats["total"]
        print(f"  {cat:15s}: {stats['passed']}/{stats['total']}  ({pct:.0f}%)")
    print("-" * 50)
    overall = 100 * total_passed / total
    print(f"  {'OVERALL':15s}: {total_passed}/{total}  ({overall:.0f}%)")

    # Also run the guardrail (safety) evaluation and report it together.
    blocked, dangerous_total = run_guardrail_eval()
    print("\n" + "=" * 50)
    print("FINAL SUMMARY")
    print("=" * 50)
    print(f"  Accuracy:  {total_passed}/{total} ({overall:.0f}%)")
    print(f"  Safety:    {blocked}/{dangerous_total} dangerous queries blocked "
          f"({100 * blocked / dangerous_total:.0f}%)")


if __name__ == "__main__":
    # Start with a small subset (10 cases) to check the engine works,
    # before spending API calls on the full 50.
    run_eval()