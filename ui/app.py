import requests
import streamlit as st

API_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="Text-to-SQL", page_icon="🗄️", layout="wide")
st.title("🗄️ Text-to-SQL Assistant")
st.caption("Ask a question in plain English — get safe, verified SQL.")

question = st.text_input(
    "Your question",
    placeholder="e.g. How many customers are there?",
)

# When the user asks, call the API and remember the result in session state.
# Streamlit reruns the whole script on every click, so we store the result
# so it survives across reruns (e.g. when clicking a feedback button).
if st.button("Ask", type="primary") and question:
    with st.spinner("Thinking..."):
        try:
            response = requests.post(
                f"{API_URL}/query",
                json={"question": question},
                timeout=60,
            )
            st.session_state.result = response.json()
            st.session_state.asked_question = question
        except Exception as e:
            st.error(f"Could not reach the API: {e}")
            st.stop()

# Render whatever result is currently stored (if any).
if "result" in st.session_state:
    result = st.session_state.result
    status = result.get("status")

    if status == "clarification":
        st.warning("This question is ambiguous — please clarify:")
        st.write(f"**{result['question']}**")
        for opt in result["options"]:
            st.write(f"- {opt}")

    elif status == "blocked":
        st.error(f"Query blocked by safety guardrails: {result['reason']}")

    elif status == "error":
        st.error(f"Error: {result['reason']}")

    elif status == "success":
        st.subheader("Generated SQL")
        st.code(result["sql"], language="sql")

        st.subheader(f"Confidence: {result['confidence']:.0%}")
        st.json(result["confidence_breakdown"])

        st.write("**Explanation:**", result["explanation"])

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

        if result.get("sanity_flags"):
            for flag in result["sanity_flags"]:
                st.warning(flag)

        # --- Feedback buttons (the flywheel) ---
        st.divider()
        st.write("Was this result correct?")
        col1, col2 = st.columns(2)

        def send_feedback(is_correct):
            """Send the user's thumbs up/down to the API."""
            try:
                requests.post(
                    f"{API_URL}/feedback",
                    json={
                        "question": st.session_state.asked_question,
                        "sql": result["sql"],
                        "is_correct": is_correct,
                    },
                    timeout=10,
                )
                st.success("Thanks! Your feedback was recorded.")
            except Exception as e:
                st.error(f"Could not send feedback: {e}")

        with col1:
            if st.button("👍 Correct"):
                send_feedback(True)
        with col2:
            if st.button("👎 Incorrect"):
                send_feedback(False)