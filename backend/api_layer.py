"""
API integration layer -- now backed by Google's Gemini API (free tier),
instead of Anthropic's API.

Exactly three call types, as required by the spec:
  - generate_question(subject, difficulty, history)
  - evaluate_answer(subject, question, user_answer)
  - generate_explanation(subject, question, user_answer)

Subject is just a string parameter ("Python", "C", ...). Nothing about any
particular subject is hardcoded here.

Requires: GEMINI_API_KEY environment variable.
"""

import json
import os
from pathlib import Path

import requests

DEFAULT_MODEL = "gemini-2.5-flash"


def _load_dotenv_value(key_name):
    """Load a single KEY=VALUE pair from a local .env file if present."""
    start_dir = Path(__file__).resolve().parent
    for directory in (start_dir, start_dir.parent):
        env_path = directory / ".env"
        if not env_path.exists():
            continue

        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            if name.strip() != key_name:
                continue
            value = value.strip().strip('"').strip("'")
            return value
    return None


def _get_api_key():
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        api_key = _load_dotenv_value("GEMINI_API_KEY") or _load_dotenv_value("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Missing Gemini API key. Set GEMINI_API_KEY in your environment or add it to a repo-root .env file."
        )
    return api_key


def _get_model():
    model = os.environ.get("GEMINI_MODEL") or _load_dotenv_value("GEMINI_MODEL")
    return model or DEFAULT_MODEL


def _call(system_prompt, user_prompt):
    api_key = _get_api_key()
    model = _get_model()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    body = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"parts": [{"text": user_prompt}]}],
        "generationConfig": {"response_mime_type": "application/json"},
    }
    resp = requests.post(url, json=body, timeout=30)
    if not resp.ok:
        raise RuntimeError(f"Gemini API error {resp.status_code}: {resp.text[:300]}")

    data = resp.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(text)


def generate_question(subject, difficulty, history):
    history_summary = "\n".join(
        f"- (difficulty {h['difficulty']}, topic: {h.get('topic', 'n/a')}): "
        f"{'answered correctly' if h['correct'] else 'answered incorrectly'}"
        for h in history
    ) or "No questions asked yet."

    system_prompt = (
        "You are a question generator for a programming proficiency assessment tool. "
        "Generate exactly ONE question for the given subject and difficulty. "
        "Difficulty is 1-5: 1 = absolute beginner (syntax, variables, print), "
        "3 = working knowledge (loops, functions, basic data structures), "
        "5 = advanced applied knowledge (pointers/memory in C, decorators/generators "
        "in Python, debugging non-obvious bugs, algorithmic reasoning). "
        "Pick whichever of 'mcq' or 'code' best tests that difficulty level, and avoid "
        "topics already covered in the history given to you. "
        "Respond with ONLY a single JSON object in this exact shape:\n"
        '{"type": "mcq" or "code", "question": "...", '
        '"options": ["...", "...", "...", "..."] (omit/empty for type=code), '
        '"correct_answer": "...", "topic": "short topic label"}'
    )
    user_prompt = (
        f"Subject: {subject}\n"
        f"Target difficulty: {difficulty} (1=easiest, 5=hardest)\n"
        f"History so far:\n{history_summary}\n\n"
        "Generate the next question now."
    )
    return _call(system_prompt, user_prompt)


def evaluate_answer(subject, question, user_answer):
    system_prompt = (
        "You are an answer evaluator for a programming proficiency assessment. "
        "Judge correctness. For MCQ, match on meaning, not exact casing/wording. "
        "For code questions, judge logic/output, not formatting. "
        "Respond with ONLY a single JSON object in this exact shape:\n"
        '{"correct": true or false, "reasoning": "one short sentence"}'
    )
    user_prompt = (
        f"Subject: {subject}\n"
        f"Question type: {question.get('type')}\n"
        f"Question: {question.get('question')}\n"
        f"Options (if any): {question.get('options')}\n"
        f"Correct answer / expected behavior: {question.get('correct_answer')}\n"
        f"Student's answer: {user_answer}\n\n"
        "Evaluate now."
    )
    return _call(system_prompt, user_prompt)


def generate_explanation(subject, question, user_answer):
    system_prompt = (
        "You are a patient programming tutor. The student answered a question "
        "incorrectly. In 3-5 short sentences, explain why their answer was wrong and "
        "what the correct reasoning/answer is. Be concise, concrete, and encouraging. "
        "Respond with ONLY a single JSON object in this exact shape:\n"
        '{"explanation": "..."}'
    )
    user_prompt = (
        f"Subject: {subject}\n"
        f"Question: {question.get('question')}\n"
        f"Options (if any): {question.get('options')}\n"
        f"Correct answer / expected behavior: {question.get('correct_answer')}\n"
        f"Student's (incorrect) answer: {user_answer}\n\n"
        "Explain now."
    )
    return _call(system_prompt, user_prompt)