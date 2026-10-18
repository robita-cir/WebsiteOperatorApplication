# CIR website operator

A local, offline tool for the Centre for Intelligent Robotics (CIR) website. A lab operator who does not know front-end
code changes the site's content (people, events, news, openings, publications, partners, funding, facilities,
documents, gallery) through a web page on their own computer. A small local model drafts wording from the facts the
operator gives it. Nothing reaches the website until the operator previews the changes, and an approver from a named
list approves them. Every change can be undone from History.

The app is built for the CIR website template, Astro with Markdown content collections. It never changes site
structure, layout or code. A technical person still deploys the site.

**Status: first build (v0.2).** All twelve content collections, the approval and undo path, the site check, the launch
readiness list and the history are built and tested. Native Windows and the WSL2 bundle have not been tested yet.
See [docs/PLANNING.md](docs/PLANNING.md).

## Use the app

```bash
.venv/bin/site-agent-app --site path/to/website
```

On Windows, use `.venv\Scripts\site-agent-app --site path\to\website`. The app opens in the browser at
http://127.0.0.1:8765. It listens only on this computer.

The screens, from the sidebar:

- **Start**: what needs attention, the main actions, and recent changes.
- **Content lists** (People, Projects, Research directions, Publications, Facilities, Events, News, Job and study
  openings, Partners, Funded programmes, Documents, Gallery albums): search, filter to samples, add, edit.
- **Samples and placeholders**: sample entries still on the site, and placeholder words left in the content.
- **Check the site**: runs the template's own check after a change, and keeps the result.
- **Launch readiness**: blockers, warnings and what already passes.
- **History**: every saved change, with Undo where it is safe, and every approval.
- **Settings**: your name (recorded with each approval) and the approvers' list.

### Making a change

1. Open a list, for example People, and press **Add**, or open an entry to **Edit**.
2. Fill in the form. For wording, write the facts in the box at the bottom, then press a **Draft** button. The helper
   only uses those facts. A number, year or web address it adds that is not in your facts is flagged, and saving is
   blocked until you remove it from the text or add it to the facts.
3. For an event, paste the notice into **Fill in from notice**. The form is filled in for you to check.
4. Press **Preview changes**. Read the changes in plain language.
5. Tick each warning you have checked, choose an approver, tick the statement, and press **Approve and save**.
6. The change is written, with a backup. If the site has a check command, it runs. To undo, use **History**.

Nothing is saved before step 5. If a file changes after you preview it, the app refuses to save and asks you to start
again.

### Removing an entry

Open the entry and use **Remove**. It goes through the same preview and approval. The file is removed from the website
and a copy is kept, so **History** can restore it.

### What the app will not do

- It will not write a code or page file (`.astro`, `.ts`, `.css`, `.html` and similar), even if a configuration lists it.
- It will not undo a change if a later change touched the same file, or if the file was edited since. It says why.
- It will not save without an approver from the list, your name in Settings, and a tick on each warning.
- It will not send your notices, drafts or the website to any server. The writing helper runs on this computer.
- It will not publish. Deployment is for the technical contact.

## Set up (for the technical contact)

Requirements: Python 3.11 or newer. A local model server, [Ollama](https://ollama.com), with a model installed. See
[docs/MODELS.md](docs/MODELS.md). Node.js 22.12 or newer and the website's packages, for the site check.

```bash
python3.12 -m venv .venv
```

```bash
.venv/bin/pip install -e ".[dev]"
```

Then, in the website folder, create `site-agent.toml` from [site-agent.example.toml](site-agent.example.toml). Set
`check_command` to `npm run check` once `npm install` has been run in the website folder. Only the technical contact
sets this value.

Command-line tools for the technical contact: `site-agent scan`, `find`, `restore`, and the older `add-event` and
`update-event` commands. The app and the command line share the same rules and the same history.

## Tests

```bash
.venv/bin/pytest
```

The tests use a fixture site and a scripted model. They never call a real model. A live test against a model server is
opt-in: `SITE_AGENT_LIVE=1 .venv/bin/pytest -m live -s`.

## Documentation

- [docs/PLANNING.md](docs/PLANNING.md): status, roadmap, open decisions. Start here if you are taking this over.
- [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) (also as [PDF](docs/REQUIREMENTS.pdf)): what the operator needs, edge cases, open questions.
- [docs/EDITABLE_SECTIONS.md](docs/EDITABLE_SECTIONS.md): every place the content can be edited.
- [docs/design/APP_DESIGN.md](docs/design/APP_DESIGN.md): the functional and visual design, with mockups in `docs/design/mockups/`.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): how the modules fit together, and the safety rules.
- [docs/DECISIONS.md](docs/DECISIONS.md): why things are built the way they are.
- [docs/MODELS.md](docs/MODELS.md): model choice by memory, and what was measured.
- [docs/TEMPLATE_CONTRACT.md](docs/TEMPLATE_CONTRACT.md): what the app assumes about the website template.
- [CONTRIBUTING.md](CONTRIBUTING.md): how to set up, test and change the code.

## Licence

MIT, proposed and not yet confirmed by the centre. See [LICENSE](LICENSE).
