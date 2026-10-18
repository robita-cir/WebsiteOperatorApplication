# CIR operator app: design

> **Status note (18 October 2026).** The app is built with FastAPI and Jinja2, not Streamlit (see [DECISIONS D13 and D19](../DECISIONS.md)). The functional design, the approval and undo rules, the palette and the mockups apply as written. Section 9 is kept as a record of the Streamlit assessment.


**Status:** design for CIR team review. It describes screens, flows and visual rules. It does not change the website or the tool.
**Sources:** `docs/REQUIREMENTS.md` (reviewed 17 October 2026; sections a to h), `docs/EDITABLE_SECTIONS.md`, `docs/PLANNING.md`. Template at commit `23f4878b60d337ebd18fac22427dcd31bdf14a86`, read only. Nothing from it was built or run.
**Companion files:** `mockups/01-dashboard.html`, `mockups/02-add-person-draft.html`, `mockups/03-preview-approve.html`, `mockups/04-check-result.html`.
**Labels used below:** *Proposed* marks a feature this design adds. *To check* marks a fact that must be tested on the target machine or in the pinned Streamlit version.

## 0. How this design was checked

- **Template colours.** The nine tokens were read from `src/styles/global.css` lines 31 to 39. Literal colours outside the tokens were located (section 8.1).
- **Contrast.** Every template token pair, and six pairs of the proposed palette, were recomputed with the WCAG 2.x formula. All matched the visual report.
- **Screens.** The 23 screen names in the functional report match REQUIREMENTS section (d). The only difference is the short label "Settings" for "Settings (technical)".
- **Citations.** The cited lines were opened, including the launch check, the events page, the header, the footer and the palette files. Four citations or figures were wrong. They are corrected in Appendix B.
- **Mockups.** The four files are 8,999 to 13,609 bytes. Each carries the label "Design mockup, not the app" once. None loads a script, stylesheet, font or image.

## 1. Design principles for a non-technical operator

1. **One path for every change.** Every change goes through Draft, Preview, Approve, Written and Site check, in that order. *Why:* one path is learned once, and it makes it impossible to reach the website files without a preview.
2. **Each change is said in a sentence before it happens.** *Why:* the operator is the last human check on public facts, and a code diff cannot be checked by someone who does not write code.
3. **Choose from lists; type only facts the operator knows.** *Why:* free typing causes wrong dates and invented categories (REQUIREMENTS (c), E1). A list cannot produce them.
4. **Machine text is traced to the operator's facts.** Every name, number, date and link in a draft must appear in what the operator typed, or it is flagged. *Why:* a small model writes plausible details that are not true (E17).
5. **Every message says what happened, what to do next, and which field.** *Why:* the operator must recover alone. A bare build error sends them to the technical contact over a typing mistake.
6. **Undo is one click away, and it refuses rather than overwrites.** *Why:* a public mistake must be reversible without a developer, and an undo must never destroy newer work (E54).
7. **Long work shows its stage, its elapsed time and a cancel button.** *Why:* a model call can take up to two minutes on an 8 GB computer. Without feedback it looks frozen.
8. **It looks like the centre's website.** The same fonts, palette and square corners. *Why:* the operator should recognise the tool as the centre's own.

Plain English throughout, in British spelling. Technical detail appears only in a "For the technical contact" box (REQUIREMENTS (d)).

**Success test** (PLANNING, milestone M5): an operator who has not seen the tool completes one add and one edit in under ten minutes, with no help.

## 2. Who uses it, and the job of each screen

### 2.1 Users (REQUIREMENTS (a))

| Who | Does in the app | Must not |
|---|---|---|
| Operator (lab or centre staff; no HTML, npm or git) | Adds, edits and removes records; reviews drafts and previews; approves; runs the site check; undoes; prepares the launch | Edit code or settings files; deploy; set the domain; approve legal or finance text |
| Content approver (head of centre or faculty lead) | Named on the approver list; approves wording, research text and photograph use | Need not operate the tool. Approvals are recorded by the operator |
| Institute reviewers (legal, finance, data protection) | Read legal, privacy, tax and donor text in a preview or a printout (proposed); give written approval | Edit files; receive model drafts |
| Technical contact | Installs the tool and the model; keeps the approver list and Settings; deploys the built site; removes the legal "Draft for review" notice after approval | Change the template's structure without review |
| Website visitor | Never uses the app. Their phone, keyboard and screen reader are the test of the public site | Not applicable |

### 2.2 The one job of each screen

| # | Screen | Its one job | Main user |
|---|---|---|---|
| 1 | Start | Show whether the website is ready, what needs attention, and the writing helper's status | Operator |
| 2 | People | Add, edit, move to alumni, remove people | Operator |
| 3 | Projects | Add, edit, feature, remove student projects | Operator |
| 4 | Research directions | Edit the title and description of the four fixed directions | Operator (rare) |
| 5 | Events | Add from a notice; edit dates and places; see upcoming and past events | Operator |
| 6 | News | Add, edit, remove news, announcements and insights | Operator |
| 7 | Job openings | Add, close and reopen openings | Operator |
| 8 | Publications | Add by DOI or by hand; fix a DOI | Operator |
| 9 | Partners | Add, mark former, feature partners | Operator |
| 10 | Funded programmes | Add, edit, remove programmes | Operator |
| 11 | Facilities | Add, edit, remove equipment | Operator |
| 12 | Documents | Upload, replace, remove PDFs | Operator |
| 13 | Gallery | Albums, text only in version 1 | Operator |
| 14 | Page wording | Edit the wording of each page | Operator (locked until P1) |
| 15 | Contact and names | Institute and site names, email, phone, address, club link | Operator |
| 16 | Navigation and footer | Relabel and retarget the eight header items and the footer links | Operator |
| 17 | Legal pages | Legal text, bracketed fields, approval record | Operator, with the institute's reviewer |
| 18 | Samples and placeholders | Find sample entries and placeholder text; replace or remove them | Operator |
| 19 | Check and preview | Run the site check; open a preview; create a test export | Operator |
| 20 | History | Every run, undo, and the approvals tab | Operator |
| 21 | Launch | Readiness checklist, approvals, readiness report | Operator and content approver |
| 22 | Settings | Operator settings; technical settings behind a password | Technical contact (operator reads) |
| 23 | Help | Plain guide, glossary, who to contact | Operator |

### 2.3 The first week

Checked against U1, U4, U53, U55 and U56 in REQUIREMENTS (b).

- **Day 1.** The technical contact has installed the tool, Node 22.12 or newer, and the writing helper. The operator opens the launcher. The console window shows the address and must stay open. Start shows the writing helper, the website folder, the last site check ("never run on this computer"), the 99 sample entries, and the three most important warnings. The operator presses Check the writing helper (U56) and sets "Your name" in Settings. That name becomes "Recorded by" on every approval.
- **Day 2, first add.** Add a person with no photograph (U1). The operator checks the details, drafts the biography, handles every highlighted item, reads the preview, picks the approver, ticks the statement and approves. The screen then says "Saved to website files" and "Site check waiting". If the writing helper is off, Write it myself is used instead.
- **Day 2, first undo.** History, then Undo this change on today's run. The confirmation says the new file moves to the archive. The approval stays on record, marked undone. This drill matters most in the first week: nothing is lost.
- **Day 3, first removal of a sample.** On People, remove a sample person. The screen lists the projects that name them and asks for the person's name to be typed (U4).
- **Day 4, first check.** Check the site on screen 19. Start may still say "Launch not ready: sample entries remain". Screen 19 says, in one line, that the site check and launch readiness are different checks.
- **Day 5, first handover (a rehearsal).** Create a test export on screen 19 after a passing site check. The folder is labelled "TEST: not for launch" (proposed). It holds the build and checksums. The technical contact confirms that it opens and builds.

