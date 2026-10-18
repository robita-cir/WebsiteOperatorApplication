# Operator tool for the CIR website: requirements

**Status:** draft for the CIR team, reviewed 17 October 2026.
**Basis:** the CIR website template at commit `23f4878b60d337ebd18fac22427dcd31bdf14a86`, read file by file (nothing built or run), and the existing operator tool in this repository (`site-agent` v0.1, events only). Facts about the template are in [EDITABLE_SECTIONS.md](EDITABLE_SECTIONS.md). Line numbers there and here refer to the files named.

## At a glance

- The operator changes content through buttons, dropdowns and short forms. A local model drafts wording from facts the operator gives it. Nothing is saved until the operator approves a preview.
- Only content changes. Pages, colours, navigation shape, research directions and the list of content types stay as they are. Structure changes need a developer.
- The template cannot yet be trusted with all content. Three problems must be fixed first (proposed changes P1, P2 and P3 in section (e)): most page wording is written into code files; partners, funding and research cannot be marked as samples, so placeholders there are invisible to the launch check; and a few values silently break links or lists.
- The existing operator tool is a good base. Its default permission to edit code files (`*.astro`, `*.ts`) must be removed, because it would let the tool change the site's structure.
- Windows and WSL2 both need a test on the actual machine before a bundle is committed to. The template's installed packages differ by operating system (`package-lock.json`).

**Words used in this document.** *Record*: one content file with fields, for example one person. *Build*: turning the site files into the public website. *Check*: the template's own check command (build plus HTML check). *Launch check*: the template's readiness list. *Model*: the local language model that drafts wording. *Ollama*: the program that runs the model on the computer. *WSL2*: Windows Subsystem for Linux, version 2. *Approve*: the operator sees the exact changes and clicks Approve. *Block*: the tool refuses to save. *Warn*: the tool shows a warning and the operator may continue.

---

## (a) Operator personas and knowledge level

| Persona | Who | What they know | What they do with the tool | What they must not do |
|---|---|---|---|---|
| Operator (main user) | Lab or centre staff member | The lab, its people, events and processes. No HTML, Astro, npm or git. Comfortable with Windows, email and word processing. May never have used a terminal | Adds and edits records; reviews drafts; approves changes; runs the check; undoes a change; checks the launch list | Edit code or settings files; publish to the live site; set the domain; approve legal or finance text |
| Content approver | Head of centre or a faculty lead | What the centre is willing to say in public. Can read a preview | Approves wording, research descriptions and photographs (with consent). Signs off the launch list | Needs no technical skill; must not change structure |
| Institute reviewers | Legal office, finance office, data-protection contact | Their own policies | Read the legal, privacy, tax and donor text in preview. Give approval in writing; the approval is recorded in the tool | Edit files. Draft text is never produced by the model for them |
| Technical contact | Developer or IT support | Node, npm, WSL2, Windows administration, Ollama, git | Installs the tool and the model; sets the domain and the club link; deploys the built site; upgrades the template; removes the legal "Draft for review" notice after approval | Change the template's structure without a review |
| Website visitor | The public | Varies: phones, screen readers, slow connections | Does not use the tool. Their experience is the test: phone width, keyboard use and clear wording | Not applicable |

---

## (b) Use cases

Each row is one thing the operator might need to do. "Model drafts" lists only text the model may write, from facts the operator supplies. Every use case that writes content ends with an approval step.

### B1. People

