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
closes (no DB snapshot held during API calls); no MinIO/object access.

## Run
```bash
# read-only; --limit for a quick first pass, --out to write the dataset CSV
python manage.py extract_gold_answers --exclude-emails test@x.org --out output/gold.csv
```
`output/` is gitignored — the gold CSV (answer text + reviewer emails) never reaches git.

## Layout
```
gold_standard/
  edit_analysis.py   # pure logic (draft detection + cosine edit-typing); unit-tested
  audit.py           # read-only orchestrator; exposes run()
  output/            # gitignored CSV + _embeddings/ cache
  README.md
# tests: toxtempass/tests/test_gold_standard_edit_analysis.py
# command: toxtempass/management/commands/extract_gold_answers.py
```