## 3. Navigation and sitemap

### 3.1 The sidebar (proposed grouping)

The sidebar lists the 23 screens in seven headed groups. Labels follow the website's own page names.

- **Start:** 1 Start
- **People and research:** 2 People; 3 Projects; 4 Research directions; 8 Publications; 10 Funded programmes
- **News, events and jobs:** 5 Events; 6 News; 7 Job openings
- **Centre and partners:** 9 Partners; 11 Facilities; 12 Documents; 13 Gallery
- **Website text:** 14 Page wording; 15 Contact and names; 16 Navigation and footer; 17 Legal pages
- **Checks and release:** 18 Samples and placeholders; 19 Check and preview; 20 History; 21 Launch
- **Settings and help** (bottom of the sidebar): 22 Settings; 23 Help

The visual report proposed five groups, one of them with twelve items. This design splits that group into three, because a long list under one heading is hard to scan.

### 3.2 Mapping, merges and deferrals

All 23 screens of REQUIREMENTS (d) are kept. No screen is added, merged or removed without the CIR team's agreement.

| Item | Decision | Why |
|---|---|---|
| Approvals | A tab on History (20), not a 24th screen | Each approval belongs to a change; the approvals log is the History list |
| Launch readiness | The Launch screen (21) | It already holds the checklist and the approval boxes |
| Screens 14 to 17 | Shown, but read-only until template change P1 moves page wording and settings into data files | Editing them now would edit `.astro` and `.ts` files, which the write list must never allow (REQUIREMENTS (e)). The screen says why it is locked |
| Settings (22) | Two parts: For you; For the technical contact (behind a password, proposed) | The operator must not change technical values |
| Research directions (4) | Kept as its own screen | Four fixed records with fixed ids, and a different rule set from projects |
| Samples (18) | Kept as its own screen | It is a worklist with bulk removal (U49); Launch links to it |
| Deferred functions | Photographs in albums (U35, P15); partner logos; a finished status for programmes (P16); a cancelled status for events (P17) | Each needs a template change or a decision |
| Profile from a CV (T9) | Deferred from version 1 | No use case in REQUIREMENTS (b) uses it, and a 3B model cannot read long CVs reliably (REQUIREMENTS (g)) |

## 4. Core flows, step by step

### 4.0 Rules common to every flow

- Every write follows the same path: **Draft**, **Preview**, **Approve**, **Written**, **Site check**.
- The nine states are those the brief requires: Empty, Drafting (with progress and cancel), Draft ready, Draft with warnings, Blocked, Approved, Written, Check passed, Check failed. For the site check, "Drafting" becomes "Running" (progress and cancel). "Not applicable" marks a state that cannot occur in that flow.
- **Keep as draft** keeps the text in the state folder, not on the website. **Approve and save to website files** writes the change. **Written** means the website's content files have changed. The change is **not yet on the website** until the technical contact builds and deploys.
- The preview before approval is drawn by the tool, so it is an approximation. The real page appears after the site check, and the screen says so once, next to the preview button.

### 4.1 Add a person (U1)

1. People, then Add person. Fields appear in the order of section 5.2.
2. **Check details.** No model is used and nothing is saved. A duplicate name (capitals and spacing ignored) is shown with the existing entry (E6, E37).
3. **Draft biography** (optional; Write it myself is always available). Drafting needs three to six facts.
4. Read the draft. Each name, year, number or link not in the facts is highlighted. Remove it, or tick that it is correct, one item at a time (E17).
5. **Preview.** The people card (`/people/`) and the profile (`/people/<slug>/`), at desktop and phone width (proposed). The address is shown as permanent (E40).
6. **Approve.** Choose the approver from the list, tick the statement, and press Approve and save to website files.
7. **Written.** `src/content/people/<slug>.md` is created with only the fields given. The portrait is copied only once its file is in place (E9). The site check is queued.

| State | What the operator sees | What they can do |
|---|---|---|
| Empty | The form. Check details is on. Draft biography is off until three facts are typed | Fill in; check; write it myself |
| Drafting | Stage line, elapsed seconds, Cancel. The facts stay as typed | Wait; cancel keeps the facts |
| Draft ready | Biography in an editable box, with a word count (target 80 to 150) | Edit; redraft; preview |
| Draft with warnings | Each flagged name, number or link is listed, with Remove and Correct | Handle every item; approve stays off until all are handled |
| Blocked | Plain reasons above the button: "Choose a group." "Homepage must start with https://." "Tick the consent box to use this photo." | Fix each field named |
| Approved | "Approved by [approver] on [date]. Saving to website files." | Nothing; the write follows at once |
| Written | "Saved to website files: src/content/people/[slug].md." Undo is shown. "Site check waiting." | Undo; continue |
| Check passed | "Site check passed. The change is in the website files and not yet on the website." | Continue |
| Check failed | "The change is saved, but the site check failed: [message], in [field]. The site is Not ready." | Undo this change; show details; check again (E27) |

### 4.2 Edit an event (U13)

1. Events, then Upcoming or Past. Choose the event and press Change date, time or place.
2. Enter the new date, time or place. A blank venue shows "To be confirmed" on the event page (EDITABLE area 4).
3. The tool lists other content files that still show the old date or place. It searches content files only. Page wording is not searched, and the screen says so.
4. An optional summary update, drafted from the new facts. Off by default.
5. **Preview.** Each changed line, before and after. Only the changed keys are rewritten (DECISIONS D5). Other matching lines are listed as "Review these yourself" and are not changed.
6. Approve and write. The site check is queued.

Date rules: a real calendar date (E1); the end on or after the start (E3).

| State | What the operator sees | What they can do |
|---|---|---|
| Empty | The current values; "Nothing changed yet"; approve off | Enter new values |
| Drafting | Only when a summary update is asked for; otherwise not applicable | Wait or cancel |
| Draft ready | A proposed summary, to accept or edit | Accept or edit |
| Draft with warnings | "These lines still show the old date and cannot be changed here", with the list | Review each line by hand |
| Blocked | End before start (E3); date not real (E1) | Correct the date |
| Approved | Before and after lines, approver, date | Nothing |
| Written | Changed keys only; "Review these lines yourself" stays on screen; Undo shown | Undo; continue |
| Check passed | "Site check passed." | Continue |
| Check failed | As 4.1 | Undo; show details; check again |

### 4.3 Add a news item (U17)

1. News, then Add. Choose the kind (news, announcement or insight), the date, the headline and the summary. Add two to four facts, or type the full text instead of drafting it.
2. **Draft.** A summary of up to 300 characters and a body of 100 to 250 words, from the facts only (task T6).
3. Checks: a real date; a summary present; nothing beyond the facts. The headline warns at 70 characters and is blocked at 120 (E14).
4. **Preview.** The entry on `/news/` and the item page `/news/<slug>/`, at desktop and phone width. The preview says whether the item will be among the three newest on the homepage, and which item it will push off.
5. Approve and write `src/content/news/<slug>.md`. The site check is queued.

| State | What the operator sees | What they can do |
|---|---|---|
| Empty | The form; Draft is off until two facts are typed | Type facts |
| Drafting | Stage line, elapsed seconds, Cancel | Wait or cancel |
| Draft ready | Summary and body in editable boxes, with length counts | Edit; redraft |
| Draft with warnings | The homepage displacement warning; flagged facts | Handle each item |
| Blocked | Headline over 120; no date; no summary | Fix the field named |
| Approved | Approver and date | Nothing |
| Written | "Saved to website files." Undo shown | Undo; continue |
| Check passed | "Site check passed. The homepage shows the change after the next build." | Continue |
| Check failed | As 4.1 | Undo; show details |

