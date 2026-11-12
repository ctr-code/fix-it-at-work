# User stories

Stories for each role, in the order the user meets them on their journey. Each one is either built (✅) or rated
by how important it is: **High**, **Medium** or **Low**.

## Reporter (any signed-up user)

| # | As a reporter, I want to… | Status |
|---|---|---|
| 1 | sign up and sign in with my username or email | ✅ |
| 2 | reset a forgotten password | ⚠️ allauth has the pages, but no email sending is set up, so it won't work. **High** |
| 3 | have my email address checked when I sign up | **Medium** (verification is off) |
| 4 | report an issue with its building, location, urgency, who's affected, health and safety risk and asset tag | ✅ |
| 5 | attach up to 5 photos to my report | ✅ |
| 6 | choose my language and how I'd like to be contacted | ✅ |
| 7 | report without an account, or for someone else | **Low** |
| 8 | get a reference number and a receipt straight away | ✅ (shown on screen only) |
| 9 | get updates by email, Teams or phone, as I chose | **High**: messages are only stored and shown on the tracking page, never sent |
| 10 | track my report's progress through each stage | ✅ |
| 11 | find a report by its reference | ✅ |
| 12 | see my open reports and recent closed ones on my home page | ✅ (only the last 5 closed ones) |
| 13 | see my full report history and search it | **Medium** |
| 14 | add more details or photos after I've reported | **High** |
| 15 | answer questions from the case handler | **High** |
| 16 | withdraw a report that's no longer needed | **Medium** |
| 17 | be told if my report was merged as a duplicate, and follow the original | ✅ I'm told and given the original's reference, but I can't see the original. That part is **Low** |
| 18 | get an outcome letter in my language, told when AI helped write it | ✅ |
| 19 | rate the outcome and comment, and change that within 14 days | ✅ |
| 20 | reopen a case that wasn't really fixed | **High** |
| 21 | use the site itself in my language, not just get letters in it | **Medium** |
| 22 | change my email address | ✅ |
| 23 | change my name, or delete my account and data | **Medium** (privacy law) |

## Case handler

| # | As a case handler, I want to… | Status |
|---|---|---|
| 1 | see what needs me on my home page: new reports, replies due, unhappy reporters, overdue cases | ✅ |
| 2 | see a triage queue ordered by the AI's priority, with filters | ✅ |
| 3 | see the AI's suggested category, priority and team, with its reasons and confidence | ✅ |
| 4 | accept or change the category, priority, team and officer | ✅ |
| 5 | merge a duplicate, with the AI suggesting a likely match | ✅ |
| 6 | have the deadline set and an acknowledgement recorded automatically | ✅ |
| 7 | ask the reporter for more information before triaging | **High** |
| 8 | search all cases by reference, keyword, reporter, status or date | **High**: there's no search outside Django admin |
| 9 | see in-progress cases with their teams, ordered by deadline and with filters | ✅ |
| 10 | change the priority, team or officer after triage | **High**: the case page is read-only after triage |
| 11 | add internal notes that the reporter can't see | **High** |
| 12 | be warned before a deadline is missed and when it has been | **High** (now only a count on the home page) |
| 13 | see a case's full record: visits and messages | ✅ |
| 14 | review and edit the AI's outcome letter, then approve it, which closes the case | ✅ |
| 15 | regenerate the letter, or change its language | **Low** |
| 16 | see unhappy reporters so I can follow up | ✅ |
| 17 | record that I followed up an unhappy reporter, and what happened | **Medium** |
| 18 | reopen a closed case, or undo a merge | **Medium** |
| 19 | see who changed what on a case, and when | **High** (no change history yet) |
| 20 | act on many cases at once (assign, merge, close) | **Low** |

## Field officer

| # | As a field officer, I want to… | Status |
|---|---|---|
| 1 | be told when I'm given a new job | **High** |
| 2 | see my jobs, ordered by deadline, with location and priority filters | ✅ |
| 3 | see my team's unassigned jobs and take one | ✅ |
| 4 | see the full job details and photos on my phone | ✅ |
| 5 | see past jobs at the same asset or location | **Medium** |
| 6 | get directions or a map to the location | **Low** |
| 7 | record a visit (what I found and what I did) by typing or speaking | ✅ |
| 8 | get an AI summary of my visit notes | ✅ |
| 9 | add a photo to a visit | ✅ |
| 10 | mark a job as fixed, or leave it open for another visit | ✅ |
| 11 | record time spent and parts used | **Medium** |
| 12 | put a job on hold (for example, waiting for parts), with the deadline paused | **Medium** |
| 13 | hand a job back or pass it to a colleague | **Medium** |
| 14 | work without a signal and sync later | **Low** |

## Manager

| # | As a manager, I want to… | Status |
|---|---|---|
| 1 | have everything a case handler can do | ✅ |
| 2 | see headline figures: open, overdue, fixed first time, average time to fix, deadlines met, response on time, satisfaction | ✅ |
| 3 | see how often staff accept the AI's suggestion, and how many duplicates were merged | ✅ |
| 4 | see workload and results for each team, and case numbers for each category | ✅ |
| 5 | see a list of overdue cases | ✅ |
| 6 | filter the dashboard by date, building or team, and see trends over time | **High** (figures cover all time only) |
| 7 | export figures and cases to CSV or PDF | **High** |
| 8 | give people staff roles and put field officers in teams | ✅ |
| 9 | switch off a leaver's account from the app | **Medium** (only possible in Django admin) |
| 10 | manage teams, categories, AI keywords and deadlines in the app | **Medium** (only possible in Django admin) |
| 11 | see the AI's accuracy for each category, to tune it | **Low** |
| 12 | have deadlines count only working hours | **Low** (the clock runs 24/7) |

## Administrator (Django superuser)

| # | As an administrator, I want to… | Status |
|---|---|---|
| 1 | manage users, roles, cases, teams, categories, officers and deadlines in Django admin | ✅ |
| 2 | load or reset demo data, and sync categories | ✅ |
| 3 | connect a real email service so messages get sent | **High** |
| 4 | switch the rule-based AI for a real model through settings | **Medium** |
| 5 | set how long data is kept, then anonymise or delete old cases | **Medium** |

## Biggest gaps

- Messages are never actually sent, so password reset doesn't work either.
- After a report goes in, the reporter and handler can't talk to each other or change it.
- Cases can't be searched or reassigned after triage.
