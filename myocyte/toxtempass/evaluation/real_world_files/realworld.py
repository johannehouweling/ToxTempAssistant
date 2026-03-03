# tier 3
# to only run tier 3 exp put in experiment command <--skip-ncontrol --skip-pcontrol> at the end
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import TextIO

import pandas as pd
from django.core.management.color import make_style
from langchain_openai import ChatOpenAI
from toxtempass import LLM_API_KEY, LLM_ENDPOINT, config
from toxtempass.evaluation.config import config as eval_config
from toxtempass.evaluation.post_processing.utils import has_answer_not_found
from toxtempass.evaluation.utils import select_question_set
from toxtempass.models import Answer, Question
from toxtempass.tests.fixtures.factories import AssayFactory, DocumentDictFactory
from toxtempass.views import process_llm_async
from tqdm.auto import tqdm

logger = logging.getLogger("llm")

style = make_style()

_FILE_PATTERNS = ["*.pdf", "*.docx", "*.xlsx", "*.txt", "*.pptx"]


def _iter_realworld_files(input_dir: Path) -> list[Path]:
    files: list[Path] = []
    for pat in _FILE_PATTERNS:
        files.extend(Path(input_dir).rglob(pat))
    return sorted(files)


def _iter_single_docs(input_dir: Path) -> list[tuple[str, str, Path]]:
    """Return (assay_name, doc_type, file_path) for each document file.
    Expected structure: input_dir/<assay>/<doc_type>/<file>
    Files placed directly under <assay> get doc_type "unknown".
    """
    result = []
    for fp in _iter_realworld_files(input_dir):
        parts = fp.relative_to(input_dir).parts
        result.append((parts[0], parts[1] if len(parts) > 2 else "unknown", fp))
    return result


def _iter_combined_assays(input_dir: Path) -> list[tuple[str, list[Path]]]:
    """Return (assay_name, [all_files]) for each top-level assay folder."""
    return [
        (d.name, files)
        for d in sorted(Path(input_dir).iterdir())
        if d.is_dir() and (files := _iter_realworld_files(d))
    ]


def _infer(
    doc_filenames: list[str],
    assay_title: str,
    question_set_label: str | None,
    experiment: str | None,
    llm: ChatOpenAI | None,
) -> list:
    """Run LLM inference for one unit (single doc or combined assay).
    Returns Answer list.
    """
    input_doc_dict = DocumentDictFactory(
        document_filenames=doc_filenames,
        num_bytes=0,
        extract_images=eval_config.get_extract_images(experiment),
    )
    question_set = select_question_set(question_set_label)
    assay = AssayFactory(title=assay_title, description="", question_set=question_set)
    questions = Question.objects.filter(
        subsection__section__question_set=question_set
    ).order_by("answering_round", "id")
    for q in questions:
        Answer.objects.get_or_create(assay=assay, question=q)
    process_llm_async(
        assay.id,
        input_doc_dict,
        extract_images=eval_config.get_extract_images(experiment),
        chatopenai=llm,
        verbose=True,
    )
    return list(Answer.objects.filter(assay=assay).select_related("question"))


def _process_answers(answers: list) -> tuple[pd.DataFrame, list[dict]]:
    """Build a DataFrame and failures list from Answer objects."""
    rows = []
    for a in answers:
        answer_text = a.answer_text or " "
        rows.append({
            "qID": a.question.id,
            "question": a.question.question_text,
            "llm_answer": answer_text,
            "is_empty": (not answer_text.strip()),
            "is_not_found": has_answer_not_found(answer_text) if answer_text else True,
            "answer_len": len(answer_text.strip()),
        })
    failures = [
        {"question_id": a.question.id, "question_text": a.question.question_text,
         "answer_text": a.answer_text}
        for a in answers
        if not a.answer_text or has_answer_not_found(a.answer_text)
    ]
    return pd.DataFrame(rows), failures


def _build_record(
    df: pd.DataFrame,
    failures: list[dict],
    *,
    run_mode: str,
    assay: str,
    doc_type: str,
    file: str,
    file_type: str,
    answer_csv: Path,
) -> dict:
    n = int(df.shape[0])
    passes = int(((~df["is_empty"]) & (~df["is_not_found"])).sum())
    return {
        "run_mode": run_mode,
        "assay": assay,
        "doc_type": doc_type,
        "file": file,
        "file_type": file_type,
        "total": n,
        "passes": passes,
        "n_not_found": int(df["is_not_found"].sum()),
        "completeness": (passes / n * 100.0) if n else 0.0,
        "failures": failures,
        "answer_len_mean": float(df["answer_len"].mean()) if n else 0.0,
        "answer_len_median": float(df["answer_len"].median()) if n else 0.0,
        "answer_csv": str(answer_csv),
    }


