from openai import OpenAI
from dotenv import load_dotenv

# Reuse the embedding + similarity helpers we already built in Phase 1.
from schema_filter import embed_text, cosine_similarity

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