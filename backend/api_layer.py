"""
API integration layer -- now backed by Groq's OpenAI-compatible API.

Exactly three call types, as required by the spec:
  - generate_question(subject, difficulty, history)
  - evaluate_answer(subject, question, user_answer)
  - generate_explanation(subject, question, user_answer)

Subject is just a string parameter ("Python", "C", ...). Nothing about any
particular subject is hardcoded here.

Requires: GROQ_API_KEY environment variable.
"""

import json
import os
from pathlib import Path

import requests

DEFAULT_MODEL = "llama-3.3-70b-versatile"


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
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        api_key = _load_dotenv_value("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Missing Groq API key. Set GROQ_API_KEY in your environment or add it to a repo-root .env file."
        )
    return api_key


def _get_model():
    model = os.environ.get("GROQ_MODEL") or _load_dotenv_value("GROQ_MODEL")
    return model or DEFAULT_MODEL


def _build_avoid_text(avoid_questions):
    if not avoid_questions:
        return ""
    serialized = json.dumps(avoid_questions, ensure_ascii=False)
    return (
        "Do not repeat any question that matches one of these exact question texts: "
        f"{serialized}. "
    )


def _call(system_prompt, user_prompt):
    api_key = _get_api_key()
    model = _get_model()
    url = "https://api.groq.com/openai/v1/chat/completions"
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    resp = requests.post(url, json=body, headers={"Authorization": f"Bearer {api_key}"}, timeout=30)
    if not resp.ok:
        if resp.status_code == 401:
            raise RuntimeError(
                "Groq API key was rejected (401). Make sure GROQ_API_KEY is a Groq key from console.groq.com, not a Google/AI Studio key."
            )
        raise RuntimeError(f"Groq API error {resp.status_code}: {resp.text[:300]}")

    data = resp.json()
    text = data["choices"][0]["message"]["content"]
    return json.loads(text)


def generate_question(subject, difficulty, history, question_type=None, question_stage=None, avoid_questions=None):
    history_summary = "\n".join(
        f"- (difficulty {h['difficulty']}, topic: {h.get('topic', 'n/a')}): "
        f"{'answered correctly' if h['correct'] else 'answered incorrectly'}"
        for h in history
    ) or "No questions asked yet."

    type_instruction = (
        f"Generate exactly ONE {question_type} question. "
        if question_type in ("mcq", "code")
        else "Generate exactly ONE question. "
    )

    stage_instruction = ""
    if question_type == "code" and question_stage == "first":
        stage_instruction = (
            "This is the first coding question: keep it simple, answerable in a few lines, and avoid long boilerplate. "
        )
    elif question_type == "code" and question_stage == "second":
        stage_instruction = (
            "This is the second coding question: keep it short, but make it noticeably harder than the first coding question. "
        )

    avoid_instruction = _build_avoid_text(avoid_questions)

    system_prompt = (
        "You are a question generator for a programming proficiency assessment tool. "
        f"{type_instruction}"
        f"{stage_instruction}"
        f"{avoid_instruction}"
        "Difficulty is 1-5: 1 = absolute beginner (syntax, variables, print), "
        "3 = working knowledge (loops, functions, basic data structures), "
        "5 = advanced applied knowledge (pointers/memory in C, decorators/generators "
        "in Python, debugging non-obvious bugs, algorithmic reasoning). "
        "If a question type was provided, you must use that exact type and avoid "
        "changing it. Otherwise pick whichever of 'mcq' or 'code' best tests that difficulty level, and avoid "
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

    avoid_set = set(avoid_questions or [])
    last_error = None
    for attempt in range(3):
        question = _call(system_prompt, user_prompt)
        question_text = (question or {}).get("question")
        if question_text and question_text not in avoid_set:
            return question
        avoid_set.add(question_text)
        last_error = question_text
        system_prompt = (
            system_prompt
            + " The previous attempt repeated an already-used question, so generate a different one now."
        )

    raise RuntimeError(
        f"Groq kept returning a repeated question: {last_error or 'unknown question'}"
    )


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