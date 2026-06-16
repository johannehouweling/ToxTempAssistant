# gold_standard — production scientist-accepted answers as ground truth

This workstream turns the answers scientists reviewed and **accepted** in production (drafted
by gpt-4o-mini) into a reusable ground-truth gold set, and quantifies *how* scientists changed
the model's drafts. It is the right reference for evaluation — far better than comparing models
to gpt-4o-mini, which is a weak baseline.

## What "gold" means here
A gold answer = the live `Answer.answer_text` where `accepted=True`, on a **non-demo** assay
(demo assays are auto-seeded per user and excluded). These are expert-approved, so they are the
reference any candidate model (or gpt-4o-mini itself) should be scored against.

## The draft / edit-typing — and the era caveat (read this)
We can often recover gpt-4o-mini's **original draft** and measure what the scientist changed —
but **only for assays generated before 2025-09-13** (git-verified):

| assay generated | draft write path | draft in history? |
|---|---|---|
| before 2025-09-13 | `answer.save()` | **yes** — earliest non-blank history snapshot |
| on/after 2025-09-13 | queryset `.update()` (commit `5f12fd7`) | **no** — bypasses simple-history |

For post-cutoff assays the draft must be reconstructed by re-running gpt-4o-mini (a follow-up).
Most reviewed assays predate the cutoff, so edit-typing is available now for the bulk of them.

## Edit-typing is semantic
The draft→final change is typed using **embedding cosine similarity** (the primary, *meaning*
signal) plus a lexical/length check (surface), via the project's SHA-cached embeddings
(`post_processing/embeddings.py`) so it is reproducible and cheap on re-run:

`none` (accepted verbatim) · `cosmetic` (typo/unit) · `expand` / `trim` (content added/removed,
meaning kept) · `edit` (reword/moderate) · `rewrite` (meaning changed) · `abstain_to_answer`
(model abstained, scientist answered — a confirmed recall gap) · `answer_to_abstain` (scientist
rejected a likely hallucination). Thresholds live in one place: `edit_analysis.py`.

The `edit_type` distribution is the scientific payoff — e.g. the share accepted verbatim
measures gpt-4o-mini's draft quality against human ground truth.

## Safety
Strictly read-only: DB reads run in a `SET TRANSACTION READ ONLY` transaction with
`pre_save`/`pre_delete`/`m2m_changed` write-tripwires; embeddings run *after* the transaction
closes (no DB snapshot held during API calls); no MinIO/object access. With `--no-cosine`
(the production default below) **no embeddings run at all** — prod does a pure DB read and
the cosine typing is computed locally.

## Run — local / dev
```bash
# read-only; --limit for a quick pass; default output is output/_analysis/gold_answers_<ts>.csv
python manage.py extract_gold_answers --limit 3
```
`--out` accepts a file (used verbatim) or a directory (gets a timestamped name); with no
`--out` it writes `output/_analysis/gold_answers_<YYYYMMDD_HHMM>.csv`. `output/` is gitignored
— the CSV (answer text + reviewer emails) never reaches git. Add `--no-cosine` to skip the
embedding pass (then type it with `enrich_gold_cosines`, as in production below).

## Run — production (the split: read on prod, type locally)

Prod has **no OpenAI embeddings credential** — the chat models are Azure Foundry, whose key
401s against `api.openai.com`, and Azure doesn't serve `text-embedding-3-large`. So the prod
step runs **`--no-cosine`**: a pure read-only DB dump, **no key needed**. The cosine
edit-typing is then computed on your machine, where the OpenAI key + the SHA embedding cache
live. The typed result is identical to an inline run — it's just split in two.

Code reaches prod by **merging to `main`** (auto-release → `Publish image` → `Deploy`,
~5–15 min on the Actions tab). Then, on the prod host (not in the `docker` group, so `sudo`;
explicit container name `djangoapp`, not `docker compose`):

```bash
# 1) extract — READ-ONLY, no OpenAI key, no API calls (one physical line)
sudo docker exec djangoapp python manage.py extract_gold_answers --no-cosine --out /tmp/gold.csv

# 2) copy it out of the container and make it readable
sudo docker cp djangoapp:/tmp/gold.csv /home/$USER/gold.csv && sudo chmod 644 /home/$USER/gold.csv
```
```bash
# 3) on your LOCAL machine, pull it down (gitignored landing spot)
scp <user>@<prod-host>:/home/<user>/gold.csv ~/Downloads/gold_no_cosine.csv

# 4) fill the cosine edit-typing locally (uses your OpenAI key + SHA cache). No --out → it
#    lands in output/_analysis/gold_answers_typed_<ts>.csv, which the plotting scripts glob for.
cd myocyte && poetry run python manage.py enrich_gold_cosines --in ~/Downloads/gold_no_cosine.csv
```
```bash
# 5) wipe the prod copies — the CSV holds gold answers + reviewer emails (PII)
sudo docker exec djangoapp rm -f /tmp/gold.csv && sudo rm -f /home/$USER/gold.csv
```

No `--exclude-emails` by default: demo assays are already filtered in code, and `owner_email`
is a column, so drop any genuine test accounts during analysis rather than risk losing real
reviewers. Add `--exclude-emails a@x,b@y` only for known dummy accounts. Known non-gold
scratch/test/partial **assays** are dropped centrally via `audit.EXCLUDED_ASSAY_IDS`
(currently #75 `hNTP_Test_C` + #115 partial hNTP); add ids there as more are identified — it
filters per-assay, not per-person, so real reviews by the same owner are kept (e.g. that
owner's full hNTP review #103 stays).

**Inline (with-cosine) alternative:** if a valid OpenAI key is available to the container
(`-e OPENAI_API_KEY=sk-…`), drop `--no-cosine` and skip steps 3–4 — the extract types inline.
The split is preferred so no key ever touches prod.

**Fallback** if step 1 prints `Unknown command` / `unrecognized arguments: --no-cosine`, the
container is still the old image — from the repo dir on prod: `sudo docker compose --profile
prod pull djangoapp && sudo docker compose --profile prod up -d djangoapp`, then retry.

**Tip (paste mangling):** keep each command on ONE physical line.

The companion **sufficiency** check (how much gold exists, by whom, with what docs) is
`python manage.py assess_ground_truth` — same read-only / prod-ops pattern.

## Layout
Mirrors `real_world/output/` — outputs bucketed by purpose; all scripts stay tracked in the
package root (`output/` is gitignored except `.gitkeep`, so they live here, not under it).
```
gold_standard/
  edit_analysis.py   # pure logic (draft detection + cosine edit-typing); unit-tested
  audit.py           # read-only orchestrator; exposes run() (--no-cosine skips embeddings)
  enrich.py          # local pass: fill cosine + edit type for a --no-cosine CSV
  status_table.py    # per-assay coverage table (md/html/png) from the latest typed gold
  bakeoff.py         # score cross-provider models vs gold (cosine + abstention agreement)
  README.md
  output/            # gitignored except .gitkeep (gold answers + reviewer emails = PII)
    _analysis/       #   data CSVs: gold_answers_typed_*, ground_truth_assessment_*, bakeoff_*
    _plotting/       #   figures: gold_status_table.{md,html,png}, bakeoff.{html,png}
    _embeddings/     #   SHA-cached vectors (reproducible, cheap re-runs)
# commands: extract_gold_answers (prod, read-only) · enrich_gold_cosines (local, typing)
#           · assess_ground_truth (sufficiency). status_table/bakeoff run as scripts.
# scripts glob the newest output/_analysis/gold_answers_typed_*.csv as the gold.
# tests: toxtempass/tests/test_gold_standard_edit_analysis.py
```
