# Accessibility notes

The brief asks us to "design with accessibility in mind: readable fonts, good contrast, keyboard use, clear
language" and to "run a quick accessibility check and note what you found". This page covers what we built in,
how we checked it, what the check found, and what we haven't tested yet.

## Summary

- We checked **14 pages** covering every role (reporter, case handler, field officer, manager) at **three
  widths** (1280px desktop, 375px phone, 320px narrow phone): 42 checks in all, plus a keyboard walk-through.
- The check found **four problems**: two contrast failures, and two pages that scrolled sideways on phones.
  **All four are fixed**, and a re-run of all 42 checks came back clean.
- We have **not yet tested with a screen reader** (NVDA, JAWS or VoiceOver) or with disabled users. That is the
  most important next step before real use.

## How we checked (13 November 2026)

| What | How |
|---|---|
| Pages | Sign in; the reporter's home, Report an issue, My reports and a report's tracking page; the Case queue, Triage, a case page and Change assignment; My jobs, a job page and Alerts; the Dashboard and People |
| Widths | 1280px, 375px and 320px (320px is the narrowest width WCAG 2.2's reflow rule, 1.4.10, asks pages to work at without sideways scrolling) |
| Automated checks | Page language and title; one `<main>` and one `<h1>`; heading levels in order; images have alt text; every form field and button has a name; no duplicate IDs; every `aria-labelledby`, `aria-describedby` and `aria-controls` points at something; text contrast against WCAG AA (4.5:1, or 3:1 for large text); no sideways scrolling |
| Keyboard | From the top of the Report form: Tab reaches the skip link first, the skip link moves focus into the main content, and fields show a visible focus ring |

We planned to use axe-core for the automated checks, but our tooling doesn't allow loading outside scripts into
the page, so we wrote our own checks for the WCAG rules above instead. A free axe or Lighthouse scan (both are
built into Chrome's developer tools) would be a good second opinion.

## What we found and fixed

| Found | Where | WCAG | Fix |
|---|---|---|---|
| Link text 4.2:1 (needs 4.5:1): Bootstrap's link blue on our grey page background | "← Back to queue", "Forgot your password?", "See all my reports" and other links outside the white panels | 1.4.3 Contrast | Links now use a darker blue (`#0a58ca`, 6:1) |
| Button text 4.4:1: Bootstrap's grey outline buttons | "Unread" on Alerts, "Record a voice note" | 1.4.3 Contrast | These buttons now use our muted ink colour (7:1) |
| People page scrolled sideways on phones | The roles table | 1.4.10 Reflow | On phones each person becomes a card, like the other tables |
| Dashboard scrolled sideways at 320px | "Workload by team" | 1.4.10 Reflow | On phones each team becomes a card; the table also got a caption for screen readers |

We also added a **reduced motion** setting: people who ask their device for less motion get no animated
transitions or smooth scrolling.

## What's built in

**Reading and seeing**
- Body text is 17px, in Inter, with a consistent type scale and generous line spacing.
- Colours are design tokens chosen for contrast: the brand teal is 8.6:1 on white, and muted text is 7:1.
- Nothing relies on colour alone. Priorities, statuses and alerts always have a word ("Urgent", "Overdue",
  "New"), and the urgency cards have icons as well.
- The chart colours were checked with a palette validator for colour blindness, contrast and lightness. Every
  chart has a "Show as a table" view, and the latest full week's values are written on the chart.
- Pages work from 320px wide. Tables become cards on phones, and the Case queue and dashboard tabs become a grid
  of large buttons.

**Keyboard and assistive technology**
- A "Skip to main content" link, `lang="en-gb"`, landmarks (header, navigation, main, footer) and one `h1` per
  page.
- A visible focus outline on every link and button, and a teal ring on form fields.
- Form fields and main buttons are 44px tall, so they are easy to tap.
- Sortable table headings are buttons that announce their sort order (`aria-sort`).
- Tabs (Case queue, Needs attention) follow the standard pattern: arrow keys, Home and End.
- Updates are announced: filter results ("Showing 3 of 12 cases"), unread counts ("Alerts, 2 unread"), the
  location, map and voice note status messages, and the photo upload.
- Form errors appear next to the field, in words, and the reporter's answers are kept.

**Other ways to do things**
- **Location:** pick a building from a list, type an address, use the device's location, or drop a pin on a map.
  The map also works by keyboard (arrow keys to move, then "Pin the centre of the map").
- **Photos:** drag and drop, tap to use the camera, or the normal file picker if JavaScript is off.
- **Officers' notes:** type, dictate (Chrome and Edge), or record a voice note.
- **Language:** reporters choose English, Polish, Urdu or Spanish, and every message to them is in that language.
  Urdu is set right to left.
- **Clear language:** plain words and short sentences ("What is the problem?", "Who is affected?"), no jargon,
  and the reference number is always shown.

## Known gaps and next steps

1. **Screen reader testing.** Test the report form, tracking page and officer job page with NVDA (Windows) and
   VoiceOver (iPhone), ideally with people who use them every day.
2. **The map.** The OpenStreetMap map is hard to use with a screen reader. Every other way of giving a location
   still works, so nobody depends on it.
3. **Dictation** only works in Chrome and Edge. Typing and voice notes work everywhere.
4. **Translations** of the reporter messages were written for this prototype and need checking by native
   speakers.
5. **Not covered by our check:** the Django admin pages, text over images, and zoom to 200% on desktop (the 320px
   check covers most of the same ground).
6. **Who could be left out?** People without a smartphone or internet access. A phone line or a kiosk that puts
   reports into the same system would help, and the form's plain wording would carry over to a script for staff.
