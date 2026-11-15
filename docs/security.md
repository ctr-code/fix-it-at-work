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
- **Not production-ready yet.** HTTPS settings and real email need finishing before real use (see the last
  section).

## Data

| What we hold | Why | How it's protected |
|---|---|---|
| Reporter's name and email (from their account) | To reply to them | Visible only to staff and to the reporter themselves |
| Report text, building and room | To find and fix the problem | Role-based access (below) |
| **Exact location** (optional) | To find problems outside a building | Only taken when the reporter presses "Use my current location" or drops a pin, and they can remove it before sending. Rounded to about a metre |
| **Photos** (reports and visits) and **voice notes** (visits) | Evidence for the fix | Only JPG, PNG and WEBP photos (10MB each, 5 at a time) and audio recordings (20MB) are accepted, checked on the server by type and size. Stored in **Cloudinary** when it's set up (see *Uploaded files*), otherwise in the app's `media` folder |
| Who did what, and when | Accountability | Triage, change history, alerts, messages and letters all record the person and the time |

All demo data is fictional: made-up names, `example.com` email addresses, and addresses such as "10 Example
Square". The buildings' map points are general spots in Birmingham, not anyone's home.

## Secrets and configuration

- The secret key, database address, demo password and Cloudinary key (`CLOUDINARY_URL`) live in a `.env` file, which `.gitignore` keeps out of the
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

Automated tests (208 in total) cover these rules, for example that officers and reporters are refused the
Change assignment page, that officers can't see another team's alerts, and that staff opening a report don't
mark the reporter's messages as read.

## Web protections

- **Forms:** every form that changes data is a POST with Django's CSRF token (all 13 of them).
- **Cross-site scripting:** templates escape everything by default. Our JavaScript puts user text on the page
  with `textContent`, never as HTML, and data passed to scripts uses Django's `json_script`.
- **Clickjacking:** `X-Frame-Options` stops other sites framing the app.
- **Outside code:** the only outside script is the map library (Leaflet, from cdnjs). It loads only when a
  reporter presses "Pick on a map", is pinned with a **Subresource Integrity** hash so the browser refuses it if
  it's been changed, and doesn't send our page address. Map links open OpenStreetMap, and the officer's
  "Directions" link opens Google Maps, both with `noopener noreferrer`; neither sends anything until it's opened.
- **Other external services:** the Inter font loads from Google Fonts on every page, which shares visitors' IP
  addresses with Google. Bootstrap and the icons are served from our own site. Hosting the font ourselves would
  remove this.

## Uploaded files

Report photos, visit photos and voice notes are stored in one of two places:

- **Cloudinary**, when `CLOUDINARY_URL` is set (for example on Heroku). Files survive restarts. Photos are stored
  as images and voice notes as audio, all as Cloudinary's **authenticated** type, so Cloudinary refuses their plain
  links.
- **The app's `media` folder**, when it isn't (local development). It isn't served at `/media/` at all.

Either way, the server checks every file's type and size before it's saved, and **links are private**
(`cases/files.py`, since 15 November):

- Every photo and voice note is reached through `/files/<name>`. That view finds the case the file belongs to and
  only sends it to someone allowed to see that case (`can_view_case`): the reporter, staff, or officers in the
  case's team. Anyone else, or a file that doesn't exist, gets "not found", so a copied link gives nothing away.
  Signed-out visitors are sent to sign in.
- Locally the view sends the file itself, marked `private` (never kept by shared caches) and `nosniff`, with a
  Content Security Policy that stops an upload ever running as a page.
- With Cloudinary it redirects to a **signed link that expires after 5 minutes**.
- Files uploaded to Cloudinary **before** this change are still public until someone runs
  `python manage.py make_uploads_private` once where Cloudinary is used (it has a `--dry-run`). It moves each one
  to the authenticated type and is safe to run again. This couldn't be run from the development computer, which
  doesn't use Cloudinary.

**One thing still needs care:**

- **Cloudinary is an outside service** that holds personal data (photos and voice recordings). Real use would
  need a data processing agreement and a check of where it stores data. This doesn't break the brief's "no
  connection to real systems" rule for the demo, because only fictional data is uploaded.

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
| Uploads made to Cloudinary before private links are still public | Run `python manage.py make_uploads_private` once on the server that uses Cloudinary |
| Photos and voice notes are held by an outside service (Cloudinary) | A data processing agreement, and storage in the UK or EU |
| Voice notes and exact locations are personal data | Set how long they're kept (for example, delete voice notes 90 days after a case closes) and say so in a privacy notice |
| Old test page in Git history | Rotate anything sensitive it could expose (nothing real was in it) and, if needed, rewrite the history |
| No security headers beyond Django's defaults | Add a Content Security Policy allowing only our own site, Google Fonts, cdnjs, the OpenStreetMap tiles and Cloudinary (or host the font ourselves) |

Other next steps: run a dependency audit (`pip-audit`) in CI, add two-factor sign-in for staff, and log role
changes as well as case changes.
