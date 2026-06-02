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


def gather_input_files(assay_dir: Path, extract_images: bool) -> list[Path]:
    """All ingestible files in the bundle except the ``description/`` folder.

    The description is delivered via ``Assay.description`` instead, so excluding it
    here avoids feeding it twice. ``toxtemp/`` is intentionally NOT excluded — a
    user uploading an existing/related ToxTemp is a realistic scenario.
    """
    allowed = _TEXT_SUFFIXES | (_IMAGE_SUFFIXES if extract_images else set())
    files: list[Path] = []
    for p in sorted(assay_dir.rglob("*")):
        if not p.is_file() or p.name == ".gitkeep":
            continue
        if "description" in set(p.relative_to(assay_dir).parts):
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


def run(
    question_set_label: str | None = None,
    repeat: bool = False,
    input_dir: Path | None = None,
    output_base_dir: Path | None = None,
    experiment: str | None = None,
    stdout: TextIO | None = None,
) -> None:
    """Run the Tier 3 (real-world) pipeline for all configured models.

    Args:
        question_set_label: Optional QuestionSet label; defaults to latest visible.
        repeat: Re-generate even if an assay's CSV already exists.
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
    exp_name = experiment or "default"
    # Context is experiment-scoped: extract_images (and thus the assembled context)
    # can differ per experiment, so the faithfulness judge must read this
    # experiment's context, not whichever experiment happened to run first.
    context_dir = output_base_dir / exp_name / "_context"
    context_dir.mkdir(parents=True, exist_ok=True)

    assay_dirs = sorted([d for d in input_dir.iterdir() if d.is_dir()])
    if not assay_dirs:
        stdout.write(style.ERROR(f"No assay folders under {input_dir}."))
        return
    stdout.write(
        style.HTTP_INFO(
            f"Tier 3 [{exp_name}] — {len(assay_dirs)} assays × {len(models)} models "
            f"(extract_images={extract_images})."
        )
    )

    for model_config in models:
        model_name = model_config["name"]
        temp = model_config["temperature"]

        llm, info, llm_key = resolve_eval_llm(model_name, temp)
        if llm is None:
            stdout.write(style.ERROR(f"{info} — skipping."))
            continue
        stdout.write(style.SUCCESS(f"Using ({model_name}) via {info}."))

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
                rows = [
                    {"not_found": parse_answer(a)["not_found"]}
                    for a in df.get("answer", pd.Series(dtype=str))
                ]
                answered, total, rate = _completeness(rows)
                records.append(
                    {
                        "assay": assay_name,
                        "completeness_rate": rate,
                        "answered": answered,
                        "total": total,
                    }
                )
                stdout.write(style.NOTICE(f"  {assay_name}: cached (REPEAT off)."))
                continue

            description = read_description(assay_dir)
            files = gather_input_files(assay_dir, extract_images)
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
            )

            answers = (
                Answer.objects.filter(assay=assay)
                .select_related("question")
                .order_by("question__answering_round", "question__id")
            )
            rows = []
            for a in answers:
                text = a.answer_text or ""
                rows.append(
                    {
                        "question": a.question.question_text,
                        "answer": text,
                        "not_found": parse_answer(text)["not_found"],
                    }
                )
            pd.DataFrame(rows, columns=["question", "answer", "not_found"]).to_csv(
                csv_path, index=False
            )
            answered, total, rate = _completeness(rows)
            records.append(
                {
                    "assay": assay_name,
                    "completeness_rate": rate,
                    "answered": answered,
                    "total": total,
                }
            )
            stdout.write(style.SUCCESS(f"  {assay_name}: {rate}% ({answered}/{total})"))

        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        summary = {
            "timestamp": timestamp,
            "tier": 3,
            "experiment": experiment,
            "model": model_name,
            "temperature": temp,
            "extract_images": extract_images,
            "prompt_hash": prompt_hash,
            "prompts": {
                "base_prompt": base_prompt,
                "image_prompt": prompts["image_prompt"],
            },
            "records": records,
        }
        (out_dir / f"tier3_summary_{timestamp}.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        stdout.write(
            style.SUCCESS(f"Tier 3 [{exp_name}] {model_name}: summary → {out_dir}")
        )

    stdout.write(style.SUCCESS(f"Tier 3 [{exp_name}] complete."))