def _run_single_docs(
    input_dir: Path,
    model_output_dir: Path,
    llm: ChatOpenAI | None,
    model_name: str,
    question_set_label: str | None,
    experiment: str | None,
    repeat: bool,
    stdout: TextIO,
) -> list[dict]:
    """Run LLM on each document independently. Returns list of records."""
    single_docs = _iter_single_docs(input_dir)
    if not single_docs:
        stdout.write(style.ERROR(f"No input files found in {input_dir}"))
        return []

    records = []
    for assay_name, doc_type, doc_path in tqdm(
        single_docs, desc=f"single-doc ({model_name})", position=0, leave=True
    ):
        out_dir = model_output_dir / assay_name / doc_type
        out_dir.mkdir(parents=True, exist_ok=True)
        answer_csv = out_dir / f"tier3_answers_{doc_path.stem}.csv"
        if answer_csv.exists() and not repeat:
            stdout.write(
                f"Skipping {assay_name}/{doc_type}/{doc_path.name} (output exists)"
            )
            continue

        answers = _infer(
            [str(doc_path)],
            f"{assay_name}/{doc_type}/{doc_path.name}",
            question_set_label, experiment, llm,
        )
        df, failures = _process_answers(answers)
        df.to_csv(answer_csv, index=False)
        record = _build_record(
            df, failures, run_mode="single", assay=assay_name, doc_type=doc_type,
            file=doc_path.name, file_type=doc_path.suffix.lower(), answer_csv=answer_csv,
        )
        records.append(record)
        stdout.write(style.SUCCESS(
            f"{assay_name}/{doc_type}/{doc_path.name}: {record['completeness']:.1f}%"
        ))
    return records


def _run_combined(
    input_dir: Path,
    model_output_dir: Path,
    llm: ChatOpenAI | None,
    model_name: str,
    question_set_label: str | None,
    experiment: str | None,
    repeat: bool,
    stdout: TextIO,
) -> list[dict]:
    """Run LLM on all documents per assay combined. Returns list of records."""
    combined_assays = _iter_combined_assays(input_dir)
    if not combined_assays:
        stdout.write(style.ERROR(f"No assay folders found in {input_dir}"))
        return []

    records = []
    for assay_name, assay_files in tqdm(
        combined_assays, desc=f"combined ({model_name})", position=0, leave=True
    ):
        out_dir = model_output_dir / assay_name / "combined"
        out_dir.mkdir(parents=True, exist_ok=True)
        answer_csv = out_dir / "tier3_answers_combined.csv"
        if answer_csv.exists() and not repeat:
            stdout.write(f"Skipping {assay_name}/combined (output exists)")
            continue

        answers = _infer(
            [str(f) for f in assay_files],
            f"{assay_name}/combined",
            question_set_label, experiment, llm,
        )
        df, failures = _process_answers(answers)
        df.to_csv(answer_csv, index=False)
        record = _build_record(
            df, failures, run_mode="combined", assay=assay_name, doc_type="combined",
            file=f"{len(assay_files)} files", file_type="mixed", answer_csv=answer_csv,
        )
        records.append(record)
        stdout.write(style.SUCCESS(
            f"{assay_name}/combined: {record['completeness']:.1f}%"
        ))
    return records


def run(
    question_set_label: str | None = None,
    repeat: bool = False,
    input_dir: Path | None = None,
    output_base_dir: Path | None = None,
    experiment: str | None = None,
    mode: str = "both",
    stdout: TextIO | None = None,
) -> None:
    """Run Tier3 pipeline for all configured models.
    Args:
        question_set_label: Optional QuestionSet label to use
        repeat: Re-run even if output already exists
        input_dir: Tier3 input directory (contains assay subfolders)
        output_base_dir: Tier3 output base directory
        experiment: Name of experiment configuration to use (from eval_config.experiments)
        mode: "single" (one doc at a time), "combined" (all assay docs together),
              or "both" (run single then combined)
        stdout: Output stream for progress and status messages.
    """
    stdout.write(eval_config.summarize_experiment_config(experiment=experiment))

    input_dir = input_dir or eval_config.realworld_input
    output_base_dir = output_base_dir or eval_config.realworld_output
    models = eval_config.get_models(tier=3, experiment=experiment)
    prompts = eval_config.get_prompts(experiment)
    prompt_hash = eval_config.get_prompt_hash(experiment)

    for model_config in models:
        model_name = model_config["name"]
        temp = model_config["temperature"]

        if LLM_API_KEY and LLM_ENDPOINT:
            llm = ChatOpenAI(
                api_key=LLM_API_KEY, base_url=config.url, temperature=temp,
                model=model_name, default_headers=config.extra_headers,
            )
            stdout.write(style.SUCCESS(
                f"Using ({model_name}) at {LLM_ENDPOINT} with temperature={temp}."
            ))
        else:
            stdout.write(style.ERROR("Required environment variables are missing"))
            llm = None

        model_output_dir = output_base_dir / (
            f"{model_name}_temp{temp}" if temp is not None else model_name
        )
        model_output_dir.mkdir(parents=True, exist_ok=True)

        shared = dict(
            input_dir=input_dir, model_output_dir=model_output_dir, llm=llm,
            model_name=model_name, question_set_label=question_set_label,
            experiment=experiment, repeat=repeat, stdout=stdout,
        )
        records = []
        if mode in ("single", "both"):
            records.extend(_run_single_docs(**shared))
        if mode in ("combined", "both"):
            records.extend(_run_combined(**shared))

        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        output_file = model_output_dir / f"tier3_summary_{timestamp}.json"
        summary = {
            "timestamp": timestamp, "experiment": experiment, "mode": mode,
            "model": model_name, "temperature": temp, "prompt_hash": prompt_hash,
            "prompts": {"base_prompt": prompts["base_prompt"],
                        "image_prompt": prompts["image_prompt"]},
            "records": records,
        }
        with open(output_file, "w", encoding="utf-8") as out_f:
            json.dump(summary, out_f, indent=2)
        stdout.write(style.SUCCESS(f"Realworld results saved to {output_file}."))