### 4.4 Undo a change (U53)

1. History, then choose a run, or press Undo last change (the newest run that can be undone).
2. Details: what changed (before and after), the files, the approver, and the site check after the run.
3. Press Undo this change. The confirmation states the effect in plain words, for example "This moves Jane Doe to the archive. Her portrait moves with her."
4. The tool restores the before-state. A new file moves to the archive; nothing is deleted. The undo is recorded as a new run. The site check is queued.

The refusal rules are in section 7.3.

| State | What the operator sees | What they can do |
|---|---|---|
| Empty | "No changes recorded yet." | Nothing |
| Drafting | Not applicable | Not applicable |
| Draft ready | Not applicable | Not applicable |
| Draft with warnings | Only warnings, for example "A portrait will also move to the archive." | Read; confirm |
| Blocked | Refused for one of three reasons: a file changed since the run; a later change touches the same record; the backup has gone (E53, E54) | Read the reason; view the current file; ask the technical contact |
| Approved | "Confirmed by the operator." The approval record stays | Nothing |
| Written | "Restored. The undo is recorded in History." | Continue |
| Check passed | "Site check passed." | Continue |
| Check failed | Undo is still allowed; the screen says it may fix the failure | Undo; show details |

### 4.5 Run the site check (U51)

1. Start, or Check and preview (19), then press Check the site.
2. Stages: "Building the site", then "Checking the pages' HTML". Cancel is available.
3. Result: "Passed at [time]", or each problem as a plain sentence with its page, record and field. The original message is kept in a details box for the technical contact (E28). Section 7.4 gives the mapping.

The command comes from fixed settings only (REQUIREMENTS (e), rule S8). The operator cannot change it.

| State | What the operator sees | What they can do |
|---|---|---|
| Empty | "The site has not been checked on this computer yet." | Check |
| Running (in place of Drafting) | Stage line, elapsed seconds, Cancel | Wait or cancel |
| Draft ready; Draft with warnings; Approved; Written | Not applicable | Not applicable |
| Blocked | "Waiting: the writing helper is busy. The check starts when it finishes." Or "Node.js 22.12 or newer is needed" (E30). Or "This install belongs to another system" (E31) | Wait; or ask the technical contact to fix the install |
| Check passed | "Passed at [time]. The website files build without errors." | Continue |
| Check failed | Problems as plain sentences, each with its page, record and field; "The site is Not ready." | Open each entry; show the preview; undo the last change |

### 4.6 Prepare the launch (U54)

1. Launch (21). The checklist combines the template's launch check (`scripts/launch-check.mjs`) with the tool's own checks: sample entries (lines 25 to 37); the styleguide page (lines 39 to 44); the "Draft for review" notices (lines 46 to 57); the site address (lines 59 to 66); the social-sharing image (lines 74 to 79); and the placeholder scan (EDITABLE area 17), which the template's check does not do.
2. Approvals, each chosen from the approver list: the content approver; the technical contact; the legal office for each legal page; the finance office for the Support page; a consent answer for each photograph.
3. **Save readiness report.** It is written to the state folder, not to the website.

| State | What the operator sees | What they can do |
|---|---|---|
| Empty | "Launch readiness has not been checked yet." | Run the checks |
| Drafting | Not applicable | Not applicable |
| Draft ready | Not applicable | Not applicable |
| Draft with warnings | Warnings listed, for example "62 of 62 people entries have no portrait" (launch check line 91). Warnings do not block | Read; acknowledge |
| Blocked | Blockers listed; "Not ready to launch: N blockers." | Fix each one |
| Approved | Each approval with name and date. A text changed since approval shows "Needs approval again" | Approve again |
| Written | "Readiness report saved to the state folder." | Continue |
| Check passed | "No blockers. Ready for the technical contact to build and deploy." Never "Launched" or "Published" | Save the report |
| Check failed | "Not ready: the site check failed." | Show details |

### 4.7 Other use cases

Every use case in REQUIREMENTS (b) follows section 4.0. The table gives what differs, for the use cases not covered above. The rest (U7, U9, U11, U16, U18, U24, U27, U30, U33, U34, U37, U41, U42, U45, U47, U51, U53) follow the forms and states of sections 4.1 to 4.6.

| Use case | Flow in brief | What differs | Blocks on |
|---|---|---|---|
| U2 Edit person | Changed fields; approve the changed lines | Drafting only if a new biography is asked for | As U1 |
| U3 Move to alumni | Set an alumni group; confirm | Warning: projects still name the person | Group from the list |
| U4 Remove person | Show dependants; type the name | "Written" means moved to the archive | Typed confirmation (E41) |
| U5 Portrait | Upload; crop preview; consent | Blocked under 800 px, over 20 MB, or without consent | E9, E10, E11, E44 |
| U6 Add project | Title, direction, students, featured; summary drafted (T4) | Warning if a student is not in People (E7); warning above four featured (E46) | Title over 120 (E14) |
| U8 Abstract | Notes, then abstract (T5) | Warning on new names, numbers or dates | Word count 120 to 250 (proposed) |
| U10 Research direction text | Title (60) and description (300) | Codes and ids are read-only | Only the four fixed ids |
| U12 Event from a notice | Paste the notice (up to 3,000 characters); Read notice (T1, T2) | A date with no clear year opens a calendar question (E1); a missing date blocks (E2) | Unclear or missing dates |
| U14 Cancel or postpone | Choose cancelled, or a new date | Until P17 the status lives in the summary | Confirmation |
| U15 Past events leave Upcoming | No action; changes at each build | Start shows "Out of date" when the last build is over one day old (E5) | None |
| U19 Add opening | Type from seven; deadline; email; summary (T7) | Warning if the deadline has passed (E45) | A valid email |
| U20, U21 Close or reopen | Status; deadline | Warning if the deadline has passed while still open | Deadline today or later (U21) |
| U22 Publication by DOI | DOI or pasted reference; fields from the pasted text only (T8) | Duplicate DOI (E25); DOI not confirmed (E24); DOI cleaned (E23) | Year 1950 to next year; one author |
| U23 Publication without DOI | Title, authors, venue, year, type, link | None | Link must be https |
| U25, U31, U49 Remove samples or facilities | Choose; typed confirmation; archive | Each removal is its own change, except U49, which is one run | Dependants (E41) |
| U26 Add partner | Name, country, kind, status, summary (200), featured | Warning above six featured | Name required |
| U28 Add funded programme | Title, funder, partner, amount as text, period | Warning if the partner is not on the partners list | Title and funder required |
| U29 End programme | No status until P16; Remove is the only route | Removal takes the programme off /research/ at once | Typed confirmation |
| U32 Upload PDF | PDF; title; kind; date; description | Not a PDF (E56); over 20 MB; warning that PDFs are not checked for accessibility | Title and description |
| U35 Album photographs | Not available in version 1 | The only state is "Not available" | P15 |
| U36 Contact details | Email, phone, two address lines | Warning: the privacy notice must be reviewed (E47) | A valid email; phone format |
| U38 Club link | Address and label | Warning on example.org or a GitHub address | Must be https |
| U39 Domain | Technical only; the operator sees it read-only | None | Both files change together |
| U40 Navigation labels | Label (16) and target from the list | Adding or removing items is not offered (section 12, question 5) | Target must exist |
| U43 Join answer | Answer (80 words) from the facts (T11) | Removes the Sample label on that answer (P10) | No eligibility, fee or deadline claim not in the facts |
| U44 Support text | Finance-approved text, pasted; no draft | Finance approval is required | Placeholder wording |
| U46 Legal pages | Text and each bracketed field; approval record | The "Draft for review" notice cannot be removed here. Text changed after approval needs approval again | The notice is protected |
| U48 Review samples | List by area; each action is its own change | Review changes nothing | Dependants (E41) |
| U50 Placeholder scan | Lists the markers in EDITABLE area 17 | Read-only | None |
| U52 Preview | Opens a copy of the last good build | Not available until a build exists | A build |
| U55 Export | Build and checksums in a folder | Labelled "TEST" while blockers remain (proposed) | The site check must have passed |
| U56 Writing helper check | Server reachable; model installed; a short test reply and its time | Shown on Start | None |

