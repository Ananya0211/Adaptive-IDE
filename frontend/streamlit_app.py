import streamlit as st
import requests

API_BASE = "http://localhost:5000"

def safe_json(resp):
    try:
        return resp.json()
    except ValueError:
        return {"error": f"Backend returned a non-JSON response (status {resp.status_code}): {resp.text[:200]}"}

st.set_page_config(page_title="Adaptive Proficiency Quiz", layout="centered")
st.title("Adaptive Programming Proficiency Quiz")

defaults = {
    "session_id": None,
    "question": None,
    "question_number": 0,
    "finished": False,
    "result": None,
    "last_feedback": None,
    "subject": None,
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val


def reset():
    for key in list(st.session_state.keys()):
        del st.session_state[key]


# ---------- Screen 1: subject selection ----------
if st.session_state.session_id is None and not st.session_state.finished:
    subject = st.selectbox("Choose a subject", ["Python", "C"])
    if st.button("Start Quiz"):
        resp = requests.post(f"{API_BASE}/start_quiz", json={"subject": subject})
        if resp.ok:
            data = safe_json(resp)
            st.session_state.session_id = data["session_id"]
            st.session_state.question = data["question"]
            st.session_state.question_number = data["question_number"]
            st.session_state.subject = subject
            st.rerun()
        else:
            st.error(safe_json(resp).get("error", "Failed to start quiz"))

# ---------- Screen 2: feedback after an answer, before next question ----------
elif st.session_state.last_feedback and not st.session_state.finished:
    fb = st.session_state.last_feedback
    if fb["correct"]:
        st.success("Correct! " + (fb.get("reasoning") or ""))
    else:
        st.error("Incorrect. " + (fb.get("reasoning") or ""))
        if fb.get("explanation"):
            st.info(fb["explanation"])
    if st.button("Next question"):
        st.session_state.last_feedback = None
        st.rerun()

# ---------- Screen 3: quiz in progress ----------
elif st.session_state.question and not st.session_state.finished:
    q = st.session_state.question
    st.subheader(f"Question {st.session_state.question_number}")
    if q.get("topic"):
        st.caption(f"Topic: {q['topic']}")
    st.write(q["question"])

    if q["type"] == "mcq" and q.get("options"):
        user_answer = st.radio(
            "Choose an answer", q["options"], key=f"mcq_{st.session_state.question_number}"
        )
    else:
        user_answer = st.text_area(
            "Your answer / code", key=f"code_{st.session_state.question_number}"
        )

    if st.button("Submit Answer"):
        resp = requests.post(
            f"{API_BASE}/submit_answer",
            json={"session_id": st.session_state.session_id, "user_answer": user_answer or ""},
        )
        if resp.ok:
            data = resp.json()
            st.session_state.last_feedback = {
                "correct": data["correct"],
                "reasoning": data.get("reasoning"),
                "explanation": data.get("explanation"),
            }
            if data["finished"]:
                st.session_state.finished = True
                st.session_state.result = data["level"]
            else:
                st.session_state.question = data["next_question"]
                st.session_state.question_number = data["question_number"]
            st.rerun()
        else:
            st.error(resp.json().get("error", "Failed to submit answer"))

# ---------- Screen 4: final result ----------
if st.session_state.finished and st.session_state.result:
    if st.session_state.last_feedback:
        fb = st.session_state.last_feedback
        if fb["correct"]:
            st.success("Correct! " + (fb.get("reasoning") or ""))
        else:
            st.error("Incorrect. " + (fb.get("reasoning") or ""))
            if fb.get("explanation"):
                st.info(fb["explanation"])

    st.divider()
    st.balloons()
    st.header(st.session_state.result["label"])
    st.write(f"Score: {st.session_state.result['score']} / 5")
    if st.button("Restart"):
        reset()
        st.rerun()