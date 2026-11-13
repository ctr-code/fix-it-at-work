# Security notes

The brief asks for a solution that is "secure by design", with "no connection to real systems and no passwords or
keys in shared files or screenshots", and for us to explain our security considerations in the presentation.
This page sets out what we did, what we checked, and what would still need doing before real use.

## Summary

- **Fictional data only, and no real systems.** No real people, addresses or organisations. Emails are printed
  in the server window, not sent. The AI runs inside the app, so no report text goes to an outside AI service.
- **Everyone sees only what their role allows.** Every page and every action checks the user's role on the
  server, not just in the menu. Reporters see only their own reports, and officers only their own team's jobs.
- **Standard web protections are on.** CSRF tokens on every form, escaped output, protection against the site
  being framed by other sites, rate-limited sign-in, and strong-password rules.
- **People decide; the AI suggests.** Every routing decision, duplicate merge and outgoing letter is approved by
  a named person, and every change is recorded.
- **Not production-ready yet.** HTTPS settings, private file storage and real email need finishing before real
  use (see the last section).

## Data

| What we hold | Why | How it's protected |
|---|---|---|
| Reporter's name and email (from their account) | To reply to them | Visible only to staff and to the reporter themselves |
| Report text, building and room | To find and fix the problem | Role-based access (below) |
| **Exact location** (optional) | To find problems outside a building | Only taken when the reporter presses "Use my current location" or drops a pin, and they can remove it before sending. Rounded to about a metre |
| **Photos** (reports and visits) and **voice notes** (visits) | Evidence for the fix | Only JPG, PNG and WEBP photos (10MB each, 5 at a time) and audio recordings (20MB) are accepted, checked on the server by type and size. See *Known risks* for how they're stored |
| Who did what, and when | Accountability | Triage, change history, alerts, messages and letters all record the person and the time |

All demo data is fictional: made-up names, `example.com` email addresses, and addresses such as "10 Example
Square". The buildings' map points are general spots in Birmingham, not anyone's home.

## Secrets and configuration

- The secret key, database address and demo password live in a `.env` file, which `.gitignore` keeps out of the
  repository. The README says never to commit it, and no password appears in code, docs or screenshots.
- `DEBUG` is **off unless** the environment turns it on, and the allowed host names come from the environment.
- **One slip, now fixed:** a temporary test page was committed by mistake. It held fictional demo names and
  emails and some expired security tokens, no passwords. We removed it and added a `.gitignore` rule so test
  pages can't be committed again, but it's still in the Git history.

## Signing in and roles

- Sign-in uses django-allauth, with Django's password rules (minimum length, not too common, not all numbers, not
  too similar to the username).
- allauth's **rate limits** are on, e.g. 10 failed sign-ins a minute per IP address and 5 every 5 minutes per
  account, which slows down password guessing.
- **Everyone who signs up is a Reporter.** Only a Manager can give someone a staff role (People page), and nobody
  can change their own role.

## Who can see and do what

Every view checks permissions on the server (`role_required` and `can_view_case` in `cases/permissions.py`), so
hiding a link is never the only protection:

| Role | Can | Can't |
|---|---|---|
| Reporter | Report, see and add to their **own** reports, rate the fix | See anyone else's report or any staff page |
| Field officer | See their **own team's** jobs and record visits on jobs assigned to them; see alerts for them and their team | Open another team's job, record a visit on someone else's job or a closed job, see the Case queue |
| Case handler | Triage, merge duplicates, change priority or assignment, approve letters | Use the Dashboard or People page |
| Manager | Everything a handler can, plus the Dashboard and roles | Change their own role |

Automated tests (141 in total) cover these rules, for example that officers and reporters are refused the
Change assignment page, that officers can't see another team's alerts, and that staff opening a report don't
mark the reporter's messages as read.

## Web protections

- **Forms:** every form that changes data is a POST with Django's CSRF token (all 9 of them).
- **Cross-site scripting:** templates escape everything by default. Our JavaScript puts user text on the page
  with `textContent`, never as HTML, and data passed to scripts uses Django's `json_script`.
- **Clickjacking:** `X-Frame-Options` stops other sites framing the app.
- **Outside code:** the only outside script is the map library (Leaflet, from cdnjs). It loads only when a
  reporter presses "Pick on a map", is pinned with a **Subresource Integrity** hash so the browser refuses it if
  it's been changed, and doesn't send our page address. Map links open OpenStreetMap with `noopener noreferrer`.
- **Other external services:** the Inter font loads from Google Fonts on every page, which shares visitors' IP
  addresses with Google. Bootstrap and the icons are served from our own site. Hosting the font ourselves would
  remove this.

## AI and human approval

- The AI (`cases/ai.py`) is rule-based and runs inside the app, so no report text is sent to an outside AI
  service.
- A person approves every decision that affects someone: routing, duplicate merges and outgoing letters.
  Officers can only change their own jobs.
- AI suggestions are labelled as AI, and the dashboard tracks how often staff accept them.

## Known risks and what we'd do before real use

`python manage.py check --deploy` (Django's own production checklist) reports five things, all expected for a
prototype:

| Risk | What to do |
|---|---|
| HTTPS isn't enforced; cookies can travel without HTTPS (`SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`) | Turn these on in production behind HTTPS |
| Email uses the console backend | Use a real mail service with its key in the environment, never in code |
| **Uploaded photos and voice notes are served from `/media/` without checking who's signed in** (in development), and file names can be guessed | Store uploads in private cloud storage (for example S3 or Azure Blob) and serve them through a view that checks `can_view_case`, using short-lived signed links |
| In production, uploads aren't served at all, and Heroku's disk is wiped on restart | The same private storage fixes both |
| Voice notes and exact locations are personal data | Set how long they're kept (for example, delete voice notes 90 days after a case closes) and say so in a privacy notice |
| Old test page in Git history | Rotate anything sensitive it could expose (nothing real was in it) and, if needed, rewrite the history |
| No security headers beyond Django's defaults | Add a Content Security Policy allowing only our own site, Google Fonts, cdnjs and the OpenStreetMap tiles (or host the font ourselves) |

Other next steps: run a dependency audit (`pip-audit`) in CI, add two-factor sign-in for staff, and log role
changes as well as case changes.
