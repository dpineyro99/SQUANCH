import os.path
from pathlib import Path
from datetime import datetime, timedelta

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

BASE_DIR = Path(__file__).resolve().parent
CREDENTIALS_PATH = BASE_DIR / "credentials.json"
TOKEN_PATH = BASE_DIR / "token.json"

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
TIMEZONE = "America/Mexico_City"


def get_calendar_service():
    creds = None

    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_PATH, "w") as token:
                token.write(creds.to_json())
        else:
            raise RuntimeError("Google Calendar no está autorizado. Ejecuta google_calendar_test.py primero.")

    return build("calendar", "v3", credentials=creds)


def create_google_event(title: str, event_datetime: str | None, description: str = ""):
    if not event_datetime:
        return None

    start = datetime.fromisoformat(event_datetime)
    end = start + timedelta(hours=1)

    service = get_calendar_service()

    event = {
        "summary": title,
        "description": description or "Creado por SQUANCH.",
        "start": {
            "dateTime": start.isoformat(),
            "timeZone": TIMEZONE,
        },
        "end": {
            "dateTime": end.isoformat(),
            "timeZone": TIMEZONE,
        },
    }

    created = service.events().insert(calendarId="primary", body=event).execute()

    return {
        "id": created.get("id"),
        "htmlLink": created.get("htmlLink"),
    }


def list_upcoming_google_events(max_results: int = 20):
    from datetime import datetime, timezone

    service = get_calendar_service()

    now_iso = datetime.now(timezone.utc).isoformat()

    events_result = service.events().list(
        calendarId="primary",
        timeMin=now_iso,
        maxResults=max_results,
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    return events_result.get("items", [])
