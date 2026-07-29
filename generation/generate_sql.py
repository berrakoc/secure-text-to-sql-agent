import json
import sqlparse
from openai import OpenAI
from dotenv import load_dotenv
from db.schema import build_schema_text
from db.schema_filter import get_relevant_tables

load_dotenv()
client = OpenAI()

# Few-shot examples now include the richer output shape:
# sql + explanation + confidence + the tables the query uses.
# The last example shows the clarification shape for ambiguous questions.
FEW_SHOT_EXAMPLES = [
    {
        "question": "How many tracks are there in total?",
        "answer": {
            "type": "sql",
            "sql": "SELECT COUNT(*) FROM Track;",
            "explanation": "Counts all rows in the Track table.",
            "confidence": 0.98,
            "tables_used": ["Track"],
        },
    },
    {
        "question": "What is the total revenue from customers in the USA?",
        "answer": {
            "type": "sql",
            "sql": (
                "SELECT SUM(Invoice.Total) AS TotalRevenue\n"
                "FROM Invoice\n"
                "WHERE Invoice.BillingCountry = 'USA';"
            ),
            "explanation": "Sums invoice totals where the billing country is the USA.",
            "confidence": 0.95,
            "tables_used": ["Invoice"],
        },
    },
    {
        # Ambiguous question -> ask instead of guessing.
        "question": "Who is our best customer?",
        "answer": {
            "type": "clarification",
            "question": "What do you mean by 'best' customer?",
            "options": [
                "The customer who spent the most money in total",
                "The customer with the most invoices",
                "The customer with the most recent purchase",
            ],
        },
    },
]


def build_messages(question):
    """Assemble the message list: system prompt + few-shot examples + question.
    The schema is filtered to the tables relevant to this question."""

    relevant_tables = get_relevant_tables(question, top_n=4)
    schema_text = build_schema_text(only_tables=relevant_tables)

    system_prompt = f"""You are an expert SQL assistant for a SQLite database.

For each question, respond with a JSON object in one of two shapes:

1. If the question is clear, return SQL with metadata:
   {{"type": "sql",
     "sql": "<a single valid SQLite SELECT query>",
     "explanation": "<one short sentence describing what the query does>",
     "confidence": <a number from 0 to 1 for how sure you are>,
     "tables_used": ["<table names the query reads from>"]}}

2. If the question is ambiguous (could reasonably mean different things),
   do NOT guess. Ask for clarification:
   {{"type": "clarification",
     "question": "<what is unclear>",
     "options": ["<option 1>", "<option 2>"]}}

Rules:
- Only use tables and columns that exist in the schema below.
- Only generate read-only SELECT queries. Never write or change data.
- Use the foreign key hints (-- ... refers to ...) to write correct JOINs.
- Use the example values to match real values in the data.
- Return ONLY the JSON object, nothing else.

Database schema:
{schema_text}
"""

    messages = [{"role": "system", "content": system_prompt}]

    for ex in FEW_SHOT_EXAMPLES:
        messages.append({"role": "user", "content": ex["question"]})
        messages.append({"role": "assistant", "content": json.dumps(ex["answer"])})

    messages.append({"role": "user", "content": question})
    return messages


def validate_sql_syntax(sql):
    """Basic syntax/type check with sqlparse, before the query is ever run.
    Returns a dict: is it parseable, what statement type is it (SELECT/DROP/...),
    and whether it contains more than one statement.
    This is the first brick of the safety layer built in the next step."""

    parsed = sqlparse.parse(sql)

    # Keep only non-empty statements (ignores a trailing ';')
    statements = [s for s in parsed if str(s).strip()]

    if not statements:
        return {"valid": False, "statement_type": None,
                "message": "Empty or unparseable SQL"}

    # Multiple statements (e.g. "SELECT ...; DROP ...") is a classic
    # injection pattern -> reject early.
    if len(statements) > 1:
        return {"valid": False, "statement_type": None,
                "message": "Multiple SQL statements are not allowed"}

    # Identify the statement type: SELECT, INSERT, UPDATE, DELETE, DROP, ...
    stmt_type = statements[0].get_type()

    if stmt_type == "UNKNOWN":
        return {"valid": False, "statement_type": None,
                "message": "Could not determine statement type"}

    return {"valid": True, "statement_type": stmt_type, "message": "OK"}


def generate_sql(question):
    """Take a question and return a parsed dict:
    either a rich SQL answer or a clarification request."""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=build_messages(question),
        temperature=0,
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)


# Quick test
if __name__ == "__main__":
    questions = [
        "How many customers are there?",
        "Who is our best customer?",  # should trigger clarification
    ]
    for q in questions:
        print(f"QUESTION: {q}")
        result = generate_sql(q)

        if result["type"] == "sql":
            print("SQL:", result["sql"])
            print("EXPLANATION:", result["explanation"])
            print("CONFIDENCE:", result["confidence"])
            print("TABLES USED:", result["tables_used"])
            # Run the new syntax check on the generated SQL
            check = validate_sql_syntax(result["sql"])
            print("SYNTAX CHECK:", check)
        elif result["type"] == "clarification":
            print("NEEDS CLARIFICATION:", result["question"])
            for opt in result["options"]:
                print("  -", opt)
        print("-" * 60)

    # Bonus: prove the syntax checker can spot a dangerous statement type.
    # (The model won't produce this, but the safety layer will inspect such
    #  strings in the next step.)
    print("DANGEROUS SQL TEST:")
    print(validate_sql_syntax("DROP TABLE Album;"))