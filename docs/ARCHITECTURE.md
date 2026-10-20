# Architecture

This document describes how the code is organised, what happens when an operator runs a command, and which safety rules
the code keeps. Read [PLANNING.md](PLANNING.md) first for the goals.

## The short version

The model is never trusted with the final file. It does two narrow jobs, each with output that the tool can check:

1. **Read a notice** and return one JSON object with the event's fields. The tool checks the object against the schema,
   then writes the file itself. The model never writes YAML.
2. **Propose search/replace edits** for lines that show an old event detail, but only in the opt-in `--assisted` mode.
   An edit is applied only if its search text appears exactly once in the file.

Everything else is deterministic: finding files, replacing a known date or name on a line that also names the event,
checking the schema, showing the diff, backing up, and restoring.

## Modules

```
src/site_agent/
├── cli.py            Command-line entry point. Parses arguments, runs one command, shows the plan, asks for approval.
├── workflows.py      The two requests: plan_add_event and plan_update_event. Coordinates the other modules.
├── config.py         Reads site-agent.toml and the command-line overrides. Rejects unknown keys.
├── site.py           Reads the site folder. Lists collections, finds text, and enforces the write allow-list.
├── events.py         Event-specific: find an event by name, load it, choose a new file name.
├── schemas.py        The Event model (mirrors the template's schema). COLLECTIONS maps folder name to model.
├── frontmatter.py    Reads and writes YAML frontmatter. Changes existing files one line at a time.
├── substitute.py     Replaces known old values with new ones, only on lines that name the event.
├── edits.py          Parses and applies search/replace blocks from the model (assisted mode). An edit that changes
                     text the model was not shown is refused.
├── text_utils.py     Slugs, date spellings, line matching, excerpts for the model, grounding warnings.
├── factcheck.py      The fact check for written text (S14). Used when drafting and when saving.
├── plan.py           A plan is a list of file changes plus notes. Renders diffs.
├── validate.py       Checks content against its collection's rules, before writing and on demand.
├── apply.py          Writes a plan, keeps backups and a run log, undoes a write that fails part way, restores a run,
                     runs the check command.
├── prompts.py        Loads the prompt texts.
├── prompts/          The prompt texts themselves (edit these to tune behaviour; no code change needed).
├── errors.py         SiteAgentError: a message for the operator, shown without a traceback.
└── llm/
    ├── base.py       ChatClient protocol, Message, LLMError, the HTTP helper.
    ├── ollama.py     Ollama client (/api/chat).
    ├── openai_compat.py  OpenAI-style client (/v1/chat/completions).
    └── parsing.py    Reads JSON from imperfect replies; strips reasoning blocks.
```

Dependencies between them point downwards: `cli` uses `workflows`, `apply` and `validate`; `workflows` uses `events`,
`substitute`, `edits`, `llm`, `frontmatter`, `text_utils`; those use `site`, `schemas`, `config`. Nothing below
`workflows` imports the CLI or the model clients.

## What happens in `add-event`

```
notice.txt ──► ask_json(extract_new_event prompt) ──► JSON object
                                                       │
                              _clean (keep known keys) │
                                                       ▼
                              Event.model_validate (schema; error names the field)
                                                       │
                     new_event_path (slug from title)  │
                                                       ▼
                 render_document (frontmatter from model + body)  ──► Plan (one new file)
                                                       │
                 ungrounded_fields (warn if a date or place is not in the notice)
                                                       ▼
   CLI: print plan ──► check_plan (schema + allow-list) ──► preview only, or ask ──► apply_plan
                                                                                      │
                                                  backups, run log, write, check command
```

## What happens in `update-event`

```
find_event (file name, exact title, or close match)
   │
load_event (validated record + exact text)
   │
ask_json(extract_update_event, current record + instruction) ──► changed keys
   │   missing keys keep their old value; null removes a key
   ▼
changes = {key: new value}  ──► set_frontmatter_values on the event file (surgical edit)
   │
substitutions_for(old record, changes)     e.g. "10 March 2026" → "14 April 2026", "2026-03-10" → "2026-04-14", …
   │
find_mentions(old values) across the site, excluding the event file
   │
for each file (the event file first):
   replace_on_anchor_lines   → only lines containing the old title; reported with line numbers
   leftovers (lines not changed) → reported; with --assisted, sent to the model as an excerpt; edits outside it are refused (S17)
   │
Plan (changed files + notes) ──► same review and apply path as add-event
```

