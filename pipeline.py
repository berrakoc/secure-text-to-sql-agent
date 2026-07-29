from generation.generate_sql import generate_sql, validate_sql_syntax
from safety.guardrails import check_query
from safety.execute import run_readonly
from detection.verify import (
    verify_sql_matches_question,
    sanity_check_result,
    compute_confidence,
    multi_query_validation,
)


def answer_question(question):
    """The full text-to-SQL pipeline, end to end.

    Flow:
      question -> generate -> (clarification? stop)
               -> syntax check -> guardrails -> (blocked? stop)
               -> read-only execution -> packaged result

    Always returns a dict with a "status" field so callers know what happened:
      "clarification" | "blocked" | "error" | "success"
    """

    # Step 1: ask the model for SQL (or a clarification request)
    generated = generate_sql(question)

    # Step 2: if the question was ambiguous, stop and return the clarification
    if generated["type"] == "clarification":
        return {
            "status": "clarification",
            "question": generated["question"],
            "options": generated["options"],
        }

    sql = generated["sql"]

    # Step 3: basic syntax / statement-type check
    syntax = validate_sql_syntax(sql)
    if not syntax["valid"]:
        return {"status": "error", "sql": sql, "reason": syntax["message"]}

    # Step 4: run the safety guardrails (may add a LIMIT)
    guard = check_query(sql)
    if not guard["allowed"]:
        return {"status": "blocked", "sql": sql, "reason": guard["reason"]}

    safe_sql = guard["sql"]  # possibly has a LIMIT added

    # Step 5: execute on the read-only connection
    execution = run_readonly(safe_sql)
    if not execution["success"]:
        return {"status": "error", "sql": safe_sql, "reason": execution["error"]}

    # Step 5b: run hallucination-detection checks (Phase 3)
    # Signal 1: does the SQL back-translate to the original question?
    verification = verify_sql_matches_question(question, safe_sql)
    # Signal 2: does the result look sane? (cheap, no LLM)
    sanity_flags = sanity_check_result(execution, safe_sql)
    # Signal 3: for complex queries, cross-check with an independent query.
    multi_query = multi_query_validation(question, safe_sql, execution)
    # Combine all signals into a real, explainable confidence score.
    scoring = compute_confidence(
        syntax_valid=syntax["valid"],
        alignment_similarity=verification["similarity"],
        sanity_flags=sanity_flags,
        multi_query=multi_query,
    )

    # Step 6: package everything together
    return {
        "status": "success",
        "question": question,
        "sql": safe_sql,
        "explanation": generated.get("explanation"),
        # Real computed confidence replaces the model's self-reported one
        "confidence": scoring["confidence"],
        "confidence_breakdown": scoring["breakdown"],
        "back_translated_question": verification["back_translated"],
        "sanity_flags": sanity_flags,
        "multi_query_check": multi_query["detail"],
        "tables_used": generated.get("tables_used"),
        "columns": execution["columns"],
        "rows": execution["rows"],
        "row_count": execution["row_count"],
        "elapsed_ms": execution["elapsed_ms"],
        "plan": execution["plan"],
    }


def print_result(result):
    """Pretty-print a pipeline result for the terminal."""
    status = result["status"]

    if status == "clarification":
        print("NEEDS CLARIFICATION:", result["question"])
        for opt in result["options"]:
            print("  -", opt)

    elif status == "blocked":
        print("BLOCKED:", result["reason"])
        print("  SQL:", result["sql"])

    elif status == "error":
        print("ERROR:", result["reason"])
        print("  SQL:", result.get("sql"))

    elif status == "success":
        print("SQL:", result["sql"])
        print("EXPLANATION:", result["explanation"])
        print(f"CONFIDENCE: {result['confidence']}  breakdown={result['confidence_breakdown']}")
        print("BACK-TRANSLATED:", result["back_translated_question"])
        print("MULTI-QUERY:", result["multi_query_check"])
        if result["sanity_flags"]:
            print("SANITY FLAGS:", result["sanity_flags"])
        print(f"RESULT ({result['row_count']} rows, {result['elapsed_ms']} ms):")
        print("  COLUMNS:", result["columns"])
        for row in result["rows"][:10]:
            print("  ", row)


if __name__ == "__main__":
    questions = [
        "How many customers are there?",
        "Which 3 countries generate the most revenue?",
        "Who is our best customer?",   # clarification
    ]
    for q in questions:
        print(f"\nQUESTION: {q}")
        print("-" * 60)
        print_result(answer_question(q))