import os
import re
import time
import sqlite3
from pathlib import Path
import requests
from datetime import datetime, timedelta, date
from dotenv import load_dotenv

try:
    from google_calendar import list_upcoming_google_events
except Exception:
    list_upcoming_google_events = None

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "squanch.db"
CHAT_ID_FILE = "telegram_chat_id.txt"
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


def now():
    return datetime.now()


def db():
    return sqlite3.connect(str(DB_PATH))


def send_telegram(text: str):
    if not TOKEN:
        print("Missing TELEGRAM_BOT_TOKEN")
        return False

    if not os.path.exists(CHAT_ID_FILE):
        print("No telegram_chat_id.txt yet. Send /start to bot first.")
        return False

    chat_id = open(CHAT_ID_FILE).read().strip()
    if not chat_id:
        print("Empty chat id")
        return False

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    r = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=20)
    print("telegram", r.status_code, r.text[:120])
    return r.ok


def ensure_daily_table():
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS daily_digests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            digest_date TEXT NOT NULL UNIQUE,
            sent_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def normalize_time(time_text: str):
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


def parse_event_datetime(date_text: str, time_text: str, created_at: str):
    if not time_text:
        return None

    try:
        base = datetime.fromisoformat(created_at)
    except Exception:
        base = now()

    d = (date_text or "").lower().strip()
    parsed_time = normalize_time(time_text)
    if not parsed_time:
        return None

    hour, minute = parsed_time
    target_date = base.date()

    if "mañana" in d or "manana" in d:
        target_date = (base + timedelta(days=1)).date()
    elif "hoy" in d:
        target_date = base.date()
    else:
        weekdays = {
            "lunes": 0, "martes": 1, "miercoles": 2, "miércoles": 2,
            "jueves": 3, "viernes": 4, "sabado": 5, "sábado": 5, "domingo": 6,
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
                return candidate
            except Exception:
                pass

    return datetime.combine(target_date, datetime.min.time()).replace(hour=hour, minute=minute)


def ensure_event_datetime(row):
    event_id, title, date_text, time_text, person, created_at, event_datetime = row

    if event_datetime:
        try:
            return datetime.fromisoformat(event_datetime)
        except Exception:
            return None

    parsed = parse_event_datetime(date_text, time_text, created_at)
    if not parsed:
        return None

    conn = db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE events SET event_datetime = ? WHERE id = ?",
        (parsed.isoformat(timespec="seconds"), event_id)
    )
    conn.commit()
    conn.close()

    return parsed


