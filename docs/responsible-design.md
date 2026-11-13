# Responsible-design checklist

The brief's checklist asks five questions: who uses this and who could be left out, what data it uses, where AI
helps and where a human decides, what could go wrong, and how we would know. This page answers each one for Fix
It at Work, with the evidence behind it. The [accessibility notes](accessibility.md) and
[security notes](security.md) go into more detail on those two areas.

## 1. Who uses this, and who could be left out?

| Who | What they need | How we've designed for them |
|---|---|---|
| **Reporters** (any employee) | A quick way to report, to know it's been received, and a clear answer | A short report form with plain questions, a reference number straight away, updates at every stage, and a My reports page |
| **Case handlers** | Reports arriving in the right place with less admin | AI-suggested team, category, priority and duplicates, which they approve or change; counts of what's waiting |
| **Field officers** | A simple mobile view and a fast way to record visits | My jobs on a phone, alerts for new jobs, dictation, voice notes and photos |
| **Managers** | Workload, delays and performance | A dashboard with Needs attention, weekly trends and where time goes |

**Who could be left out, and what we did about it:**

| At risk | Why | What we did | Still a gap |
|---|---|---|---|
| People who don't read English well | Forms and replies in English; the AI matches English words | Reporters choose English, Polish, Urdu or Spanish, and every message to them is in that language (Urdu right to left). The AI recognises danger words in all four, and **never suggests a lower priority than the reporter chose** | The page itself is in English. The AI misses some categories in other languages (see 4). Translations need checking by native speakers |
| Disabled people | Screen readers, keyboard-only use, low vision, motion sensitivity | Checked against WCAG AA on 14 pages at three widths, with problems fixed. Several ways to do each thing (type, dictate or record; pick a building, type an address or drop a pin) | Not yet tested with screen readers or with disabled users |
| People who write briefly or with spelling mistakes | The AI has less to go on | The AI tolerates near-miss spellings and flags short or unclear reports as low confidence so a person checks them | Misspelled key words can still lower the suggested priority (see 4) |
| People without a smartphone or computer at work | The service is online only | Works on any phone browser; nothing to install | A phone line or kiosk would be needed for full reach |
| Officers in poor signal | Visits recorded on site | Light pages; voice notes and photos are optional | No offline mode |

## 2. What data does it use?

- **Only fictional data.** Demo people, `example.com` email addresses, made-up building addresses, and the brief's
  categories and SLA table. No real personal data was used to build or test it.
- **What a real deployment would hold:** the reporter's name and email (from their account), the report text and
  photos, an **optional exact location** (only when the reporter chooses to share it, rounded to about a metre),
  the officers' notes, photos and **optional voice notes**, and a record of who did what and when.
- **No data leaves the app for AI.** The AI is rule-based and runs inside the app, so report text isn't sent to an
  outside AI service. If a real model replaced it, that would need a data agreement and a check of where the data
  goes.
- **Minimal by default.** Location, photos and voice notes are optional, and reporters can remove a location
  before sending.
- **Where uploads go:** photos and voice notes are stored in Cloudinary, an outside service, when it's set up.
  Only fictional files are uploaded in the demo; real use would need a data processing agreement.

## 3. Where does AI help, and where does a human decide?

| AI suggests or drafts | A person decides | How people know AI was involved |
|---|---|---|
| Team, category and priority for a new report, with reasons and a confidence score | The case handler approves or changes them at triage, and can change them later (each change is logged with their name and a reason) | Shown in a purple "AI suggestion" box with its reasoning; the dashboard tracks how often staff accept it |
| A possible duplicate of an open case | The handler decides whether to merge | "Possible duplicate" with a link to compare |
| A short summary of each officer's visit | The officer writes the notes, and their full notes are kept beside the summary | Labelled "AI summary" |
| The outcome letter to the reporter, in their language | The handler edits and approves it before it's sent | The reporter's letter says it was drafted with AI help and names who checked it |

**The AI never sends anything to a reporter on its own, and never closes, merges or routes a case.** Automatic
messages (receipt, progress updates) are fixed templates, not AI.

## 4. What could go wrong?

