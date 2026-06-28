"""
Quiz controller: subject-agnostic. Subject is just a string passed through to
the API layer -- no subject-specific branching lives here, so adding a new
subject (or a non-programming one later, e.g. OS/CN) requires no changes to
this file.

Holds in-memory session state (no DB needed for this iteration), drives the
adaptive difficulty loop, and runs the rule-based level-decision logic.
"""

import uuid

from api_layer import generate_question, evaluate_answer, generate_explanation, generate_clue

MAX_QUESTIONS = 6
START_DIFFICULTY = 3
MIN_DIFFICULTY = 1
MAX_DIFFICULTY = 5
QUESTION_SEQUENCE = [
    {"type": "mcq"},
    {"type": "mcq"},
    {"type": "mcq"},
    {"type": "mcq"},
    {"type": "code", "stage": "first", "max_difficulty": 2},
    {"type": "code", "stage": "second", "max_difficulty": 3},
]

# session_id -> session state dict
_sessions = {}


def start_quiz(subject, topic_mode="adaptive", fixed_topic=None):
    session_id = str(uuid.uuid4())
    question_spec = QUESTION_SEQUENCE[0]
    question = generate_question(
        subject,
        START_DIFFICULTY,
        [],
        question_type=question_spec["type"],
        question_stage=question_spec.get("stage"),
        avoid_questions=[],
        fixed_topic=fixed_topic if topic_mode == "same_topic" else None,
    )
    _sessions[session_id] = {
        "subject": subject,
        "topic_mode": topic_mode,
        "fixed_topic": fixed_topic if topic_mode == "same_topic" else None,
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
    fixed_topic = session.get("fixed_topic")
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

    # Adaptive difficulty rule: correct -> harder, incorrect -> easier.
    next_difficulty = (
        min(MAX_DIFFICULTY, difficulty + 1) if is_correct
        else max(MIN_DIFFICULTY, difficulty - 1)
    )

    result = {
        "correct": is_correct,
        "reasoning": evaluation.get("reasoning"),
        "explanation": explanation_text,
        "question_type": question.get("type"),
        "topic": question.get("topic"),
        "finished": False,
    }
    if question.get("type") == "code":
        result["expected_answer"] = question.get("correct_answer")
        result["submitted_answer"] = user_answer

    if session["question_count"] >= MAX_QUESTIONS:
        session["finished"] = True
        result["finished"] = True
        result["level"] = compute_level(session["history"])
        result["history"] = session["history"]
        return result

    next_question_spec = QUESTION_SEQUENCE[session["question_count"]]
    target_difficulty = min(
        next_difficulty,
        next_question_spec.get("max_difficulty", MAX_DIFFICULTY),
    )
    next_question = generate_question(
        subject,
        target_difficulty,
        session["history"],
        question_type=next_question_spec["type"],
        question_stage=next_question_spec.get("stage"),
        avoid_questions=[item["question"] for item in session["history"] if item.get("question")],
        fixed_topic=fixed_topic,
    )
    session["difficulty"] = target_difficulty
    session["current_question"] = next_question
    session["question_count"] += 1

    result["next_question"] = _public_question(next_question)
    result["question_number"] = session["question_count"]
    return result


def get_clue_for_current_question(session_id):
    session = _sessions.get(session_id)
    if session is None:
        raise ValueError("Invalid or expired session_id")
    if session["finished"]:
        raise ValueError("Quiz already finished for this session")

    question = session["current_question"]
    clue_obj = generate_clue(session["subject"], question)
    return {"clue": clue_obj.get("clue", "Try breaking the problem into smaller steps.")}


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
        return {
            "level": 1,
            "label": "Level 1 (Foundational)",
            "score": 0,
            "correct_count": 0,
            "total_questions": 0,
            "accuracy": 0,
            "recent_avg_difficulty": 0,
            "topic_breakdown": {},
        }

    total_weight = sum(h["difficulty"] for h in history)
    correct_weight = sum(h["difficulty"] for h in history if h["correct"])
    ratio = (correct_weight / total_weight) if total_weight else 0

    recent = history[-3:]
    recent_avg_difficulty = sum(h["difficulty"] for h in recent) / len(recent)
    correct_count = sum(1 for h in history if h["correct"])
    total_questions = len(history)
    accuracy = (correct_count / total_questions) * 100 if total_questions else 0

    topic_breakdown = {}
    for row in history:
        topic = row.get("topic") or "General"
        if topic not in topic_breakdown:
            topic_breakdown[topic] = {"attempted": 0, "correct": 0}
        topic_breakdown[topic]["attempted"] += 1
        if row["correct"]:
            topic_breakdown[topic]["correct"] += 1

    final_score = 0.6 * (ratio * MAX_DIFFICULTY) + 0.4 * recent_avg_difficulty
    level = 2 if final_score >= 3 else 1
    label = "Level 2 (Applied)" if level == 2 else "Level 1 (Foundational)"

    return {
        "level": level,
        "label": label,
        "score": round(final_score, 2),
        "correct_count": correct_count,
        "total_questions": total_questions,
        "accuracy": round(accuracy, 1),
        "recent_avg_difficulty": round(recent_avg_difficulty, 2),
        "topic_breakdown": topic_breakdown,
    }
