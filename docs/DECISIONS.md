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


## D20. Long text is checked against the facts, and is not a source of facts

The fact check applies to the body and to every long text box: summary, description and biography. A draft fills one of
these boxes, and a person may type into them too. Saving is blocked while a number, year, web address or email in new or
changed text is not in the facts. On an edit, text that is unchanged is not checked, so an old record is not blocked by a
rule that did not exist when it was written.

Long text is left out of the facts. Before this change, a summary counted as a fact for itself, so the check could never
flag a number in it. Numbers match whole items only: "10" is not supported by "2010". A date field also supports its prose
spellings, such as "5 November 2026".

Why: the first version checked only the body, and a substring match let "10" pass on "2010". Claims are not covered by
this decision. See PLANNING.md, section 6, item 6.

Consequence: a number typed into a long text box must also be in the facts. The form shows the item, and saving stays
blocked until it is removed or added.

## D21. A write that fails part way is undone before the error is shown

If a file cannot be written after earlier files in the same plan have been written, every file is put back from its
backup, and any new file is removed. No run log is written, so the run does not appear in History. The operator is told
that nothing was written.

Why: before this change the site could be left half changed, with no run to undo, although the backups existed. If a
restore itself fails, the error names the backup folder, so the files can be put back by hand.

## D22. An update with a model edit that cannot be placed is not written

An assisted edit is applied only when its search text is among the lines the model was shown, and it matches exactly once
in the file. An edit that does not match, or that would change text outside those lines, is listed as a failure. The
command line then writes nothing, even with `--yes`, and lists the lines for editing by hand.

Why: the rest of the update may depend on the edit that failed, and a half-applied update is harder to check than a
refused one.

Consequence: an operator using `--assisted` may need to make one edit by hand and run the update again.

## D23. A cancelled job does not save its result

A background job's save step runs under the job's lock, and only if the job has not been cancelled. Once cancel returns,
nothing is saved afterwards. The model's answer may still arrive, and it is discarded. Since D38 the model call itself is
stopped as well (this sentence was true before D38).

Why: the operator presses Cancel because they do not want the draft. Before this change the draft was saved anyway and
appeared later.

## D24. A notice fill keeps the notice as the facts

When a form is filled from a notice, the notice text is placed in the facts box if that box is empty, so the fact checks
can use it. Dates and places in the filled-in fields that the notice does not state are listed as notes on the draft. The
kind is lower-cased, as the record rules require.

Why: the notice fill had no grounding notes in the app, although requirement U12 asks for them, and the notice's own
numbers would otherwise have been flagged.

## D25. Model output is capped, and the call limit is ten minutes

Each model call asks for at most 1,200 output tokens (`max_output_tokens`), so a runaway reply cannot run for hours. The
default call timeout is now 600 seconds. A run of `deepseek-r1:7b` took 436 seconds in the measurements, which the old
300-second default would have cut off. The timeout applies to each read from the server, not to the whole call.

Why: an unbounded reply is the main cause of a very slow call, and the old limit cut off a valid slow answer.

## D26. Replies are asked for in the record's shape, with a fallback

When the server accepts a JSON schema, the event record is requested in that shape, so keys, types and the kind choices are
set when the reply is written. If the server answers HTTP 400 to the schema request, the same call is retried once in
plain JSON mode. Other errors are not retried this way.

Why: the harness already repaired many replies, but a schema removes the failure at its source. The fallback keeps older
servers working.

## D27. Model calls are logged by count and hash only

Each model call appends one line to `calls.jsonl` in the site's `.site-agent` folder: the time, provider, model, seconds,
output tokens, a hash of the prompt, and whether it succeeded. The text of the notice and of the reply is never written.

Why: a log of calls helps tune the models, and a hash lets two prompt versions be told apart. Keeping the text out means the
log can be shared without exposing the operator's notices. Reviewing this decision is open under REQUIREMENTS E49.

## D28. A reply that breaks the record rules is sent back once

If the model returns valid JSON that the event rules reject, the rule message is sent back in the same conversation, and the
model may correct its own record once. The same happens when an update's merged record is invalid. A second failure is
reported to the operator with the field named.

Why: the model can usually fix a wrong date or kind when told what is wrong; a second retry seldom helps, and costs time.

## D29. Dates and places must be quoted from the notice

