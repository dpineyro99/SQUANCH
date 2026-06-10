from fastapi import FastAPI
from pydantic import BaseModel
from memory import save_memory, get_memories, search_memories
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI
import sqlite3
import subprocess
import os
import json
import threading

try:
    from google_calendar import create_google_event, get_calendar_service
except Exception:
    create_google_event = None

load_dotenv()

app = FastAPI()
DB_PATH = "squanch.db"
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str


class MemoryRequest(BaseModel):
    category: str = "general"
    content: str
    source: str = "manual"


def now():
    return datetime.now().isoformat(timespec="seconds")

def db():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent TEXT NOT NULL,
            action TEXT NOT NULL,
            summary TEXT NOT NULL,
            detail TEXT,
            ref_type TEXT,
            ref_id INTEGER,
            created_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            done INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            date_text TEXT,
            time_text TEXT,
            person TEXT,
            done INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent TEXT NOT NULL,
            status TEXT NOT NULL,
            prompt TEXT,
            result TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pending_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action_type TEXT NOT NULL,
            payload TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            text TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()

def add_log(text: str):
    conn = db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO logs (text, created_at) VALUES (?, ?)",
        (text, now())
    )
    conn.commit()
    conn.close()


def add_message(role: str, text: str):
    conn = db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO messages (role, text, created_at) VALUES (?, ?, ?)",
        (role, text, now())
    )
    conn.commit()
    conn.close()

def get_recent_messages(limit: int = 12):
    conn = db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT role, text FROM messages ORDER BY id DESC LIMIT ?",
        (limit,)
    )
    rows = cursor.fetchall()
    conn.close()
    rows.reverse()
    return [{"role": row[0], "text": row[1]} for row in rows]

def smart_summary(text: str):
    if not text:
        return "Actividad"

    clean = " ".join(text.replace("\n", " ").split())
    words = clean.split()

    if len(words) <= 6:
        return clean[:60]

    return " ".join(words[:6])[:60]

def add_activity(agent: str, action: str, summary: str, detail: str = "", ref_type: str = "", ref_id: int | None = None):
    conn = db()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO activities (agent, action, summary, detail, ref_type, ref_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (agent, action, summary, detail, ref_type, ref_id, now())
    )
    conn.commit()
    conn.close()

def get_activities(limit: int = 16):
    conn = db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, agent, action, summary, detail, ref_type, ref_id, created_at
        FROM activities
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,)
    )
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": row[0],
            "agent": row[1],
            "action": row[2],
            "summary": row[3],
            "detail": row[4],
            "ref_type": row[5],
            "ref_id": row[6],
            "created_at": row[7],
        }
        for row in rows
    ]

def get_logs(limit: int = 16):
    conn = db()
    cursor = conn.cursor()
    cursor.execute("SELECT text, created_at FROM logs ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [{"text": row[0], "created_at": row[1]} for row in rows]

def add_task(task_text: str):
    conn = db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO tasks (text, created_at) VALUES (?, ?)",
        (task_text, now())
    )
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return task_id

