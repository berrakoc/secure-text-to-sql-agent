from openai import OpenAI
from dotenv import load_dotenv
from schema import build_schema_text

# Load API key from .env
load_dotenv()
client = OpenAI()

# Build the schema text once (reused for every question)
SCHEMA_TEXT = build_schema_text()


def generate_sql(question):
    """Take a natural language question and return a SQL query as text."""

    # The system prompt tells the model its role and gives it the schema
    system_prompt = f"""You are an expert SQL assistant for a SQLite database.
Given a question, write a single valid SQLite SQL query that answers it.

Rules:
- Only use tables and columns that exist in the schema below.
- Return ONLY the SQL query, no explanation, no markdown code fences.
- Use the foreign key hints (-- ... refers to ...) to write correct JOINs.

Database schema:
{SCHEMA_TEXT}
"""

    # Send the question to the model
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ],
        temperature=0,  # deterministic output for SQL
    )

    return response.choices[0].message.content.strip()


# Quick test with a few questions
if __name__ == "__main__":
    questions = [
        "How many customers are there?",
        "List the top 5 artists with the most albums.",
        "What is the total revenue from invoices in the USA?",
    ]

    for q in questions:
        print(f"QUESTION: {q}")
        print(generate_sql(q))
        print("-" * 60)