The model gives the exact words of the notice for the date, end date, venue and series. On the command line, a date that is
not quoted from the notice blocks the write, and the operator is told to check the notice or edit the file by hand. A venue or
series that is not quoted is a note to check. In the web form, the same checks appear as notes beside the filled-in fields,
and the operator still decides. An end date always needs its own quote.

Why: a wrong date is the costliest mistake a notice can cause, so it is refused rather than noted. A venue or series is easier
to correct by hand, so it is only noted. The web form keeps the operator in charge of every field.

## D30. A relative date is worked out in code

When a notice says "next Monday" or "tomorrow", the model returns the phrase, and the code works out the calendar date from
today's date. If the model also gave a date that differs, the code's date is used and a note says so. Supported phrases are
today, tomorrow, "this" or bare weekdays, and "next" weekdays. Any other phrase is left to the operator.

Why: calendar arithmetic is a known weakness of small models, and it is checkable in code.

## D31. Duplicate people and DOIs block a save; duplicate event titles warn

A new or edited person whose name matches another person (after accents, case, punctuation and "Last, First" order are
ignored) is blocked. A publication with the same DOI as another is blocked. An event with the same title as another is a
warning. Names that are not on the site get a hint with up to three close names.

Why: a second copy of a person or a DOI breaks links and counts, so it is refused. Two events can share a title legitimately,
so they are only flagged.

## D32. Proposed limits are enforced, and can be changed in one place

Years must be from 1950 to next year. Titles are at most 120 characters. The homepage shows four featured projects and six
featured partners, so a warning appears when a fifth project or a seventh partner is marked featured. An opening whose deadline
has passed gets a warning, unless it is marked closed. These numbers are named constants in `records.py` and
`repository.py`, and are proposed until the CIR team confirms them (REQUIREMENTS U6, U9, U19, U22, U26).

## D33. Claims in a draft are warnings, not blocks

A draft sentence that shares no meaningful word with the operator's facts is shown in the draft panel as a sentence to check.
It does not block a save and does not count as an unsupported number. The check is lexical, so it can miss a claim that reuses
the facts' words, and it can flag a true sentence that uses new words. Open decision 6 in PLANNING.md records the choice.

Why: a lexical check is cheap and explainable, but not reliable enough to block on.

## D34. The site check runs on a copy before anything is written

Before a change is written, the site is copied to a temporary folder, the change is applied to the copy, and the site's check
command runs there. A failing check blocks the write on the web and on the command line. The copy links to the site's
`node_modules` rather than copying it. If the link cannot be made (for example on Windows without the right permission), the
write goes ahead and the check runs after it, as before, and the reason is shown.

Why: a build break found after a write needs a second repair, while one found before a write costs nothing. The copy keeps the
real site untouched.

## D35. Dates, files and homepage lines are checked and reported, never changed

The launch screen and the audit warn when an event has ended, when news says it is coming up but is dated more than 60 days
ago, when a photo or PDF is missing or of the wrong type, when the social-sharing image is not 1200 by 630 pixels, and when a
homepage or news line gives a different date from the event it names. The machine's local date is used until the CIR team
answers the time-zone question (REQUIREMENTS Q11). Placeholder words in the site pages are warnings for the technical
contact, not blockers.

## D36. Search matches every word, in any order, and ignores accents

A search matches when every word of the query is found in one of the entry's key fields, in any order, ignoring case and
accents. Choice fields also match their labels.

Why: an operator should not have to remember the exact order or accent of a name.

## D37. The command-line restore follows the undo rules

`site-agent restore` refuses a run that a later change has touched, exactly as the app does, and `--dry-run` shows what would
change without changing anything.

Why: the command line was able to overwrite later edits, which breaks the undo rules (D17).

## D38. Replies stream, and a cancel closes the connection

Both model clients ask the server to stream the reply. The job runner tells the client, while the job runs, that the
operator has cancelled. The client then closes the connection, and the model stops writing. A cancelled job still never runs
its save step. The job page shows how many characters have arrived, so a long wait is visible.

Limits: a cancel is noticed when the next part of the reply arrives. If the model is silent before its first words (for example
while it loads or reads a long prompt), the cancel waits for those first words or for the timeout. A cancelled call is logged
as not successful, with the error "cancelled".