## Safety rules

Each rule has at least one test. If you change code near one of them, keep the test passing or change the test on purpose.

| # | Rule | Where it is enforced | Test |
|---|---|---|---|
| S1 | Nothing is written without `--apply` (and `--yes` or a terminal answer). | `cli._review_and_apply` | `test_add_event_without_apply_only_previews`, `test_apply_without_yes_or_a_terminal_refuses_to_write` |
| S2 | Writes only inside the site root, and only to content files (`src/content/**/*.md` by default). Code and page file types (`.astro`, `.ts`, `.tsx`, `.js`, `.mjs`, `.cjs`, `.css`, `.html`) are refused even when a configuration lists them. Never `node_modules`, `dist`, `.git`, `.site-agent`. | `Site.resolve`, `Site.is_writable` (code types refused here), `Site.write` | `test_paths_that_leave_the_site_are_refused`, `test_writable_allow_list`, `test_apply_refuses_paths_outside_the_allow_list` |
| S3 | Every replaced file is copied to a backup first, and each run is logged. | `apply.apply_plan` | `test_apply_writes_backs_up_and_logs_then_restore_undoes_it` |
| S4 | A file that changed after the plan was made is not overwritten. | `apply.apply_plan` | `test_apply_refuses_a_file_that_changed_after_planning` |
| S5 | A change that would leave a content file invalid is not written. | `validate.check_plan`, for every content collection (the CLI calls it before the question) | `test_a_plan_that_would_break_an_event_file_is_refused` |
| S6 | The model never writes frontmatter text; the tool renders it from the validated record. | `workflows.plan_add_event` (`render_document`) | `test_add_event_renders_the_file_from_the_validated_record` |
| S7 | A model edit is applied only if its search text appears exactly once. | `edits._place` | `test_ambiguous_search_text_is_not_applied`, `test_missing_search_text_is_reported_and_leaves_the_file_alone` |
| S8 | The check command comes only from `site-agent.toml`. Model text never reaches it. | `apply.run_check` (the config value is its only input) | `test_run_check_reports_success_and_failure` |
| S9 | Model traffic goes only to the configured `base_url`. | `llm/base.post_json` | `test_ollama_sends_the_chat_request_and_reads_the_reply` |
| S10 | Lines that show old details but do not name the event are never changed without the operator's opt-in. | `workflows.plan_update_event` | `test_by_default_lines_without_the_event_name_are_reported_not_guessed` |
| S16 | A write that fails part way is undone before the error is shown. Every file is put back as it was, and no run log is written. | `apply.apply_plan`, `apply._put_back` | `test_a_write_that_fails_part_way_is_undone_and_leaves_no_run` |
| S17 | An update is not written while one of its model edits cannot be placed, or changes text the model was not shown. The lines are listed for hand editing. | `workflows._ask_model_for_leftovers`, `cli._review_and_apply` | `test_an_update_with_a_model_edit_that_cannot_be_placed_writes_nothing`, `test_model_edit_that_cannot_be_placed_is_reported_not_applied` |

## Data the tool reads and writes

- Reads: the site's Markdown and text files (not binaries, not dependency folders, not files over 1 MB), and
  `site-agent.toml`.
- Writes: the changed files, `.site-agent/backups/<run id>/…` (byte copies of replaced files), and
  `.site-agent/runs/<run id>.json` (what changed, when, with which model). The website's own `.gitignore` should list
  `.site-agent/` so these files stay out of commits.
- Network: only the model server named in `[llm].base_url`.

## Extension points

- **A new model backend:** implement `chat(messages, *, json_mode) -> str` and add a branch to `llm.make_client`.
- **A new collection (for example news):** add a Pydantic model to `schemas.py`, register it in `COLLECTIONS`, add a
  `Site`-level helper if it needs its own lookup like `events.find_event`, add a `plan_add_<thing>` workflow with its
  own extraction prompt, and add tests. `validate` and the allow-list then apply automatically.
- **A new prompt:** add `prompts/<name>.md` and call `load_prompt`. Placeholders are written `{{name}}`.
- **A new check:** `apply.run_check` runs any command string. A richer check would return structured results.

## Known limits

- Only the Event collection is validated and supported.
- Frontmatter edits keep existing lines, but a line-level change does not re-check Markdown or Astro syntax. The
  check command does that.
- Date detection handles five common English spellings. A range such as "10–12 March 2026" is not replaced
  automatically; it is reported.
