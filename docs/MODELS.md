# Models

The tool needs a local model server to draft wording from the operator's notes. This document says which model to use
on which computer, how to install it, and what was measured. Measurements are small and early; treat them as a
starting point, not a verdict.

## Choosing a model by memory

| Computer memory | Start with | Notes |
|---|---|---|
| 16 GB | `qwen2.5:7b` (about 4.7 GB) | The model used for most testing so far |
| 8 GB | `llama3.2:3b` (about 2.0 GB) | Tested for event extraction only. Check it on real notices first |

Reasoning models (`qwen3:8b`, `deepseek-r1:7b`) print a thinking block before the answer. The parser strips it, but
these models have not been tested yet.

The memory figures are for the model alone. The operating system, the browser and the Streamlit screens need more.
On 8 GB, close other large programs while drafting.

## Installing the model server

1. Install Ollama from <https://ollama.com>. On Windows, the installer starts the server in the background.
2. Download a model once, in a terminal:

   ```bash
   ollama pull qwen2.5:7b
   ```

3. Check that the server is running:

   ```bash
   ollama list
   ```

On WSL2 the server runs inside Linux. Keep the default address `http://localhost:11434`. If the tool runs on Windows and
the server runs in WSL2, or the other way round, see the notes in REQUIREMENTS.md section (f).

## Measured so far

Machine: Linux under WSL2, 16 logical CPUs, about 10 GB of memory available, no GPU. Each figure is one run unless
stated.

| Model | Task | Result | Time |
|---|---|---|---|
| `qwen2.5:7b` | Event from a notice (`tests/test_live.py`) | Title, date, venue and summary correct. Kind `programme` chosen for an open day (a judgement). The body added one sentence the notice did not state | about 15 s |
| `llama3.2:3b` | Same notice | Title, date, venue and summary correct. Kind the same. Body left empty | about 13 s |
| `qwen2.5:7b` (re-run, 20 October 2026) | Same notice, `tests/test_live.py` | Title, kind, date and venue correct | 27 s |
| `qwen3:8b` | Same notice | Date, venue and kind correct. The title came out in lower case ("annual open day") and the test passed anyway | 251 s |
| `deepseek-r1:7b` | Same notice | Title, kind, date and venue correct | 436 s |
| `qwen2.5:7b` | Drafting a biography in the app's drafting code (`draft_section`), five sets of invented facts | Fluent and on topic. **Each draft added claims the facts did not state** (for example "improve patient care and operational efficiency"). The fact check passed all five, because it checks numbers, years, addresses and emails only | 38 s for the first (model loading), then 1.5 to 2 s each |
| `qwen2.5:7b` | Update an event on the CIR template clone (dry run) | Four fields changed correctly from one instruction | about 4 s |
| `qwen2.5:7b` and `llama3.2:3b` | Update an event on the example site: the event file and the homepage line that names it | Both produced the same correct change, without the model editing the homepage line | not timed |
| `qwen2.5:7b` | Model-assisted edit (`--assisted`) on lines that did not name the event | **Unsafe.** Changed "Proposal deadline: 10 March 2026" when asked about a "Save the date" line. The rule added afterwards: unrelated lines are never changed without the operator's opt-in, and the tool lists them. Since 20 October 2026 the code also refuses an edit that changes text the model was not shown, and refuses an update with an edit it cannot place | not timed |

What these results mean:

- Extraction of structured fields from a short notice works on the three models tested for it (`qwen2.5:7b`,
  `qwen3:8b`, `deepseek-r1:7b`), and on `llama3.2:3b`. Each time is one run, and includes loading the model where it was
  not already in memory. `qwen2.5:7b` was the fastest: about nine times faster than `qwen3:8b` and sixteen times faster
  than `deepseek-r1:7b`. Those two reasoning models are slow on a 16 GB machine for little gain here, and `qwen3:8b`
  lower-cased a title. Two runs per model is not enough to rank them. The evaluation set in PLANNING.md (M6) is the next
  step.
