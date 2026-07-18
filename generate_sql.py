from openai import OpenAI
from dotenv import load_dotenv
from schema import build_schema_text
from schema_filter import get_relevant_tables  # NEW: table filtering

load_dotenv()
client = OpenAI()

# NOTE: No longer build one fixed schema. The schema is now built
# per question, using only the tables relevant to that question.

# Build the schema text once (reused for every question)
SCHEMA_TEXT = build_schema_text()

# Few-shot examples: question -> correct SQL, specific to the Chinook schema.
# These teach the model the expected style (JOINs, naming, LIMIT).
FEW_SHOT_EXAMPLES = [
    {
        "question": "How many tracks are there in total?",
        "sql": "SELECT COUNT(*) FROM Track;",
    },
    {
        "question": "List the top 5 artists with the most albums.",
        "sql": (
            "SELECT Artist.Name, COUNT(Album.AlbumId) AS AlbumCount\n"
            "FROM Artist\n"
            "JOIN Album ON Artist.ArtistId = Album.ArtistId\n"
            "GROUP BY Artist.ArtistId\n"
            "ORDER BY AlbumCount DESC\n"
            "LIMIT 5;"
        ),
    },
    {
        "question": "What is the total revenue from customers in the USA?",
        "sql": (
            "SELECT SUM(Invoice.Total) AS TotalRevenue\n"
            "FROM Invoice\n"
            "WHERE Invoice.BillingCountry = 'USA';"
        ),
    },
    {
        "question": "Which genre has the most tracks?",
        "sql": (
            "SELECT Genre.Name, COUNT(Track.TrackId) AS TrackCount\n"
            "FROM Genre\n"
            "JOIN Track ON Genre.GenreId = Track.GenreId\n"
            "GROUP BY Genre.GenreId\n"
            "ORDER BY TrackCount DESC\n"
            "LIMIT 1;"
        ),
    },
]


def build_messages(question):
    """Assemble the full message list: system prompt + few-shot examples
    + the user's actual question. The schema is filtered to relevant tables."""

    # Pick only the tables relevant to this question
    relevant_tables = get_relevant_tables(question, top_n=4)

    # Build schema text using just those tables
    schema_text = build_schema_text(only_tables=relevant_tables)

    system_prompt = f"""You are an expert SQL assistant for a SQLite database.
Given a question, write a single valid SQLite SQL query that answers it.

Rules:
- Only use tables and columns that exist in the schema below.
- Return ONLY the SQL query, no explanation, no markdown code fences.
- Use the foreign key hints (-- ... refers to ...) to write correct JOINs.
- Use the example values to match real values in the data.

Database schema:
{schema_text}
"""

    messages = [{"role": "system", "content": system_prompt}]

    for ex in FEW_SHOT_EXAMPLES:
        messages.append({"role": "user", "content": ex["question"]})
        messages.append({"role": "assistant", "content": ex["sql"]})

    messages.append({"role": "user", "content": question})

    return messages


def generate_sql(question):
    """Take a natural language question and return a SQL query as text."""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=build_messages(question),
        temperature=0,
    )
    return response.choices[0].message.content.strip()


# Quick test — including a harder question not covered by the examples
if __name__ == "__main__":
    questions = [
        "How many customers are there?",
        "Which 3 countries generate the most revenue?",
        "List the names of tracks longer than 5 minutes.",
    ]
    for q in questions:
        print(f"QUESTION: {q}")
        print(generate_sql(q))
        print("-" * 60)