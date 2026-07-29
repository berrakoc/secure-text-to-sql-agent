from openai import OpenAI
from dotenv import load_dotenv

# Reuse the embedding + similarity helpers we already built in Phase 1.
from db.schema_filter import embed_text, cosine_similarity

# Add these to the imports at the top of verify.py
from generation.generate_sql import generate_sql
from safety.execute import run_readonly

load_dotenv()
client = OpenAI()


def back_translate_sql(sql):
    """Ask the model to describe, in plain English, what question this SQL answers.
    This is the reverse direction: SQL -> question.
    A correct SQL should back-translate to something close to the original question."""

    system_prompt = """You are a SQL expert. You are given a SQL query.
Describe, in a single plain English question, what question this query answers.
Return ONLY the question, nothing else."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": sql},
        ],
        temperature=0,
    )
    return response.choices[0].message.content.strip()


def verify_sql_matches_question(original_question, sql):
    """Check whether the SQL actually answers the user's original question.

    Steps:
      1. Back-translate the SQL into a question.
      2. Embed both the original and back-translated questions.
      3. Measure cosine similarity between them.

    Returns a dict with the back-translation, the similarity score,
    and a simple pass/fail flag against a threshold."""

    back_translated = back_translate_sql(sql)

    # Embed both questions and compare their meaning
    original_vec = embed_text(original_question)
    back_vec = embed_text(back_translated)
    similarity = cosine_similarity(original_vec, back_vec)

    # If the two questions are far apart, the SQL likely answers the wrong thing.
    THRESHOLD = 0.75
    aligned = similarity >= THRESHOLD

    return {
        "original_question": original_question,
        "back_translated": back_translated,
        "similarity": round(float(similarity), 3),
        "aligned": aligned,
    }

def sanity_check_result(execution_result, sql):
    """Run cheap, LLM-free sanity checks on an execution result.
    These don't prove correctness — they raise flags worth lowering
    confidence for. Returns a list of human-readable warning strings
    (empty list means nothing looked suspicious).

    execution_result is the dict returned by run_readonly():
    it has columns, rows, row_count, etc."""

    flags = []

    rows = execution_result.get("rows", [])
    columns = execution_result.get("columns", [])
    row_count = execution_result.get("row_count", 0)

    # Check 1: empty result set. Sometimes correct, but often a wrong filter.
    if row_count == 0:
        flags.append("Result is empty — a filter value might not match the data")

    # Check 2: aggregate queries (COUNT/SUM/AVG) should usually return
    # a single row. Detect the aggregate case and sanity-check its shape/value.
    sql_upper = sql.upper()
    is_aggregate = any(fn in sql_upper for fn in ("COUNT(", "SUM(", "AVG("))
    has_group_by = "GROUP BY" in sql_upper

    if is_aggregate and not has_group_by:
        # An aggregate without GROUP BY should collapse to one row.
        if row_count > 1:
            flags.append(
                f"Aggregate query returned {row_count} rows (expected 1)"
            )
        # If it's a single numeric value, check it isn't negative.
        if row_count == 1 and len(rows[0]) == 1:
            value = rows[0][0]
            if isinstance(value, (int, float)) and value < 0:
                flags.append(f"Aggregate value is negative ({value})")

    # Check 3: a column that is entirely NULL often signals a bad JOIN.
    if rows:
        for col_index, col_name in enumerate(columns):
            all_null = all(row[col_index] is None for row in rows)
            if all_null:
                flags.append(f"Column '{col_name}' is entirely NULL — possible bad JOIN")

    return flags

def compute_confidence(syntax_valid, alignment_similarity, sanity_flags,
                       multi_query=None):
    """Combine independent signals into a single confidence score (0 to 1).

    Signals:
      - syntax_valid: bool, did the SQL pass the syntax/type check?
      - alignment_similarity: float 0-1, SQL-to-question back-translation match
      - sanity_flags: list of sanity warnings (more flags -> lower confidence)
      - multi_query: optional dict from multi_query_validation().
        If two independent queries agreed -> boost; if they disagreed -> penalty;
        if it wasn't run -> no effect.

    Returns the final score plus an explainable breakdown."""

    syntax_score = 1.0 if syntax_valid else 0.0
    alignment_score = float(alignment_similarity)
    sanity_score = max(0.0, 1.0 - 0.25 * len(sanity_flags))

    # Base weighted combination of the three always-available signals.
    weights = {"syntax": 0.2, "alignment": 0.5, "sanity": 0.3}
    base = (
        weights["syntax"] * syntax_score
        + weights["alignment"] * alignment_score
        + weights["sanity"] * sanity_score
    )

    # Multi-query adjustment (only if it actually ran).
    multi_query_effect = "not run"
    if multi_query and multi_query.get("checked"):
        if multi_query.get("agrees"):
            # Two independent queries agreed -> nudge confidence up.
            base = base + 0.1 * (1.0 - base)  # move 10% toward 1.0
            multi_query_effect = "agreed (boosted)"
        else:
            # They disagreed -> strong doubt, cut confidence.
            base = base * 0.5
            multi_query_effect = "disagreed (penalized)"

    return {
        "confidence": round(base, 3),
        "breakdown": {
            "syntax_score": round(syntax_score, 3),
            "alignment_score": round(alignment_score, 3),
            "sanity_score": round(sanity_score, 3),
            "multi_query": multi_query_effect,
        },
    }

def is_complex_question(sql):
    """Cheap heuristic: is this query complex enough to be worth a second,
    independent check? We only run the expensive multi-query validation
    on queries that join tables or aggregate — simple lookups are skipped."""
    sql_upper = sql.upper()
    signals = ("JOIN", "GROUP BY", "HAVING", "UNION")
    return any(s in sql_upper for s in signals)


def generate_alternative_sql(question):
    """Ask the model to answer the same question with a DIFFERENT SQL approach.
    We nudge it to vary its strategy so the two queries are truly independent."""
    hint = (
        question
        + "\n\n(Write the SQL using a different approach than usual — "
        "for example a subquery instead of a JOIN, or a different "
        "aggregation strategy. The result must still be correct.)"
    )
    result = generate_sql(hint)
    # The model might return a clarification; only proceed if it gave SQL.
    if result.get("type") == "sql":
        return result["sql"]
    return None


def multi_query_validation(question, primary_sql, primary_result):
    """Run a second, independently-generated query and compare results.

    Returns a dict:
      - checked: was multi-query validation actually run?
      - agrees: did the two approaches produce the same result?
      - detail: human-readable explanation

    primary_result is the dict from run_readonly() for the first query."""

    # Skip cheap/simple queries entirely
    if not is_complex_question(primary_sql):
        return {"checked": False, "agrees": None,
                "detail": "Simple query — multi-query validation skipped"}

    # Generate a second SQL with a different approach
    alt_sql = generate_alternative_sql(question)
    if alt_sql is None:
        return {"checked": False, "agrees": None,
                "detail": "Could not generate an alternative query"}

    # Run the alternative query (read-only, like everything else)
    alt_result = run_readonly(alt_sql)
    if not alt_result["success"]:
        return {"checked": True, "agrees": False,
                "detail": f"Alternative query failed to run: {alt_result['error'][:60]}"}

    # Compare the two result sets. We sort rows so that ordering
    # differences don't count as disagreement (same data, different order).
    primary_rows = sorted(str(r) for r in primary_result["rows"])
    alt_rows = sorted(str(r) for r in alt_result["rows"])

    if primary_rows == alt_rows:
        return {"checked": True, "agrees": True,
                "detail": "Two independent queries produced identical results"}
    else:
        return {"checked": True, "agrees": False,
                "detail": (f"Results differ: primary returned "
                           f"{primary_result['row_count']} rows, "
                           f"alternative returned {alt_result['row_count']} rows"),
                "alt_sql": alt_sql}

# Quick test: one good match, and one deliberately mismatched SQL
if __name__ == "__main__":
    # Case 1: the SQL genuinely answers the question -> should align
    print("CASE 1 (should align):")
    result = verify_sql_matches_question(
        "How many customers are there?",
        "SELECT COUNT(*) FROM Customer;",
    )
    for k, v in result.items():
        print(f"  {k}: {v}")

    print()

    # Case 2: the question and SQL don't match -> should NOT align
    print("CASE 2 (should NOT align):")
    result = verify_sql_matches_question(
        "How many customers are there?",
        "SELECT Name FROM Track WHERE Milliseconds > 300000;",
    )
    for k, v in result.items():
        print(f"  {k}: {v}")

    # --- Sanity check tests ---
    print("\n" + "=" * 50)
    print("SANITY CHECK TESTS")
    print("=" * 50)

    # A normal, healthy result: one row, positive count
    healthy = {
        "columns": ["COUNT(*)"],
        "rows": [(59,)],
        "row_count": 1,
    }
    print("\nHealthy result:")
    print("  flags:", sanity_check_result(healthy, "SELECT COUNT(*) FROM Customer;"))

    # An empty result (suspicious)
    empty = {"columns": ["Total"], "rows": [], "row_count": 0}
    print("\nEmpty result:")
    print("  flags:", sanity_check_result(empty, "SELECT SUM(Total) FROM Invoice WHERE BillingCountry = 'Wakanda';"))

    # An all-NULL column (bad JOIN signal)
    null_col = {
        "columns": ["Name", "Title"],
        "rows": [("AC/DC", None), ("Accept", None)],
        "row_count": 2,
    }
    print("\nAll-NULL column result:")
    print("  flags:", sanity_check_result(null_col, "SELECT Artist.Name, Album.Title FROM Artist JOIN Album ..."))

    # --- Confidence scoring tests ---
    print("\n" + "=" * 50)
    print("CONFIDENCE SCORING TESTS")
    print("=" * 50)

    # A good query: valid syntax, high alignment, no flags -> high confidence
    print("\nGood query:")
    print(" ", compute_confidence(
        syntax_valid=True,
        alignment_similarity=0.98,
        sanity_flags=[],
    ))

    # A suspicious query: valid syntax, but low alignment and one flag
    print("\nSuspicious query (wrong question + empty result):")
    print(" ", compute_confidence(
        syntax_valid=True,
        alignment_similarity=0.14,
        sanity_flags=["Result is empty — a filter value might not match the data"],
    ))

    # --- Multi-query validation tests ---
    print("\n" + "=" * 50)
    print("MULTI-QUERY VALIDATION TESTS")
    print("=" * 50)

    # A complex question (has a GROUP BY) -> validation should run
    q1 = "Which 3 countries generate the most revenue?"
    sql1 = ("SELECT BillingCountry, SUM(Total) AS TotalRevenue\n"
            "FROM Invoice\nGROUP BY BillingCountry\n"
            "ORDER BY TotalRevenue DESC\nLIMIT 3;")
    res1 = run_readonly(sql1)
    print(f"\nQ: {q1}")
    print(" ", multi_query_validation(q1, sql1, res1))

    # A simple question (no JOIN/GROUP BY) -> validation should be skipped
    q2 = "How many customers are there?"
    sql2 = "SELECT COUNT(*) FROM Customer;"
    res2 = run_readonly(sql2)
    print(f"\nQ: {q2}")
    print(" ", multi_query_validation(q2, sql2, res2))