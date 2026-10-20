# Template contract

This file says what the tool assumes about the CIR website template, which version it was checked against, and how to
keep the two in step. If the template changes, read this file first.

## The version this was checked against

- Repository: <https://github.com/robita-cir/cirwebsitetemplate>
- Commit: `23f4878b60d337ebd18fac22427dcd31bdf14a86` (16 October 2026, "Replace the README screenshot table with a
  one-line note")

Read-only checks were run against a clone of this commit: `site-agent scan`, `site-agent validate` (9 event files, 0
errors), `site-agent find`, and a dry run of `update-event`. The template was never built or run by this project.

## What the tool assumes

### Content layout

- Each content collection is a folder: `src/content/<collection>/`. Each entry is one Markdown file with a top block
  between two `---` lines.
- The file name (without `.md`) becomes the page address. For events, `src/content/events/event-1.md` is
  `/events/event-1/`. Renaming a file changes its link.
- Only the event collection is supported by the tool today. `site-agent scan` lists the others as "not supported yet".

### The event schema

The rules for every collection are in `src/site_agent/records.py`, one table per collection. The event rules are also in
`src/site_agent/schemas.py`, which the command line uses. Both copy `src/content.config.ts`:

| Field | Rule in the template | Rule in the tool |
|---|---|---|
| `title` | text, required | text, required, not empty |
| `kind` | one of `workshop`, `programme`, `talk`, required | same |
| `series` | text, optional | text, optional. the template's workshop-series block shows only the literal name `series-1` (see below) |
| `date` | date, required | date, required, written `YYYY-MM-DD` |
| `endDate` | date, optional | date, optional, not earlier than `date` (the template does not check this; see P8) |
| `venue` | text, optional | text, optional |
| `summary` | text, optional | text, optional |
| `sample` | true or false, default false | same; the tool never writes `sample: true` for a new event |

Unknown keys are ignored by the site. The tool reports them as warnings.

### Things the template does that the tool must respect

- `sample: true` marks a placeholder. The launch check refuses to pass while any remain. The tool's `scan` command
  counts them. Partners, funded programmes and research directions cannot carry the flag at all (P2).
- Dates decide "upcoming" and "archive" at build time. The tool does not decide this.
- The homepage counts and the workshop-series block depend on the literal series name `series-1` (`index.astro` line 31,
  `events.astro` line 21). A new event with any other series name is silently left out of those blocks. Until P3 is
  done, the tool should only write series names agreed with the centre.
- Some wording is written into page files, not into content. The tool does not edit it. A line in a page that names
  an event is changed only by the update flow, and only where writes to that file are allowed (see below).

### Writes and checks

- The tool writes only the paths in `writable` in `site-agent.toml`. The default is `src/content/**/*.md`: content only.
  Code and page file types (`.astro`, `.ts`, `.js`, `.css`, `.html` and similar) are refused even when a configuration lists
  them. This was narrowed on 18 October 2026 (DECISIONS D14).
- The check command is configured per site. The template's check is `npm run check` (build plus HTML check). It needs
  Node 22.12 or newer and the template's packages installed (`npm install`). The tool does not install them.

- Before a write, every content file that a change touches is checked against its collection's rules: the event schema
  for events (`schemas.py`), and the table in `records.py` for every other collection. A change that would leave one
  invalid is not written.

## Known differences between the template's documents and its code

The template's own documents disagree with the code in several places. The full table is in EDITABLE_SECTIONS.md,
area 20. Where the tool depends on one of these, the code is the source of truth.

## How to keep the tool in step with the template

1. Clone the template at the new commit into a folder the tool does not write to.
2. Run `site-agent scan --site <clone>` and `site-agent validate --site <clone>`. Both must report no errors.
3. Compare `src/content.config.ts` with the table above. Change `schemas.py` and the prompts in
   `src/site_agent/prompts/` if a field changed.
4. Run `pytest`. Update the fixtures in `tests/fixtures/mini_site/` if a field name changed.
5. Update the commit and date at the top of this file.

## Changes the CIR team has been asked to make in the template

These are listed as P1 to P19 in REQUIREMENTS.md, section (e). None has been made. The tool works without them, but
several operator workflows are limited until P1 to P3 are done.

## Checked against the template copy (18 October 2026)

On a copy of commit 23f4878b, with nothing built or installed:

- Every record in the template passes the app's content rules: 62 people, 11 projects, 4 research directions, 9 events,
  2 news, 2 openings, 3 publications, 12 partners, 4 funded programmes, 4 facilities, 2 documents, 4 gallery albums.
- 99 entries carry `sample: true`. The launch readiness report counts the same 99.
- Partners and funded programmes have no sample flag in the template, so their placeholder words are listed as warnings.
- Launch readiness also reports the placeholder values in the site settings file, and the three legal pages still marked
  "Draft for review".

## Checks the template does not make

The app's launch screen and its audit also warn about things the template's launch script does not check: an event whose end
date has passed (on the machine's local date), news that says it is coming up but is dated more than 60 days ago, a homepage or
news line that gives a different date from the event it names, a photo or PDF that is missing or of the wrong type, and
placeholder words in the site pages. These are warnings with a place to fix them; none of them changes a content file.

## Run against the template copy (20 October 2026)

On a copy of commit 23f4878b, installed with `npm ci` under Node 22.23.3 (the template needs 22.12 or newer), on the
developer's WSL2 machine:

- `npm run check` passes. The build makes 113 pages and the HTML check reports no errors.
- `npm run check:launch` exits 1 with 105 blocker lines: 99 sample entries, `src/pages/styleguide.astro`, the three legal
  pages marked "Draft for review", and `site.url`. The app's launch report had no check for the styleguide page, the
  social-sharing image, the bracketed placeholders in the legal pages, the club link, the search index or the portraits.
  These now follow the template's rules, so the app and the template agree on what blocks a launch.
- An end-to-end run through the app, on a copy of that site with `check_command = "npm run check"`: the app started on
  localhost, a person was added, previewed and approved, the template's check ran through the app and passed, the file
  was written, and undo removed it again. This was on the developer's WSL2 machine. The operator's own machine and
  native Windows are not tested yet (PLANNING.md, milestone M3).
