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