## 5. Forms

### 5.1 Rules for every form

- **Field order** follows REQUIREMENTS (d) for each screen. A required field says "required" in its label, so the requirement is not shown by colour or an asterisk alone.
- **Help text** is visible under the label, never only in a hover tooltip. Keyboard and screen-reader users need it too.
- **When validation runs:**
  - *When the operator leaves a field:* format, length and uniqueness for that field. Choice fields check when they change.
  - *On Check details:* every field, and the rules that involve two fields (for example consent with a portrait, or an end date before the start date).
  - *On Preview:* the full set again, and the warnings that need acknowledgement.
  - *On Approve:* the full set again. Each file is compared with the fingerprint taken when the preview was made. If a file has changed, approval is refused and the screen offers to reload (E32).
- **Error wording.** Pattern: the field name, a colon, what happened, then what to do next. Plain English. No jargon such as "schema", "frontmatter" or "exception". No exclamation marks. The typed text is kept.

Examples:

- Homepage: this address does not start with https://. Add https:// at the beginning.
- Name: Jane Doe is already listed as a faculty member. Open that entry, or use a name that differs in more than capitals and spacing.
- Portrait: this photo is 600 pixels tall. It must be at least 800 pixels. Choose a larger photo.
- Consent to use the photo: tick this box to use the photo, or remove the photo.
- Date: 10/03/2026 could mean 10 March or 3 October. Pick the date from the calendar.
- End date: this date is before the start date. Pick a date on or after the start date.
- Facts for the profile: add at least three facts. The draft needs them, so the model does not guess.

On Preview, the first field in error receives focus where Streamlit allows. Each error is linked to its field (`aria-describedby`).

### 5.2 People form (U1), in order

| # | Field | Required | Limit | Rule and note |
|---|---|---|---|---|
| 1 | Name | Yes | 80 characters | Unique; capitals and spacing ignored. Help: "Write the name as it should appear on the website." |
| 2 | Group | Yes | Six choices | Faculty; Research scholar; M.Tech student; Research alumnus; M.Tech alumnus; B.Tech alumnus (EDITABLE areas 1 and 14.5) |
| 3 | Role | No | 80 characters | Shown on the card and the profile |
| 4 | Department | No | 120 characters | Shown on the card and the profile |
| 5 | Interests | No | Up to 10 tags, 60 characters each | Shown as tags |
| 6 | Homepage | No | Web address | Must start with https:// (U1) |
| 7 | Portrait | No | JPG or PNG; at least 800 pixels tall; 20 MB | Resized on import; warning if not close to 4:5 (U5) |
| 8 | Consent to use the photo | Yes, when a portrait is added | Tick box | Recorded with the change (E44) |
| 9 | Order | No | Whole number, 1 to 999 | Lower numbers first in the group; the first four faculty appear on the homepage |
| 10 | Facts for the profile | Yes, to draft | 1,000 characters | Three to six facts; the draft uses only these |
| 11 | Biography | No | Drafted to 80 to 150 words; editable up to 250 | Empty shows "Biography to be added" on the profile |

### 5.3 Event form (U12, U13), in order

