# Contributing

Thank you for helping. Read [docs/PLANNING.md](docs/PLANNING.md) first. It says what the tool is for, what is done, and
what is open.

## Set up

On Linux or WSL2:

```bash
python3.12 -m venv .venv
```

```bash
.venv/bin/pip install -e ".[dev]"
```

On Windows (PowerShell): `py -3.12 -m venv .venv`, then `.venv\Scripts\pip install -e ".[dev]"`. Python 3.11 or newer is
required.

## Check your change

```bash
.venv/bin/pytest
```

```bash
.venv/bin/ruff check src tests
```

The tests use a scripted model and never call a real one. To run the one live test against a model server:

```bash
SITE_AGENT_LIVE=1 SITE_AGENT_MODEL=qwen2.5:7b .venv/bin/pytest -m live -s
```

If your change depends on model behaviour, run the live test and record the result in
[docs/MODELS.md](docs/MODELS.md).

## Rules for changes

- **Safety rules.** Each rule in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) (S1 to S17) has a test. Keep the test
  passing. If a rule itself must change, write the new rule in [docs/DECISIONS.md](docs/DECISIONS.md) first.
- **Operator messages.** Errors and notes are read by a non-technical operator. Write them in plain English, say what
  to do next, and name the file and the field.
- **Structure.** The tool changes content, not site structure. A change that lets it edit code or layout needs a
  decision recorded in DECISIONS.md.
- **Comments.** Explain why, not what. Keep the existing density.
- **Background work.** A job that saves something passes the save as `finish` to `JobRunner.start`. A cancelled job does
  not run it, so a cancel means nothing is saved.
- **No real content in the repository.** Use `tests/fixtures/mini_site/` for examples. Do not copy the CIR template into
  this repository; it has no licence file yet.

## Running the app while you work

```bash
.venv/bin/site-agent-app --site tests/fixtures/mini_site --no-browser
```

Use a copy of a website, never the real one, while you try changes. The app writes to the site folder.

## Adding a content collection

The app's rule table is the source for its forms, checks and file writing.

1. Read the collection's fields in the template's `src/content.config.ts`, and its edge cases in REQUIREMENTS.md, section (c).
2. Add a `Spec` with its `Field`s to `records.py` and register it in `SPECS`. The write check (`validate.py`) uses the same table. Choose the field kinds (text, long, choice,
   int, date, url, email, list, doi, path, person_list, partner_name) that match the template's schema and the proposed
   limits.
3. If another collection names entries of this one, add it to `DEPENDENCIES` in `repository.py`.
4. Add tests for each edge case in the fixture site (`tests/fixtures/mini_site`), and add one valid example file there.
5. If the collection has a body or long text, give it a `body_label` and let the drafting prompt do the rest.
6. Update TEMPLATE_CONTRACT.md. Check the rules against the template copy (see that document).

The command line's event workflows (`workflows.py`) are separate. A new collection does not need a command-line workflow.

## Adding a model backend

Implement `chat(messages, *, json_mode) -> str` in `src/site_agent/llm/`, add a branch to `make_client` in
`llm/__init__.py`, and test it against a small local server as `tests/test_llm_clients.py` does.

## Pull requests

- Describe what changed and why, and which safety rule or document it touches.
- Include the test output and, for model changes, the live result.
- Do not commit `.venv/`, `.site-agent/` or any file from a real website folder.
