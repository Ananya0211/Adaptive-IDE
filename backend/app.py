from flask import Flask, request, jsonify
from werkzeug.exceptions import HTTPException

import quiz_controller as qc

app = Flask(__name__)


@app.errorhandler(Exception)
def handle_any_exception(e):
    if isinstance(e, HTTPException):
        return e
    return jsonify({"error": str(e)}), 500


@app.route("/start_quiz", methods=["POST"])
def start_quiz_route():
    data = request.get_json(force=True) or {}
    subject = data.get("subject")
    topic_mode = data.get("topic_mode", "adaptive")
    fixed_topic = data.get("fixed_topic")

    if subject not in ("Python", "C"):
        return jsonify({"error": "subject must be 'Python' or 'C'"}), 400
    if topic_mode not in ("adaptive", "same_topic"):
        return jsonify({"error": "topic_mode must be 'adaptive' or 'same_topic'"}), 400
    if topic_mode == "same_topic" and not fixed_topic:
        return jsonify({"error": "fixed_topic is required when topic_mode is 'same_topic'"}), 400

    session_id, question = qc.start_quiz(subject, topic_mode=topic_mode, fixed_topic=fixed_topic)
    return jsonify({
        "session_id": session_id,
        "question": question,
        "question_number": 1,
    })


@app.route("/submit_answer", methods=["POST"])
def submit_answer_route():
    data = request.get_json(force=True) or {}
    session_id = data.get("session_id")
    user_answer = data.get("user_answer", "")

    try:
        result = qc.submit_answer(session_id, user_answer)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify(result)


@app.route("/get_clue", methods=["POST"])
def get_clue_route():
    data = request.get_json(force=True) or {}
    session_id = data.get("session_id")
    if not session_id:
        return jsonify({"error": "session_id is required"}), 400

    try:
        result = qc.get_clue_for_current_question(session_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify(result)


if __name__ == "__main__":
    app.run(port=5000, debug=True)