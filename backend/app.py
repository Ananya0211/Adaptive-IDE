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
    if subject not in ("Python", "C"):
        return jsonify({"error": "subject must be 'Python' or 'C'"}), 400

    session_id, question = qc.start_quiz(subject)
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


if __name__ == "__main__":
    app.run(port=5000, debug=True)