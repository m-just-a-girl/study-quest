import os
import time
import io
import secrets
import base64
import json
from collections import defaultdict, deque
from datetime import date, timedelta
import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, session, g
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token

load_dotenv()
app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.secret_key = os.getenv("FLASK_SECRET_KEY") or secrets.token_hex(32)
app.url_map.strict_slashes = False
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
FIREBASE_PROJECT_ID = "study-verse-105d7"
conversation_histories = defaultdict(list)
request_windows = defaultdict(deque)

QUESTS = {
    "physics-electric": {
        "title": "Electric Potential",
        "subject": "Physics",
        "minutes": 25,
        "xp": 30,
    },
    "chemistry-organic": {
        "title": "Organic Reactions",
        "subject": "Chemistry",
        "minutes": 25,
        "xp": 50,
    },
    "maths-limits": {
        "title": "Limits Recall",
        "subject": "Mathematics",
        "minutes": 25,
        "xp": 40,
    },
}

def progress_state():
    state = session.get("progress")
    if not state:
        state = {
            "xp": 0,
            "completed": [],
            "streak": 0,
            "last_completed": None,
            "completion_log": [],
            "active": None,
        }
        session["progress"] = state
    return state

def active_elapsed_seconds(active):
    end_time = active.get("paused_at") or int(time.time())
    return max(0, end_time - active["started_at"] - active.get("paused_seconds", 0))

def public_progress(state):
    active = state.get("active")
    active_public = None
    if active:
        elapsed = active_elapsed_seconds(active)
        active_public = {
            "quest_id": active["quest_id"],
            "subject": active.get("subject", QUESTS[active["quest_id"]]["subject"]),
            "topic": active.get("topic", QUESTS[active["quest_id"]]["title"]),
            "started_at": active["started_at"],
            "required_seconds": active["required_seconds"],
            "remaining_seconds": max(0, active["required_seconds"] - elapsed),
            "is_paused": bool(active.get("paused_at")),
        }
    completed = state.get("completed", [])
    today = date.today()
    log = [date.fromisoformat(item) for item in state.get("completion_log", [])]
    return {
        "xp": state.get("xp", 0),
        "level": state.get("xp", 0) // 500 + 1,
        "streak": state.get("streak", 0),
        "completed": completed,
        "boss_hp": max(0, 100 - len(completed) * 25),
        "active": active_public,
        "goals": {
            "day": sum(item == today for item in log),
            "week": sum(item >= today - timedelta(days=6) for item in log),
            "month": sum(item.year == today.year and item.month == today.month for item in log),
        },
        "quests": QUESTS,
    }

@app.get("/")
def landing_page():
    return render_template("Index.html")

@app.get("/login")
def login():
    return render_template("login.html")

@app.get("/onboarding")
def onboarding():
    return render_template("onboarding.html")

@app.get("/dashboard")
def dashboard():
    return render_template("dashboard.html")

def local_fallback(topic, mode):
    if "photosynthesis" in topic.lower():
        return """PHOTOSYNTHESIS — EXAM NOTES

Definition:
Photosynthesis is how green plants use light to make glucose from carbon dioxide and water.

Equation:
6CO₂ + 6H₂O + light → C₆H₁₂O₆ + 6O₂

1. Light-dependent reactions occur in the thylakoids. Chlorophyll absorbs light, water is split, oxygen is released, and ATP and NADPH are produced.
2. The Calvin cycle occurs in the stroma. Carbon dioxide, ATP, and NADPH are used to build glucose.

Memory trick: light reactions charge the batteries; the Calvin cycle uses them to build sugar.

Quick check: Which gas is released when water is split?"""
    return (
        f"Study request: {topic}\n\n"
        "The online AI service is temporarily unreachable. Check the OpenRouter "
        "key and internet connection, then try again."
    )

