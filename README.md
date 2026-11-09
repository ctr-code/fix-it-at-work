# Fix It at Work

WMCA AI Hackathon, "Request to Resolution", Setting B (workplace and facilities).
A person reports a workplace issue, AI helps triage it, an officer fixes it, the reporter gets a reply in their
language, and managers see how well it's working. All data is fictional.

## Run it locally (Windows)

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # psycopg2 may fail on Python 3.14 - not needed locally
.venv/Scripts/python manage.py migrate
.venv/Scripts/python manage.py seed_demo                   # loads fictional demo data (re-run to reset)
.venv/Scripts/python manage.py runserver
```

Create a `.env` file first with `DJANGO_DEBUG=True`, a `DJANGO_SECRET_KEY` and a `DEMO_PASSWORD` (used for all demo
logins - never commit it). Without `DATABASE_URL` it uses SQLite. Then open http://localhost:8000 in Chrome.

## Accounts and roles

Sign-in and sign-up use django-allauth. Each user has one role, and the home page and menu change to match it.

| Role | Can do | Demo login |
|---|---|---|
| Reporter | Report issues, see only their own reports | `alex` |
| Case handler | Triage, merge duplicates, approve outcome letters | `jo` |
| Field officer | See and update their own team's jobs | `sam`, `priya`, `tom`, `aisha`, `dan`, `mei`, `grace`, `owen` |
| Manager | Everything a handler can, plus the dashboard and the People page | `rob` |

Everyone who signs up starts as a Reporter. Only a Manager can give someone a staff role (People page), and a
Django superuser is treated as a Manager.

## The journey (one screen per stage)

| Stage | Who | URL |
|---|---|---|
| 1. Report | Reporter | `/report/`, track at `/track/` |
| 2. Triage and route | Case handler | `/triage/` |
| 3-4. Attend and record | Field officer (mobile) | `/officer/` |
| 5. Respond | Case handler | "Review AI letter" on `/triage/` |
| 6. Review | Manager | `/dashboard/`, roles at `/people/` |

## Where AI is used (`cases/ai.py`)

All AI lives in one file so it can be swapped for a real model. The current version is rule-based, so it works
offline with no keys.

- **Triage**: suggests category, priority, team and a possible duplicate, with reasons and a confidence score.
- **Visit summary**: turns an officer's typed or dictated note (Chrome speech-to-text) into a short case note.
- **Outcome letter**: drafted in the reporter's language (English, Polish, Urdu, Spanish).

Responsible AI choices:
- A person approves every triage decision, duplicate merge and outgoing letter.
- AI content is always shown in a purple "AI" box, and the reporter is told when AI helped write their letter.
- AI never sets a lower priority than the reporter chose. Safety words are checked in several languages, and
  vague reports get low confidence and a "check carefully" flag instead of a low priority.
- The dashboard tracks how often staff accept the AI's suggestion.