def check_reminders():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, title, date_text, time_text, person, created_at, event_datetime,
               reminder_24h_sent, reminder_1h_sent, reminder_15m_sent
        FROM events
        WHERE done = 0
    """)

    rows = cur.fetchall()
    conn.close()

    current = now()

    for row in rows:
        event_id = row[0]
        title = row[1]
        date_text = row[2] or ""
        time_text = row[3] or ""
        person = row[4] or ""
        created_at = row[5]
        event_datetime = row[6]
        sent_24h = row[7] or 0
        sent_1h = row[8] or 0
        sent_15m = row[9] or 0

        dt = ensure_event_datetime((event_id, title, date_text, time_text, person, created_at, event_datetime))
        if not dt:
            continue

        minutes_left = (dt - current).total_seconds() / 60

        reminders = [
            ("24h", 1440, "reminder_24h_sent", sent_24h),
            ("1h", 60, "reminder_1h_sent", sent_1h),
            ("15m", 15, "reminder_15m_sent", sent_15m),
        ]

        for label, target_minutes, column, already_sent in reminders:
            if already_sent:
                continue

            if 0 <= minutes_left <= target_minutes:
                msg = (
                    "🔔 Recordatorio SQUANCH\n\n"
                    f"{title}\n"
                    f"Fecha/Hora: {dt.strftime('%Y-%m-%d %H:%M')}\n"
                    f"Faltan aprox: {label}"
                )

                if send_telegram(msg):
                    conn = db()
                    cur = conn.cursor()
                    cur.execute(f"UPDATE events SET {column} = 1 WHERE id = ?", (event_id,))
                    cur.execute(
                        "INSERT INTO activities (agent, action, summary, detail, ref_type, ref_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        ("Calendar Agent", "reminder_sent", f"Reminder {label}: {title}", msg, "event", event_id, now().isoformat(timespec="seconds"))
                    )
                    conn.commit()
                    conn.close()


def already_sent_daily_digest(today_str: str):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM daily_digests WHERE digest_date = ?", (today_str,))
    exists = cur.fetchone() is not None
    conn.close()
    return exists


def mark_daily_digest_sent(today_str: str):
    conn = db()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO daily_digests (digest_date, sent_at) VALUES (?, ?)",
        (today_str, now().isoformat(timespec="seconds"))
    )
    cur.execute(
        "INSERT INTO activities (agent, action, summary, detail, ref_type, ref_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("System", "daily_digest_sent", "Daily pending digest sent", today_str, "", None, now().isoformat(timespec="seconds"))
    )
    conn.commit()
    conn.close()


def get_open_tasks():
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT id, text, created_at FROM tasks WHERE done = 0 ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    return rows


def get_open_events():
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, title, date_text, time_text, person, created_at, event_datetime
        FROM events
        WHERE done = 0
        ORDER BY id DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return rows


def send_daily_digest_if_needed():
    current = now()

    # Manda una vez al día entre 11:00 y 11:04.
    if current.hour != 11 or current.minute > 4:
        return

    today_str = current.date().isoformat()

    if already_sent_daily_digest(today_str):
        return

    tasks = get_open_tasks()
    events = get_open_events()

    today_events = []
    no_date_events = []
    future_events = []

    for row in events:
        event_id, title, date_text, time_text, person, created_at, event_datetime = row
        dt = ensure_event_datetime(row)

        if dt and dt.date() == current.date():
            today_events.append((event_id, title, dt, person))
        elif dt:
            future_events.append((event_id, title, dt, person))
        else:
            no_date_events.append((event_id, title, date_text, time_text, person))

    lines = []
    lines.append("📋 SQUANCH — Pendientes de hoy")
    lines.append(f"{current.strftime('%Y-%m-%d')} · 11:00\n")

    lines.append("📅 HOY")
    if today_events:
        for event_id, title, dt, person in sorted(today_events, key=lambda x: x[2]):
            extra = f" — {person}" if person else ""
            lines.append(f"• {dt.strftime('%H:%M')} — {title}{extra}")
    else:
        lines.append("• No tienes eventos para hoy.")

    lines.append("\n🧾 TASKS SIN FECHA")
    if tasks:
        for task_id, text, created_at in tasks:
            lines.append(f"• #{task_id} {text}")
    else:
        lines.append("• No tienes tasks pendientes.")

    lines.append("\n❓ EVENTOS SIN FECHA CLARA")
    if no_date_events:
        for event_id, title, date_text, time_text, person in no_date_events:
            raw = " ".join([date_text or "", time_text or ""]).strip()
            raw = f" — {raw}" if raw else ""
            lines.append(f"• #{event_id} {title}{raw}")
    else:
        lines.append("• Ninguno.")

    lines.append("\n🔜 PRÓXIMOS")
    upcoming = sorted(future_events, key=lambda x: x[2])[:5]
    if upcoming:
        for event_id, title, dt, person in upcoming:
            lines.append(f"• {dt.strftime('%d %b %H:%M')} — {title}")
    else:
        lines.append("• No hay próximos eventos con fecha.")

    msg = "\n".join(lines)

    if send_telegram(msg):
        mark_daily_digest_sent(today_str)




def sync_google_calendar_to_squanch():
    if not list_upcoming_google_events:
        return

    try:
        google_events = list_upcoming_google_events(max_results=30)
    except Exception as e:
        print("Google Calendar sync error:", e)
        return

    conn = db()
    cur = conn.cursor()

    imported = 0

    for item in google_events:
        google_id = item.get("id") or ""
        title = item.get("summary") or "Evento Google Calendar"
        link = item.get("htmlLink") or ""
        start = item.get("start", {})

        event_datetime = start.get("dateTime") or start.get("date") or ""

        if not google_id or not event_datetime:
            continue

        exists = cur.execute(
            "SELECT id FROM events WHERE google_event_id = ?",
            (google_id,)
        ).fetchone()

        if exists:
            continue

        cur.execute(
            """
            INSERT INTO events (
                title,
                date_text,
                time_text,
                person,
                done,
                created_at,
                event_datetime,
                google_event_id,
                google_event_link
            )
            VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?)
            """,
            (
                title,
                "Google Calendar",
                "",
                "",
                now().isoformat(timespec="seconds"),
                event_datetime[:19],
                google_id,
                link
            )
        )

        event_id = cur.lastrowid

        cur.execute(
            """
            INSERT INTO activities (
                agent,
                action,
                summary,
                detail,
                ref_type,
                ref_id,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "Calendar Agent",
                "synced",
                title,
                "Imported from Google Calendar",
                "event",
                event_id,
                now().isoformat(timespec="seconds")
            )
        )

        imported += 1

    conn.commit()
    conn.close()

    if imported:
        print(f"Google Calendar sync imported {imported} events")


def main():
    ensure_daily_table()

    print("SQUANCH reminder worker running...")
    print("Daily digest active at 11:00.")

    while True:
        try:
            sync_google_calendar_to_squanch()
            check_reminders()
            send_daily_digest_if_needed()
        except Exception as e:
            print("worker error:", e)

        time.sleep(60)


if __name__ == "__main__":
    main()
