import html
import difflib

import streamlit as st
import streamlit.components.v1 as components
import requests

try:
    from streamlit_ace import st_ace  # type: ignore[reportMissingImports]
    HAS_ACE = True
except Exception:
    st_ace = None
    HAS_ACE = False

API_BASE = "http://localhost:5000"

def safe_json(resp):
    try:
        return resp.json()
    except ValueError:
        return {"error": f"Backend returned a non-JSON response (status {resp.status_code}): {resp.text[:200]}"}

st.set_page_config(page_title="Adaptive Proficiency Quiz", layout="wide")
st.title("Adaptive Programming Proficiency Quiz")

st.markdown(
    """
    <style>
    .block-container {
        max-width: 1100px;
        padding-top: 1.5rem;
    }

    .question-card {
        user-select: none;
        -webkit-user-select: none;
        -ms-user-select: none;
        line-height: 1.7;
        font-size: 1.05rem;
        margin-bottom: 0.5rem;
    }

    textarea {
        min-height: 320px !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

components.html(
        """
        <script>
        (function () {
            function blockClipboard(el) {
                if (!el || el.dataset.guardBound === '1') {
                    return;
                }
                el.dataset.guardBound = '1';
                el.addEventListener('paste', (event) => event.preventDefault());
                el.addEventListener('copy', (event) => event.preventDefault());
                el.addEventListener('cut', (event) => event.preventDefault());
                el.addEventListener('contextmenu', (event) => event.preventDefault());
            }

            function applyGuards() {
                try {
                    const parentDoc = window.parent.document;
                    parentDoc.querySelectorAll('.question-card').forEach((el) => {
                        el.style.userSelect = 'none';
                        el.style.webkitUserSelect = 'none';
                        el.oncopy = () => false;
                        el.oncut = () => false;
                        el.oncontextmenu = () => false;
                    });

                    parentDoc
                        .querySelectorAll('textarea, .ace_editor, .ace_text-input')
                        .forEach(blockClipboard);

                    parentDoc.querySelectorAll('iframe').forEach((frame) => {
                        try {
                            const frameDoc = frame.contentDocument || frame.contentWindow.document;
                            frameDoc
                                .querySelectorAll('textarea, .ace_editor, .ace_text-input')
                                .forEach(blockClipboard);
                            if (frame.contentWindow && frame.contentWindow.ace) {
                                Object.values(frame.contentWindow.ace.editors || {}).forEach((editor) => {
                                    editor.commands.removeCommand('paste');
                                });
                            }
                        } catch (error) {
                            // Some frames may not be inspectable; guard the ones the browser allows.
                        }
                    });
                } catch (error) {
                    // Best effort only: if the browser blocks parent access, the app still works.
                }
            }

            applyGuards();
            setInterval(applyGuards, 1000);
        })();
        </script>
        """,
        height=0,
)

defaults = {
    "session_id": None,
    "question": None,
    "question_number": 0,
    "finished": False,
    "result": None,
    "last_feedback": None,
    "subject": None,
    "topic_mode": "adaptive",
    "fixed_topic": None,
    "current_clue": None,
    "last_code_review": None,
    "history": [],
    "pending_final_result": None,
    "pending_final_history": None,
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val


def reset():
    for key in list(st.session_state.keys()):
        del st.session_state[key]


def format_change_lines(submitted_answer, expected_answer):
    diff_lines = difflib.unified_diff(
        (submitted_answer or "").splitlines(),
        (expected_answer or "").splitlines(),
        lineterm="",
    )
    change_lines = []
    for line in diff_lines:
        if line.startswith(("---", "+++", "@@")):
            continue
        if line.startswith("-"):
            change_lines.append(line)
        elif line.startswith("+"):
            change_lines.append(line)
    return "\n".join(change_lines) if change_lines else "No line-level differences detected."


# ---------- Screen 1: subject selection ----------
if st.session_state.session_id is None and not st.session_state.finished:
    subject = st.selectbox("Choose a subject", ["Python", "C"])
    topic_mode = st.radio(
        "Assessment mode",
        options=["Adaptive mixed topics", "Same broad topic"],
        horizontal=True,
    )
    fixed_topic = None
    if topic_mode == "Same broad topic":
        broad_topics = [
            "Basics and Syntax",
            "Control Flow and Functions",
            "Data Structures",
            "Problem Solving and Debugging",
        ]
        fixed_topic = st.selectbox("Choose a topic", broad_topics)

    if st.button("Start Quiz"):
        payload = {
            "subject": subject,
            "topic_mode": "same_topic" if topic_mode == "Same broad topic" else "adaptive",
            "fixed_topic": fixed_topic,
        }
        resp = requests.post(f"{API_BASE}/start_quiz", json=payload)
        if resp.ok:
            data = safe_json(resp)
            st.session_state.session_id = data["session_id"]
            st.session_state.question = data["question"]
            st.session_state.question_number = data["question_number"]
            st.session_state.subject = subject
            st.session_state.topic_mode = payload["topic_mode"]
            st.session_state.fixed_topic = fixed_topic
            st.session_state.current_clue = None
            st.session_state.last_code_review = None
            st.session_state.history = []
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

    if st.session_state.last_code_review:
        cr = st.session_state.last_code_review
        st.markdown("### Code changes suggested")
        st.caption("Correct answer for this coding question")
        if cr.get("correct_answer"):
            st.code(cr["correct_answer"], language=cr.get("language", "text"))
        if cr.get("diff"):
            st.caption("Difference between your submitted code and the expected approach")
            st.code(cr["diff"], language=cr.get("language", "text"))

    next_label = "View final result" if st.session_state.pending_final_result else "Next question"
    if st.button(next_label):
        st.session_state.last_feedback = None
        st.session_state.current_clue = None
        st.session_state.last_code_review = None
        if st.session_state.pending_final_result:
            st.session_state.finished = True
            st.session_state.result = st.session_state.pending_final_result
            st.session_state.history = st.session_state.pending_final_history or []
            st.session_state.pending_final_result = None
            st.session_state.pending_final_history = None
        st.rerun()

# ---------- Screen 3: quiz in progress ----------
elif st.session_state.question and not st.session_state.finished:
    q = st.session_state.question
    st.subheader(f"Question {st.session_state.question_number}")
    if q.get("topic"):
        st.caption(f"Topic: {q['topic']}")
    if st.session_state.topic_mode == "same_topic" and st.session_state.fixed_topic:
        st.caption(f"Quiz mode: Same broad topic ({st.session_state.fixed_topic})")
    st.markdown(f'<div class="question-card">{html.escape(q["question"] or "")}</div>', unsafe_allow_html=True)

    if st.button("Need a clue?"):
        clue_resp = requests.post(
            f"{API_BASE}/get_clue",
            json={"session_id": st.session_state.session_id},
        )
        if clue_resp.ok:
            st.session_state.current_clue = safe_json(clue_resp).get("clue")
            st.rerun()
        else:
            st.error(safe_json(clue_resp).get("error", "Could not fetch clue"))

    if st.session_state.current_clue:
        st.info(f"Clue: {st.session_state.current_clue}")

    if q["type"] == "mcq" and q.get("options"):
        user_answer = st.radio(
            "Choose an answer",
            q["options"],
            index=None,
            key=f"mcq_{st.session_state.question_number}",
        )
    else:
        code_key = f"code_{st.session_state.question_number}"
        code_lang = "python" if st.session_state.subject == "Python" else "c_cpp"
        if HAS_ACE:
            st.caption("Code editor supports tab-based indentation.")
            user_answer = st_ace(
                value=st.session_state.get(code_key, ""),
                language=code_lang,
                theme="github",
                key=f"ace_{code_key}",
                height=320,
                tab_size=4,
                show_gutter=True,
                wrap=True,
                auto_update=True,
            ) or ""
            st.session_state[code_key] = user_answer
        else:
            st.caption("Install streamlit-ace for a richer indented editor. Using textarea fallback.")
            user_answer = st.text_area(
                "Your answer / code",
                key=code_key,
                height=320,
            )

    if st.button("Submit Answer"):
        if q["type"] == "mcq" and user_answer is None:
            st.warning("Please choose an answer before submitting.")
            st.stop()

        resp = requests.post(
            f"{API_BASE}/submit_answer",
            json={"session_id": st.session_state.session_id, "user_answer": user_answer or ""},
        )
        if resp.ok:
            data = safe_json(resp)
            st.session_state.last_feedback = {
                "correct": data["correct"],
                "reasoning": data.get("reasoning"),
                "explanation": data.get("explanation"),
            }
            st.session_state.current_clue = None
            st.session_state.last_code_review = None

            if (
                data.get("question_type") == "code"
                and data.get("expected_answer")
                and not data.get("correct")
            ):
                diff_text = format_change_lines(
                    data.get("submitted_answer"),
                    data.get("expected_answer"),
                )
                st.session_state.last_code_review = {
                    "correct_answer": data.get("expected_answer") or "",
                    "diff": diff_text,
                    "language": "python" if st.session_state.subject == "Python" else "c",
                }

            if data["finished"]:
                st.session_state.pending_final_result = data.get("level")
                st.session_state.pending_final_history = data.get("history", [])
            else:
                st.session_state.question = data["next_question"]
                st.session_state.question_number = data["question_number"]
            st.rerun()
        else:
            st.error(safe_json(resp).get("error", "Failed to submit answer"))

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
    st.write(
        f"Correct answers: {st.session_state.result.get('correct_count', 0)} / "
        f"{st.session_state.result.get('total_questions', 0)}"
    )
    st.write(f"Accuracy: {st.session_state.result.get('accuracy', 0)}%")
    st.write(
        "Recent difficulty average: "
        f"{st.session_state.result.get('recent_avg_difficulty', 0)}"
    )

    topic_breakdown = st.session_state.result.get("topic_breakdown", {})
    if topic_breakdown:
        st.markdown("### Topic-wise scoring")
        for topic, stats in topic_breakdown.items():
            attempted = stats.get("attempted", 0)
            correct = stats.get("correct", 0)
            pct = (correct / attempted) * 100 if attempted else 0
            st.write(f"{topic}: {correct}/{attempted} ({pct:.0f}%)")

    if st.button("Restart"):
        reset()
        st.rerun()
