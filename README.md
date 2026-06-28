# Adaptive IDE

A working proof-of-concept for an adaptive programming assessment engine. It
places a student into one of two proficiency levels, **Level 1
(Foundational)** or **Level 2 (Applied)**, using a short quiz generated and
graded through a Groq-hosted LLM.

This is iteration 1 of a larger adaptive IDE project. It covers the entry
assessment only, not the IDE itself.

There is no question bank and no static content file. Questions, answer
evaluation, explanations, and clues are generated on demand through the API.

## Features

- Supports **Python** and **C** assessments.
- Generates 6 questions per session: 4 MCQs followed by 2 coding questions.
- Adapts difficulty after each answer on a 1-5 scale.
- Offers two quiz modes:
  - **Adaptive mixed topics**: questions can move across topics.
  - **Same broad topic**: all questions stay within a selected topic.
- Provides a clue on request without revealing the final answer.
- Shows explanations for incorrect answers.
- For incorrect coding answers, shows the expected answer and a line-level diff.
- Computes final proficiency with a simple rule-based score.

## How It Works

1. The user selects a subject: **Python** or **C**.
2. The user chooses adaptive mixed topics or a fixed broad topic.
3. The backend asks Groq for a question at the starting difficulty.
4. The user answers an MCQ or writes a short code snippet.
5. The backend sends the answer to Groq for evaluation.
   - Correct answers increase the next question's difficulty.
   - Incorrect answers decrease the next question's difficulty and trigger an
     explanation.
6. After 6 questions, the backend computes a weighted score and returns the
   final level.

## Architecture

```text
adaptive_quiz/
|-- requirements.txt
|-- backend/
|   |-- api_layer.py        # Groq calls, prompts, .env loading
|   |-- quiz_controller.py  # session state, difficulty, scoring
|   `-- app.py              # Flask routes
`-- frontend/
    `-- streamlit_app.py    # Streamlit UI, calls the Flask API
```

- `backend/api_layer.py` owns all Groq API calls and prompt logic.
- `backend/quiz_controller.py` owns in-memory sessions, question ordering,
  difficulty changes, clue handling, and final scoring.
- `backend/app.py` exposes the HTTP endpoints used by the frontend.
- `frontend/streamlit_app.py` renders the Streamlit interface.

Subject is passed through each layer as a string. The controller is
subject-agnostic, so adding another subject mainly requires prompt tuning and
route/UI validation updates.

Sessions are stored in memory in a Python dictionary keyed by UUID. Restarting
the backend clears active sessions.

## Prerequisites

- Python 3.10+
- A Groq API key from [console.groq.com](https://console.groq.com)

## Setup

From the project root:

```bash
pip install -r requirements.txt
```

Set your Groq API key in one of these ways.

### Option 1: Environment Variable

PowerShell:

```powershell
$env:GROQ_API_KEY="your-key-here"
```

macOS / Linux:

```bash
export GROQ_API_KEY="your-key-here"
```

This only lasts for the current terminal session. Set it in the terminal that
runs the backend.

### Option 2: `.env` File

Create a `.env` file in either the project root or the `backend/` directory:

```text
GROQ_API_KEY=your-key-here
```

Optionally choose a Groq model:

```text
GROQ_MODEL=llama-3.3-70b-versatile
```

If `GROQ_MODEL` is not set, the backend uses
`llama-3.3-70b-versatile`.

## Running

Open two terminals from the project root.

Terminal 1: backend

```bash
cd backend
python app.py
```

The Flask API runs on `http://localhost:5000`.

Terminal 2: frontend

```bash
cd frontend
streamlit run streamlit_app.py
```

Streamlit opens the quiz UI in your browser.

## API Endpoints

### `POST /start_quiz`

Starts a new quiz session.

```json
{
  "subject": "Python",
  "topic_mode": "adaptive",
  "fixed_topic": null
}
```

Use `"topic_mode": "same_topic"` with a `fixed_topic` value to keep the whole
quiz within one broad topic.

### `POST /submit_answer`

Submits the current answer for evaluation.

```json
{
  "session_id": "session-uuid",
  "user_answer": "selected option or code"
}
```

### `POST /get_clue`

Requests a clue for the current question.

```json
{
  "session_id": "session-uuid"
}
```

## Configuration Knobs

In `backend/quiz_controller.py`:

| Constant | Default | Meaning |
| --- | ---: | --- |
| `MAX_QUESTIONS` | 6 | Total questions per quiz session |
| `START_DIFFICULTY` | 3 | Starting difficulty on the 1-5 scale |
| `MIN_DIFFICULTY` | 1 | Lowest possible difficulty |
| `MAX_DIFFICULTY` | 5 | Highest possible difficulty |
| `QUESTION_SEQUENCE` | 4 MCQ + 2 code | Question type order |

The final level threshold is in `compute_level()`. Currently, a final score of
`3` or higher maps to **Level 2 (Applied)**; lower scores map to **Level 1
(Foundational)**.

## Troubleshooting

- **Missing API key**: set `GROQ_API_KEY` in the backend terminal or add it to
  a local `.env` file.
- **401 / rejected key**: make sure the key is a Groq key from
  `console.groq.com`, not a key from another provider.
- **Streamlit shows a non-JSON or `JSONDecodeError` message**: the backend
  likely returned an error page. Check the Flask terminal for the traceback.
- **The code editor is missing**: confirm `streamlit-ace` installed from
  `requirements.txt`. The app falls back to a regular text area if it is not
  available.
- **Ctrl+C does not stop Streamlit on Windows**: press Ctrl+C twice or close the
  terminal window.

## Known Limitations

- Only two levels are reported.
- Sessions are in memory only.
- There are no persistent users, accounts, or quiz history.
- The app depends on LLM output quality and availability.
- There are no automated tests yet.