def ask_ai(topic, mode):
    prompts = {
        "notes": "Create concise, structured, exam-focused study notes.",
        "quiz": "Create five practice questions followed by a separate answer key.",
        "explain": "Explain clearly and simply with an example and recall question.",
        "revision": "Create a rapid revision sheet with formulas, key facts, and recall prompts.",
        "voice": "Answer in short, natural spoken sentences suitable for text-to-speech.",
        "exam_panic": (
            "Use web research to identify only the most important, repeatedly tested, "
            "high-confidence topics needed to target passing marks. State the exam, "
            "assumptions, priorities, and source links. Never claim a topic is confirmed "
            "unless the sources support it."
        ),
    }
    instruction = prompts.get(
        mode,
        "Answer naturally and helpfully. The request may be academic, creative, "
        "practical, technical, or conversational.",
    )
    if not OPENROUTER_API_KEY:
        return local_fallback(topic, mode), True

    session = requests.Session()
    session.trust_env = False
    try:
        response = session.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://127.0.0.1:5000",
                "X-Title": "Study Quest",
            },
            json={
                "model": "openrouter/free",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are Study Quest, a capable general conversational AI "
                            "assistant and study companion. Answer any reasonable question "
                            "naturally, like a modern chat assistant. You can teach, explain, "
                            "brainstorm, write, summarize, plan, calculate, and chat. Be "
                            "accurate, admit uncertainty, and adapt to the user's request. "
                            "For study questions, be an encouraging exam-focused tutor."
                        ),
                    },
                    *conversation_histories[g.user_id][-10:],
                    {
                        "role": "user",
                        "content": f"{instruction}\n\nUser message: {topic}",
                    },
                ],
                **({"plugins": [{"id": "web", "max_results": 5}]} if mode == "exam_panic" else {}),
            },
            timeout=45,
        )
        payload = response.json()
        if response.ok and payload.get("choices"):
            answer = payload["choices"][0]["message"]["content"]
            history = conversation_histories[g.user_id]
            history.extend([
                {"role": "user", "content": topic},
                {"role": "assistant", "content": answer},
            ])
            if len(history) > 20:
                del history[:-20]
            return answer, False
        app.logger.warning("OpenRouter rejected request: %s", payload)
    except (requests.RequestException, ValueError):
        app.logger.exception("OpenRouter request failed")
    return local_fallback(topic, mode), True

@app.before_request
def protect_api():
    if not request.path.startswith("/api/"):
        return None
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify(error="Please sign in again."), 401
    token = auth_header.removeprefix("Bearer ").strip()
    try:
        if os.getenv("REQUIRE_VERIFIED_AUTH") == "1":
            claims = id_token.verify_firebase_token(
                token, GoogleRequest(), audience=FIREBASE_PROJECT_ID
            )
        else:
            payload = token.split(".")[1]
            payload += "=" * (-len(payload) % 4)
            claims = json.loads(base64.urlsafe_b64decode(payload))
            if claims.get("aud") != FIREBASE_PROJECT_ID or claims.get("exp", 0) < time.time():
                raise ValueError("Invalid token claims")
        g.user_id = claims.get("uid") or claims.get("sub")
        if not g.user_id:
            raise ValueError("Missing user id")
    except Exception:
        return jsonify(error="Your session is invalid or expired. Please sign in again."), 401

    now = time.time()
    window = request_windows[g.user_id]
    while window and window[0] < now - 60:
        window.popleft()
    if len(window) >= 60:
        return jsonify(error="Too many requests. Please wait a minute."), 429
    window.append(now)
    return None

@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(self), microphone=(self)"
    return response

@app.post("/api/study-assistant")
def study_assistant():
    data = request.get_json(silent=True) or {}
    topic = str(data.get("topic", "")).strip()
    mode = str(data.get("mode", "explain")).strip().lower()
    if not topic:
        return jsonify(error="Please enter a topic or question."), 400
    if len(topic) > 1000:
        return jsonify(error="Please keep the request under 1,000 characters."), 400
    result, offline = ask_ai(topic, mode)
    return jsonify(result=result, offline=offline)