Title (required, 120 characters); Kind (required: workshop, programme or talk); Series (none, or the approved list; until P3 only "none" and the template's `series-1`, the one name the site groups, `events.astro` line 21); Start date (required; calendar); End date (calendar; not before the start, E3); Venue (120 characters; blank shows "To be confirmed"); Summary (300 characters); Description (drafted to 60 to 200 words; required before publishing, proposed). The notice text (up to 3,000 characters) is entered on the "Add from a notice" tab before the form.

### 5.4 News form (U17), in order

Kind (required: news, announcement or insight); Date (required; calendar); Headline (required; 120 characters, warning at 70); Summary (required; 300 characters); Facts (two to four, used only for drafting); Full text (drafted to 100 to 250 words). The form has no "featured" field, because the template has none (EDITABLE area 5).

## 6. The preview and approval screen

### 6.1 How a change is shown

The preview has two parts.

- **What it will look like.** The card or item as it will appear on the site, at desktop and phone width (proposed), with the note "The real page appears after the site check."
- **What will change.** Each change is a plain sentence, with a table of before and after values for the record. Examples:
  - "Role changed from 'Research fellow' to 'Senior research fellow'."
  - "A new person, Jane Doe, will be added to Faculty on the People page."
  - "Jane Doe will move to the archive. Two project pages will show her name as plain text."

Before the approval box, the screen lists the other effects of the change: the homepage effect, the other pages that name the record, and every warning. Each warning has its own tick box, "I have checked this". A blocker must be fixed. It cannot be ticked.

### 6.2 The approve control

Order on the screen:

1. **Approver.** A dropdown of the names on the approver list in Settings. If the list is empty, the screen says: "No approvers are listed. Ask the technical contact to add names in Settings." Approve stays off.
2. **Statement.** A tick box that states what the approver's name certifies. For content: "I have checked these facts against their source" (proposed wording). For legal and finance text, a reference field appears, "Reference of the written approval (email subject and date)", and it is required.
3. **Approve and save to website files.** The only primary button on the screen. It stays off until there are no blockers, every warning is ticked, an approver is chosen, and the statement is ticked. The reason is shown beside it: "To approve, choose an approver and tick the statement."
4. **Keep as draft**, **Go back and edit**, and a text link, **Discard these changes**, which asks for confirmation.

Pressing Enter in a text field never approves. Only the button does (proposed; to check in Streamlit). After approval the line reads: "Approved by [approver] on [date and time]. Recorded by [operator]." The date is set at the moment of approval. It is never typed.

### 6.3 What "approve" records

| Field | Content |
|---|---|
| Approval ID | Created by the tool |
| Kind | Content, launch, legal, finance, photograph consent, or privacy notice change |
| Approver | Name and role, from the approver list |
| Recorded by | The operator's name, from Settings |
| Date and time | Local time, with the time zone |
| Scope | The run ID, the record path and the changed fields |
| Text fingerprint | A hash of the exact text approved |
| Statement | The tick that was made |
| Reference | Required for legal and finance (for example an email subject and date) |
| Status | Current; Needs approval again (the text changed); Undone |

The record proves that the operator recorded, on this computer and at this time, that the named approver approved this exact text, and the reference given. It does not prove who was at the keyboard, that the approver saw the text unless they did, or that the reference is genuine. It is a record, not a signature. Stronger evidence is a printed readiness report that approvers sign by hand (proposed).

Approvals cannot be edited. A later change to an approved text marks that approval "Needs approval again", and the screen says so.

## 7. Status and feedback

### 7.1 Status banners

Start shows three status lines, and every screen shows them at the top:

- **Site check:** "Passed at 14:05"; "Failed after your last change"; "Not run on this computer"; "Out of date: changed since the last check".
- **Writing helper:** "Ready"; "Busy: drafting [name]"; "Not running"; "Model not installed".
- **Launch:** "Not ready: N blockers"; "No blockers: ready for the technical contact".

Each banner has one of four tones (info, success, warning, error), a word prefix ("Info:", "Done:", "Warning:", "Error:") and an icon. Colour is never the only signal. Error banners stay until the problem is resolved. Information and success use a status role. An error produced by an action uses an alert role.

### 7.2 Toasts, progress and calm messages

- **Toasts** are for low-stakes confirmations only, such as "Draft kept." Approvals, failures and check results never use a toast, because a toast disappears on its own (to check Streamlit's toast behaviour).
- **Drafting stages:** "Checking your facts." Then "Connecting to the writing helper." Then "Writing the draft. [seconds] seconds so far." Then "Checking the draft against your facts." Then "Draft ready", or "Could not draft: [reason]". The model gives no reliable percentage, so the screen shows elapsed seconds and the stage.
- **Calm messages on time.** At 120 seconds: "Still working. You can keep waiting, or cancel and write it yourself." At 300 seconds the job stops: "Stopped after five minutes. Nothing was saved. Your facts are still here."
- **Check stages:** "Building the site." Then "Checking the pages' HTML." Then "Passed" or "Failed".

### 7.3 Undo and refusal rules

Undo is offered only when:

1. No later run has changed the same files. The newest run is undone first. To undo an older run, the newer runs on the same files are undone first, in order.
2. Each file still matches the fingerprint recorded after the run.
3. The backup for the run still exists. Backups cover the last 200 runs (E53, proposed).

When a test fails, the screen says which test. A refusal caused by a file change reads: "This file has changed since this change was saved. Undo is refused so newer work is not lost." No overwrite option is offered.

### 7.4 Mapping check results to a page and a field

Each problem from the site check becomes one block:

1. **Page:** the public address and its name, for example "People › Example person › /people/example-person/".
2. **Field:** the label the operator sees, for example "Homepage".
3. **What is wrong:** one sentence.
4. **What to do:** one sentence.
5. **Buttons:** "Open this entry" (returns to the form, with the field focused) and "Show the page" (the preview).
6. **Details for the technical contact:** the original message, folded away.

The mapping from a build message to a page and a field is done by the service, not by the screen. A message the service cannot map appears under "Other messages (for the technical contact)". It is never hidden.

## 8. Visual design

### 8.1 Colour palette (light mode only)

Template tokens, all from `src/styles/global.css` lines 31 to 39 (in the `:root` block):

| Token | Hex | Source | Contrast | Use in the app |
|---|---|---|---|---|
| paper | #ffffff | line 31 | ink 18.44:1 on paper | Page background |
| band | #f6f7f9 | line 32 | ink 17.20:1 on band | Sidebar, table headers, alternate areas |
| ink | #101030 | line 33 | 18.44:1 on paper | Text and headings |
| muted | #4a4f66 | line 34 | 8.07:1 on paper; 7.53:1 on band | Hints, secondary text, metadata |
| line | #d9dce3 | line 35 | 1.37:1 on paper | Rules and card edges only. Not for inputs or text |
| accent | #17766a | line 36 | 5.47:1 on paper; 5.11:1 on band | Links, labels, focus ring, primary button fill |
| on-accent | #ffffff | line 37 | 5.47:1 on accent | Text on the primary button |
| brand | #30a090 | line 38 | 3.20:1 on paper | Decoration only |
| highlight | #8a5a12 | line 39 | 5.91:1 on paper; 5.52:1 on band | Warning text; sample badge |

Proposed tokens (not in the template, which defines no status colours):

| Token | Hex | Contrast | Use |
|---|---|---|---|
| control-border | #6f7489 | 4.63:1 on paper; 4.32:1 on band | Input, checkbox and secondary-button edges (WCAG 1.4.11) |
| accent-tint | #e3efec | ink 15.65:1 on it; accent focus ring 4.65:1 on it | Current sidebar item |
| disabled-text | #6b6f84 | 4.63:1 on band | Disabled controls only (exempt under WCAG 1.4.3 for inactive controls) |
| warning-bg | #f8efe0 | highlight text 5.18:1 on it | Warning banner background |
| error-text | #a4262c | 7.26:1 on paper; 6.20:1 on error-bg | Error text and error edge |
| error-bg | #fbe9e9 | ink 15.75:1 on it | Error banner background |
| success-text | #1d6b4f | 6.43:1 on paper; 5.60:1 on success-bg | Success text |
| success-bg | #e6f2ed | ink 16.06:1 on it | Success banner background |
| info-text | #2d4f8e | 8.01:1 on paper; 6.89:1 on info-bg | Information text |
| info-bg | #e9eef8 | ink 15.85:1 on it | Information banner background |

Every status colour is also carried by a word and an edge, never by colour alone. The brand colour is not used for text.

**Why light only.** The template is light only and says so (`global.css` line 30; `docs/01-site-overview.md` line 72). A dark palette would double every check. Streamlit follows the operator's system theme unless the base theme is set (to check), so the app sets the base theme to light.

**Literal colours outside the tokens.** These should become tokens in the app's code: the SVG figure (`src/components/ManipulatorFigure.astro`), the Pagefind search colours (`src/pages/search.astro` lines 54 to 58), the theme colour (`src/layouts/Layout.astro` line 33), the favicon (`public/favicon.svg` lines 2 and 3), and the grid colour at 55% opacity (`src/styles/global.css` lines 205 and 206). The internal style guide page (`src/pages/styleguide.astro`) repeats the hex values and must be deleted before launch (launch check, lines 39 to 44).

**Template findings for the CIR team** (outside the app):
- The comments at `global.css` lines 33 and 34 understate the ink and muted contrast. They say 17.6 and 7.7; the formula gives 18.44 and 8.07. Every pass result stands.
- `PersonCard.astro` line 34 sets the initials at 60% accent on band: 2.46:1, below the 3:1 for large text. The initials are hidden from screen readers (line 33), so the problem is visual only. The app must not copy it.

### 8.2 Typography

- **Families.** Source Serif 4 for headings and page titles (`global.css` lines 11 and 57 to 62). Inter for body text, forms and buttons (lines 12 and 51). JetBrains Mono for labels, dates, file names and eyebrows (lines 13 and 111 to 119).
- **Loading.** The app bundles the Latin variable WOFF2 files from the same Fontsource packages the template uses (`package.json` lines 21 to 23), at the versions in the template's lock file. The developer copies the files at build time, declares them with `@font-face` in the one theme stylesheet, and falls back to the system UI fonts. No Google Fonts link is used. The template makes no third-party font request (`docs/01-site-overview.md` line 18), and the tool must work offline.
- **Licences.** The three families are under the SIL Open Font License 1.1 (to check the licence files in the installed packages). The licence text ships with the bundle.
- **Type scale** (the 1280 px values, then the 1024 px values):

| Use | Family | Weight | 1280 px (size / line) | 1024 px (size / line) |
|---|---|---|---|---|
| Page title (h1) | Source Serif 4 | 500 | 32 / 38 | 28 / 34 |
| Section (h2) | Source Serif 4 | 500 | 22 / 28 | 20 / 26 |
| Record title (h3) | Source Serif 4 | 500 | 18 / 24 | 18 / 24 |
| Body | Inter | 400 | 16 / 24 | 16 / 24 |
| Reading text (draft, preview) | Inter | 400 | 16 / 26 | 16 / 26 |
| Label | Inter | 600 | 14 / 20 | 14 / 20 |
| Hint and error | Inter | 400 and 600 | 14 / 20 | 14 / 20 |
| Table text | Inter | 400 | 14 / 20 | 14 / 20 |
| Button | Inter | 600 | 15 / 20 | 15 / 20 |
| Eyebrow, date, label | JetBrains Mono | 400 | 12 / 16, uppercase, 0.1em tracking | same |
| Technical value (ids, file names) | JetBrains Mono | 400 | 13 / 20 | same |

Body text is never below 14 px. The smallest text is 12 px, used only for uppercase mono labels. The template's sample tag is 0.62 rem, about 10 px (`SampleTag.astro` line 6), too small for the app. The template's body line height is 1.7 (`global.css` line 53), which is too loose for dense forms. The app uses 1.5 for controls and 1.6 for reading text.

### 8.3 Spacing and layout

- **Scale:** a 4 px base, with steps of 4, 8, 12, 16, 20, 24, 32, 40, 48 and 64 px. The template's Tailwind utilities use the same 4 px base, so the values match the public site.
- **Page padding:** 20 px below 640 px and 32 px above (the template's `px-5` and `sm:px-8`, `Header.astro` line 13).
- **Width:** the content area is at most 1216 px (76 rem, `global.css` line 25), the public site's width. Forms read at most 720 px wide inside it.
- **Top bar:** 56 px (proposed). The public header is 80 px (`Header.astro` line 13). The app needs the room for status banners.
- **Sidebar:** 232 px wide at 1024 px and above.

### 8.4 Corners, borders, shadows and focus

- **Corners:** square (0 radius) on every surface, control, badge and table, like the template's sample tag and most of the site. The only exception is the 2 px corner of the focus outline (`global.css` line 90). The template's `Badge.astro` uses a pill (line 17). The app does not, so that the sample badge matches the rest.
- **Borders:** 1 px control-border for inputs, checkboxes and secondary buttons. 1 px line only for card edges and rules.
- **Shadows:** none. The template uses one shadow, on its mobile menu (`Header.astro` line 44). One proposed overlay shadow may be used for a menu or a dialog.
- **Focus:** a 2 px solid accent outline with a 3 px offset (`global.css` lines 87 to 91). It is always visible and never removed. The app has no dark surfaces. Accent on the ink colour would be 3.37:1, which passes as a focus ring but fails as text.

### 8.5 Component inventory

| Component | Purpose | States |
|---|---|---|
| Page header | Names the screen; holds its main action | Default; with a status badge; action disabled with the reason beside it; focus |
| Sidebar navigation | Moves between the 23 screens | Default; hover; focus; current (`aria-current="page"`, accent-tint, 3 px accent bar, bold); locked (screens 14 to 17, with the reason) |
| Record list, search and filter | Finds one record and opens it | Default; hover; focus; selected; loading; empty ("No people yet. Add a person."); no matches ("No people match. Clear the search."); error ("The list could not be read. Check the website folder in Settings."); sample rows with the badge |
| Form field (label, hint, error) | Collects one fact | Default; hover; focus; filled; read-only; disabled; error (2 px error edge and "Error:" text); near the limit (counter at 90%); over the limit (blocks save) |
| Model-draft panel | Shows progress, the draft and its warnings | Idle (button and time hint); drafting (stages, elapsed, Cancel); cancelled ("Drafting cancelled. Your facts are kept."); draft ready; draft with warnings; blocked; failed ("The writing helper did not reply. Write the text yourself, or try again."); timed out |
| Preview card | Shows the change in plain sentences | No change; changes listed; blocked (reason at the top, approve off); phone-width view (proposed) |
| Approve control | Records an approval with approver, statement and date | Disabled with the reason; enabled; saving; saved (banner with Undo); conflict ("This record changed after you opened it. Nothing was saved. Reload to see the new version."); failed (nothing saved) |
| Status banner | States the screen's condition | Info; success; warning; error (stays until resolved) |
| Check result panel | Shows each problem with its page and field | Not run; running; passed; failed; out of date; details open or closed |
| History row | One saved change, and its undo | Latest (Undo enabled); older (Undo off, with the reason); undone; refused; focus; empty |
| Sample or placeholder badge | Marks sample content | Sample; placeholder text found (proposed). Screen-reader text: "sample content, replace before launch" (`SampleTag.astro` line 9) |

Also needed: a primary button (accent fill, on-accent text, turning to ink on hover as in `Button.astro` line 13); a secondary button (control-border edge, ink text); a text link (accent text, underlined on hover, `Button.astro` line 15); dropdowns; tabs; a confirmation dialog for typed confirmations; and a toast. Buttons are 40 px high, row actions 32 px. The minimum target is 24 px (WCAG 2.2 criterion 2.5.8).

### 8.6 Accessibility (WCAG 2.2 AA)

- **Contrast.** Every text pair in 8.1 is at least 4.5:1. Every edge that identifies a control (input, checkbox, focus) is at least 3:1.
- **No colour-only meaning.** Warnings and errors carry a word, an icon and an edge.
- **Keyboard.** The tab order follows the page: sidebar; page actions; main content from top to bottom; side panels (for example the draft panel); footer actions. Enter in a field never approves. Escape closes a dialog and returns focus to the control that opened it.
- **Focus.** Always visible (8.4). A skip link leads to the main content, as in the template (`Layout.astro` line 57; `global.css` lines 121 to 135).
- **Target size.** At least 24 by 24 CSS px. A checkbox's label is part of its target.
- **Labels.** Every field has a visible label. Hints and errors are linked with `aria-describedby`. Placeholder text never replaces a label, and it uses the muted colour (8.07:1), not a light grey.
- **Names.** The sidebar is a navigation landmark with `aria-current`. Each row action names its record ("Edit Example person"). Decorative glyphs are hidden from screen readers.
- **Live updates.** A polite live region announces drafting at start, finish, cancel and failure, not every second.
- **Motion.** No animation is needed. The template's reduced-motion rule is kept (`global.css` lines 257 to 271).
- **Zoom and reflow.** No page-level horizontal scroll at 1024 px. Tables scroll inside their own box. At 400% zoom, content stacks in one column. This is a goal to test (WCAG 1.4.10).
- **Testing.** axe-core is already a development dependency of the template (`package.json` line 29). Run it on every app screen. Test the keyboard-only path on both platforms. Measure Streamlit's default widget colours in the running app, because the palette covers only the colours the app sets.

### 8.7 Screen sizes

- **Lab desktop:** designed at 1280 px wide.
- **Floor:** 1024 px, with no horizontal page scroll.
- **Below 1024 px:** the sidebar becomes a menu button (proposed) and the content stacks.
- The public site's desktop navigation appears only from 1280 px (`Header.astro` line 18). The app keeps its sidebar down to 1024 px, so its breakpoint is its own.

## 9. Streamlit implementation notes

Streamlit is not installed on this machine, so its version has not been checked. Everything marked *to check* must be tested against the version the bundle pins.

### 9.1 What the theme configuration can set

- In `.streamlit/config.toml`, under `[theme]`: `base = "light"`; `primaryColor = "#17766a"`; `backgroundColor = "#ffffff"`; `secondaryBackgroundColor = "#f6f7f9"`; `textColor = "#101030"`; and `font`, which takes only the built-in choices "sans serif", "serif" or "monospace" (to check).
- Server settings: `address = "127.0.0.1"` keeps the tool local (REQUIREMENTS (f)). `maxUploadSize` is a single value for every uploader. Usage statistics can be switched off (`browser.gatherUsageStats = false`), for privacy (E49). (to check)

### 9.2 What needs custom CSS

Put all custom CSS in one file, injected with `st.markdown(..., unsafe_allow_html=True)`:

- `@font-face` for the three bundled families, and the token variables on `:root`.
- Heading sizes (8.2), square corners, spacing, and the focus ring on every control.
- Status banners and sample badges in the token colours, if the built-in alerts cannot be set.
- Sidebar group labels and the style of the current item.
- The 1216 px content width and the 720 px form column.

Streamlit's internal class names change between releases, so this CSS must be tested after every upgrade.

### 9.3 What breaks when the page is resized (thresholds to check)

- `st.columns` stacks below a width that Streamlit sets. The draft panel beside a form needs a stacking rule of its own.
- The sidebar collapses to a button below a width. The menu button must stay easy to find.
- `st.dataframe` scrolls sideways. Fixed pixel column widths hide the right-hand side.
- `st.tabs` overflows on narrow windows. Keep the tab labels short: Upcoming, Past, Add from a notice.
- `st.dialog` becomes nearly full screen on small widths. Its typed-confirmation field must stay reachable.
- `st.toast` can cover content on small widths.

### 9.4 Forms and validation (the decision)

- `st.form` holds its widgets' values until the form is submitted. That fits "half-finished entries are not written", but it cannot check a field when the operator leaves it.
- **Decision:** the record forms (screens 2 to 13) use ordinary widgets outside any form, so field checks run when the operator leaves a field, as the brief asks. Nothing reaches the website files until Approve. In-progress text is kept in the state folder as a draft (section 12, question 1). Each change reruns the script. Forms of this size should be fast enough (to check).
- The approval block (approver, statement, button) is one `st.form`, so approval is a single action.
- **Trade-off:** more reruns, and more care that state lives in the service and session state, not in the order of widgets.

### 9.5 Progress and cancel

- Streamlit reruns the script on every interaction, so the model call must not run inside the script. The service starts drafting in a background thread and returns at once. The page shows the stages with `st.status` and `st.progress`, and refreshes them with a fragment that runs every second or two (`st.fragment` with `run_every`; to check).
- Cancel calls a service function that sets a flag and closes the model's connection. Whether the model server stops generating when the connection closes must be tested on both platforms.
- Streamlit's own Stop button ends the script run, not the job. A job ends on completion, on cancel, or at the 300-second limit.
- Leaving the page does not cancel the job. A finished draft waits in the state folder (functional report, section 6).

### 9.6 Navigation and links

- `st.navigation` with `st.Page` for each screen, grouped into the sections of 3.1 (to check the grouping API in the pinned version).
- "Open this entry" uses session state with `st.switch_page` or `st.page_link` (to check).

### 9.7 Uploads

`maxUploadSize` is one value for all uploads. The 20 MB limits for portraits and PDFs (REQUIREMENTS (d), screens 2 and 12) are therefore enforced by the media service on the server, and each limit is shown as text on its screen. This differs from the REQUIREMENTS (d) wording, which says size limits "are set in the Streamlit configuration for each type" (Appendix A, item 7).

### 9.8 Widget for each component

| Component | Streamlit widget | Caveat |
|---|---|---|
| Page header | `st.title` restyled by CSS; `st.caption`; `st.page_link` | Title size needs CSS |
| Sidebar | `st.navigation` with sections | Current-item style by CSS |
| Record list | `st.text_input` (search, with a visible label); `st.selectbox` (group filter); `st.dataframe` (read-only list) with row selection (to check); row actions as `st.button` | Scrolls sideways; no inline editing |
| Form field | `st.text_input`, `st.text_area`, `st.selectbox`, `st.multiselect`, `st.number_input`, `st.date_input`; visible hint with `st.caption` above the field | No built-in error look, so error text is styled by CSS. Do not use `help=` tooltips |
| Draft panel | Background thread; `st.status`; `st.progress`; `st.fragment` with `run_every`; `st.button` for Cancel | Test cancel on both platforms |
| Preview card | `st.container(border=True)` (to check); simple HTML inside `st.markdown` | Keep the HTML simple |
| Approve control | `st.form` with `st.selectbox` (approver), `st.checkbox` (statement) and `st.form_submit_button` (primary) | Disabled-button behaviour to check |
| Status banner | `st.info`, `st.success`, `st.warning`, `st.error` | Their colours may not match the tokens (to check) |
| Check result | `st.error` for the summary; `st.container(border=True)` per problem; `st.expander` for details with `st.code` | "Open this entry" by session state |
| History row | `st.columns` with a `st.button` for Undo, or `st.dataframe` with row selection | Undo confirmation in `st.dialog` (to check) |
| Sample badge | `st.badge` (to check), or a styled span | The word "Sample" stays visible |
| Other | `st.tabs` (events); `st.file_uploader` (portraits and PDFs, checked on the server); `st.date_input` (calendar); `st.toast` (confirmations only) | |

### 9.9 What is Streamlit-specific, so it can be replaced

- Every `st.*` call, `config.toml`, the CSS file and the session-state keys are Streamlit-specific.
- Not Streamlit-specific: the tokens, the type and spacing scales, the component states and wording, the sidebar groups, the message file, the mapping from check output to page and field, the layout rules, and every service call. The UI module imports only the `api` module (REQUIREMENTS (e)).

## 10. Mockups

| File | Bytes | Shows |
|---|---|---|
| `mockups/01-dashboard.html` | 9,777 | Start: the launch status (not ready, with blockers and warnings), the writing helper status, the main actions, and recent changes with Undo on the newest row |
| `mockups/02-add-person-draft.html` | 13,609 | The People form with a draft panel: a year and a link not in the facts (blocking), a homepage address error, Preview off with its reason, and the drafting state with progress and Cancel |
| `mockups/03-preview-approve.html` | 11,506 | The preview with the plain-language change table, a sample card with initials, and the approve control |
| `mockups/04-check-result.html` | 8,999 | The check result, with one failure mapped to a page, a record and a field; a details box; and the other checks |

All four use light colours only, label their sample content, load nothing from outside the file, and carry the label "Design mockup, not the app" once. They are for review, not for implementation.

**Differences between the mockups and this design.** Items 1 to 3 were fixed after the review (the approver is a dropdown from the approver list; the drafting time reads "up to two minutes"; the message names the homepage address). Items 4, 5 and 7 remain:

1. Mockup 03 asks for the approver's name as typed text. The design uses a dropdown from the approver list, and "Recorded by" comes from Settings (section 6.2).
2. Mockup 02 says drafting "takes 15 to 60 seconds". Replace it with "This can take up to two minutes on this computer" until five drafts have been measured (section 7.2).
3. Mockup 02 says "Preview is off until the homepage is corrected". It should name the field: "until the homepage address is corrected".
4. The h1 stays at 32 px in the mockups. The step down to 28 px at 1024 px is in the scale (8.2) but not in the CSS.
5. A few spacing values in the mockups (6, 10, 14, 18 and 22 px) are off the scale. Snap them to it.
6. The numbers in the mockups (143 checks, 12 sample entries, a 96-word biography, 41 seconds, 38 words) are invented and labelled as sample.
7. Mockup 03 puts the statement tick box above the approver, and section 6.2 puts the approver first. The statement wording in the mockup ("I have read the changes above and approve them") is a placeholder; section 6.2 proposes "I have checked these facts against their source".

## 11. Design decisions, with trade-offs

| # | Decision | Alternative | Why, and the trade-off |
|---|---|---|---|
| 1 | One path for every change: Draft, Preview, Approve, Written, Site check | Quick edits that save at once | One path to learn. Cost: one more click per change |
| 2 | The preview is drawn by the tool; the real page appears after the site check | Build and render each change | A build takes time and memory, and the 8 GB rule forbids running it beside the model. Cost: the preview can differ slightly, and the screen says so |
| 3 | The approver is chosen from a list kept by the technical contact | Typed names | There is no login, so only a list keeps names consistent. Cost: the list must be kept up to date |
| 4 | "Remove" moves to an archive kept for 90 days; no permanent delete in the app | Permanent delete with a backup | Reversible, and the technical contact purges. Cost: archive clutter until purged |
| 5 | Undo the newest run first, per file | Undo any run at any time | Protects newer work (E54). Cost: an older mistake needs several undos |
| 6 | Drafts continue if the operator leaves the page | Cancel when the page closes | Model calls are slow, and a finished draft is not wasted. Cost: the console must stay open, and old drafts must be cleared |
| 7 | Ordinary widgets for record forms, with checks on leaving a field; `st.form` only for approval | `st.form` for the whole record | Meets the brief's check-on-leave rule. Cost: more reruns and more state handling |
| 8 | Seven headed sidebar groups | One flat list of 23 | Easier to scan. Cost: one more click for a rarely used screen |
| 9 | Light mode only | Dark mode | Matches the public site and halves the checks. Cost: no dark mode for people who need one; the system dark setting is not followed |
| 10 | Bundled fonts from the template's Fontsource packages | System fonts, or Google Fonts | Same look, works offline, no third-party request. Cost: bundle size and licence notices |
| 11 | Square corners, no shadows | Rounded cards | Matches the public site. Cost: a harder look |
| 12 | A new control-border token, #6f7489 | The template's `line` token (1.37:1) | The `line` token fails WCAG 1.4.11 for inputs. Cost: inputs look darker than the public site's rules |
| 13 | Screens 14 to 17 shown, read-only, with the reason | Hidden until P1 | The operator can see what is coming. Cost: a locked area in the menu |
| 14 | Typed confirmation for removals | A plain Confirm button | A removal breaks pages that link to the record. Cost: friction, used only for removals |
| 15 | Test export allowed before launch, labelled "TEST: not for launch" (proposed) | No export before launch | Lets the technical contact rehearse. Cost: a test build may be passed on; the label is on every page |
| 16 | Enter never approves | Enter submits | Prevents accidental approval. Cost: one more click |

## 12. Open questions for the CIR team

Numbering continues from the 25 questions in REQUIREMENTS (h). These questions are new.

| # | Question | Recommended answer |
|---|---|---|
| 1 | May drafts stay on the computer until they are approved or discarded? The brief says nothing is saved until approval; REQUIREMENTS (d) keeps drafts in the state folder | Yes, labelled "Draft, not on the website". Delete them when approved or discarded, and never keep them beyond 90 days. Confirm this, because the stricter reading would drop autosave |
| 2 | Who is on the approver list? | The head of centre as content approver, with a named deputy. Legal, finance and data protection offices named by role. The list lives in Settings |
| 3 | Is a written approval with an email reference enough for legal and finance records? | Yes. The reference (email subject and date) is required on the approval |
| 4 | Who approves a change? REQUIREMENTS (a) gives wording to the content approver; (b) lists the operator as the approver | New public wording, and any change beyond a date or typo, needs the content approver's name from the list. The operator approves dates, places and typos, recorded as "Recorded by" |
| 5 | May the operator add or remove navigation items? REQUIREMENTS (d) allows up to eight; (a) and (b) keep the navigation shape | No. Only the labels and targets of the eight existing items |
| 6 | What drafting time does the centre accept? The brief says 15 to 60 seconds; REQUIREMENTS (g) targets under 120 seconds on 8 GB | Show "up to two minutes on this computer" until measured, then show the measured median |
| 7 | Is the profile-from-CV task (T9) needed in version 1? No use case in REQUIREMENTS (b) uses it | No. Defer it |
| 8 | May a preview be printed or saved as a PDF for institute reviewers? | Yes (proposed). The file carries the same warnings and approval status |
| 9 | After launch, changes need a deploy. How often does the technical contact deploy? | A fixed weekly slot, recorded as "Last deployed" in Settings. The screen warns when a written change is older than the slot |
| 10 | Is removing the "Draft for review" notice an exception to "the operator alone"? | Accept it. The technical contact removes the notice after written legal approval, and launch readiness names the step |
| 11 | Retention: drafts, logs and archive for 90 days; run history for 200 runs (E49, E53, Q12) | Accept |
| 12 | At what free space should the tool warn? | Below 2 GB free (proposed); the technical contact may change it |
| 13 | Is one operator computer the master for each site? | Yes in version 1. A second computer for the same site is not supported (E32, E55) |
| 14 | May a test export leave the building? | Yes, to the technical contact only, labelled "TEST: not for launch" |

## Appendix A. Conflicts found, and how this design resolves them

1. **"Nothing saved until approval" against drafts kept in the state folder** (REQUIREMENTS (d)). Resolved: "saved" means written to the website files. Drafts are kept, labelled, and deleted (question 1).
2. **The operator approves against the content approver approves** (REQUIREMENTS (a) and (b)). Resolved: the operator presses approve, and a named approver is recorded (question 4).
3. **Navigation shape against "up to eight items"** (REQUIREMENTS (a) and (d), screen 16). Resolved: labels and targets only (question 5).
4. **Run backup against archive** (U4 against Q12). Resolved: "Remove" moves a file to the archive for 90 days. The run backup exists only for undo, for 200 runs.
5. **Settings edited as a TypeScript file against "code files must never be writable"** (REQUIREMENTS (e), site settings row). Resolved: no code editing. Screens 14 to 17 stay read-only until P1 (milestone M2).
6. **Whole-form submission against validation on leaving a field** (REQUIREMENTS (d) and the brief). Resolved in section 9.4.
7. **"Size limits set in the Streamlit configuration for each type"** (REQUIREMENTS (d)) against Streamlit's single upload setting. Resolved: the service enforces per-type limits, and the configuration holds the ceiling (to check).
8. **Drafting time**: the brief's 15 to 60 seconds against REQUIREMENTS (g)'s 120 seconds on 8 GB. Resolved by question 6.
9. **"Operator alone" against the legal notice** (U46). Accepted as an exception (question 10).
10. **"Operator alone" against deployment.** A visible change needs a deploy by the technical contact, as the brief says. Resolved by question 9.
11. **Retention periods** (E49, E53, Q12). Resolved by question 11.

## Appendix B. Corrections made while checking the subordinate reports

1. **Launch warning for portraits.** The functional report gave "60 people have no portrait" as an example. The template has 62 people entries, none with a portrait, so the live warning reads "62 of 62 people entries have no portrait" (`scripts/launch-check.mjs` line 91).
2. **Accessibility notice line.** The visual report cites the "Draft for review" notice at `accessibility.astro` line 5. The notice is at line 12. The report also cites `privacy.astro` and `terms.astro` line 12, which the manager did not open.
3. **Content approver citation.** The functional report cites "screen 1 of REQUIREMENTS (a)" for the content approver. That is the content approver row of the persona table in REQUIREMENTS (a).
4. **Decision citation.** The functional report cites `docs/DECISIONS.md` D4 for leaving other matching lines unchanged. D4 concerns exact replacement. This design cites D5 only.
5. **Drafting time and approver entry.** The mockups conflict with the functional report on both points (section 10).

## Appendix C. Verified counts

- 99 entries carry `sample: true` (EDITABLE area 17; counted in `src/content`).
- 62 people entries; none has a `photo:` field (counted in `src/content/people`).
- 11 student projects, 9 events, 2 news items, 2 openings, 3 publications, 12 partners, 4 funded programmes, 4 facilities, 2 documents and 4 gallery albums (EDITABLE section 2).