| # | Use case and trigger | Operator input | Model drafts | Tool checks | Operator approves | Result |
|---|---|---|---|---|---|---|
| U1 | Add a person. A new member joins, or a former member is to be listed | Name; group (dropdown of six); role; department; interests; homepage (optional); portrait (optional); three to six facts for the profile; consent tick if a portrait is used | Biography, 80 to 150 words, from the facts only | Name present and not already listed (capitals and spacing ignored). Group from the list. Homepage is https. Portrait is JPG or PNG, at least 800 px tall. Biography contains no name, year, number or link that is not in the facts | Card and profile preview; the biography; the consent tick | New person record; portrait copied to the portraits folder under the person's short name |
| U2 | Edit a person. Role, department or interests change | Choose the person; change fields | Optional new biography from new facts | As U1. Project links re-checked | Changed lines shown before and after | Only the changed lines are rewritten |
| U3 | Move a person to an alumni group. The person has left. (This is the template's only "archive") | Choose the person; choose the alumni group | None | Warns that the person stays named in their projects | Confirm the move | Group changed; person moves to the alumni list |
| U4 | Remove a person. Entered by mistake, or a sample is removed | Choose the person | None | Lists projects that name them (those names become plain text). Requires a typed confirmation | Confirm | Record deleted; a copy kept in the run backup |
| U5 | Add or replace a portrait | Image file; consent tick | None | JPG or PNG; at least 800 px tall; warns if not close to 4:5; size limit; file name from the person's short name | Crop preview | Portrait saved; the person's photo field set |

### B2. Student projects and research directions

| # | Use case and trigger | Operator input | Model drafts | Tool checks | Operator approves | Result |
|---|---|---|---|---|---|---|
| U6 | Add a student project. A project is approved | Title; direction (five choices); students (pick from People, or type a name); status (optional); summary facts; featured yes or no | Summary, up to 30 words, from the title and facts | Title up to 120 characters. Each student matched to a person, else a warning with the closest names. At most four featured (warning). Direction from the list | Card and project page preview | Project record created |
| U7 | Edit a project. Students, status or direction change | Choose the project; change fields | None | As U6 | Changed lines shown | Only changed lines rewritten |
| U8 | Write or replace an abstract | Notes, or a draft abstract | Abstract, 120 to 250 words, from the notes | Word count. No new names, numbers or dates. Placeholder text removed | Approve the text | Abstract saved |
| U9 | Feature or unfeature a project for the homepage | Yes or no; order | None | Warns when more than four are featured | Approve | Featured setting saved |
| U10 | Change a research direction's title or description. Wording update | Title (up to 60 characters); description (up to 300) | Optional shorter description, on request | Only the four directions can be edited. Their ids cannot change | Approve | That direction's record changed |
| U11 | Delete a project. Duplicate or cancelled | Choose the project | None | Shows the people whose profiles list it. Typed confirmation | Confirm | Record deleted; backup kept |

### B3. Events

| # | Use case and trigger | Operator input | Model drafts | Tool checks | Operator approves | Result |
|---|---|---|---|---|---|---|
| U12 | Add an event from a notice. A notice arrives by email or on paper | Notice text (pasted or file) | Event fields as a structured object (title, kind, dates, venue) and a one- or two-sentence summary | Dates are real calendar dates. End on or after start. Kind from the list. Every date and venue in the notice must also appear in the notice (otherwise warning). Series from the approved list | Preview of the event card and page, with each drafted field highlighted | Event record created |
| U13 | Change an event's date, time or place. Dates move | Choose the event; new values | Optional summary update | Date rules. Lists other pages that mention the old date or place | Each listed line, before and after | Changed lines saved; other lines listed for review |
| U14 | Cancel or postpone an event | Choose the event; "cancelled" or a new date | Optional short notice for the summary | The template has no cancelled status. Until proposed change P17, the summary is changed | Confirm | Summary changed |
| U15 | Past events leave the upcoming list. Happens by date | Nothing | None | The site decides at each build. The tool shows when the last build was made | None | Archive updated after the next build |
| U16 | Delete an event | Choose the event | None | Typed confirmation | Confirm | Record deleted; backup kept |

### B4. News, announcements and insights

| # | Use case and trigger | Operator input | Model drafts | Tool checks | Operator approves | Result |
|---|---|---|---|---|---|---|
| U17 | Add a news item, announcement or insight. Something is to be published | Kind; date; headline; two to four facts; optional full text | Summary up to 300 characters, and body of 100 to 250 words, from the facts | Headline up to 120 characters. Date valid. Summary present. Nothing beyond the facts | Preview on the list and on the item's page | Record created; homepage updated at the next build |
| U18 | Edit or delete a news item. A correction or a withdrawal | Choose the item | Optional rewrite | As U17 | Changed lines, or a typed confirmation for delete | Record changed or deleted |

### B5. Job openings

| # | Use case and trigger | Operator input | Model drafts | Tool checks | Operator approves | Result |
|---|---|---|---|---|---|---|
| U19 | Add an opening. A position is approved | Title; type (seven choices); deadline; summary facts; apply email (blank means the centre's general address) | Summary up to 400 characters, from the facts | Type from the list. Deadline a real date. Email valid. Warns if the deadline has passed | Preview | Record created |
| U20 | Close an opening. Post filled or deadline passed | Choose the opening; set status to closed | None | Warns if the deadline has passed and the status is still open | Confirm | Status set to closed; listed as "Applications closed" |
| U21 | Reopen or extend an opening. Deadline moved | New deadline; status open | None | Deadline is today or later | Confirm | Record changed |

### B6. Publications

| # | Use case and trigger | Operator input | Model drafts | Tool checks | Operator approves | Result |
|---|---|---|---|---|---|---|
| U22 | Add a publication from a DOI or a pasted reference. A paper is accepted or published | DOI, or the pasted reference | Fields taken from the pasted text only: authors in order; type from the list | DOI cleaned (web prefix and "doi:" removed). Format checked. Duplicate DOI blocked. Year from 1950 to next year. At least one author. Optional online lookup, off by default | Preview of the entry, as it will appear | Record created |
| U23 | Add a publication without a DOI (preprint, thesis, working paper) | Title; authors; venue; year; type; web link | None | Link is https. Year and authors checked | Preview | Record created |
| U24 | Fix a DOI that does not resolve. A check shows it is broken | New DOI | None | Format. Resolution if online | Confirm | DOI changed |
| U25 | Remove sample publications before launch | Choose items | None | Shows the "[Sample]" title on each | Confirm | Records deleted |

### B7. Partners and funded programmes

| # | Use case and trigger | Operator input | Model drafts | Tool checks | Operator approves | Result |
|---|---|---|---|---|---|---|
| U26 | Add a partner. A new collaboration starts | Name; country; academic or industry; present or former; summary; featured yes or no | Summary up to 200 characters, from the facts | Name required. Featured partners show on the homepage only when present. Warns above six featured | Preview | Record created |
| U27 | Mark a partner as former. A collaboration ends | Choose the partner | None | Warns if the partner is named in a funded programme | Confirm | Status changed |
| U28 | Add a funded programme. A grant is awarded | Title; funder; partner (pick or type); amount as the funder writes it; period; summary | Summary from the facts | Warns if the partner is not on the partners list. Amount and period kept as text | Preview | Record created |
| U29 | End a funded programme. The programme has finished | Choose the programme | None | No status field exists (proposed P16). Until then the only route is delete | Confirm | Record deleted |

### B8. Facilities

| # | Use case and trigger | Operator input | Model drafts | Tool checks | Operator approves | Result |
|---|---|---|---|---|---|---|
| U30 | Add or edit a facility. New or changed equipment | Name; kind (pick or type); summary; order | Summary up to 200 characters, from the facts | Name and summary required | Preview | Record created or changed |
| U31 | Remove a facility. Equipment retired | Choose the facility | None | Typed confirmation | Confirm | Record deleted; backup kept |

### B9. Documents (PDF files)

| # | Use case and trigger | Operator input | Model drafts | Tool checks | Operator approves | Result |
|---|---|---|---|---|---|---|
| U32 | Upload a PDF. A report or policy is approved | PDF file; title; kind; date; description | None | The file really is a PDF (checked from its start, not its name). Size limit (proposed 20 MB). File name cleaned. Title and description present. Warns that PDFs are not checked for accessibility | Preview of the download entry; file name | PDF saved in the documents folder; document record linked |
| U33 | Replace or remove a PDF. A new version, or withdrawal | New file, or remove | None | As U32. The old file kept in the backup | Confirm | File replaced or removed |

### B10. Gallery albums

| # | Use case and trigger | Operator input | Model drafts | Tool checks | Operator approves | Result |
|---|---|---|---|---|---|---|
| U34 | Add or edit an album (text only). An event is planned | Title; period; description | Description up to 300 characters, from the facts | Title and description required | Preview | Album created or changed |
| U35 | Add photographs to an album. Photographs are supplied | Photographs, captions, consent | None | Not supported by the template. The tool says so and writes nothing until proposed change P15 is made | Not available in version 1 | Nothing written |

### B11. Site settings and contact details

| # | Use case and trigger | Operator input | Model drafts | Tool checks | Operator approves | Result |
|---|---|---|---|---|---|---|
| U36 | Change contact details. The email, phone or address changes | Email; phone; two address lines | None | Email valid. Phone in an accepted format. Display and dialling versions produced from one entry. Warns that the privacy notice must be reviewed if the address changes | Confirm | Settings changed |
| U37 | Change the institute name or short names | Names | None | Not blank, and not still "Institute name". Warns if the name appears in legal text | Confirm | Settings changed |
| U38 | Change the student club link | Web address; label | None | Address must be https. Warns on example.org or GitHub addresses | Confirm | Link changed |
| U39 | Set the domain. Final address confirmed | Domain | None | https. Both places changed together | Technical contact confirms | Two values changed |
| U40 | Change a navigation or footer label | Label; target page (dropdown of existing pages) | None | Target must exist. At most eight navigation items. Labels up to 16 characters (proposed) | Confirm | Changed |

### B12. Page wording

| # | Use case and trigger | Operator input | Model drafts | Tool checks | Operator approves | Result |
|---|---|---|---|---|---|---|
| U41 | Change homepage text. A refresh of the wording | Headline (up to 80 characters); lead (up to 300); headings; button labels | Optional lead rewrite, from the facts | Length. No placeholder text left. Claims listed for the approver | Preview of the homepage | Text changed (needs P1) |
| U42 | Change About text: mission, history, milestones, leadership | Paragraphs; milestone year, title and text (text up to 200 characters); leadership name chosen from People | Optional mission rewrite, from the facts | Leadership names must match People entries (needs P4) | Preview | Text changed |
| U43 | Edit the Join page questions and answers | Question; facts for the answer | Answer up to 80 words, from the facts | No eligibility, fee or deadline claim that is not in the facts | Approve | Answer changed; "Sample" label removed (needs P10) |
| U44 | Edit Support text: giving routes, tax notes, donor tiers | Wording approved by the finance office | None. The model is not used for finance text | Only non-empty text. Warns if placeholder wording remains | Finance approval recorded (name and date) | Text changed |
| U45 | Edit contact enquiry types and the campus note | Text | Optional rewrite | Length | Confirm | Changed |
| U46 | Edit the legal pages (accessibility, privacy, terms). Institute review | Text; values for each bracketed field | None. The model does not draft legal text | Lists bracketed fields still open. The "Draft for review" notice cannot be edited or removed by the tool | Institute approval recorded (name and date) | Text changed. Notice removed only by the technical contact |
| U47 | Change the workshop series title and lead | Title; lead | Optional rewrite | Length | Confirm | Changed |

### B13. Samples and placeholders

| # | Use case and trigger | Operator input | Model drafts | Tool checks | Operator approves | Result |
|---|---|---|---|---|---|---|
| U48 | Review every sample entry before launch | Nothing | None | Lists every sample entry by area, and the pages that show the Sample label | For each: replace, or remove | Records updated |
| U49 | Remove all samples in one step | Confirm the count | None | Blocks if a remaining entry depends on a sample (for example a project that names a sample person) | Typed confirmation | Samples removed; backup kept |
| U50 | Find remaining placeholder text | Nothing | None | Scans records and page wording for the markers listed in EDITABLE_SECTIONS, area 17 | Fix each one | List cleared |

### B14. Check, preview and undo

| # | Use case and trigger | Operator input | Model drafts | Tool checks | Operator approves | Result |
|---|---|---|---|---|---|---|
| U51 | Run the site check after changes | Nothing | None | Runs the configured check command. Turns each error into a plain sentence naming the file and field | Reads the result | Pass, or a plain error with file and field |
| U52 | Preview the site | Nothing | None | Needs a successful build. If there is none, says so | None | Local preview opens in the browser |
| U53 | Undo a change. A mistake is noticed | Choose the run | None | Refuses if the file has changed since the run | Confirm | Files restored; the undo is logged |

### B15. Launch preparation and handover

| # | Use case and trigger | Operator input | Model drafts | Tool checks | Operator approves | Result |
|---|---|---|---|---|---|---|
| U54 | Prepare the launch. A launch date is set | Approval records for content, legal and finance | None | Runs the template's launch check plus the extra checks in section (e). Lists blockers and warnings | Approval boxes ticked and recorded | Readiness report saved |
| U55 | Hand over the built site. Launch is ready | Nothing | None | Creates an export folder with the build and checksums. Does not contact any server | Technical contact deploys the folder | Export folder created |

### B16. Writing helper (the model)

| # | Use case and trigger | Operator input | Model drafts | Tool checks | Operator approves | Result |
|---|---|---|---|---|---|---|
| U56 | Check the writing helper. Start of a session, or after an error | Nothing | None | Server reachable. Model installed. A short test reply and its time | None | Status shown on the start screen |

---

## (c) Edge cases and failure modes

Each row names something that can go wrong and what the tool must do. Behaviour words: **Block** (refuse to save), **Warn** (show, let the operator continue), **Ask** (the operator must choose), **Fallback** (a safe default), **Log** (record in the history).

| # | Situation | What can go wrong | Required behaviour |
|---|---|---|---|
| E1 | A date with no year or in an unclear form (for example "10/03/2026" or "next Tuesday") | Read as the wrong day or month. Some software reads 10/03 as 3 October | Block until the operator picks a date from a calendar. The model returns ISO dates (YYYY-MM-DD) only. The tool never guesses |
| E2 | The notice gives no date for an event or news item | A required field is empty | Block; Ask the operator for the date |
| E3 | End date before start date | The template does not check this | Block |
| E4 | A multi-day event, or a one-day event | Dropped from "upcoming" at midnight UTC on its last day, which is early morning in India, for example | Keep the event upcoming through its whole last day in the centre's time zone (needs P8). Until then, the start screen lists events that end today or tomorrow |
| E5 | The site is not rebuilt after dates pass | "Upcoming" is stale | Warn on the start screen when the last build is over one day old and an event has passed. Offer to run the build |
| E6 | Two people with the same name | Project links and profiles go to the wrong person | Block duplicates (capitals and spacing ignored). Ask for a unique display name if two real people share one |
| E7 | A student name typed differently from the person's name | The link and the profile entry silently disappear | Warn with the closest matches. Ask the operator to choose |
| E8 | A person has no portrait | Initials are shown | Allow. The preview shows the initials |
| E9 | A portrait path is wrong or the file is missing | A broken picture, with no build error | Block. The tool writes the photo path only after the file is in place. The launch check lists missing files |
| E10 | A portrait is too small or the wrong shape | Blurred or cropped faces | Block below 800 px tall. Warn outside about 4:5 and offer a crop |
| E11 | A very large photograph (for example a phone photo of 10 MB or more) | Slow page; upload fails | Resize to 1,000 px tall and keep the original in the backup (proposed). Block an original above 20 MB (proposed) |
| E12 | A phone photograph is stored sideways | Portrait shown sideways | Apply the rotation stored in the file when importing (proposed) |
| E13 | Alternative text for images | Visitors using screen readers hear nothing or a file name | Portraits use the person's name (template rule). Gallery photographs, once supported, are blocked until a caption and alternative text are written |
| E14 | A very long title or name | Heading spreads over many lines; the browser tab title is cut at about 68 characters | Warn at 70 characters. Block at 120 |
| E15 | A very long unbroken text (a web address or DOI) | Overflows on a phone | Allow (the template wraps it). The tool shows a phone-width preview (proposed) |
| E16 | A navigation label that is too long | The header overflows on a desktop screen | Block over 16 characters (proposed) |
| E17 | The model writes a fact that was not given (a name, number, date or link) | False information looks plausible and gets published | Fact check: every number, date, name and link in a draft must appear in the operator's input. Otherwise the tool highlights it and blocks until it is removed or confirmed |
| E18 | The model's reply is not in the right format | Bad data reaches the save step | Retry once with stricter instructions. Then show an empty form with what could be read. Nothing is saved from a failed reply |
| E19 | The model is slow or runs out of memory | The computer freezes or the tool crashes | Time limit (default 300 seconds). A cancel button. Warn not to run the build and the model together on an 8 GB computer |
| E20 | The model server is not running | Drafting fails | Plain message; manual entry still works. Nothing crashes |
| E21 | The model server address points to another computer | Notices and CVs leave the computer | Block unless the technical contact has set the address. Show the address on the Settings screen |
| E22 | The operator asks for legal, tax, finance or medical wording | Legal risk | Not offered. The tool says the institute must write this text |
| E23 | A DOI pasted with a web prefix or "doi:" in front | Broken link | Clean the DOI and show the cleaned value before saving |
| E24 | A DOI that does not resolve, or uses the placeholder prefix 10.0000 | Broken link on the publications page | Warn "DOI not confirmed". Allow saving with a reason noted. Never block for lack of internet |
| E25 | The same DOI is already listed | A duplicate entry | Block. Show the existing entry |
| E26 | A publication has both a DOI and a web link | Only the DOI is shown; the link is hidden | Warn that only the DOI will show. Ask which to keep |
| E27 | The check fails after a save | The site cannot be built | Keep the saved change. Show the error in plain English. Offer Undo. Mark the site "not ready" until it passes |
| E28 | The build error names a file or field the operator does not understand | Confusion and guesswork | Translate common messages (missing field, wrong choice, invalid date, invalid address) into plain instructions. Keep the original message in a "details" box for the technical contact |
| E29 | The HTML check fails (markup problem) | A page may be broken | Show the page and the rule. No automatic fix. The technical contact decides |
| E30 | Node is missing or older than 22.12 | The build cannot run | Block the build with a plain message. Editing still works |
| E31 | Dependencies installed on another operating system (for example a folder copied from Windows to WSL2) | The build fails in confusing ways | Detect the mismatch (a marker file records the system). Ask the technical contact for a fresh install |
| E32 | Two people edit the same file at the same time | One overwrites the other | Compare the file's fingerprint at load and at save. If it changed, Block and offer to reload |
| E33 | A file is open in another program (Windows) | A save fails midway | Retry three times over a few seconds. Then a plain message ("close the file in other programs"). Never leave a half-written file |
| E34 | The site folder is inside a cloud-synced folder (OneDrive, Dropbox, Google Drive) | Locked files; duplicate copies created by the sync | Warn at start-up. Recommend a local folder (section f) |
| E35 | Power cut or crash during a save | A corrupted file | Write to a temporary file, then replace the original in one step |
| E36 | A name that Windows reserves (CON, PRN, AUX, NUL, COM1 to COM9, LPT1 to LPT9) | The file cannot be created | Block. Add a word to the name |
| E37 | Two names that differ only in capitals (Jane-Doe and jane-doe) | Collide on Windows | The uniqueness check ignores capitals |
| E38 | Accented letters or dashes in names and titles (Müller, "human–robot") | File names break or look wrong | Keep the text as typed in the file, saved as UTF-8. Make the file name plain ASCII (for example "muller") |
| E39 | A long folder path on Windows | Tools fail when the path passes 260 characters | Check the path length at start-up. Recommend a short folder near the drive root |
| E40 | An entry is renamed after it is published | Its web address changes and old links break | Block renaming. Offer to create a new entry instead. A redirect is needed for a true rename (proposed P19) |
| E41 | An entry that other pages depend on is deleted (a student, a partner named by a funded programme) | Pages lose links or show blanks | Warn and list the dependants. Delete only after confirmation |
| E42 | "[Sample]" is left in a title after the sample is replaced | Visitors see "Sample" | The tool strips the prefix when a sample is replaced. The launch check lists any left |
| E43 | Bank account details or private personal data typed into a text field | The data is published | Block strings that look like bank account numbers or IBANs. Warn on personal phone numbers and email addresses |
| E44 | A photograph without consent | A privacy breach | Block until the consent box is ticked. The consent is recorded with the change |
| E45 | An opening's deadline has passed but its status is still open | The position still shows "Apply by email" | Warn, and offer to close it. The template will not close it by itself |
| E46 | More than four featured projects, or more than six featured partners | Extra items are hidden without notice | Warn. Show which items will appear |
| E47 | The address or phone number changes | The privacy notice and the footer disagree | Warn that the privacy notice must be reviewed. Both phone fields always change together |
| E48 | Homepage counts include sample entries | Wrong numbers are shown | Warn on the start screen. Proposed P18 counts only published entries |
| E49 | Run logs keep notices and CVs | Personal data kept on the computer | Keep logs for 90 days (proposed) and provide a purge. Logs are never sent anywhere |
| E50 | A settings file has an unknown key or a typo (for example "modle") | The wrong model runs without warning | Block at start-up and name the key (existing rule D10) |
| E51 | The template is upgraded without updating the tool | The tool follows old rules | Compare a fingerprint of the template's rules at start-up. Block saves until the tool is updated |
| E52 | A new model or new prompt is introduced | Quality drops without anyone noticing | Run a fixed test set (sample notices with known answers) before a new model is used |
| E53 | The backup folder fills the disk | Saves fail | Keep the last 200 runs (proposed). Warn when free space is low |
| E54 | An undo after the file was changed by someone else | Newer work is overwritten | Refuse the undo if the file changed since the run (existing rule S4) |
| E55 | Two copies of the tool run on the same site | Two write paths | A lock file in the site's state folder. The second copy refuses with a plain message |
| E56 | A file renamed to .pdf that is not a PDF | Broken download | Check the file's first bytes. Block if it is not a PDF |

---

## (d) User interface requirements (Streamlit, version 1)

**Principles**

- One screen for one task. The operator sees exactly what will change before anything is saved.
- Every fixed choice is a dropdown. Typing is for facts the operator knows.
- Every save goes through review and then approval. No silent writes.
- Plain English on every operator screen. Technical details appear only in a "For the technical contact" box.
- The undo button is visible on every result screen.
- The screens call only the service facade (section e). They contain no site rules.

**Screens and form fields**

| # | Screen | Fields and controls, in order | Limits and help text |
|---|---|---|---|
| 1 | Start | Panels (read-only): writing helper status with a "Check" button; site folder; last check result and its age; count of sample entries; list of the three most important warnings | Shows "last build was N days ago" when old |
| 2 | People | Table with a group filter; buttons Add, Edit, Move to alumni, Delete. Form: Name (80); Group (dropdown, six); Role (80); Department (120); Interests (tags, up to 10, 60 each); Homepage (https web address); Portrait (upload, JPG or PNG, 20 MB; resized on import); Consent (tick box, required with a portrait); Order (number, 1 to 999); Facts for the profile (text, 1,000 characters); Biography (generated at 80 to 150 words; editable up to 250) | Help: "Write the name as it should appear on the website" |
| 3 | Projects | Table grouped by direction. Form: Title (120); Direction (dropdown, five); Students (multi-select from People, plus "type a name" with a warning); Status (optional dropdown); Summary (300); Featured (tick box, warns above four); Order; Abstract (generated, 120 to 250 words) | Warning shown when a student is not in People |
| 4 | Research directions | Four cards. Form: Code (4); Title (60); Description (300) | Help: "The four directions are fixed by the website's structure" |
| 5 | Events | Tabs: Upcoming; Past; Add from a notice. Notice tab: Notice text (3,000 characters); "Read notice" button. Event form: Title (120); Kind (dropdown, three); Series (dropdown: none or the approved list); Start date (calendar); End date (calendar, not before start); Venue (120); Summary (300); Description (generated, 60 to 200 words) | Warnings for any date or place not found in the notice |
| 6 | News | Table. Form: Kind (dropdown, three); Date (calendar); Headline (120); Summary (300); Full text (generated, 100 to 250 words) | |
| 7 | Job openings | Table grouped by open and closed. Buttons: Close now; Reopen. Form: Title (120); Type (dropdown, seven); Status (open or closed); Deadline (calendar, optional); Summary (400); Apply email (optional); Order | Warning when the deadline has passed |
| 8 | Publications | Add-from-DOI panel: DOI; "Look up" button; optional reference text. Form: Title (250); Authors (one per line, in order, at least one); Venue (120); Year (number); Type (dropdown, six); DOI; Web link (optional); Direction (optional) | DOI check result shown in plain words |
| 9 | Partners | Table in three groups: academic, industry, former. Form: Name (120); Country (60); Kind (dropdown, two); Status (dropdown, two); Summary (200); Featured (tick box); Order | |
| 10 | Funded programmes | Table. Form: Title (120); Funder (120); Partner (pick from list or type); Amount (60, "as the funder writes it"); Period (30, for example 2024–2027); Summary (300); Order | |
| 11 | Facilities | Table. Form: Name (120); Kind (pick or type); Summary (200); Order | |
| 12 | Documents | Table. Form: Title (120); Kind (dropdown, five); Date (calendar, optional); Description (300); PDF (upload, PDF only, 20 MB) | Shows whether a PDF is attached |
| 13 | Gallery | Table of albums. Form: Title (120); Period (30); Description (300); Order | Notice: "Photographs are not supported yet" |
| 14 | Page wording | One section per page in EDITABLE_SECTIONS, area 14. Each section: its fields (text boxes) and a "Preview page" button | Length limits per field (proposed) |
| 15 | Contact and names | Name; short name; institute; institute short name; institute website (https); email; phone; address (two lines); student club label and link | Domain is not on this screen (technical) |
| 16 | Navigation and footer | Navigation items: label (16) and target (dropdown of existing pages). Footer: link labels and targets within the fixed columns | At most eight navigation items |
| 17 | Legal pages | For each of the three pages: its text sections; each bracketed field as its own box; approval record (approver name and date) | The "Draft for review" notice is shown but cannot be edited on this screen |
| 18 | Samples and placeholders | List of sample entries by area; placeholder scan results; buttons Replace, Remove, and Remove all (with count) | |
| 19 | Check and preview | "Check the site" button; results in plain English with a details box; "Open preview" button; "Export for technical contact" button | Shows the last result and its time |
| 20 | History | List of runs (date, what changed, who approved); "Undo last change" button; details | |
| 21 | Launch | Launch checklist in plain English; status per item; approval boxes; "Save readiness report" button | Does not publish anything |
| 22 | Settings (technical) | Site folder; writing helper address and model name; time zone for events; check command (fixed, shown only); upload limits; log retention | Locked by a technical password (proposed) |
| 23 | Help | How to use each screen; a short glossary; who to contact | |

**Behaviour shared by all screens**

- Forms are submitted as a whole (Streamlit forms), so half-finished entries are not saved.
- Long tasks (drafting, the build) run in the background with a progress message and a cancel button.
- Uploads are checked on the server, not only in the browser. Size limits are set in the Streamlit configuration for each type.
- The tool listens only on the local address (127.0.0.1) and says which address to open.
- Drafts are kept in the state folder so they survive a restart.
- Text uses British English. Error messages say what to do next.
- The tool's own screens meet WCAG 2.2 AA contrast and can be used from the keyboard (proposed).
- Previews are shown at phone width as well as desktop width (proposed).

---

## (e) Service architecture

### Layers

```
Screens (Streamlit)            replaceable; any other front end can replace this layer
      |  calls only
Service facade (api)           one function per operator action; returns plain results
      |
Services                       people, projects, research, events, news, openings,
                               publications, partners, funding, facilities, documents,
                               gallery, site settings, page wording, legal pages,
                               samples, placeholders, launch, drafting
      |  use
Rules                          schema rules, references, dates, DOI and web addresses, slugs
      |  use adapters
Adapters                       content store, model client, build runner, media,
                               history, configuration, platform (Windows and WSL2)
```

### Modules (one responsibility each)

| Module (proposed name) | One responsibility | Main interface | How it stays replaceable |
|---|---|---|---|
| `ui` | Show screens and collect input | Streamlit pages only | Imports only `api`. Contains no rules |
| `api` | One function per operator action | For example `preview_person(form)`, `approve(preview_id)`, `run_check()`. Returns plain results | The single entry point. Another front end calls the same functions |
| `config` | Read settings; reject unknown keys | `load_settings(folder)` | Exists today (`config.py`) |
| `content_store` | Read and write content files safely | `list(collection)`, `read(collection, id)`, `write(collection, id, record, body, expected_fingerprint)`, `delete(...)`, `fingerprint(...)` | An interface (`ContentStore`). A database could replace the files later |
| `frontmatter` | Change only the changed lines of a file's top block | `set_values(text, changes)`, `render(record, body)` | Exists today (`frontmatter.py`) |
| `schema_rules` | The template's rules per collection, with proposed limits; a fingerprint of the template's rules | `validate(collection, record)` returns plain messages | A table of rules, checked against the template at a pinned commit |
| `references` | Checks between entries and files | `check_students(names)`, `check_partner(name)`, `check_files()`, `dependants(entry)` | Works through `content_store` |
| `slugs` | Short names for file names and web addresses | `make_slug(title, taken)`, `is_reserved(name)` | Pure functions, tested with Windows reserved names |
| `dates` | Strict date reading; the upcoming rule | `parse_iso(text)`, `is_upcoming(event, now, zone)` | The time zone comes from settings |
| `identifiers` | DOI and web-address rules | `clean_doi(text)`, `check_doi(doi, online)`, `check_url(url)` | The online lookup is an optional adapter, off by default |
| `media` | Portraits and PDFs: checks, resizing, copying | `import_portrait(file, slug, consent)`, `import_pdf(file, slug)` | Image handling behind an interface |
| `drafting` | Build the prompt for each task, call the model, check the result | `draft(task, facts)` returns a draft with warnings. Never writes | Prompts are text files. The model is reached through `model_client` |
| `model_client` | Talk to the local model server | `health()`, `complete(messages, json_mode)` | Adapters: Ollama (exists) and an OpenAI-compatible server (exists) |
| `page_wording` | Read and write fixed page wording | `sections()`, `get(key)`, `set(key, text)` | Works on a data file after P1. Until then, a fixed map of keys to lines, tested |
| `site_settings` | Read and write site settings | `get()`, `set(...)` | A data file after P1. Until then, a strict editor for the TypeScript file |
| `legal_pages` | Legal text, bracketed fields and the protected notice | `open_fields(page)`, `set_field(page, field, text)` | The notice text is protected by a test |
| `samples` | Find, replace or remove sample entries | `list()`, `replace(...)`, `remove(...)` | Uses `references` to find dependants |
| `placeholders` | Scan for placeholder markers | `scan(site)` | Marker list kept in one file |
| `build` | Run the check command and read the result | `run_check(timeout)` returns messages mapped to file and field | The command comes from settings only (existing rule S8) |
| `launch` | Build the launch report | `report()` returns blockers, warnings and passes | Reads the template's launch check output and adds its own checks |
| `history` | Runs, backups, undo, approvals | `list_runs()`, `restore(run_id)`, `record_approval(...)` | Exists in part (`apply.py`); split out |
| `platform` | Paths, line endings, file locks, long paths, Node and model detection | `to_site_path(...)`, `write_text(path, text)`, `check_environment()` | One adapter per operating system |
| `export` | The handover folder with checksums | `export(folder)` | |

### Rules for replaceability

- The screens and `api` never import an adapter directly. The adapters are passed in at start-up in one place.
- A content type is data: a rule table, a folder, and a template for showing it. Adding one should not need a new class.
- Storage, the model and the screens can each be replaced without changing the rules.
- The rules are tested against example records with no model and no network.
- Every message the operator sees comes from one file, so wording can be changed without code changes.

### Existing code to keep and extend

- Keep: `config.py`, `frontmatter.py`, `validate.py`, `apply.py`, `workflows.py`, `events.py`, `llm/` (Ollama and OpenAI-compatible clients), `prompts/`, `text_utils.py`, `plan.py`, `errors.py`.
- `cli.py` becomes one front end among others. The Streamlit screens are a second.
- `schemas.py` covers only events today. It must cover every collection (through the rule table).

### Changes to existing rules (proposed)

- **Write permissions.** The default writable paths (`site-agent.example.toml`: `src/**/*.md`, `src/**/*.astro`, `src/**/*.ts`, `src/**/*.tsx`) must be narrowed to content and media only: `src/content/**/*.md`, `public/people/**`, `public/documents/**`, and the settings data file once P1 creates it. Code files must never be writable by the operator tool. It would supersede decision D7 in `docs/DECISIONS.md`, once agreed.
- **Atomic writes.** Writes are direct today (`site.py` line 68 writes straight to the file). Use a temporary file and a single replace, with retries on Windows.
- **Shell command.** The check command runs through the shell (`apply.py` lines 116-118, `shell=True`). On Windows that is cmd.exe; on WSL2 it is sh. Keep one configured command and test it on both.
- **Template state folder.** The tool asks that `.site-agent/` be listed in the website's `.gitignore`. The template's `.gitignore` does not list it (add it, P12).
- **Missing documents.** The tool's README links to `docs/PLANNING.md`, `docs/MODELS.md`, `docs/TEMPLATE_CONTRACT.md` and `CONTRIBUTING.md`. None of them exists in the repository. `docs/ARCHITECTURE.md` links to PLANNING.md. These must be written or the links removed.

### Template changes needed (proposed)

These keep every page's layout and structure. They move wording into data files, make placeholders visible to the launch check, and remove silent breakages.

| ID | Change | Why | Priority |
|---|---|---|---|
| P1 | Move page wording (EDITABLE_SECTIONS area 14) and site settings (area 13) into data files that pages read | Most wording lives in code files | Must |
| P2 | Give research directions, partners and funded programmes a sample flag, and add a placeholder scan to the launch check | Placeholders there are invisible today | Must |
| P3 | Replace the literal series name `series-1` (`events.astro` 21; `index.astro` 31) with a fixed list of series | Any other series name is silently dropped | Must |
| P4 | About page: read facilities and leadership from their collections, or remove the duplicates | Two copies of the same facts | Should |
| P5 | Use the site email on the people page (line 140) and the gallery page (line 45) | Hard-coded addresses | Must |
| P6 | Make the header monogram read the short name; set the domain in one place; make the displayed and dialling phone numbers come from one entry | Two sources for one value | Should |
| P7 | Display the social-links setting, or remove it | A setting that does nothing | Should |
| P8 | Events: block end dates before start; keep an event upcoming through its last day in the centre's time zone | Wrong cut-off | Must |
| P9 | Build-time checks: DOI without a web prefix; photo and document paths must exist (missing file fails the build); https-only club and homepage links | Broken links pass silently | Must |
| P10 | Show the Sample label on every people list and on homepage faculty cards (`index.astro` 143). Show the FAQ label only on sample answers | Mislabelled content | Should |
| P11 | Publications: show the web link even when a DOI exists, or document the rule | A link is hidden | Should |
| P12 | Add `.site-agent/` to the template's `.gitignore` | Tool files would enter version control | Must |
| P13 | Launch check: fix the message path (`docs/06` should be `docs/03`); check the domain in both files; check the institute name, email, phone and address for placeholder values | Launch check misses real problems | Must |
| P14 | Decide the licence and add a licence file (the template has none) | Legal position unclear | Must before sharing |
| P15 | Gallery: a photo list with captions and alternative text. Partner logos as an option | Photographs cannot be added | Should, before the first event photographs |
| P16 | Funded programmes: a status (current or finished) | A finished programme cannot be hidden | Should |
| P17 | Events: a status (cancelled or postponed) and a notice line | A cancellation cannot be shown | Should |
| P18 | Homepage and page counts: count only published, non-sample entries | Counts are wrong while samples exist | Should |
| P19 | A redirect list, so renamed or removed pages keep working | Old links break | Should |

P1, P2 and P3 should be agreed before the operator tool is built. Otherwise the tool can only edit what is already in data files (people, projects, events, news and similar), and the placeholders stay invisible.

---

## (f) Cross-platform requirements (native Windows and WSL2)

| Topic | Requirement | Applies to | Evidence |
|---|---|---|---|
| Operating systems | The tool and the site build must both run on native Windows and on WSL2 (Ubuntu). Test each on the actual machine before the bundle is committed | Both | The tool's README says Windows has not been tested. The template says to use WSL (`README.md` 33; `docs/03` 13) |
| Node | Node 22.12 or newer, checked at start-up. On Windows, use a portable (zip) Node 22 build so no installer or administrator rights are needed (technical contact to confirm) | Both | `package.json` lines 7-9 |
| Platform-specific packages | Do not copy `node_modules` or a Python environment between Windows and WSL2. Install on each machine. Each operating system has its own compiled files | Both | `package-lock.json` lists compiled packages for win32, linux and darwin (for example `@astrojs/compiler-binding-win32-x64-msvc` and `…-linux-x64-gnu`) |
| Paths | Store paths relative to the bundle. Never write `C:\` or `/mnt/c` into settings. Convert paths in one platform adapter | Both | `astro.config.mjs` lines 14-16 |
| Where the site lives | On WSL2, keep the site on the Linux file system, not on a Windows drive (`/mnt/c`, `/mnt/d`). File-change events are unreliable there, which is why the template polls | WSL2 | `astro.config.mjs` lines 14-16 |
| Line endings | Write LF line endings and UTF-8 without a byte-order mark. Read files with or without the mark | Both | `.gitattributes` line 2 (`text=auto eol=lf`). `site.py` line 68 writes LF; line 49 reads `utf-8-sig` |
| Long paths | Windows limits paths to 260 characters by default. Keep the site folder near the drive root (for example `C:\CIR\site`). Check the length at start-up. Enabling long paths needs administrator rights (technical contact) | Windows | General Windows behaviour; a deep `node_modules` tree is likely to exceed the limit. To verify on the target machine |
| File names | Apply the reserved-name, trailing-dot and capital-letter rules (section c, E36 and E37) | Windows | `slugs` module |
| File locks | A file open in another program, or held by a preview server, can block saves and replacements. Retry, then give a plain message. Build into a new folder and then swap (proposed). Do not write into `dist/` while the preview runs | Windows | No retry exists today (`apply.py`). The Astro dev server watches files (`astro.config.mjs` 14-16) |
| Synced folders | Do not keep the site in OneDrive, Dropbox or Google Drive folders. Warn at start-up | Windows | General behaviour (section c, E34) |
| Memory | On an 8 GB computer, do not run the build and the model at the same time | Both | General. To verify by measurement |
| Model server | Default address `http://localhost:11434`, set in settings. The tool checks it is reachable and the model is installed. On WSL2 with Ollama on Windows, test the address that the bundle uses. Never start an unknown program automatically | Both | `llm/ollama.py` line 26 (`/api/chat`); `site-agent.example.toml` `base_url` |
| Model files | Models are large and Ollama keeps them in its own folder, whose location differs by system. The bundle holds a manifest (model name and checksum), not the model | Both | General Ollama behaviour |
| Local address and firewall | Streamlit listens on 127.0.0.1 only. The Windows firewall may ask for permission; allow private networks only | Windows | Section (d) |
| Administrator rights | The tool runs as a normal user. Installing Node, Ollama or long-path support may need an administrator (technical contact) | Windows | General |
| Check command | The check command must work the same in cmd.exe and sh. Keep it simple and test on both | Both | `apply.py` 116-118 |
| Text encoding | Names with accents and dashes are UTF-8 in files and in the console | Both | `cli.py` line 222 sets UTF-8 on the output stream |
| Launchers | Use `.bat` files or a Python launcher. Avoid PowerShell scripts (execution policy) and avoid shell-only launchers | Both | General |
| Antivirus | Unsigned programs may be blocked by Windows SmartScreen. Provide signed files, or a documented way to allow them | Windows | General |

### Bundle requirements

- **What the bundle holds:** the tool (a pinned version); a Python environment created on each machine; the site folder (the template at its pinned commit, with the approved changes); a settings file with relative paths only; prompt files; the operator guide; a model manifest; optionally a portable Node 22 for each system.
- **What the bundle does not hold:** `node_modules`, Python environments, and the model files. These are created or pulled on each machine.
- **Two builds, one source:** one bundle for Windows and one for WSL2, built from the same source with the same version numbers.
- **Moving between machines:** copy the content, backups, run logs and settings. Do not copy `node_modules`, Python environments or Node. The technical contact runs the set-up step on the new machine.
- **Start-up checks:** Node version; Ollama reachable; model installed; site folder found; the site's dependencies match the system; path length; cloud-sync warning; template fingerprint.
- **Upgrades:** replace the tool folder; keep the state folder (backups, runs, drafts) and the content.
- **Pinning:** the Python dependencies are pinned in a lock file (proposed) so a rebuilt bundle behaves the same.

---

## (g) Model requirements

### Tasks, outputs and context

Context means the text the model reads plus the text it writes. The sizes below are targets to be measured on the actual computer, not measured results.

| Task | Input | Output format | Output limit | Context needed (target) | Checks after the model |
|---|---|---|---|---|---|
| T1 Notice to event fields | A notice, usually 50 to 300 words | One structured object with fixed keys | About 300 tokens | 2,048 (3B) to 4,096 (8B) | Format; every date, place and name appears in the notice; kind from the list |
| T2 Event summary and description | Event fields and facts | Summary: one or two plain sentences. Description: 60 to 200 words, plain paragraphs | About 80 tokens (summary); about 300 (description) | 3,072 | Length; no new facts |
| T3 Person biography | Three to six facts | Two to four plain paragraphs. No headings, no links | About 300 tokens | 3,072 | 80 to 150 words; no name, year, number or link not in the facts |
| T4 Project summary | Title, students, direction, facts | One or two sentences, up to 30 words | About 60 tokens | 2,048 | Length; names match People |
| T5 Project abstract | Title and notes, up to 1,000 words | 120 to 250 words, plain paragraphs | About 500 tokens | 4,096 (3B: keep notes short); 6,144 (8B) | Word count; facts check |
| T6 News item | Facts or notes | Headline up to 120 characters; summary up to 300; body 100 to 250 words | About 600 tokens | 4,096 | Lengths; facts check |
| T7 Opening summary | Notice text, up to 600 words | Plain text up to 400 characters | About 150 tokens | 3,072 | Length. Deadline and contact come from fields, not the model |
| T8 Publication from a pasted reference | Reference text, up to 300 words | Structured object: title, ordered authors, venue, year, type from the list, DOI | About 400 tokens | 3,072 | DOI and year checked by code; authors compared with the pasted text; type from the list |
| T9 Profile from a CV | CV text, one or two pages | Structured object: name, role, department, interests | About 300 tokens | 6,144 (chunk longer CVs) | Operator confirms each field. The name must appear in the CV |
| T10 Shorten to a limit | Existing text and a limit | Plain text | About one third of the limit | 2,048 | Length; no new facts (word overlap check) |
| T11 FAQ answer | Question and facts | Plain text up to 80 words | About 150 tokens | 3,072 | No eligibility, fee or date claim not in the facts |

**Not model tasks.** These are code or human tasks: DOI and web-address format; dates; file and web names; numbers; phone and email format; legal, finance, donor and tax text; bank details; photo consent; image handling; alternative text for photographs; approval records.

**Settings.** Temperature 0.1 for structured extraction (current default in `site-agent.example.toml`). About 0.3 for drafting (proposed). Context window 8,192 as the default ceiling; the setting costs memory, so measure it. Time limit 300 seconds (current default).

### Choosing a model by memory

| Computer memory | Realistic choice | Notes |
|---|---|---|
| 8 GB | A 3B model, quantised | Expect slow replies. Do not run the build and the model together. Manual forms must always be available |
| 16 GB | A 7B or 8B model. The current default is `qwen2.5:7b` | Better extraction from longer notices and CVs. Still needs every check |

Set a target for response time on the target machine (proposed): under 60 seconds for a biography on 16 GB, and under 120 seconds on 8 GB.

### What a 3B model can do, and what it cannot

**Can do, with the checks in place:**
- Turn three to six short facts into two or three plain sentences.
- Shorten a sentence to a limit.
- Pick one value from a short list.
- Write a simple structured object from a short notice, when the server's JSON mode is on. JSON mode guarantees valid syntax, not the right fields, so the tool still checks the fields.

**Cannot do reliably:**
- Follow more than a few rules at once.
- Count words, or stay within a length without checking.
- Avoid filling gaps with plausible invented details when the facts are thin.
- Read a long CV or a multi-page notice in one go.
- Read PDFs or images.
- Understand unusual date formats.
- Keep names and numbers consistent across a long text.
- Judge accuracy, tone or legal risk.

**What an 8B model adds:** more reliable extraction from longer text, more consistent style, and fewer format failures. It still cannot be trusted without the checks.

**Rules for every model**

- The operator supplies the facts. The model is never the source of a fact.
- The tool checks every output (format, length, facts) before showing it. Model output is never saved directly.
- A failed reply is retried once with stricter instructions. After that the operator gets an empty form and the notes.
- The model never writes DOIs, web addresses, email addresses, phone numbers, dates to be calculated, bank details, or legal, finance, donor or tax text.
- Prompts are text files that the technical contact can improve without code changes (existing design).

---

## (h) Open questions for the CIR team

Each question has a recommended answer. The team should confirm or change each one before the tool is built.

| # | Question | Recommended answer |
|---|---|---|
| 1 | Which computer will the operator use: native Windows, or WSL2? | Test native Windows first, on the operator's machine, by installing Node 22 and running the check. Use WSL2 only if that test fails |
| 2 | Where will the site folder live? | On a local disk, with a short path (Windows: near the drive root; WSL2: on the Linux file system). Never in a synced or network folder |
| 3 | Which model, on which computer? | 16 GB: the current default, `qwen2.5:7b`. 8 GB: a 3B model only after testing on real notices. Manual forms always available |
| 4 | Who approves wording and photographs? | A named content approver, for example the head of centre. The tool records the approver's name and date with each batch |
| 5 | Who approves the legal pages? | The institute's legal office, in writing. The tool records the approval. The technical contact removes the "Draft for review" notice |
| 6 | Who writes finance, tax and donor text? | The finance office. The model is not used for it |
| 7 | Will bank account details be published? | No, as the template says. Keep "account details on request" |
| 8 | What is the final domain, and who hosts the site? | Institute IT confirms both before the first real content. The technical contact sets the domain in both files. The launch check must check both (P13) |
| 9 | What happens to the student club link? | Point it to the club's live site once it is up. Until then, hide it or mark it as pending, and keep the launch warning |
| 10 | What event series names are used? | A fixed list agreed by the centre, held by the tool, once P3 is done. Not the placeholder `series-1` |
| 11 | Which time zone decides "upcoming" events? | The centre's local time zone. An event stays upcoming through its last day (P8) |
| 12 | Delete or archive? | No permanent delete in the tool. "Remove" moves the file to an archive folder outside the site, kept for 90 days (proposed). The technical contact deletes permanently |
| 13 | What consent is needed for photographs? | Written consent from each identifiable person. The tool records a yes or no with each change. The centre keeps the signed form |
| 14 | When will gallery photographs be supported? | Before the first event with photographs: approve P15 (photo list with captions and alternative text). Until then, albums are text only |
| 15 | Are partner logos wanted? | Text tiles until a partner gives permission for a logo. Then P15 |
| 16 | Which languages? | English, with British spelling, for version 1 |
| 17 | Where do notices, CVs and drafts go? | They stay on the computer. Local model only. Logs are deleted after 90 days (proposed) |
| 18 | Who decides the licence for the template and the tool? | The centre, before sharing. The template has no licence file. The tool's MIT licence is only proposed |
| 19 | Who is the technical contact after handover? | A named person and a deputy, recorded on the centre's handover sheet |
| 20 | Should homepage counts include samples? | No. Count published entries only (P18). Until then, hide the counts |
| 21 | Are the homepage limits right (four faculty, four featured projects)? | Keep them. The tool warns when more are chosen |
| 22 | Can projects name students who are not in People? | Yes, with a warning. The link appears only when the name matches a person |
| 23 | Should About leadership come from People entries? | Yes (P4), so each fact has one source |
| 24 | Is a contact or newsletter form wanted? | Not in version 1. Keep email. A form needs a decision on storing data and a privacy notice change |
| 25 | Who signs off the launch? | The content approver and the technical contact, recorded in the launch report |