@app.post("/api/reset-conversation")
def reset_conversation():
    conversation_histories.pop(g.user_id, None)
    return jsonify(ok=True)

@app.get("/api/progress")
def get_progress():
    return jsonify(public_progress(progress_state()))

@app.post("/api/quest/start")
def start_quest():
    data = request.get_json(silent=True) or {}
    quest_id = str(data.get("quest_id", ""))
    if quest_id not in QUESTS:
        return jsonify(error="Unknown quest."), 404

    state = progress_state()
    quest = QUESTS[quest_id]
    requested_minutes = data.get("minutes", quest["minutes"])
    try:
        focus_minutes = max(1, min(180, int(requested_minutes)))
    except (TypeError, ValueError):
        focus_minutes = quest["minutes"]
    state["active"] = {
        "quest_id": quest_id,
        "subject": str(data.get("subject") or quest["subject"]).strip()[:80],
        "topic": str(data.get("topic") or quest["title"]).strip()[:120],
        "started_at": int(time.time()),
        "required_seconds": focus_minutes * 60,
        "paused_at": None,
        "paused_seconds": 0,
    }
    session["progress"] = state
    session.modified = True
    return jsonify(ok=True, progress=public_progress(state))

@app.post("/api/quest/mode")
def set_quest_mode():
    state = progress_state()
    active = state.get("active")
    if not active:
        return jsonify(error="Start a focus session first."), 400

    mode = str((request.get_json(silent=True) or {}).get("mode", ""))
    now = int(time.time())
    if mode == "break" and not active.get("paused_at"):
        active["paused_at"] = now
    elif mode == "focus" and active.get("paused_at"):
        active["paused_seconds"] = active.get("paused_seconds", 0) + now - active["paused_at"]
        active["paused_at"] = None
    elif mode not in {"focus", "break"}:
        return jsonify(error="Unknown session mode."), 400

    state["active"] = active
    session["progress"] = state
    session.modified = True
    return jsonify(ok=True, progress=public_progress(state))

@app.post("/api/quest/complete")
def complete_quest():
    state = progress_state()
    active = state.get("active")
    if not active:
        return jsonify(error="Start a quest before completing it."), 400

    quest_id = active["quest_id"]
    elapsed = active_elapsed_seconds(active)
    remaining = max(0, active["required_seconds"] - elapsed)
    if remaining:
        return jsonify(
            error="The focus session is not finished yet.",
            remaining_seconds=remaining,
        ), 409

    quest = QUESTS[quest_id]
    state.setdefault("completed", []).append(quest_id)
    state.setdefault("completion_log", []).append(date.today().isoformat())
    state["xp"] = state.get("xp", 0) + quest["xp"]
    state["active"] = None

    today = date.today()
    last_value = state.get("last_completed")
    last = date.fromisoformat(last_value) if last_value else None
    if last != today:
        state["streak"] = state.get("streak", 0) + 1 if last == today - timedelta(days=1) else 1
        state["last_completed"] = today.isoformat()

    session["progress"] = state
    session.modified = True
    return jsonify(
        ok=True,
        awarded_xp=quest["xp"],
        subject=active.get("subject", quest["subject"]),
        topic=active.get("topic", quest["title"]),
        progress=public_progress(state),
    )

@app.post("/api/get-notes")
def get_notes():
    data = request.get_json(silent=True) or {}
    topic = str(data.get("topic", "")).strip()
    if not topic:
        return jsonify(error="A topic is required."), 400
    result, offline = ask_ai(topic, "notes")
    return jsonify(topic=topic, notes=result, offline=offline)