- Text matching is case-insensitive and whitespace-tolerant, but it does not understand synonyms or translations.
- The model extraction is a single call per notice. Long notices are sent whole; very long ones may exceed the context
  window of a small model.


## The operator app (added in v0.2)

The app is a thin layer over the rules. It has no rule of its own.

```
web/                 FastAPI routes and Jinja2 pages. Reads forms, calls services, shows results.
  app.py             Routes. Every form is checked for the CSRF token. Redirects stay on this site.
  server.py          Starts the app on 127.0.0.1 only, and opens the browser.
  templates/         The screens (base layout, list, record form, preview, history, check, launch, samples, settings).
  static/app.css     The approved design tokens (docs/design/APP_DESIGN.md, section 8).
records.py           The content rules: one table per collection (fields, kinds, choices, required, defaults).
                     Form input becomes typed values; values become a file; a file is re-checked against the same table.
repository.py        The one place a form becomes a plan. Lists records, checks references, builds the plan and
                     the plain-language changes. Blockers stop a save; warnings need a tick before approval.
appstate.py          Settings (operator name, approvers), previews, drafts, the approval log and the last check.
                     JSON in .site-agent/, written through a temporary file so a crash cannot leave a half file.
drafting.py          Model drafting: prompts, background jobs with cancel, and the model status.
launch.py            Samples, placeholder words, the launch report. Mirrors the template's launch check.
history.py           Lists runs and decides whether each can be undone (strict rules, see S13).
```

### How a change travels

```
form ──► repository.create/update/archive ──► Outcome (errors, blockers, warnings, plain changes, Plan)
                                                  │
                                       appstate.save_preview  (stored with a fingerprint of the exact text)
                                                  │
                  approve: approver from list ─ statement ─ each warning ticked ─ fingerprint re-checked
                                                  │
                  apply_plan  (backup, write, run log with a hash of every file written)
                                                  │
                  appstate.add_approval  (approval linked to the run)  ──► site check job (if configured)
```

### Safety rules added with the app

| # | Rule | Where it is enforced | Test |
|---|---|---|---|
| S11 | An approval applies only to the exact text previewed. The fingerprint is checked before writing. | `plan.fingerprint`, `web/app.py` approve route | `test_a_change_made_after_the_preview_is_refused` |
| S12 | A save needs an approver from the list, the operator's name in Settings, the statement, and a tick on every warning. | `web/app.py` approve route | `test_approval_needs_an_approver_and_the_operator_name` |
| S13 | Undo is offered only when no later change touched the same files and each file still holds exactly what the run wrote. The reason is shown otherwise. | `history.undo_status` | `test_undo_refuses_when_the_file_was_edited_afterwards`, `test_an_older_change_cannot_be_undone_before_a_newer_one` |
| S14 | Written text may use only the facts given. A number, year, address or email in a draft or in any long text box, when it is new or changed, must appear in the facts as a whole item. Long text is not a fact. Saving is blocked while such an item remains. | `factcheck.fact_problems`, `factcheck.unsupported_tokens`, `repository.create` and `update` | `test_new_long_text_with_an_unsupported_number_is_a_problem`, `test_a_number_is_only_supported_as_a_whole_item`, `test_draft_items_not_in_the_facts_block_saving_until_resolved` |
| S15 | The app listens on 127.0.0.1 only. It answers only to localhost names. Every change form needs the CSRF token. Redirects stay on this site. Entry names are checked before a file is touched. | `web/server.py`, `TrustedHostMiddleware`, `checked_form`, `_safe_next`, `valid_id` | `test_posting_without_the_form_token_is_refused`, `test_redirects_cannot_leave_the_site`, `test_a_bad_entry_name_cannot_reach_other_folders` |

### Where the app keeps its records

Inside the website folder, in `.site-agent/` (git-ignored; the website's own `.gitignore` should list it):

- `settings.json`: the operator's name and the approvers' list.
- `previews/`: changes waiting for approval. Removed on approval or discard.
- `drafts/`: wording the model produced, kept for the form until it is used. They are labelled as drafts and never reach the
  website without approval. Keeping them on disk is a deliberate exception to "nothing is saved" (see DECISIONS D15).
- `approvals.jsonl`: an append-only log. Each line says who approved, who recorded it, when, which files, and the
  fingerprint.
- `runs/` and `backups/`: every written change and the bytes it replaced, for undo.
- `last_check.json`: the result of the last site check.
