from fastapi import FastAPI
from pydantic import BaseModel

from pipeline import answer_question
from db.schema import build_schema_text

# Create the FastAPI application
app = FastAPI(title="Text-to-SQL API")

# Simple in-memory history of past queries for this session.
# (Resets when the server restarts — fine for a demo. A real app
#  would store this in a database.)
HISTORY = []


class QueryRequest(BaseModel):
    question: str


@app.get("/")
def root():
    """Health-check endpoint to confirm the API is running."""
    return {"status": "ok", "message": "Text-to-SQL API is running"}


@app.post("/query")
def query(request: QueryRequest):
    """Accept a natural language question and return the full pipeline result."""
    result = answer_question(request.question)

    # Record this query in the session history
    HISTORY.append({
        "question": request.question,
        "status": result.get("status"),
        "sql": result.get("sql"),
        "confidence": result.get("confidence"),
    })

    return result


@app.get("/schema")
def schema():
    """Return the database schema (tables, columns, relationships)
    as the same CREATE TABLE style text the model sees."""
    return {"schema": build_schema_text()}


@app.get("/history")
def history():
    """Return the list of questions asked in this session, newest first."""
    return {"history": list(reversed(HISTORY))}