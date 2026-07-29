import requests
import streamlit as st

# The base URL of our FastAPI service
API_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="Text-to-SQL", page_icon="🗄️", layout="wide")
st.title("🗄️ Text-to-SQL Assistant")
st.caption("Ask a question in plain English — get safe, verified SQL.")

# Text input for the user's question
question = st.text_input(
    "Your question",
    placeholder="e.g. How many customers are there?",
)

# When the user clicks the button, call the API
if st.button("Ask", type="primary") and question:
    with st.spinner("Thinking..."):
        try:
            response = requests.post(
                f"{API_URL}/query",
                json={"question": question},
                timeout=60,
            )
            result = response.json()
        except Exception as e:
            st.error(f"Could not reach the API: {e}")
            st.stop()

    status = result.get("status")

    # Case 1: the question was ambiguous -> show clarification options
    if status == "clarification":
        st.warning("This question is ambiguous — please clarify:")
        st.write(f"**{result['question']}**")
        for opt in result["options"]:
            st.write(f"- {opt}")

    # Case 2: the query was blocked by the safety layer
    elif status == "blocked":
        st.error(f"Query blocked by safety guardrails: {result['reason']}")

    # Case 3: something went wrong
    elif status == "error":
        st.error(f"Error: {result['reason']}")

    # Case 4: success -> show SQL, confidence, and results
    elif status == "success":
        # Show the generated SQL with syntax highlighting
        st.subheader("Generated SQL")
        st.code(result["sql"], language="sql")

        # Show the confidence score and its breakdown
        confidence = result["confidence"]
        st.subheader(f"Confidence: {confidence:.0%}")
        st.json(result["confidence_breakdown"])

        # Show the natural language explanation
        st.write("**Explanation:**", result["explanation"])

        # Show the results as a table
        st.subheader(f"Results ({result['row_count']} rows)")
        if result["rows"]:
            st.dataframe(
                data=result["rows"],
                use_container_width=True,
                column_config={
                    str(i): col for i, col in enumerate(result["columns"])
                },
            )
        else:
            st.info("No rows returned.")

        # Show any sanity flags as warnings
        if result.get("sanity_flags"):
            for flag in result["sanity_flags"]:
                st.warning(flag)