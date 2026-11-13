# Functional gaps

What the app still doesn't do, compared with the WMCA challenge brief and with what a real deployment would need.
Written 13 November 2026.

## Already closed

The first comparison with the brief found six functional gaps. All six are now built:

| Gap | Now |
|---|---|
| Teams weren't alerted automatically | Email alerts to the team and officer when a case is routed or changed, an Alerts page and an unread count |
| Location was free text only | Address, latitude and longitude on each case, from a building list, the reporter's location or a pin on a map |
| Visits stored one photo and no audio | Up to 5 photos, a voice note and the dictation transcript per visit |
| SLA rules didn't match the brief | The brief's table, counted in working hours and days, skipping weekends and bank holidays |
| No trends on the dashboard | Weekly reported vs resolved, and the median time at each stage |
| The receipt was English only | Every message to the reporter is in their chosen language |

Since then, a teammate's work (merged from main) closed most of another gap:

| Gap | Now |
|---|---|
| Uploads didn't work in production (not served, and lost when Heroku restarts) | Photos and voice notes are stored in **Cloudinary** when `CLOUDINARY_URL` is set, so they're kept and served in production. The links are still public (see below) |

## Still open

### 1. Would break in a real deployment

| Gap | Why it matters | Suggested fix |
|---|---|---|
| **Uploaded files have public links** | Anyone with the link to a photo or voice note can open it without signing in. The links are hard to guess and only shown to people allowed to see the case, but they can be copied or shared | Cloudinary's authenticated delivery, with files served through a view that checks the user can see the case, using short-lived signed links |
| **Cloudinary holds personal data** | Photos and voice recordings are stored by an outside service | A data processing agreement, and storage in the UK or EU |
| **Email is printed, not sent** | Right for the brief's "no real systems" rule, but nobody actually receives alerts or messages | A mail service, with its key in the environment |

### 2. Missing pieces of the journey

| Gap | Why it matters | Suggested fix |
|---|---|---|
| **No early warning for urgent or unsafe reports** | Teams are only alerted once a handler triages, so an urgent report sent late in the day waits in the queue. The dashboard only flags it after its response target has passed | Alert the case handlers (and the AI-suggested team, as a heads-up) as soon as an urgent or "could hurt someone" report arrives |
| **No "new details" flag** | When a reporter adds details or photos to an open case, or answers a handler's request for more information, the case page shows it but nothing flags it in the Case queue or on My jobs, so it's easily missed | A "New details" tag in the Case queue and on My jobs until a handler or the officer opens the case, plus an alert to the officer |
| **Unhappy reporters can't be ticked off** | They stay on the list for four weeks whatever is done, so they can't be counted in the Case queue badge | A "Followed up" button that records who followed up and when |
| **The outcome letter mixes languages** | A Polish letter is drafted in Polish, but "What we did" is the officer's notes in English | Translate the officer's action, or keep a short summary in the reporter's language and attach the full notes in English |

### 3. AI limits

These are explained in more detail in the [responsible-design checklist](responsible-design.md).

| Gap | Effect | Suggested fix |
|---|---|---|
| Misspelled danger and leak words ("leek", "celing") aren't recognised | The suggested priority can be lower than for the same report in clear English. It never drops below the reporter's own urgency, and a person approves it | Add common misspellings to the danger words, and extend near-miss matching to them |
| Reports in other languages often get no category | Safe (marked low confidence for a person to choose) but more work for handlers | More category words in Polish, Urdu and Spanish, or a multilingual AI model |
| One known false duplicate match | Same room and category, but a different problem | Weigh the description more heavily than the room |
| Sentences split at abbreviations; "Dr" taken as a first name | Visit summaries can cut a sentence short, and a letter can greet someone as "Dear Dr" | Recognise common abbreviations and titles |

### 4. Reach

| Gap | Why it matters | Suggested fix |
|---|---|---|
| Only messages to reporters are translated | The pages themselves are in English, which matters most on the report form | Translate the report form and tracking page first, with Django's translation tools |
| No offline mode | Officers in basements or poor signal can't record a visit | Save visits on the phone and send them when back online |
| No non-digital way to report | People without a smartphone or computer at work can't report | A phone line or kiosk where staff fill in the same form |
| One working week for every team | SLA targets use Mon–Fri 08:00–17:00 for all, although each team has its own working hours | Use each team's working hours for its cases |
| Bank holidays stop at the end of 2027 | Due dates after that would count holidays as working days | Add later years in the admin, or load them from the GOV.UK bank holidays feed |

### 5. Differences from the brief to explain in the pitch

| Difference | Why |
|---|---|
| **Platform:** the brief names Microsoft Power Platform; this is Django | Agreed team choice (to confirm with the organisers) |
| **Data model:** reporter details are stored on each case, not in a separate Reporter table | Simpler for a prototype; each case keeps the details as they were when reported. A Reporter table would avoid repeating them |

## Suggested order

1. **Early warning for urgent reports** and the **"new details" flag**, which most improve the journey for staff.
2. **Misspelled danger words**, which is a quick improvement to fairness.
3. **Private links for uploaded files**, before any real (non-fictional) photos or voice notes are uploaded.
4. Everything else as time allows.

If the demo runs on Heroku, check that `CLOUDINARY_URL` is set there, or uploads will be lost on each restart.
