import json
from openai import OpenAI
from dotenv import load_dotenv
from schema import build_schema_text
from schema_filter import get_relevant_tables

load_dotenv()
client = OpenAI()

# Few-shot examples now include the JSON shape we want the model to produce.
# Most are normal SQL answers; the last one shows how to ask for clarification
# when a question is ambiguous.
FEW_SHOT_EXAMPLES = [
    {
        "question": "How many tracks are there in total?",
        "answer": {"type": "sql", "sql": "SELECT COUNT(*) FROM Track;"},
    },
    {
        "question": "List the top 5 artists with the most albums.",
        "answer": {
            "type": "sql",
            "sql": (
                "SELECT Artist.Name, COUNT(Album.AlbumId) AS AlbumCount\n"
                "FROM Artist\n"
                "JOIN Album ON Artist.ArtistId = Album.ArtistId\n"
                "GROUP BY Artist.ArtistId\n"
                "ORDER BY AlbumCount DESC\n"
                "LIMIT 5;"
            ),
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
        },
    },
    {
        # Ambiguous example: "best customer" could mean several things.
        # The model should ask instead of guessing.
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

    # Pick only the tables relevant to this question
    relevant_tables = get_relevant_tables(question, top_n=4)
    schema_text = build_schema_text(only_tables=relevant_tables)

    system_prompt = f"""You are an expert SQL assistant for a SQLite database.

For each question, respond with a JSON object in one of two shapes:

1. If the question is clear, return SQL:
   {{"type": "sql", "sql": "<a single valid SQLite query>"}}

2. If the question is ambiguous (could reasonably mean different things),
   do NOT guess. Ask for clarification:
   {{"type": "clarification", "question": "<what is unclear>", "options": ["<option 1>", "<option 2>"]}}

Rules:
- Only use tables and columns that exist in the schema below.
- Use the foreign key hints (-- ... refers to ...) to write correct JOINs.
- Use the example values to match real values in the data.
- Return ONLY the JSON object, nothing else.

Database schema:
{schema_text}
"""

    messages = [{"role": "system", "content": system_prompt}]

    # Add each few-shot example, with the answer serialized as JSON text
    for ex in FEW_SHOT_EXAMPLES:
        messages.append({"role": "user", "content": ex["question"]})
        messages.append({"role": "assistant", "content": json.dumps(ex["answer"])})

    messages.append({"role": "user", "content": question})
    return messages


def generate_sql(question):
    """Take a question and return a parsed dict:
    either {"type": "sql", ...} or {"type": "clarification", ...}."""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=build_messages(question),
        temperature=0,
        response_format={"type": "json_object"},  # force valid JSON output
    )
    # Parse the JSON string into a Python dict
    return json.loads(response.choices[0].message.content)


# Quick test: two clear questions and one ambiguous one
if __name__ == "__main__":
    questions = [
        "How many customers are there?",
        "Which 3 countries generate the most revenue?",
        "Who is our best customer?",  # should trigger clarification
    ]
    for q in questions:
        print(f"QUESTION: {q}")
        result = generate_sql(q)

        if result["type"] == "sql":
            print("SQL:")
            print(result["sql"])
        elif result["type"] == "clarification":
            print("NEEDS CLARIFICATION:")
            print(f"  {result['question']}")
            for opt in result["options"]:
                print(f"   - {opt}")

        print("-" * 60)