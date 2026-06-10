import json
import shlex
import sqlite3
import subprocess
import time
from datetime import datetime

DB_PATH = "squanch.db"
PROJECT_ROOT = "/home/dpnhclawd/jarvis"

SAFE_COMMANDS = {
    "pwd": ["pwd"],
    "git status": ["git", "status"],
    "git diff": ["git", "diff"],
    "git log": ["git", "log", "--oneline", "-5"],
    "ls": ["ls"],
    "ls backend": ["ls", "backend"],
    "ls dashboard": ["ls", "dashboard"],
    "python version": ["python3", "--version"],
    "node version": ["node", "--version"],
    "npm version": ["npm", "--version"],
}


def now():
    return datetime.now().isoformat(timespec="seconds")


def db():
    return sqlite3.connect(DB_PATH)


def get_next_executor_job():
    conn = db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, prompt
        FROM jobs
        WHERE agent = 'Executor Agent'
          AND status = 'queued'
        ORDER BY id ASC
        LIMIT 1
        """
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return {"id": row[0], "prompt": row[1]}


def update_job(job_id, status, result=None):
    conn = db()
    cursor = conn.cursor()

    if result is None:
        cursor.execute(
            "UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?",
            (status, now(), job_id),
        )
    else:
        cursor.execute(
            "UPDATE jobs SET status = ?, result = ?, updated_at = ? WHERE id = ?",
            (status, result, now(), job_id),
        )

    conn.commit()
    conn.close()


def add_activity(agent, action, summary, detail="", ref_type="job", ref_id=None):
    conn = db()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO activities (agent, action, summary, detail, ref_type, ref_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (agent, action, summary, detail, ref_type, ref_id, now()),
    )
    conn.commit()
    conn.close()


def normalize_prompt(prompt):
    text = (prompt or "").strip().lower()

    prefixes = [
        "run ",
        "ejecuta ",
        "executor ",
        "terminal ",
        "cmd ",
        "command ",
    ]

    for prefix in prefixes:
        if text.startswith(prefix):
            text = text[len(prefix):].strip()

    return text


def run_safe_command(prompt):
    command_key = normalize_prompt(prompt)

    if command_key not in SAFE_COMMANDS:
        allowed = "\n".join([f"- {cmd}" for cmd in SAFE_COMMANDS.keys()])
        return (
            "Command rejected by Executor Agent safety policy.\n\n"
            f"Requested: {prompt}\n\n"
            "Allowed commands:\n"
            f"{allowed}"
        )

    cmd = SAFE_COMMANDS[command_key]

    try:
        result = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )

        output = ""
        output += f"$ {shlex.join(cmd)}\n\n"

        if result.stdout:
            output += result.stdout

        if result.stderr:
            output += "\nSTDERR:\n" + result.stderr

        output += f"\n\nExit code: {result.returncode}"

        return output[-8000:]

    except subprocess.TimeoutExpired:
        return "Command timed out after 60 seconds."
    except Exception as e:
        return f"Executor Agent error: {e}"


def main():
    print("SQUANCH Executor Agent v0.1 started.")
    print("Listening for queued Executor Agent jobs...")

    while True:
        job = get_next_executor_job()

        if not job:
            time.sleep(2)
            continue

        job_id = job["id"]
        prompt = job["prompt"]

        print(f"Running job #{job_id}: {prompt}")

        update_job(job_id, "working")
        add_activity(
            "Executor Agent",
            "working",
            f"Job #{job_id}",
            detail=prompt,
            ref_type="job",
            ref_id=job_id,
        )

        result = run_safe_command(prompt)

        update_job(job_id, "completed", result)
        add_activity(
            "Executor Agent",
            "completed",
            f"Job #{job_id}",
            detail=result,
            ref_type="job",
            ref_id=job_id,
        )

        print(f"Completed job #{job_id}")


if __name__ == "__main__":
    main()
