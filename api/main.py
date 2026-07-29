from fastapi import FastAPI
from pydantic import BaseModel

from pipeline import answer_question

# Create the FastAPI application
app = FastAPI(title="Text-to-SQL API")


# Define the shape of an incoming request body using Pydantic.
# FastAPI uses this to validate input automatically.
class QueryRequest(BaseModel):
    question: str


@app.get("/")
def root():
    """A simple health-check endpoint to confirm the API is running."""
    return {"status": "ok", "message": "Text-to-SQL API is running"}


@app.post("/query")
def query(request: QueryRequest):
    """Accept a natural language question and return the full pipeline result:
    generated SQL, execution results, confidence score, or a clarification."""
    result = answer_question(request.question)
    return result