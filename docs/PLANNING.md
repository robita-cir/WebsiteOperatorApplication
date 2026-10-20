# Planning

This is the document to read first if you are taking the project over. It says what the app is for, what is built and
tested, what is not, what the CIR team still has to decide, and what to do next.

The requirements are in [REQUIREMENTS.md](REQUIREMENTS.md) (also as [PDF](REQUIREMENTS.pdf)). The list of every place the
content can be edited is in [EDITABLE_SECTIONS.md](EDITABLE_SECTIONS.md). The functional and visual design is in
[design/APP_DESIGN.md](design/APP_DESIGN.md). All three were written from the CIR website template at commit
`23f4878b60d337ebd18fac22427dcd31bdf14a86`.

## 1. What the project is for

A lab operator who does not know front-end code changes the CIR website's content through a few buttons and forms. A
small local model drafts wording from facts the operator gives it. Nothing is saved until an approver from a named list
approves a preview. A technical contact deploys the site.

Decisions from the CIR team so far:

- The operator is lab or centre staff, not a developer. They do not deploy.
- Every change is a few clicks, and every change goes through the same path: draft, preview, approve, write, check.
- Wording is drafted by a local model (about 3B to 8B parameters, 8 GB to 16 GB of memory). Nothing is fixed in code.
- Only content changes. Pages, layout, navigation shape and code stay as they are.
- Native Windows and WSL2 must both work. The tool is a portable bundle.

## 2. Status (20 October 2026)

| Area | State | Evidence |
|---|---|---|
| Web app for the operator (FastAPI, Jinja2) | Built. Every collection, the approval and undo path, the site check, launch readiness, history, samples, settings | `tests/test_web.py`; start with `site-agent-app --site <folder>` |
| Content rules for all twelve collections | Built. Mirror the template's schema, plus proposed limits (https-only addresses, DOIs without a web prefix, file paths that must exist) | `records.py`. Every one of the template copy's 119 records passes; 99 of them are samples |
| Approval, fingerprint, undo rules | Built and tested. A write that fails part way is undone before the error is shown. The site check runs on a copy before anything is written | `tests/test_web.py`, `tests/test_apply.py`, `tests/test_preflight.py` |
| Model calls | Output capped at 1,200 tokens; 600-second limit per read; replies streamed, and a cancel closes the connection; replies in the record's shape where the server allows it, with a plain-JSON retry; each call logged by count and hash, never the text; model size chosen from memory with "auto" | `tests/test_llm_clients.py`, `tests/test_llm_calllog.py`, `tests/test_streaming.py`, `tests/test_hardware.py` |
| Notices and records | Dates and places must be quoted from the notice; relative dates worked out in code; a rejected record is sent back once; duplicate people and DOIs blocked; proposed limits enforced | `tests/test_grounding.py`, `tests/test_dates.py`, `tests/test_duplicates.py`, `tests/test_limits.py` |
| References and claims | A publication can be filled from pasted text, with each value checked against the text; draft sentences that the facts do not cover are flagged | `tests/test_reference.py`, `tests/test_claims.py` |
| Checks and audit | Dates, files and homepage lines are checked on the launch screen and by the audit; placeholders in pages are warnings | `tests/test_checks.py`, `tests/test_audit.py`, `tests/test_imagecheck.py`, `tests/test_launch.py` |
| Search and check messages | Search matches every word in any order, ignoring accents; a failed check says what went wrong in plain words | `tests/test_search.py`, `tests/test_explain.py` |
| Drafting from facts, fact check, notice to form | Built. The fact check covers the body and every long text box, and matches whole items. A cancelled draft stops and is not saved. Rewrite-with-facts and Suggest buttons (the model never saves). Tested with a scripted model; one model timed and a regression set run ([MODELS.md](MODELS.md)) | `drafting.py`, `factcheck.py`, `tests/test_factcheck.py`, `tests/test_jobs.py`, `tests/test_rephrase.py`, `tests/test_suggest.py`, `tests/test_web.py` |
| Spelling advice and line endings | British spelling warnings on new text (advisory, ticked like other warnings); CRLF and LF files keep their endings | `tests/test_style.py`, `tests/test_line_endings.py` |
| Command-line tool (`site-agent`) | Built, events only in the command line. An update with a model edit that cannot be placed is not written. `audit` writes a report; `restore --dry-run` shows what would change | `tests/test_cli.py`, `tests/test_audit.py` |
| Writing helper against a real model | Measured for events before the app existed. Drafting in the app is not yet measured | [MODELS.md](MODELS.md) |
| Native Windows, WSL2 bundle | Not tested on native Windows or on the operator's machine. On the developer's WSL2 machine, an end-to-end run passed on 20 October 2026 | [TEMPLATE_CONTRACT.md](TEMPLATE_CONTRACT.md), "Run against the template copy" |
| Launch readiness | Built to the template's rules, blockers and warnings. Matches the template's own check on the template copy | `launch.py`, `tests/test_launch.py` |
| Template changes P1 to P19 | Proposed. None made | [REQUIREMENTS.md](REQUIREMENTS.md) section (e) |