Why: a cancelled draft used to keep the processor busy until the model had written all of its answer, which could take minutes
on an 8 GB computer.

## D39. The model size is chosen from the computer's memory when the setting is "auto"

The example settings file now says `model = "auto"`. With 12 GB of memory or more, the default `qwen2.5:7b` is used. Below 12 GB,
`llama3.2:3b` is used. If memory cannot be read, the default is used and the reason says so. An explicit model name in
`site-agent.toml`, or `--model` on the command line, always wins. The reason is shown by `site-agent scan` and kept on the
settings. The rounded memory in the reason is shown in whole gigabytes; the 12 GB boundary uses the unrounded value.

Why: a 7B model is too slow and too large for an 8 GB computer, and a 3B model gives weaker output on a 16 GB computer. On the
ten-gigabyte development machine, "auto" chooses `llama3.2:3b`. Set the model by name to use the larger one there.

## D40. Rewrite and suggest only offer what the operator can check

Two buttons use the model, and neither saves anything. "Rewrite with only your facts" appears in the draft panel when a section
draft still has items the facts do not give. It rewrites the text now in the form, and the harness checks the new text against
the facts again. The result is a new draft that the operator reads. "Suggest" appears beside each empty choice field. The model
must answer with one of the field's own stored values. Anything else gives the plain message "The helper could not pick one of
the listed options. Choose one yourself." An accepted suggestion only pre-selects the field, and is kept as a draft of kind
"suggestion" until the operator changes the field.

Why: the operator decides every value. The model is asked for a small, checkable answer, and the harness refuses anything
that is not one of the allowed values.

## D41. Spelling advice is a warning; line endings are kept

New or changed long text and body are checked against a short table of American spellings with British forms ("organize" is
"organise"). Each match is one warning in the preview, which the operator ticks like the others. Nothing is blocked. "Program"
is only flagged as a programme for events, and "license" only as a noun. Tone is not checked by a model: there is no
measurement of tone yet, and a model judgement would put an unmeasured warning on every save.

A file that uses Windows line endings keeps them when a change is written, and a file with \n endings keeps \n. New files use \n.
A file that mixes both is treated as Windows endings and normalised when a change is rendered. Restoring a backup gives back the
exact original bytes.

## D42. Schemas name no regular expressions, and a failed schema request falls back

The reply schema sent to Ollama must not contain a regular expression. Ollama turns the schema into a grammar, and its grammar
builder crashed the local runner on the `\d` escapes in a date pattern (found on 20 October 2026 with `qwen2.5:7b`). The
dates are checked by the harness instead. A test fails if a schema sent to the model names a pattern anywhere.

If the server refuses a schema request with HTTP 400, or its runner stops with HTTP 500, the same request is sent once more in
plain JSON mode. Any other error is reported without a second request.

## D43. A cancel stops the request even while the model is silent

The client connects first, then watches the cancel flag while it waits for the reply's first words. When the job is cancelled,
the connection is shut down, so a model that is still loading or reading a long prompt stops at once. This replaces the
limit in D38: a cancel no longer waits for the first words or the timeout. A cancelled call is still logged as not successful.

Why: a cancel that does not stop the model defeats the point of the button, and a slow start is exactly when it is pressed.

## D44. Series and venue must match the words the notice uses

The model gives the venue and the series with the words the notice uses for each. If the value is longer than those words but
contains them, the value is shortened to the words, and a note says so. If the value is not part of those words, it is kept and
a note asks the operator to check it. A notice that names a series (a capitalised phrase ending in Series, Season or Course) with
no series in the record gets a note, unless the phrase is the event's own title.

Why: a small model sometimes adds a sentence to a venue. Shortening it is safe, because the operator still reads the value in the
preview. A series named in the notice and left out of the record is easy to miss.

## D45. Tone and line-ending rules

Tone is checked with fixed rules, not a model: an exclamation mark in a long paragraph, a word in capitals that is not a known
acronym, and a short list of marketing words each give an advisory warning, which the operator ticks like the spelling
warnings. Nothing is blocked. A file that mixes Windows and Unix line endings is refused, with a message to fix its line
endings by hand, because a change to it could not be made safely. Files with one ending style are unchanged.

Why: a model judgement of tone would be an unmeasured warning on every save. The file refusal is safer than rewriting a file
whose endings are already inconsistent.