- Drafting is fast enough for the operator on this machine, but it is not safe to trust. Each draft added claims the
  facts did not give, and the fact check does not look for claims. A drafting rule that forbids them, and a check for
  them, are open decisions (PLANNING.md, section 6, item 6).
- Changing text in a file by asking the model is not reliable enough to run without a person checking every line. That
  is why the tool replaces known values itself and only asks the model about lines it cannot place.
- The model is never asked to write YAML. The tool writes it from the validated record.

## Regression set on the final code (20 October 2026)

Eight synthetic notices in `tests/regression/`, each with the record it should produce (`tests/regression/expected/`). Run with
`SITE_AGENT_LIVE=1 SITE_AGENT_MODEL=<model> .venv/bin/python -m pytest -m live -s tests/test_live.py`. The machine is the
ten-gigabyte WSL2 development computer. Times are for the whole set, including loading the model. This is the run after the
last fixes (venue shortening, the missing-series note, the schema without patterns, streaming).

**qwen2.5:7b** (280 seconds for the set)

```
case                   right  wrong  noted  seconds  result
list_layout                6      0      0     89.6  ok
long_notice                6      0      0     44.5  ok
no_date                    1      0      0     25.7  ok
one_day_talk               6      0      0     22.9  ok
programme_with_series      5      1      1     33.2  wrong: series (wanted 'Example Robotics Summer Series', got None)
relative_date              6      0      2     20.0  ok
two_day_workshop           6      0      0     22.5  ok
venue_two_ways             6      0      0     21.0  ok
total                     42      1      3    279.4  98% of fields right, 0 case(s) raised an error
per field: title 7/7, kind 7/7, date 7/7, endDate 7/7, venue 7/7, series 6/7, rejected 1/1
```

**llama3.2:3b** (122 seconds for the set)

```
case                   right  wrong  noted  seconds  result
list_layout                6      0      0     28.5  ok
long_notice                6      0      0     15.0  ok
no_date                    1      0      0     21.9  ok
one_day_talk               6      0      0     12.5  ok
programme_with_series      5      1      1     12.9  wrong: series (wanted 'Example Robotics Summer Series', got None)
relative_date              6      0      2     11.5  ok
two_day_workshop           6      0      0     10.6  ok
venue_two_ways             6      0      0      8.8  ok
total                     42      1      3    121.7  98% of fields right, 0 case(s) raised an error
per field: title 7/7, kind 7/7, date 7/7, endDate 7/7, venue 7/7, series 6/7, rejected 1/1
```

What these results show:

- Both models get every date right, including "next Monday", which the code works out from the phrase (D30).
- Both still miss the series name in the programme case. The harness now notes it (D44), so the operator sees the gap in the
  preview. The model is not corrected: a missing value is left for the operator.
- The venue error seen earlier with `llama3.2:3b` (an extra sentence copied from the notice) is fixed by shortening the value to
  the quoted words (D44).
- No case raised an error, and no harness or prompt fault was seen in either run.
- The real runs found a fault that the scripted tests did not: the date pattern in the reply schema made the local runner
  crash (D42). That is fixed, and the schema now names no pattern.

**Automatic choice (D39).** On this ten-gigabyte computer `model = "auto"` chooses `llama3.2:3b`. Both models scored the same on
this set, but `llama3.2:3b` ran in about half the time. The larger model may do better on longer or less regular notices, which
this set does not test; choose by name on a computer with more memory.

## Not yet tested

- Drafting quality on real facts, for the biography, summary and description drafts. Timing was measured on invented
  facts for the biography only. The app's tests use a scripted model.

- Reasoning models (`qwen3:8b`, `deepseek-r1:7b`) for drafting and for more than one notice. Extraction was tried once.
- Any model on native Windows.
- Notices in a language other than English. A notice of about 540 words is in the regression set and passes.
- The model-assisted edit on `llama3.2:3b`.
- Many notices in a row, to measure consistency.