Test suite: 466 pass; one live model test is skipped unless `SITE_AGENT_LIVE=1`. `ruff check src tests` is clean. The test
client is `httpx2`, which Starlette recommends in place of `httpx`.

What was checked against the real template (a copy, never the template itself):

- Every record in the template passes the content rules.
- The launch readiness report finds the 99 sample entries, the placeholder site settings, the three legal pages marked
  "Draft for review", and 16 placeholder words in content that is not marked as a sample. These match the study.
- The app's start, list, form, preview, history, launch and settings pages all render from the real files.

## 3. What the app does not do yet

These are known gaps, in the order the team is likely to need them.

1. **Page wording and site settings** (screens 14 to 17 in the design) are read-only until the template moves them into
   data files (P1). The app shows them as not editable; it does not offer them.
2. **Photographs and PDFs.** The app checks that a portrait or PDF path points at a file that exists, and blocks saving
   otherwise. It does not upload files. Copy the file into `public/` first.
3. **Gallery photographs** (P15). Albums are text only.
4. **Legal and finance approvals.** The app records content approvals. Legal and finance approvals (a reference to the
   written approval) are designed but not built.
5. **The 90-day clean-up** for removed entries. Copies are kept until someone deletes them.
6. **Two people at once.** Saves are checked against the file before writing, so a clash is refused rather than
   overwritten. A lock file is not built.
7. **Drafting quality** is not measured on real notices. Timing is: five drafts on this machine took about 38 s for the
   first (the model loading) and 1.5 to 2 s each after it. The fact check covers numbers, years, web addresses and emails.
   It does not cover claims: the drafts added phrases such as "improve patient care" that no fact gives. Reading each
   draft is the operator's job, and the statement on the form says so. See open decision 6.
8. **History speed.** Each history page re-reads every run. Fine for hundreds of runs; needs an index beyond that.
9. **The old command line** (`add-event` and `update-event`, with `--assisted` as an opt-in) remains. The assisted mode
   is off by default, is not in the app, and does not write an update that it cannot apply safely.
10. **Cancel while the model is silent.** Streaming is built (D38), but a cancel waits for the model's first words, or for the
   timeout, if the model has not begun to write.
11. **Spelling and tone.** Spelling advice is built (D41). A model tone check is not built, because tone has not been measured.
12. **Mixed line endings.** A file that mixes Windows and Unix line endings is normalised to Windows endings when it changes.
13. **Model suggestions on the real notices.** Rewrite and Suggest are tested with a scripted model. Their quality on real
   drafts and real choice fields has not been measured.

## 4. Roadmap

Each milestone has an exit condition. Do not start one until the one before is accepted.

