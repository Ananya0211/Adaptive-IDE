"""
Quiz controller: subject-agnostic. Subject is just a string passed through to
the API layer -- no subject-specific branching lives here, so adding a new
subject (or a non-programming one later, e.g. OS/CN) requires no changes to
this file.

Holds in-memory session state (no DB needed for this iteration), drives the
adaptive difficulty loop, and runs the rule-based level-decision logic.
"""

import uuid

from api_layer import generate_question, evaluate_answer, generate_explanation

MAX_QUESTIONS = 6
START_DIFFICULTY = 3
MIN_DIFFICULTY = 1
MAX_DIFFICULTY = 5

# session_id -> session state dict
_sessions = {}


def start_quiz(subject):
    session_id = str(uuid.uuid4())
    question = generate_question(subject, START_DIFFICULTY, [])
    _sessions[session_id] = {
        "subject": subject,
        "difficulty": START_DIFFICULTY,
        "history": [],
        "current_question": question,
        "question_count": 1,
        "finished": False,
    }
    return session_id, _public_question(question)


def _public_question(question):
    """Strip the correct_answer field before sending to the client."""
    return {
        "type": question.get("type"),
        "question": question.get("question"),
        "options": question.get("options", []),
        "topic": question.get("topic"),
    }


def submit_answer(session_id, user_answer):
    session = _sessions.get(session_id)
    if session is None:
        raise ValueError("Invalid or expired session_id")
    if session["finished"]:
        raise ValueError("Quiz already finished for this session")

    subject = session["subject"]
    question = session["current_question"]
    difficulty = session["difficulty"]

    evaluation = evaluate_answer(subject, question, user_answer)
    is_correct = bool(evaluation.get("correct"))

    explanation_text = None
    if not is_correct:
        explanation = generate_explanation(subject, question, user_answer)
        explanation_text = explanation.get("explanation")

    session["history"].append({
        "question": question.get("question"),
        "difficulty": difficulty,
        "correct": is_correct,
        "topic": question.get("topic"),
    })

    # Adaptive difficulty rule: correct -> harder, incorrect -> same-or-easier.
    next_difficulty = (
        min(MAX_DIFFICULTY, difficulty + 1) if is_correct
        else max(MIN_DIFFICULTY, difficulty - 1)
    )

    result = {
        "correct": is_correct,
        "reasoning": evaluation.get("reasoning"),
        "explanation": explanation_text,
        "finished": False,
    }

    if session["question_count"] >= MAX_QUESTIONS:
        session["finished"] = True
        result["finished"] = True
        result["level"] = compute_level(session["history"])
        result["history"] = session["history"]
        return result

    next_question = generate_question(subject, next_difficulty, session["history"])
    session["difficulty"] = next_difficulty
    session["current_question"] = next_question
    session["question_count"] += 1

    result["next_question"] = _public_question(next_question)
    result["question_number"] = session["question_count"]
    return result


def compute_level(history):
    """
    Simple, rule-based, two-level scoring -- no ML model.

    - correct_weight: sum of difficulty over questions answered correctly
    - total_weight:   sum of difficulty over all attempted questions
    - ratio:          correct_weight / total_weight (how much "hard credit" was earned)
    - recent_avg_difficulty: average difficulty of the last 3 questions
      (rewards a student who climbed up the difficulty ladder, rather than
      being dragged down by the easy opening question)

    final_score is on a 1-5 scale; Level 2 (Applied) if final_score >= 3,
    otherwise Level 1 (Foundational).
    """
    if not history:
        return {"level": 1, "label": "Level 1 (Foundational)", "score": 0}

    total_weight = sum(h["difficulty"] for h in history)
    correct_weight = sum(h["difficulty"] for h in history if h["correct"])
    ratio = (correct_weight / total_weight) if total_weight else 0

    recent = history[-3:]
    recent_avg_difficulty = sum(h["difficulty"] for h in recent) / len(recent)

    final_score = 0.6 * (ratio * MAX_DIFFICULTY) + 0.4 * recent_avg_difficulty
    level = 2 if final_score >= 3 else 1
    label = "Level 2 (Applied)" if level == 2 else "Level 1 (Foundational)"

    return {"level": level, "label": label, "score": round(final_score, 2)}