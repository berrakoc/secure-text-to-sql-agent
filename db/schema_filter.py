import numpy as np
from openai import OpenAI
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect

load_dotenv()
client = OpenAI()

engine = create_engine("sqlite:///data/chinook.db")
inspector = inspect(engine)


def get_table_descriptions():
    """Build a short text description for each table: its name + column names.
    This is what we embed to compare against the user's question."""
    descriptions = {}
    for table in inspector.get_table_names():
        cols = [col["name"] for col in inspector.get_columns(table)]
        # e.g. "Table Invoice with columns: InvoiceId, CustomerId, Total, ..."
        descriptions[table] = f"Table {table} with columns: {', '.join(cols)}"
    return descriptions


def embed_text(text):
    """Turn a piece of text into a vector using OpenAI embeddings."""
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )
    return np.array(response.data[0].embedding)


def cosine_similarity(a, b):
    """Measure how similar two vectors are (1 = identical direction, 0 = unrelated)."""
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


# Pre-compute embeddings for all table descriptions once at import time.
# (In a real app you would cache these to disk instead of recomputing.)
TABLE_DESCRIPTIONS = get_table_descriptions()
TABLE_EMBEDDINGS = {
    table: embed_text(desc) for table, desc in TABLE_DESCRIPTIONS.items()
}


def get_relevant_tables(question, top_n=4, debug=False):
    """Return the top_n table names most relevant to the question,
    ranked by cosine similarity between the question and each table."""
    question_vec = embed_text(question)

    # Score every table against the question
    scores = {}
    for table, table_vec in TABLE_EMBEDDINGS.items():
        scores[table] = cosine_similarity(question_vec, table_vec)

    # Sort tables by score, highest first
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    # Print scores so we can see what the filter is doing
    # Optional debug output (off by default so the API stays quiet)
    if debug:
        print("Table relevance scores:")
        for table, score in ranked:
            print(f"  {table}: {score:.3f}")

    # Return just the top_n table names
    return [table for table, score in ranked[:top_n]]


# Quick test
if __name__ == "__main__":
    q = "What is the total revenue from customers in the USA?"
    print(f"QUESTION: {q}\n")
    relevant = get_relevant_tables(q)
    print(f"\nSelected tables: {relevant}")