| Risk | Likelihood | What we did | What's left |
|---|---|---|---|
| **A report in poor English or another language gets a lower priority** | Medium | The AI never goes below the reporter's own urgency; danger words are recognised in four languages; a person approves every priority | In our test, a leak written as "watter leek from celing" got **medium** where the clear version got **high** (see *Fairness*) |
| **A safety risk is missed** | Low | Danger words such as fire, sparks, gas, flood and injured raise the priority to urgent; the reporter can tick "This could hurt someone"; urgent and unsafe jobs with no officer go to the top of the dashboard | Unusual wording could still be missed, which is why a person triages every report |
| **The AI puts a report in the wrong team** | Low to medium | Confidence scores, written reasons, a person approves, and routing can be changed later with a logged reason | Reports in other languages may get no category and need a person to choose |
| **Staff over-trust the AI** ("automation bias") | Medium | Low-confidence and short reports are flagged "a person should check"; the dashboard shows the acceptance rate so a suspiciously high rate can be noticed | Needs training and review in real use |
| **Wrong duplicate merge** | Low | Only merged by a person; the reporter is told which case it was linked to | One known false match in testing (same room and category, different problem) |
| **Personal data exposed** | Low | Role-based access checked on the server for every page; reporters see only their own reports, and officers only their team's | Uploaded photos and voice notes are kept in Cloudinary but their links are public, so they need private links before real use (see the security notes) |
| **A deadline is promised that can't be met** | Medium | SLA targets in working days, as in the brief; the reporter is told when the date changes; Needs attention shows what's overdue or due within 24 hours | Targets are the brief's illustrative ones and would need agreeing with each team |

## 5. How would we know?

**Already built in**
- **Automated tests (151).** These include an AI benchmark of 63 realistic reports (category 63/63, priority
  60/63) that fails if accuracy drops, and **fairness tests** that fail if any report in poor English or another
  language is suggested below the reporter's urgency, or if danger is missed in any language.
- **Dashboard measures:** how often staff accept the AI's suggestion, first-time fix rate, resolved within SLA,
  reporter satisfaction, weekly reports in against fixes out, and the median time at each stage.
- **Audit trail:** who triaged each case and whether they accepted or changed the AI's suggestion; every later
  change to priority, team or officer, with the reason; every alert and message, and who approved each letter.
- **Unhappy reporters:** scores of 2/5 or lower, with comments, are listed for handlers to follow up and shown on
  the dashboard.

**What we'd add in real use**
1. **Compare outcomes by language:** acceptance rate, how often staff raised the AI's priority, time to fix and
   satisfaction, split by the reporter's chosen language. A gap would show bias the tests miss.
2. **Review overrides monthly:** every case where staff raised the AI's priority is a possible miss, so feed those
   reports back into the benchmark.
3. **Ask disabled users and non-English speakers to try it**, and run screen-reader tests.
4. **Watch for over-trust:** if acceptance goes above about 95%, sample cases to check people are still checking.

## Fairness: what we tested (13 November 2026)

The brief asks: *"could the AI under-prioritise reports written in poor English or in another language? Test and
explain how you reduced the risk."*

**Test 1: the AI benchmark.** 63 realistic reports, each with the answer a sensible case handler would give.
16 were written after the rules were tuned, as a fairer check.

| Group | Reports | Right category | Right priority | Under-prioritised |
|---|---|---|---|---|
| Polish, Spanish or Urdu | 5 | 5 | 5 | **0** |
| English | 58 | 58 | 55 | **0** |
| (Written after tuning) | 16 | 16 | 16 | 0 |

The three priority misses were all set **higher** than expected, never lower. Five non-English reports is a small
sample, so we ran a second test.

**Test 2: the same problem, written three ways.** The reporter chose "medium" each time.

| Problem | Clear English | Poor English | Another language |
|---|---|---|---|
| Socket sparking | Urgent, right team | Urgent, right team | Urgent (Urdu), **no category: a person chooses** |
| No heating | High, right team | High, right team | High, right team (Spanish) |
| Water through the ceiling | **High**, right team | **Medium**, right team: "leek" and "celing" weren't recognised | High (Polish), plumbing rather than roof |
| Printer jammed | Medium, right team | Medium, right team | Medium (Polish), **no category: a person chooses** |

**What this shows**
- **Safety risks were caught in every language and style**, and nothing was suggested below what the reporter
  asked for. These two guarantees are now automated tests.
- **The risk is reduced, not removed.** Poor spelling of a key word can still mean a lower suggested priority, and
  reports in other languages often get no category. In both cases the report is marked as low confidence, and a
  person makes the decision.

**How we reduced the risk**
1. The AI **never lowers** the reporter's own urgency, so whoever knows the problem best sets the minimum.
2. Danger words are recognised in **Polish, Urdu and Spanish** as well as English.
3. **Near-miss spellings** of category words are matched (e.g. "radiater").
4. Reports the AI can't place get **low confidence and a plain note** asking a person to choose, rather than a
   confident wrong answer.
5. A **person approves every priority**, and the reporter can tick "This could hurt someone", which raises the
   priority to at least high whatever the wording.

**Next steps:** add misspellings of the danger and leak words, more category words in each language, and a much
larger set of real (anonymised) reports in each language to test against; then compare outcomes by language in
real use (see 5).