@app.post("/api/analyse-material")
def analyse_material():
    uploaded = request.files.get("file")
    action = str(request.form.get("action", "notes")).strip().lower()
    instruction = str(request.form.get("instruction", "")).strip()
    if not uploaded or not uploaded.filename:
        return jsonify(error="Choose a study material file first."), 400
    raw = uploaded.read()
    if len(raw) > 8 * 1024 * 1024:
        return jsonify(error="Please upload a file smaller than 8 MB."), 400
    name = uploaded.filename.lower()
    try:
        if name.endswith(".pdf"):
            from pypdf import PdfReader
            text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(raw)).pages)
        else:
            text = raw.decode("utf-8", errors="ignore")
    except Exception:
        return jsonify(error="I could not read that file. Try PDF, TXT, or Markdown."), 400
    text = text.strip()
    if not text:
        return jsonify(error="No readable text was found in the file."), 400
    actions = {
        "notes": "Create clean, structured notes from this material.",
        "quiz": "Create a quiz and separate answer key from this material.",
        "mindmap": "Create a hierarchical text mind map from this material.",
        "summary": "Create a concise summary from this material.",
    }
    prompt = actions.get(action, actions["notes"])
    if instruction:
        prompt += "\nUser preference: " + instruction
    result, offline = ask_ai(prompt + "\n\nMATERIAL:\n" + text[:18000], "chat")
    return jsonify(result=result, offline=offline, filename=uploaded.filename)

@app.post("/api/analyse-text")
def analyse_text():
    data = request.get_json(silent=True) or {}
    text = str(data.get("text", "")).strip()
    action = str(data.get("action", "notes")).strip().lower()
    instruction = str(data.get("instruction", "")).strip()
    if not text:
        return jsonify(error="No readable text was found in the material."), 400
    if len(text) > 30000:
        text = text[:30000]
    actions = {
        "notes": "Create clear, complete notes with useful headings and a final recap.",
        "quiz": "Create a quiz from this material and put the answer key at the end.",
        "mindmap": "Create a clear hierarchical mind map from this material.",
        "summary": "Create a concise but useful summary of this material.",
    }
    prompt = actions.get(action, actions["notes"])
    if instruction:
        prompt += "\nFollow this user instruction: " + instruction
    result, offline = ask_ai(prompt + "\n\nSOURCE MATERIAL:\n" + text, "chat")
    return jsonify(result=result, offline=offline)

@app.post("/api/generate-quiz")
def generate_quiz():
    data = request.get_json(silent=True) or {}
    text = str(data.get("text", "")).strip()
    instruction = str(data.get("instruction", "")).strip()
    if not text:
        return jsonify(error="No readable material was found."), 400
    prompt = (
        "Create exactly 5 useful multiple-choice questions from the source material. "
        "Return ONLY a valid JSON array. Each item must have: question (string), "
        "options (array of exactly 4 strings), answer (zero-based integer 0-3), and "
        "explanation (one short string). Do not use Markdown or code fences."
    )
    if instruction:
        prompt += " User preference: " + instruction
    result, offline = ask_ai(prompt + "\n\nSOURCE MATERIAL:\n" + text[:18000], "chat")
    try:
        cleaned = result.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0]
        quiz = json.loads(cleaned)
        if not isinstance(quiz, list):
            raise ValueError("Quiz is not a list")
        valid = []
        for item in quiz[:5]:
            options = item.get("options", [])
            answer = item.get("answer")
            if (
                isinstance(item.get("question"), str)
                and isinstance(options, list)
                and len(options) == 4
                and isinstance(answer, int)
                and 0 <= answer < 4
            ):
                valid.append({
                    "question": item["question"],
                    "options": [str(option) for option in options],
                    "answer": answer,
                    "explanation": str(item.get("explanation", "")),
                })
        if not valid:
            raise ValueError("No valid questions")
        return jsonify(quiz=valid, offline=offline)
    except (ValueError, TypeError, json.JSONDecodeError):
        app.logger.warning("Quiz response was not valid JSON")
        return jsonify(error="The quiz could not be structured. Please try Generate Quiz again."), 502

if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG") == "1", port=int(os.getenv("PORT", "5000")))
