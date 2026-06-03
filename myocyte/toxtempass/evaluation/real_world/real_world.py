"""Tier 3 (real-world) answer generation — wired into ``manage.py run_evals``.

Mirrors ``pcontrol.py``/``ncontrol.py``: a ``run(...)`` that loops each configured
model × each real-world assay bundle, reusing the *production* ``process_llm_async``
answering path, and writes one CSV per assay (``question, answer, not_found``) plus a
per-model summary JSON. Output is **experiment-scoped**
(``real_world/output/<experiment>/<model>[_tempT]/``) so prompt-strategy experiments
on the same model don't collide.

Run it via the management command::

    manage.py run_evals --skip-pcontrol --skip-ncontrol --experiment <name>
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import TextIO

import pandas as pd
from django.core.management.color import make_style
from tqdm.auto import tqdm

from toxtempass import Config as AppConfig
from toxtempass.evaluation.config import config as eval_config
from toxtempass.evaluation.real_world.answer_utils import parse_answer
from toxtempass.evaluation.utils import resolve_eval_llm, select_question_set
from toxtempass.filehandling import split_doc_dict_by_type, stringyfy_text_dict
from toxtempass.models import Answer, Question
from toxtempass.tests.fixtures.factories import AssayFactory, DocumentDictFactory
from toxtempass.views import process_llm_async

logger = logging.getLogger("llm")
style = make_style()

# Suffixes the app can ingest (lower-cased for matching).
_TEXT_SUFFIXES = {s.lower() for s in AppConfig.TEXT_ACCEPT_FILES}
_IMAGE_SUFFIXES = {s.lower() for s in AppConfig.IMAGE_ACCEPT_FILES}
_DESC_BINARY_SUFFIXES = {".pdf", ".docx"}  # description files needing real extraction


def read_description(assay_dir: Path) -> str:
    """Return the assay description text from ``<assay>/description/`` (any suffix).

    Description files here are plain text — including one extensionless file
    (OATP1C1) — so they are read directly. A .pdf/.docx description (none today)
    would need the file extractor; we log and skip rather than read it as bytes.
    """
    desc_dir = assay_dir / "description"
    if not desc_dir.is_dir():
        return ""
    files = [
        p for p in sorted(desc_dir.iterdir()) if p.is_file() and p.name != ".gitkeep"
    ]
    for p in files:
        if p.suffix.lower() in _DESC_BINARY_SUFFIXES:
            logger.warning("Description %s is a binary doc; skipping.", p)
            continue
        try:
            return p.read_text(encoding="utf-8", errors="replace").strip()
        except OSError as exc:
            logger.warning("Could not read description %s: %s", p, exc)
    return ""


def gather_input_files(
    assay_dir: Path, extract_images: bool, skip_folders: set[str] = frozenset()
) -> list[Path]:
    """All ingestible files in the bundle except the ``description/`` folder.

    The description is delivered via ``Assay.description`` instead, so excluding it
    here avoids feeding it twice. ``toxtemp/`` is intentionally NOT excluded — a
    user uploading an existing/related ToxTemp is a realistic scenario.
    ``skip_folders`` excludes additional subfolders (e.g. bulky ``raw_data``).
    """
    allowed = _TEXT_SUFFIXES | (_IMAGE_SUFFIXES if extract_images else set())
    excluded = {"description"} | set(skip_folders)
    files: list[Path] = []
    for p in sorted(assay_dir.rglob("*")):
        if not p.is_file() or p.name == ".gitkeep":
            continue
        if excluded & set(p.relative_to(assay_dir).parts):
            continue
        if p.suffix.lower() in allowed:
            files.append(p)
    return files


def assemble_context(doc_dict: dict, description: str) -> str:
    """Reconstruct the text context the model sees (description + documents).

    Uses the same helpers ``process_llm_async`` uses internally so the saved
    context matches what was answered against (pre-truncation).
    """
    text_dict, _ = split_doc_dict_by_type(doc_dict, decode=False)
    body = stringyfy_text_dict(text_dict)
    header = f"ASSAY DESCRIPTION: {description}\n\n" if description else ""
    return header + body


def _output_dir_name(model_name: str, temp: float | None) -> str:
    """Dir name includes the temperature unless it is a reasoning/omit model."""
    return f"{model_name}_temp{temp}" if temp is not None else model_name


def _completeness(rows: list[dict]) -> tuple[int, int, float]:
    """Return (answered, total, rate%) from answer rows."""
    total = len(rows)
    answered = sum(1 for r in rows if not r["not_found"])
    return answered, total, (round(100 * answered / total, 2) if total else 0.0)


def _count_empty(df: pd.DataFrame) -> int:
    """Count TRULY empty answers (blank text) in a saved CSV.

    A blank ``answer`` cell is the rate-limit / timeout / crash signature — the
    model produced nothing — and is distinct from a legitimate "not found" (which
    has prose or structured ``answerable:no`` content). ``retry_empty`` mode keys
    off this to re-run only the damaged (assay, model) combos.
    """
    return sum(1 for a in df.get("answer", pd.Series(dtype=str)) if not str(a).strip())


def _assay_record(
    assay_dir: Path,
    files: list[Path],
    description: str,
    answered: int,
    total: int,
    rate: float,
) -> dict:
    """Per-assay summary record incl. provenance of what was fed to the model."""
    return {
        "assay": assay_dir.name,
        "completeness_rate": rate,
        "answered": answered,
        "total": total,
        "n_input_files": len(files),
        "has_description": bool(description),
        "input_files": [str(f.relative_to(assay_dir)) for f in files],
    }


def run(
    question_set_label: str | None = None,
    repeat: bool = False,
    retry_empty: bool = False,
    input_dir: Path | None = None,
    output_base_dir: Path | None = None,
    experiment: str | None = None,
    stdout: TextIO | None = None,
) -> None:
    """Run the Tier 3 (real-world) pipeline for all configured models.

    Args:
        question_set_label: Optional QuestionSet label; defaults to latest visible.
        repeat: Re-generate every assay even if its CSV already exists.
        retry_empty: Re-generate only the (assay, model) combos whose existing CSV
            has blank answers (rate-limit/timeout damage); combos that are fully
            answered are cached. Ignored when ``repeat`` is set (which redoes all).
        input_dir: Tier 3 input root (per-assay bundles); defaults to config.
        output_base_dir: Tier 3 output base; defaults to config.
        experiment: Experiment name (from eval_config.experiments); selects models
            and the prompt strategy, and scopes the output directory.
        stdout: Stream for progress output (the management command's self.stdout).

    """
    if stdout is None:  # standalone/direct invocation fallback

        class _Out:
            def write(self, msg: str) -> None:
                print(msg)

        stdout = _Out()

    input_dir = input_dir or eval_config.real_world_input
    output_base_dir = output_base_dir or eval_config.real_world_output
    models = eval_config.get_models(tier=3, experiment=experiment)
    prompts = eval_config.get_prompts(experiment)
    base_prompt = prompts["base_prompt"]
    prompt_hash = eval_config.get_prompt_hash(experiment)
    extract_images = eval_config.get_extract_images(experiment)
    skip_folders = eval_config.get_skip_folders(experiment)
    only_assays = set(eval_config.get_assays(experiment))
    exp_name = experiment or "default"
    # Context is experiment-scoped: extract_images / skip_folders (and thus the
    # assembled context) can differ per experiment, so the faithfulness judge must
    # read this experiment's context, not whichever experiment ran first.
    context_dir = output_base_dir / exp_name / "_context"
    context_dir.mkdir(parents=True, exist_ok=True)

    assay_dirs = sorted([d for d in input_dir.iterdir() if d.is_dir()])
    if only_assays:
        assay_dirs = [d for d in assay_dirs if d.name in only_assays]
    if not assay_dirs:
        stdout.write(style.ERROR(f"No assay folders under {input_dir}."))
        return
    stdout.write(
        style.HTTP_INFO(
            f"Tier 3 [{exp_name}] — {len(assay_dirs)} assays × {len(models)} models "
            f"(extract_images={extract_images})."
        )
    )

    run_ts = datetime.now().strftime("%Y%m%d_%H%M")
    experiment_summary_path = output_base_dir / exp_name / f"tier3_summary_{run_ts}.json"
    exp_description = (
        eval_config.experiments.get(experiment, {}).get("description", "")
        if experiment else ""
    )
    per_model_results: list[dict] = []

    for model_config in models:
        model_name = model_config["name"]
        temp = model_config["temperature"]

        llm, info, llm_key = resolve_eval_llm(model_name, temp)
        if llm is None:
            stdout.write(style.ERROR(f"{info} — skipping."))
            continue
        # Per-endpoint concurrency: serialise models on a shared low-TPM endpoint
        # (llm_key is "<endpoint_index>:<tag>") so large-context requests don't
        # saturate its tokens-per-minute quota and livelock on 429s.
        ep_idx = (
            int(llm_key.split(":")[0]) if llm_key and ":" in llm_key else None
        )
        model_max_workers = (
            eval_config.endpoint_concurrency.get(ep_idx)
            if ep_idx is not None else None
        )
        workers_note = (
            f" [serialised: {model_max_workers} worker]" if model_max_workers else ""
        )
        stdout.write(
            style.SUCCESS(f"Using ({model_name}) via {info}.{workers_note}")
        )

        out_dir = output_base_dir / exp_name / _output_dir_name(model_name, temp)
        out_dir.mkdir(parents=True, exist_ok=True)

        records: list[dict] = []
        for assay_dir in tqdm(
            assay_dirs, desc=f"{exp_name}:{model_name}", position=0, leave=True
        ):
            assay_name = assay_dir.name
            csv_path = out_dir / f"tier3_answers_{assay_name}.csv"

            if csv_path.exists() and not repeat:
                df = pd.read_csv(csv_path).fillna("")
                n_empty = _count_empty(df)
                # retry_empty: regenerate ONLY combos that have blank answers (the
                # rate-limit/timeout damage); a clean CSV is still cached. Without
                # retry_empty, any existing CSV is cached (current behaviour).
                if retry_empty and n_empty:
                    stdout.write(
                        style.WARNING(
                            f"  {assay_name}: {n_empty} empty answer(s) — regenerating."
                        )
                    )
                else:
                    rows = [
                        {"not_found": parse_answer(a)["not_found"]}
                        for a in df.get("answer", pd.Series(dtype=str))
                    ]
                    answered, total, rate = _completeness(rows)
                    records.append(
                        _assay_record(
                            assay_dir,
                            gather_input_files(assay_dir, extract_images, skip_folders),
                            read_description(assay_dir),
                            answered, total, rate,
                        )
                    )
                    cached_note = (
                        "cached (0 empty)" if retry_empty else "cached (REPEAT off)"
                    )
                    stdout.write(style.NOTICE(f"  {assay_name}: {cached_note}."))
                    continue

            description = read_description(assay_dir)
            files = gather_input_files(assay_dir, extract_images, skip_folders)
            if not files and not description:
                stdout.write(
                    style.WARNING(f"  {assay_name}: no ingestible inputs — skipping.")
                )
                continue

            doc_dict = DocumentDictFactory(
                document_filenames=files,
                num_text=0,  # avoid the factory's dummy Faker-text padding
                num_bytes=0,
                extract_images=extract_images,
            )

            # Persist the assembled context once per assay (model-independent).
            ctx_path = context_dir / f"{assay_name}.txt"
            if not ctx_path.exists() or repeat:
                ctx_path.write_text(
                    assemble_context(doc_dict, description), encoding="utf-8"
                )

            question_set = select_question_set(question_set_label)
            assay = AssayFactory(
                title=assay_name, description=description, question_set=question_set
            )
            questions = Question.objects.filter(
                subsection__section__question_set=question_set
            ).order_by("answering_round", "id")
            for q in questions:
                Answer.objects.get_or_create(assay=assay, question=q)

            process_llm_async(
                assay.id,
                doc_dict,
                extract_images=extract_images,
                chatopenai=llm,
                verbose=True,
                base_prompt=base_prompt,
                llm_model=llm_key,  # use the model's own context window for truncation
                max_workers=model_max_workers,  # serialise low-TPM endpoints
            )

            answers = (
                Answer.objects.filter(assay=assay)
                .select_related("question__subsection__section")
                .order_by("question__answering_round", "question__id")
            )
            rows = []
            for a in answers:
                text = a.answer_text or ""
                q = a.question
                rows.append(
                    {
                        "question_id": q.id,
                        "section": q.subsection.section.title,
                        "subsection": q.subsection.title,
                        "question": q.question_text,
                        "answer": text,
                        "not_found": parse_answer(text)["not_found"],
                    }
                )
            pd.DataFrame(
                rows,
                columns=[
                    "question_id", "section", "subsection",
                    "question", "answer", "not_found",
                ],
            ).to_csv(csv_path, index=False)
            answered, total, rate = _completeness(rows)
            records.append(
                _assay_record(assay_dir, files, description, answered, total, rate)
            )
            stdout.write(style.SUCCESS(f"  {assay_name}: {rate}% ({answered}/{total})"))

        # Accumulate this model's results into the experiment-level summary and
        # (re)write it after every model, so the experiment summary is current even
        # if the run is interrupted partway through the model list.
        mean_completeness = (
            round(sum(r["completeness_rate"] for r in records) / len(records), 2)
            if records else 0.0
        )
        per_model_results.append(
            {
                "model": model_name,
                "temperature": temp,
                "output_dir": _output_dir_name(model_name, temp),
                "mean_completeness_rate": mean_completeness,
                "records": records,
            }
        )
        experiment_summary = {
            "timestamp": run_ts,
            "tier": 3,
            "experiment": experiment,
            "description": exp_description,
            "extract_images": extract_images,
            "prompt_hash": prompt_hash,
            "prompts": {
                "base_prompt": base_prompt,
                "image_prompt": prompts["image_prompt"],
            },
            "models": [r["output_dir"] for r in per_model_results],
            "results": per_model_results,
        }
        experiment_summary_path.write_text(
            json.dumps(experiment_summary, indent=2), encoding="utf-8"
        )
        stdout.write(
            style.SUCCESS(
                f"Tier 3 [{exp_name}] {model_name}: {mean_completeness}% mean "
                f"completeness; summary → {experiment_summary_path.name}"
            )
        )

    stdout.write(style.SUCCESS(f"Tier 3 [{exp_name}] complete."))
