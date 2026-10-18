# Decisions

Short records of the choices made so far, with the reason. When a decision changes, add a new entry that supersedes
the old one, rather than rewriting history.

## D1. A separate Python command-line tool, not part of the website

The website is Astro (Node). The agent is a standalone Python 3.11+ command. Operators run one command, and the tool
can point at any site folder. It also keeps the website repository free of model code.

*Why:* operators need a simple install; Python runs on Windows and Linux; the template team does not have to adopt
Python.

## D2. Local model servers, with an OpenAI-compatible second backend

Ollama is the default. The `openai` provider covers llama.cpp's server, LM Studio and similar. There is no cloud
backend.

*Why:* notices can name private people and unpublished events. Running locally keeps them on the operator's machine,
and needs no account or payment.

## D3. Narrow, checkable model outputs instead of free-form tool use

The model returns one JSON object (JSON mode, plus a parser that tolerates code fences and chatter) or search/replace
blocks. There is no tool-calling loop yet.

*Why:* small models (3B to 8B) are much less reliable at tool-calling loops and at writing YAML than at answering a
single question about a notice. Each output can be checked. A tool loop is planned for later, once the evaluation
harness can show it helps (see PLANNING, M7).

## D4. Known values are replaced exactly; the model only sees what the tool cannot place

When a date, title, venue or series changes, the tool replaces the old value with the new one, in the same date style,
on lines that also contain the event's old title. Other lines are reported with their numbers. The model is asked about
them only when the operator passes `--assisted`.

*Why:* a test run with qwen2.5:7b changed an unrelated "Proposal deadline: 10 March 2026" line when asked to update a
"Save the date" line. A plausible wrong edit is the worst outcome for this tool, so the default path avoids guessing.

## D5. The tool renders event files; existing files are changed line by line

A new event file is written from the validated record. An existing file has only the changed keys rewritten
(`set_frontmatter_values`). Comments and the order of other keys are kept.

*Why:* keeps the template's style (quoted strings, bare dates) and avoids reformatting whole files, which would make
diffs hard to review.

## D6. Preview by default; backups and a run log for every write

Writing needs `--apply`, and a question (or `--yes`). Each replaced file is copied first, and each run is logged. A run
can be undone with `restore`.

*Why:* the operator is not a developer and may not be able to recover a file by hand.

## D7. A fixed allow-list of writable paths

Default writable paths are `src/**/*.md`, `*.astro`, `*.ts`, `*.tsx`. The site owner can change them in
`site-agent.toml`. Paths outside the site folder and inside dependency folders are always refused.

## D8. Slugs come from the title, not from the model

The file name is made from the title with a number added if it is taken. The operator may pass `--slug`.

*Why:* file names become page addresses; a predictable rule is easier to check than model output.

## D9. Validation mirrors the template's schema by hand

`schemas.py` copies the rules in the template's `src/content.config.ts`. A sync check against the real template is a
planned task (PLANNING, M1).

*Why:* parsing TypeScript to read the schema is fragile. Mirroring is simple, and `validate` shows where it drifts.

## D10. Unknown keys in the configuration are errors

*Why:* a misspelt setting such as `modle` would otherwise be silently ignored, and the operator would run a different
model than intended.

## D11. Tests use a scripted model; live tests are opt-in

The test suite never calls a real model. `tests/test_live.py` runs only with `SITE_AGENT_LIVE=1`.

*Why:* the suite must run in CI on machines without a model, and must give the same result every time.

## D12. MIT licence (proposed)

*Why:* permissive, common for research tools, easy for other centres to reuse. Not yet confirmed by the centre (see
PLANNING, open decisions).


## D13. Python with FastAPI for the operator app, not Go

*Decided 18 October 2026.* The app is FastAPI with Jinja2 pages and plain forms. It is not Streamlit, and not Go.

*Why not Go:* the rules, the file handling, the approvals and the tests are already written and passing in Python
(over 110 tests). A Go rewrite would mean rebuilding and re-proving every safety rule. The screens are HTML forms in
either language, so Go would gain nothing on the operator's side. Go's real advantage is one binary to hand over. That
can be had later by bundling a Python runtime, and by keeping the HTTP layer thin enough to rewrite. The JSON view under
`/api/` is there for that purpose.

*Why not Streamlit:* the approved design needs approval gates, a file-level check on every save, a confirmation step and
exact control over labels and focus. Streamlit reruns the whole script on each click, which makes those gates hard to
keep correct. It also restricts how the page can be styled. See D19.

## D14. The operator app changes content files only

The default writable path is `src/content/**/*.md`. Code and page file types are refused even when a configuration
lists them. This supersedes D7 for the operator app. Page wording stays read-only until the template moves it into data
files (proposal P1). Until then, a homepage line that names an event is listed for hand editing, not changed.

*Why:* the requirements say structure must not change. The earlier command-line flow could edit page code, and a test
run showed it could also change an unrelated line. Both risks go away with content-only writes.

## D15. Drafts are kept on disk, and labelled as drafts

The requirements say nothing is saved before approval, and the design asked for drafts to be kept. Drafts go in
`.site-agent/drafts/`. They are shown as "Not saved", they never reach the website without approval, and they can be
discarded by starting again. The technical contact can delete the folder at any time.

*Why:* a draft that is lost when the page is closed wastes minutes of a slow local model.

## D16. Approval is tied to the exact text

Each preview stores a fingerprint of the files it would write. The approval checks the fingerprint, and the writer
checks that each file still matches the preview before anything is written. Any edit after the preview voids it.

## D17. Undo is strict

Undo is offered only when no later change touched the same files and each file still holds what the change wrote.
Otherwise it says why. The app never overwrites newer work to make an undo succeed.

## D18. Removal is a planned change, not a special case

"Remove" creates a change in the plan that deletes the file. The bytes are copied to `.site-agent/backups/` first, so
the change can be undone. The design said "archive for 90 days". The copy is kept until someone deletes it; the 90-day
clean-up is not built yet (see PLANNING, open items).

## D19. The Streamlit design is superseded for the build, not for the screens

`docs/design/APP_DESIGN.md` names Streamlit. The functional and visual design (flows, states, approval rules, palette,
mockups) is what the app implements. The widget and theme notes in section 9 of that document do not apply. Section 9.9
names what is specific to the web framework, for a future move.