| # | Milestone | Exit condition | Who | State |
|---|---|---|---|---|
| M0 | Base repository, tests, documents | Passing | Developer | Done |
| M1 | CIR team answers the open questions in REQUIREMENTS.md section (h) | Answers recorded there, with date and name | CIR team | Open |
| M2 | Template fixes P1 to P3, P5, P8, P9, P12, P13 | The launch check reports every placeholder; missing photos and PDFs fail the build; the series list is no longer literal | Template maintainer, with the CIR team | Open |
| M3 | Native Windows and WSL2 test on the operator's machine: the app starts, a change is written, the site check runs, undo works | The test passes on both, recorded here | Developer and operator | Partly. The WSL2 run on the developer's machine passed on 20 October 2026. Open: the operator's machine and native Windows |
| M4 | Service layer and content rules | Done. The rules are tested without a model or a network | Developer | Done |
| M5 | Operator app (first build) | Done. Every collection, approval, undo, check, launch, history. Operator usability test not yet run | Developer | Built; test pending |
| M6 | Usability test with one real operator, timed, on the lab's machine | An operator completes one add and one edit in under 10 minutes without help; findings recorded | Developer and operator | Open |
| M7 | Drafting measured on real notices and facts; default model chosen for 8 GB and 16 GB | Extraction measured on eight synthetic notices (MODELS.md). Real notices and drafting still to do | Developer, with CIR notices | Open |
| M8 | Media (portraits, PDFs) and legal approvals | Uploads with size and type checks; a legal notice cannot be removed by the app | Developer, with the institute | Open |
| M9 | Handover: export folder with checksums, operator guide in plain English, technical contact's sheet | A technical person who did not build it can install and run it from the guide | Developer and technical contact | Open |
| M10 | Bundle for Windows and WSL2 | Works on both from a folder copied to a new machine | Developer and technical contact | Open |
| M11 | Decision: keep FastAPI, or move the screens (for example to Go) using the JSON view | A recorded decision based on M6 to M10 | CIR team | Open |

## 5. Work packages for collaborators

Read [ARCHITECTURE.md](ARCHITECTURE.md) and DECISIONS D13 to D19 first.

- **A. Usability.** Run the M6 test with an operator. Record each stumble. Change wording in the templates, not the code.
- **B. Drafting quality.** Build a set of real notices and facts; score drafts on accuracy and on whether the fact check
  catches what it should. Output: MODELS.md.
- **C. Windows and WSL2.** Run M3 on the operator's machine. Fix path, file-lock and line-ending problems that show up.
- **D. Template contract.** Keep `records.py` in step with the template's schema; keep TEMPLATE_CONTRACT.md current.
- **E. Media and legal.** M8, including the approval record for legal text.
- **F. Operator guide.** Plain English, with screenshots from the running app.

## 6. Open decisions

Each has a recommendation. The CIR team decides; the developer records the answer in DECISIONS.md.

1. **Licence.** The template has none. The tool's MIT licence is only proposed (REQUIREMENTS question 18).
2. **Which computer.** Native Windows first, tested on the operator's machine (REQUIREMENTS question 1).
3. **Which model, on which computer.** `qwen2.5:7b` on 16 GB. A 3B model on 8 GB only after testing on real notices.
4. **Approvers.** Who is on the list, and who keeps it (the technical contact keeps it; the content approver is named).
5. **Removal copies.** Keep them for 90 days then delete, or keep them until someone deletes them? Recommended: the 90-day
   rule, once M9 is done.
6. **Claims in drafts.** The check is lexical (D33): a sentence that shares no meaningful word with the facts is flagged, and
   a true sentence that uses new words is flagged too. A stricter drafting rule in the prompt, and a check that each sentence
   rests on a fact, are still open. Recommended: both, tested on real notices (milestone M7). The team decides.

## 7. Risks

| Risk | Effect | Mitigation |
|---|---|---|
| A model writes a plausible wrong date, place or number | A wrong public fact | The fact check flags numbers, years, addresses and emails that are not in the facts, and blocks saving while they remain. It does not check claims; the preview is read before approval; measured in M7 |
| A change is approved and then the file changes | The approval no longer matches the text | Fingerprint check before writing (S11); the write refuses changed files |
| Undo would overwrite newer work | Lost work | Strict undo rules (S13) |
| The site build breaks after a write | The site does not build | The check runs after each write; undo is one click |
| Someone opens the app from another computer | Content exposed on the network | Bound to 127.0.0.1; foreign host names refused (S15) |
| Drafts on disk hold personal data | Privacy | Local only; labelled as drafts; the technical contact can delete the folder; retention to be decided |
| Windows problems (paths, file locks, line endings) | The app fails on the operator's machine | M3 on the real machine before any bundle |

## 8. Definition of done for a change

- `pytest` passes. `ruff check src tests` is clean.
- A change to a safety rule keeps its test, and a new rule has a test and an entry in ARCHITECTURE.md.
- A change to the content rules is checked against the template copy (`site-agent validate` on the copy, and the app's
  list pages).
- A change to model behaviour comes with a live run, recorded in MODELS.md.
- The documents are updated when behaviour changes.