def get_open_tasks(limit: int = 50):
    conn = db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, text, created_at FROM tasks WHERE done = 0 ORDER BY id DESC LIMIT ?",
        (limit,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [{"id": row[0], "text": row[1], "created_at": row[2]} for row in rows]

def complete_task(task_id: int):
    conn = db()
    cursor = conn.cursor()
    cursor.execute("UPDATE tasks SET done = 1 WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()

def delete_task(task_id: int):
    conn = db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()


def normalize_event_time(time_text: str):
    import re

    if not time_text:
        return None

    t = time_text.lower().strip()
    t = t.replace("a las", "").replace("hrs", "").replace("horas", "").strip()

    m = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", t)
    if not m:
        return None

    hour = int(m.group(1))
    minute = int(m.group(2) or 0)
    meridian = m.group(3)

    if meridian == "pm" and hour < 12:
        hour += 12
    if meridian == "am" and hour == 12:
        hour = 0
    if not meridian and 1 <= hour <= 7:
        hour += 12

    return hour, minute


def parse_event_datetime_fallback(date_text: str, time_text: str):
    from datetime import datetime, timedelta
    import re

    parsed_time = normalize_event_time(time_text)
    if not parsed_time:
        return ""

    base = datetime.now()
    hour, minute = parsed_time
    d = (date_text or "").lower().strip()

    target_date = base.date()

    if "mañana" in d or "manana" in d:
        target_date = (base + timedelta(days=1)).date()
    elif "hoy" in d:
        target_date = base.date()
    else:
        weekdays = {
            "lunes": 0,
            "martes": 1,
            "miercoles": 2,
            "miércoles": 2,
            "jueves": 3,
            "viernes": 4,
            "sabado": 5,
            "sábado": 5,
            "domingo": 6,
        }

        found = None
        for name, idx in weekdays.items():
            if name in d:
                found = idx
                break

        if found is not None:
            days_ahead = (found - base.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            target_date = (base + timedelta(days=days_ahead)).date()

        m = re.search(r"\b(\d{1,2})\b", d)
        if m:
            day = int(m.group(1))
            year = base.year
            month = base.month
            try:
                candidate = datetime(year, month, day, hour, minute)
                if candidate < base - timedelta(days=1):
                    if month == 12:
                        candidate = datetime(year + 1, 1, day, hour, minute)
                    else:
                        candidate = datetime(year, month + 1, day, hour, minute)
                return candidate.isoformat(timespec="seconds")
            except Exception:
                pass

    return datetime.combine(target_date, datetime.min.time()).replace(hour=hour, minute=minute).isoformat(timespec="seconds")


def add_event(title: str, date_text: str = "", time_text: str = "", person: str = "", event_datetime: str = "", detail: str = ""):
    conn = db()
    cursor = conn.cursor()

    google_event_id = ""
    google_event_link = ""

    print("GCAL DEBUG create_google_event:", create_google_event, "event_datetime:", event_datetime)

    if create_google_event and event_datetime:
        try:
            print("GCAL DEBUG trying create:", title, event_datetime)
            google_result = create_google_event(
                title=title,
                event_datetime=event_datetime,
                description=detail or f"Creado por SQUANCH. Persona/lugar: {person}".strip()
            )
            if google_result:
                google_event_id = google_result.get("id") or ""
                google_event_link = google_result.get("htmlLink") or ""
        except Exception as e:
            print("GCAL DEBUG failed:", e)
            google_event_link = f"Google Calendar sync failed: {e}"

    cursor.execute(
        """
        INSERT INTO events (
            title,
            date_text,
            time_text,
            person,
            created_at,
            event_datetime,
            google_event_id,
            google_event_link
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            title,
            date_text,
            time_text,
            person,
            now(),
            event_datetime,
            google_event_id,
            google_event_link
        )
    )

    event_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return event_id

def get_open_events(limit: int = 20):
    conn = db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, title, date_text, time_text, person, created_at, event_datetime FROM events WHERE done = 0 ORDER BY id DESC LIMIT ?",
        (limit,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "id": row[0],
            "title": row[1],
            "date_text": row[2],
            "time_text": row[3],
            "person": row[4],
            "created_at": row[5],
            "event_datetime": row[6],
        }
        for row in rows
    ]

def complete_event(event_id: int):
    conn = db()
    cursor = conn.cursor()
    cursor.execute("UPDATE events SET done = 1 WHERE id = ?", (event_id,))
    conn.commit()
    conn.close()

def delete_event(event_id: int):
    conn = db()
    cursor = conn.cursor()

    row = cursor.execute(
        "SELECT google_event_id FROM events WHERE id = ?",
        (event_id,)
    ).fetchone()

    google_event_id = row[0] if row and row[0] else ""

    if google_event_id:
        try:
            service = get_calendar_service()
            service.events().delete(
                calendarId="primary",
                eventId=google_event_id
            ).execute()
        except Exception as e:
            print("Google Calendar delete failed:", e)

    cursor.execute("DELETE FROM events WHERE id = ?", (event_id,))
    conn.commit()
    conn.close()

def create_job(agent: str, prompt: str):
    conn = db()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO jobs (agent, status, prompt, result, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (agent, "queued", prompt, "", now(), now())
    )
    job_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return job_id

def update_job(job_id: int, status: str, result: str | None = None):
    conn = db()
    cursor = conn.cursor()

    if result is None:
        cursor.execute(
            "UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?",
            (status, now(), job_id)
        )
    else:
        cursor.execute(
            "UPDATE jobs SET status = ?, result = ?, updated_at = ? WHERE id = ?",
            (status, result, now(), job_id)
        )

    conn.commit()
    conn.close()

def get_jobs(limit: int = 20):
    conn = db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, agent, status, prompt, result, created_at, updated_at FROM jobs ORDER BY id DESC LIMIT ?",
        (limit,)
    )
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": row[0],
            "agent": row[1],
            "status": row[2],
            "prompt": row[3],
            "result": row[4],
            "created_at": row[5],
            "event_datetime": row[6],
            "updated_at": row[6],
        }
        for row in rows
    ]

def latest_coder_job_status():
    jobs = get_jobs(limit=5)
    recent_messages = get_recent_messages(limit=12)
    for job in jobs:
        if job["agent"] == "Coder Agent" and job["status"] in ["queued", "working"]:
            return "working"
    return "ready"

def create_pending_action(action_type: str, payload: dict):
    conn = db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO pending_actions (action_type, payload, status, created_at) VALUES (?, ?, ?, ?)",
        (action_type, json.dumps(payload), "pending", now())
    )
    action_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return action_id

def get_latest_pending_action():
    conn = db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, action_type, payload FROM pending_actions WHERE status = 'pending' ORDER BY id DESC LIMIT 1"
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "id": row[0],
        "action_type": row[1],
        "payload": json.loads(row[2])
    }

def complete_pending_action(action_id: int):
    conn = db()
    cursor = conn.cursor()
    cursor.execute("UPDATE pending_actions SET status = 'completed' WHERE id = ?", (action_id,))
    conn.commit()
    conn.close()

def clear_pending_actions():
    conn = db()
    cursor = conn.cursor()
    cursor.execute("UPDATE pending_actions SET status = 'cancelled' WHERE status = 'pending'")
    conn.commit()
    conn.close()

def is_yes_command(msg: str):
    return msg.strip().lower() in [
        "si", "sí", "va", "dale", "ok", "okay", "hazlo", "házlo",
        "adelante", "confirmo", "confirmado", "yes", "do it"
    ]

def is_no_command(msg: str):
    return msg.strip().lower() in [
        "no", "nel", "cancela", "cancelar", "no lo hagas", "stop"
    ]

def execute_pending_action(action):
    action_type = action["action_type"]
    payload = action["payload"]

    if action_type == "codex_review":
        prompt = payload.get("prompt", "revisa el proyecto")
        job_id, summary = start_codex_job(prompt)
        complete_pending_action(action["id"])

        return (
            f"✅ Acción confirmada.\n"
            f"Coder Agent iniciado.\n"
            f"Job #{job_id} creado.\n\n"
            f"Resumen: {summary}\n\n"
            f"Puedes pedir el resultado con:\n"
            f"job {job_id}"
        )

    complete_pending_action(action["id"])
    return "Acción pendiente completada."

def check_codex():
    try:
        result = subprocess.run(
            ["codex", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        output = (result.stdout or result.stderr).strip()
        return {"status": "detected", "version": output}
    except Exception as e:
        return {"status": "error", "version": str(e)}

PROJECTS = {
    "sports": "/home/dpnhclawd/projects/papi-sports-intelligence",
    "sports intelligence": "/home/dpnhclawd/projects/papi-sports-intelligence",
    "papi sports": "/home/dpnhclawd/projects/papi-sports-intelligence",
    "squanch": "/home/dpnhclawd/jarvis",
    "dashboard": "/home/dpnhclawd/jarvis/dashboard",
    "backend": "/home/dpnhclawd/jarvis/backend",
}

def detect_project(message: str):
    msg = message.lower()
    for key, path in PROJECTS.items():
        if key in msg:
            return path
    return "/home/dpnhclawd/jarvis"

def run_codex_review(user_message: str):
    project_path = detect_project(user_message)

    prompt = f"""
Revisa este proyecto en modo SOLO LECTURA.

No modifiques archivos.
No apliques cambios.
No ejecutes comandos destructivos.

Solicitud del usuario:
{user_message}

Devuelve en español:
1. Resumen corto
2. Los 3 problemas más importantes
3. Archivos relevantes
4. Próximo paso recomendado
"""

    result = subprocess.run(
        [
            "codex",
            "-s",
            "read-only",
            "-a",
            "never",
            "-C",
            project_path,
            "exec",
            prompt,
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )

    output = (result.stdout or result.stderr).strip()

    if not output:
        return "Codex terminó sin respuesta."

    return output[-5000:]

def codex_worker(job_id: int, user_message: str, summary: str):
    update_job(job_id, "working")
    add_activity(
        "Coder Agent",
        "working",
        summary,
        detail=user_message,
        ref_type="job",
        ref_id=job_id
    )

    try:
        result = run_codex_review(user_message)
        update_job(job_id, "completed", result)
        add_activity(
            "Coder Agent",
            "completed",
            summary,
            detail=result,
            ref_type="job",
            ref_id=job_id
        )
    except subprocess.TimeoutExpired:
        result = "Codex tardó demasiado y fue detenido por seguridad."
        update_job(job_id, "failed", result)
        add_activity(
            "Coder Agent",
            "failed",
            summary,
            detail=result,
            ref_type="job",
            ref_id=job_id
        )
    except Exception as e:
        result = str(e)
        update_job(job_id, "failed", result)
        add_activity(
            "Coder Agent",
            "failed",
            summary,
            detail=result,
            ref_type="job",
            ref_id=job_id
        )

def start_codex_job(user_message: str):
    summary = smart_summary(user_message)
    job_id = create_job("Coder Agent", user_message)

    thread = threading.Thread(
        target=codex_worker,
        args=(job_id, user_message, summary),
        daemon=True
    )
    thread.start()

    add_activity(
        "Coder Agent",
        "started",
        summary,
        detail=user_message,
        ref_type="job",
        ref_id=job_id
    )

    return job_id, summary

def detect_action(user_message: str):
    try:
        response = client.responses.create(
            model="gpt-5",
            input=f"""
You are an action extraction engine for SQUANCH.

Return ONLY valid JSON. No markdown. No explanation.

Classify the user's message as one of:

0. save_memory
Use this if the user shares a preference, project context, investment thesis, long-term note, important decision, personal workflow preference, or something SQUANCH should remember for future conversations.

Examples:
- MSTR es mi exposición a BTC
- quiero enfocarme en Polymarket Alpha
- los agentes todavía no están listos para incorporarse
- prefiero código completo y no buscar líneas
- Cerebras me interesa como inversión de AI infra

Return:
{{"intent": "save_memory", "category": "general", "content": "clean memory text"}}

1. codex_review
Use this if the user wants to review code, inspect a project, search for bugs, analyze repo structure, run code review, or ask Codex to check something.

Return:
{{"intent": "codex_review"}}

2. create_event
Use this if the message is clearly an appointment, meeting, call, dinner, lunch, reservation, visit, event, class, doctor, dentist, or scheduled commitment with a time/date/person.

Return:
{{
  "intent": "create_event",
  "title": "clean event title in Spanish",
  "date_text": "date as user said it",
  "time_text": "time as user said it",
  "person": "person or place if mentioned"
}}

3. create_task
Use this if the message is a todo, reminder, payment, errand, thing to do, follow-up, or commitment without a clear calendar event.

Return:
{{"intent": "create_task", "title": "clean task title in Spanish"}}

4. none
Use this for normal questions or conversation.

Return:
{{"intent": "none"}}

Current local datetime in Mexico City:
{now()}

User message:
{user_message}
"""
        )

        text = response.output_text.strip()
        return json.loads(text)

    except Exception:
        return {"intent": "none"}

def ask_gpt(user_message: str):
    tasks = get_open_tasks(limit=8)
    events = get_open_events(limit=8)
    jobs = get_jobs(limit=5)
    recent_messages = get_recent_messages(limit=12)

    task_context = "\n".join(
        [f"- {task['id']}: {task['text']}" for task in tasks]
    ) or "No pending tasks."

    event_context = "\n".join(
        [f"- {event['id']}: {event['title']} | {event['date_text']} | {event['time_text']} | {event['person']}" for event in events]
    ) or "No pending events."

    job_context = "\n".join(
        [f"- #{job['id']} {job['agent']}: {job['status']}" for job in jobs]
    ) or "No recent jobs."

    conversation_context = "\n".join(
        [f"{msg['role']}: {msg['text']}" for msg in recent_messages]
    ) or "No recent conversation."

    prompt = f"""
You are SQUANCH, Daniel's personal AI operating system.

Speak in Mexican Spanish.
Be direct, useful, and concise.
Daniel likes brutal honesty and practical answers.

Current pending tasks:
{task_context}

Current upcoming internal events:
{event_context}

Recent jobs:
{job_context}

Recent conversation:
{conversation_context}

Important:
Use the recent conversation to understand short replies like "sí", "no", "hazlo", "ok", "eso", "dale", or "continúa".

User message:
{user_message}
"""

    response = client.responses.create(
        model="gpt-5",
        input=prompt,
    )

    return response.output_text

init_db()
add_activity("System", "booted", "System boot completed")

@app.get("/status")
def status():
    codex = check_codex()
    tasks = get_open_tasks()
    events = get_open_events()
    logs = get_logs(limit=11)
    activities = get_activities(limit=11)
    jobs = get_jobs(limit=10)

    coder_status = latest_coder_job_status()

    return {
        "backend": "online",
        "telegram": "online",
        "memory": "active",
        "codex": codex,
        "agents": [
            {
                "name": "Coder Agent",
                "status": coder_status if codex["status"] == "detected" else "error"
            },
            {"name": "Sports Analyst", "status": "pending"},
            {"name": "Research Agent", "status": "ready"},
        ],
        "tasks_count": len(tasks),
        "events_count": len(events),
        "jobs_count": len(jobs),
        "tasks": tasks,
        "events": events,
        "jobs": jobs,
        "logs": logs,
        "activities": activities,
        "updated_at": now()
    }

@app.get("/activities")
def activities():
    return {"activities": get_activities(limit=50)}


@app.get("/memories")
def memories(limit: int = 50, q: str = ""):
    if q:
        return {"memories": search_memories(q, limit=limit)}
    return {"memories": get_memories(limit=limit)}


@app.post("/memories")
def create_memory(request: MemoryRequest):
    memory_id = save_memory(request.category, request.content, request.source)
    add_activity(
        "Memory Engine",
        "created",
        smart_summary(request.content),
        detail=request.content,
        ref_type="memory",
        ref_id=memory_id,
    )
    return {"ok": True, "memory_id": memory_id}

@app.get("/jobs")
def jobs():
    return {"jobs": get_jobs(limit=50)}

@app.get("/tasks")
def tasks():
    return {"tasks": get_open_tasks(limit=50)}

@app.patch("/tasks/{task_id}/done")
def mark_task_done(task_id: int):
    complete_task(task_id)
    add_activity("Task Agent", "completed", f"Task #{task_id}", ref_type="task", ref_id=task_id)
    return {"ok": True, "message": f"Task {task_id} completed"}

@app.delete("/tasks/{task_id}")
def remove_task(task_id: int):
    delete_task(task_id)
    add_activity("Task Agent", "deleted", f"Task #{task_id}", ref_type="task", ref_id=task_id)
    return {"ok": True, "message": f"Task {task_id} deleted"}

@app.get("/events")
def events():
    return {"events": get_open_events(limit=50)}

@app.get("/completed")
def completed():
    conn = db()
    cursor = conn.cursor()

    cursor.execute("SELECT id, text, created_at FROM tasks WHERE done = 1 ORDER BY id DESC LIMIT 100")
    task_rows = cursor.fetchall()

    cursor.execute("SELECT id, title, date_text, time_text, person, created_at, event_datetime FROM events WHERE done = 1 ORDER BY id DESC LIMIT 100")
    event_rows = cursor.fetchall()

    conn.close()

    return {
        "tasks": [
            {"id": r[0], "text": r[1], "created_at": r[2]}
            for r in task_rows
        ],
        "events": [
            {
                "id": r[0],
                "title": r[1],
                "date_text": r[2],
                "time_text": r[3],
                "person": r[4],
                "created_at": r[5],
                "event_datetime": r[6],
            }
            for r in event_rows
        ],
    }


@app.patch("/events/{event_id}/done")
def mark_event_done(event_id: int):
    complete_event(event_id)
    add_activity("Calendar Agent", "completed", f"Event #{event_id}", ref_type="event", ref_id=event_id)
    return {"ok": True, "message": f"Event {event_id} completed"}

@app.delete("/events/{event_id}")
def remove_event(event_id: int):
    delete_event(event_id)
    add_activity("Calendar Agent", "deleted", f"Event #{event_id}", ref_type="event", ref_id=event_id)
    return {"ok": True, "message": f"Event {event_id} deleted"}

@app.post("/chat")
def chat(request: ChatRequest):
    raw = request.message.strip()
    msg = raw.lower()

    add_message("user", raw)

    if is_no_command(msg):
        clear_pending_actions()
        response = "Va, cancelé la acción pendiente."
        add_message("assistant", response)
        add_activity("System", "cancelled", "Pending action cancelled")
        return {"response": response}

    if is_yes_command(msg):
        pending = get_latest_pending_action()

        if pending:
            response = execute_pending_action(pending)
            add_message("assistant", response)
            add_activity("System", "confirmed", "Pending action confirmed")
            return {"response": response}

    if msg.startswith("recuerda que ") or msg.startswith("remember that "):
        if msg.startswith("recuerda que "):
            memory_text = raw[len("recuerda que "):].strip()
        else:
            memory_text = raw[len("remember that "):].strip()

        if not memory_text:
            return {"response": "Dime qué quieres que recuerde. Ejemplo: recuerda que MSTR es mi exposición a BTC"}

        memory_id = save_memory("general", memory_text, "chat")
        summary = smart_summary(memory_text)
        add_activity("Memory Engine", "created", summary, detail=memory_text, ref_type="memory", ref_id=memory_id)
        add_message("assistant", f"🧠 Memoria guardada: {memory_text}")
        return {"response": f"🧠 Memoria guardada:\n\n{memory_text}"}

    if msg in ["memories", "memorias"]:
        memories = get_memories(limit=20)
        add_activity("Memory Engine", "listed", "Memory list requested")

        if not memories:
            return {"response": "No tengo memorias guardadas todavía."}

        text = "Memorias recientes:\n"
        for memory in memories:
            text += f"{memory['id']}. [{memory['category']}] {memory['content']}\n"

        return {"response": text.strip()}

    memory_lookup_prefixes = [
        "qué recuerdas de ",
        "que recuerdas de ",
        "qué sabes de ",
        "que sabes de ",
        "busca memoria de ",
        "buscar memoria de ",
        "memoria de ",
        "memorias de ",
    ]

    for prefix in memory_lookup_prefixes:
        if msg.startswith(prefix):
            query = raw[len(prefix):].strip()

            if not query:
                return {"response": "Dime qué tema quieres buscar en memoria. Ejemplo: qué recuerdas de Cerebras"}

            matches = search_memories(query, limit=10)
            add_activity("Memory Engine", "searched", smart_summary(query), detail=query)

            if not matches:
                return {"response": f"No encontré memorias sobre: {query}"}

            text = f"Memorias sobre {query}:\n"
            for memory in matches:
                text += f"\n{memory['id']}. [{memory['category']}] {memory['content']}"

            return {"response": text.strip()}

    if msg.startswith("run ") or msg.startswith("ejecuta "):
        command_text = raw.strip()
        job_id = create_job("Executor Agent", command_text)
        summary = smart_summary(command_text)
        add_activity(
            "Executor Agent",
            "queued",
            summary,
            detail=command_text,
            ref_type="job",
            ref_id=job_id,
        )
        response = (
            f"✅ Executor Agent iniciado.\n"
            f"Job #{job_id} creado.\n\n"
            f"Comando: {command_text}\n\n"
            f"Puedes ver el resultado con:\n"
            f"job {job_id}"
        )
        add_message("assistant", response)
        return {"response": response}

    if msg.startswith("task "):
        task_text = raw.replace("task", "", 1).strip()

        if not task_text:
            return {"response": "Escribe la task después de 'task'. Ejemplo: task pagar contador mañana"}

        task_id = add_task(task_text)
        summary = smart_summary(task_text)
        add_activity("Task Agent", "created", summary, detail=task_text, ref_type="task", ref_id=task_id)
        return {"response": f"✅ Task guardada:\n\n{task_text}"}

    if msg in ["tasks", "tareas"]:
        open_tasks = get_open_tasks(limit=50)
        add_activity("Task Agent", "listed", "Task list requested")

        if not open_tasks:
            return {"response": "No tienes tasks pendientes."}

        text = "Tasks pendientes:\n"
        for task in open_tasks:
            text += f"{task['id']}. {task['text']}\n"

        return {"response": text.strip()}

    if msg in ["events", "eventos", "citas"]:
        open_events = get_open_events(limit=50)
        add_activity("Calendar Agent", "listed", "Event list requested")

        if not open_events:
            return {"response": "No tienes eventos pendientes."}

        text = "Eventos pendientes:\n"
        for event in open_events:
            text += f"{event['id']}. {event['title']} — {event['date_text']} {event['time_text']}\n"

        return {"response": text.strip()}

    if msg in ["jobs", "trabajos"]:
        recent_jobs = get_jobs(limit=10)
        add_activity("System", "listed", "Jobs requested")

        if not recent_jobs:
            return {"response": "No hay jobs recientes."}

        text = "Jobs recientes:\n"
        for job in recent_jobs:
            text += f"#{job['id']} {job['agent']} — {job['status']}\n"

        return {"response": text.strip()}

    if msg.startswith("job "):
        parts = msg.split()

        if len(parts) < 2 or not parts[1].isdigit():
            return {"response": "Usa: job 1"}

        job_id = int(parts[1])
        recent_jobs = get_jobs(limit=50)
        selected = next((job for job in recent_jobs if job["id"] == job_id), None)

        if not selected:
            return {"response": f"No encontré el job #{job_id}."}

        result = selected.get("result") or "Ese job todavía no tiene resultado."
        add_activity("Coder Agent", "opened", f"Job #{job_id}", ref_type="job", ref_id=job_id)
        return {"response": result[-3900:]}

    if msg.startswith("done "):
        parts = msg.split()

        if len(parts) < 2 or not parts[1].isdigit():
            return {"response": "Usa: done 1"}

        task_id = int(parts[1])
        complete_task(task_id)
        add_activity("Task Agent", "completed", f"Task #{task_id}", ref_type="task", ref_id=task_id)
        return {"response": f"Task {task_id} marcada como completada."}

    if msg.startswith("delete "):
        parts = msg.split()

        if len(parts) < 2 or not parts[1].isdigit():
            return {"response": "Usa: delete 1"}

        task_id = int(parts[1])
        delete_task(task_id)
        add_activity("Task Agent", "deleted", f"Task #{task_id}", ref_type="task", ref_id=task_id)
        return {"response": f"Task {task_id} eliminada."}

    if "codex status" in msg or "version codex" in msg:
        codex = check_codex()
        response = f"Coder Agent detected: {codex['version']}"
        add_message("assistant", response)
        add_activity("Coder Agent", "checked", "Codex status")
        return {"response": response}

    if "qué puedo hacer con codex" in msg or "que puedo hacer con codex" in msg:
        create_pending_action("codex_review", {"prompt": "revisa el proyecto squanch"})
        response = (
            "Con Codex puedo revisar proyectos, buscar bugs, explicar arquitectura y detectar riesgos.\n\n"
            "También dejé preparada una acción pendiente: revisar SQUANCH.\n"
            "Si quieres ejecutarla, dime: sí, hazlo."
        )
        add_message("assistant", response)
        add_activity("Coder Agent", "prepared", "Codex review prepared")
        return {"response": response}

    if any(
        phrase in msg
        for phrase in [
            "revisa proyecto",
            "revisa el proyecto",
            "analiza proyecto",
            "analiza el proyecto",
            "busca errores",
            "code review",
            "review sports",
            "revisa sports",
            "sports intelligence",
        ]
    ):
        job_id, summary = start_codex_job(raw)

        response = (
            f"✅ Coder Agent iniciado.\n"
            f"Job #{job_id} creado.\n\n"
            f"Resumen: {summary}\n\n"
            f"Puedes pedir el resultado con:\n"
            f"job {job_id}"
        )
        add_message("assistant", response)
        return {"response": response}

    if any(word in msg for word in ["mlb", "nba", "nhl", "pick", "momio", "apuesta"]):
        add_activity("Sports Analyst", "triggered", "Sports analysis requested", detail=raw)
        return {
            "response": "Sports Analyst activado. Todavía no tiene datos deportivos conectados, pero el agente ya fue ruteado correctamente."
        }

    action = detect_action(raw)

    if action.get("intent") == "codex_review":
        job_id, summary = start_codex_job(raw)

        return {
            "response": (
                f"✅ Coder Agent iniciado.\n"
                f"Job #{job_id} creado.\n\n"
                f"Resumen: {summary}\n\n"
                f"Puedes pedir el resultado con:\n"
                f"job {job_id}"
            )
        }

    if action.get("intent") == "save_memory":
        content = action.get("content", raw)
        category = action.get("category", "general")

        if not content:
            content = raw

        memory_id = save_memory(category, content, "auto")
        summary = smart_summary(content)
        add_activity("Memory Engine", "auto_saved", summary, detail=content, ref_type="memory", ref_id=memory_id)

        return {
            "response": f"🧠 Memoria guardada automáticamente:\n\n{content}"
        }

    if action.get("intent") == "create_event":
        title = action.get("title", "Evento")
        date_text = action.get("date_text", "")
        time_text = action.get("time_text", "")
        person = action.get("person", "")
        event_datetime = action.get("event_datetime", "")

        if not event_datetime:
            event_datetime = parse_event_datetime_fallback(date_text, time_text)

        event_id = add_event(title, date_text, time_text, person, event_datetime, raw)
        summary = smart_summary(f"{title} {date_text} {time_text}")
        add_activity("Calendar Agent", "created", summary, detail=raw, ref_type="event", ref_id=event_id)

        return {
            "response": f"✅ Evento guardado:\n\n{title}\nFecha: {date_text}\nHora: {time_text}\nCalendar: sincronizado si había fecha/hora real."
        }

    if action.get("intent") == "create_task":
        title = action.get("title", raw)

        task_id = add_task(title)
        summary = smart_summary(title)
        add_activity("Task Agent", "created", summary, detail=raw, ref_type="task", ref_id=task_id)

        return {
            "response": f"✅ Task guardada automáticamente:\n\n{title}"
        }

    try:
        response = ask_gpt(raw)
        add_message("assistant", response)
        summary = smart_summary(raw)
        add_activity("GPT Brain", "answered", summary, detail=response)
        return {"response": response}
    except Exception as e:
        add_activity("GPT Brain", "failed", "GPT error", detail=str(e))
        return {"response": f"Error conectando GPT: {str(e)}"}
