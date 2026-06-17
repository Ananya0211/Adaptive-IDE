# Adaptive Programming Proficiency Quiz

A minimal, working proof-of-concept for an adaptive assessment engine that
places a student into one of two proficiency levels — **Level 1
(Foundational)** or **Level 2 (Applied)** — based on a short, dynamically
generated quiz. This is iteration 1 of a larger adaptive IDE project: it
only covers the entry-point assessment, not the IDE itself.

No question bank, no static content file. Every question, evaluation, and
explanation is generated on the fly via an LLM API call.

## How it works

1. User picks a subject: **Python** or **C**.
2. The backend asks the API for a question at a medium starting difficulty.
3. User answers (MCQ or short code snippet).
4. The backend sends the answer to the API for evaluation.
   - Correct → next question is **harder**.
   - Incorrect → API generates an **explanation**, shown to the user, then
     the next question is **same-or-easier**.
5. This repeats for a fixed number of questions (currently 6).
6. At the end, a simple rule-based scoring function (weighted by difficulty
   of correctly-answered questions) assigns a final level, shown to the user.

## Architecture
adaptive_quiz/
├── requirements.txt
├── backend/
│   ├── api_layer.py        # the only 3 API call types: generate_question, evaluate_answer, generate_explanation
│   ├── quiz_controller.py  # session state, adaptive difficulty, rule-based level decision (subject-agnostic)
│   └── app.py               # Flask routes: /start_quiz, /submit_answer
└── frontend/
    └── streamlit_app.py     # thin UI, calls the Flask API only

Subject is just a string parameter passed through every layer. None of the
quiz/level logic is subject-specific, so adding a new subject (or a
non-programming one later, e.g. OS/CN) requires no changes outside the
prompts in `api_layer.py`.

Sessions are kept in memory on the backend (a Python dict, keyed by a UUID)
— no database, no persistent accounts, by design for this iteration.

## Prerequisites

- Python 3.10+
- A Gemini API key (free tier, no credit card required) from
  [aistudio.google.com](https://aistudio.google.com) → "Get API key"

> The API layer can also be swapped to use other API instead — only
> `backend/api_layer.py` would need to change; the function signatures
> (`generate_question`, `evaluate_answer`, `generate_explanation`) and
> everything else stays the same either way.

## Setup

```bash
cd adaptive_quiz
pip install -r requirements.txt
```

Set your API key for the current terminal session:

**PowerShell (Windows)**
```powershell
$env:GEMINI_API_KEY="your-key-here"
```

**macOS / Linux**
```bash
export GEMINI_API_KEY="your-key-here"
```

This only persists for the terminal session it's set in — set it again if
you close the window, and set it in whichever terminal will run the backend
(the frontend doesn't need it).

## Running

Two terminals, run from inside `adaptive_quiz/`:

**Terminal 1 — backend**
```bash
cd backend
python app.py
```
Runs on `http://localhost:5000`.

**Terminal 2 — frontend**
```bash
cd frontend
streamlit run streamlit_app.py
```
Opens the quiz UI in your browser.

## Configuration knobs

In `backend/quiz_controller.py`:

| Constant          | Default | Meaning                              |
|--------------------|---------|---------------------------------------|
| `MAX_QUESTIONS`     | 6       | Total questions per quiz session     |
| `START_DIFFICULTY`  | 3       | Starting difficulty (1–5 scale)      |
| `MIN_DIFFICULTY`    | 1       | Floor for difficulty adjustment      |
| `MAX_DIFFICULTY`    | 5       | Ceiling for difficulty adjustment    |

Level decision threshold (`final_score >= 3` → Level 2) is in
`compute_level()` in the same file.

## Troubleshooting

- **`invalid x-api-key` / 401 errors**: the API key isn't being read
  correctly, or wasn't set in the same terminal you ran `python app.py`
  from. Run `echo $env:GEMINI_API_KEY` (PowerShell) to confirm it's set.
- **`JSONDecodeError` on the Streamlit side**: usually a symptom of the
  backend returning an HTML error page instead of JSON (e.g. an unhandled
  exception). Check the backend terminal for the actual traceback — that's
  the real error.
- **Ctrl+C not stopping the Streamlit terminal**: a known Windows quirk —
  press Ctrl+C twice, or just close the terminal window.

## Known limitations (intentional, for this iteration)

- Two levels only — no finer granularity.
- In-memory sessions only — restarting the backend wipes all active quizzes.
- No persistent user accounts or history across sessions.
- No automated tests yet.