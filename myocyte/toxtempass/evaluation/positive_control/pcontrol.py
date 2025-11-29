import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from tqdm.auto import tqdm

# Ensure project root is on PYTHONPATH so 'toxtempass' imports work
PROJECT_ROOT = Path("/Users/johannehouweling/ToxTempAssistant/myocyte")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import logging

from langchain_openai import ChatOpenAI

from toxtempass import LLM_API_KEY, LLM_ENDPOINT, config
from toxtempass.evaluation.config import config as eval_config
from toxtempass.evaluation.post_processing.utils import (
    generate_comparison_csv,
    has_answer_not_found,
)
from toxtempass.evaluation.utils import select_question_set
from toxtempass.models import Answer, Question
from toxtempass.tests.fixtures.factories import AssayFactory, DocumentDictFactory
from toxtempass.views import process_llm_async

logger = logging.getLogger("llm")


def run(
    question_set_label: str | None = None,
    repeat: bool = False,
    processed_scored_dir: Path | None = None,
    raw_dir: Path | None = None,
    output_base_dir: Path | None = None,
    experiment: str | None = None,
) -> None:
    """Run Tier1 pipeline for all configured models.

    Args:
        question_set_label: Optional QuestionSet label to use
        repeat: Re-run even if output already exists for a model
        processed_scored_dir: Tier1 processed/scored JSON directory
        raw_dir: Tier1 raw PDF directory
        output_base_dir: Tier1 output base directory
        experiment: Name of experiment configuration to use (from eval_config.experiments)
    """
    llm = None
    # Use config paths with optional overrides
    processed_scored_dir = processed_scored_dir or eval_config.pcontrol_processed_input
    raw_dir = raw_dir or eval_config.pcontrol_input
    output_base_dir = output_base_dir or eval_config.pcontrol_output

    # Get model configurations from centralized config
    models = eval_config.get_models(tier=1, experiment=experiment)

    # Get prompt configuration for this experiment
    prompts = eval_config.get_prompts(experiment)
    prompt_hash = eval_config.get_prompt_hash(experiment)

    for model_config in models:
        model_name = model_config["name"]
        temp = model_config["temperature"]
        if LLM_API_KEY and LLM_ENDPOINT:
            llm = ChatOpenAI(
                api_key=LLM_API_KEY,
                base_url=config.url,
                temperature=temp,
                model=model_name,
                default_headers=config.extra_headers,
            )
            logger.info(
                f"Using ({model_name}) at {LLM_ENDPOINT} with temperature={temp}."
            )
        else:
            logger.error("Required environment variables are missing")

        gtruth_jsons = processed_scored_dir.glob("*.json")
        gtruth_pdfs = raw_dir.glob("*.pdf")

        # Create output directory name that includes temperature for experiments
        if temp is not None:
            output_dir_name = f"{model_name}_temp{temp}"
        else:
            output_dir_name = model_name
        output_tier1 = output_base_dir / output_dir_name
        if not output_tier1.exists():
            output_tier1.mkdir(parents=True)
        output_summary = list(output_tier1.glob("tier1_summary*.json"))
        if output_summary and not repeat:
            continue

        pdf_by_stem = {pdf.stem: pdf for pdf in gtruth_pdfs}

        json_pdf_dict = {
            json_path: pdf_by_stem[json_path.stem]
            for json_path in gtruth_jsons
            if json_path.stem in pdf_by_stem
        }

        records = []

        for json_file, pdf_file_path in tqdm(
            json_pdf_dict.items(), desc="Processing files"
        ):
            pdf_file = pdf_file_path.name
            input_pdf_dict = DocumentDictFactory(
                document_filenames=[pdf_file_path], num_bytes=0
            )
            question_set = select_question_set(question_set_label)
            assay = AssayFactory(
                title=pdf_file, description="", question_set=question_set
            )
            questions = Question.objects.filter(
                subsection__section__question_set=question_set
            ).order_by("answering_round", "id")
            for q in questions:
                Answer.objects.get_or_create(assay=assay, question=q)

            process_llm_async(
                assay.id,
                input_pdf_dict,
                extract_images=eval_config.get_extract_images(experiment),
                chatopenai=llm,
            )
            print(f"Success: {assay.status}")

            answers = Answer.objects.filter(assay=assay)
            df = generate_comparison_csv(
                json_file, answers, output_tier1, pdf_file, model=llm, overwrite=False
            )

            total = int(df[df["gtruth_answer"] != ""].dropna().shape[0])
            passed_mask = (
                (df["gtruth_answer"] != "").astype(bool)
                & df["gtruth_answer"].notna()
                & df["llm_answer"].notna()
                & df["llm_answer"].astype(bool)
                & ~df["llm_answer"].apply(has_answer_not_found)
            )
            df_passed = df[passed_mask]
            df_passed["db_qid"] = df_passed["question"].apply(
                lambda x: str(Question.objects.get(question_text=x).id)
                if Question.objects.filter(question_text=x).exists()
                else pd.NA
            )
            passes = df_passed.shape[0]
            pass_rate = float(passes) / total * 100 if total > 0 else 0.0
            failures = [
                {
                    "question_id": a.question.id,
                    "question_text": a.question.question_text,
                    "answer_text": a.answer_text,
                }
                for a in answers
                if not a.answer_text or has_answer_not_found(a.answer_text)
            ]
            metrics = eval_config.validation_metrics
            agg_stats = (
                df_passed[metrics].agg(["mean", "std", "min", "max", "median"]).to_dict()
            )

            for m in metrics:
                agg_stats[m]["percent_above_threshold"] = float(
                    (df_passed[m] > eval_config.cos_similarity_threshold).mean()
                )
            records.append(
                {
                    "file": pdf_file,
                    "passes": passes,
                    "total": total,
                    "pass_rate": pass_rate,
                    "failures": failures,
                    "stats": agg_stats,
                }
            )
            print(f"{pdf_file}: {pass_rate}%")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        output_file = output_tier1 / f"tier1_summary_{timestamp}.json"

        # Build summary with experiment metadata
        summary = {
            "timestamp": timestamp,
            "experiment": experiment,
            "model": model_name,
            "temperature": temp,
            "prompt_hash": prompt_hash,
            "prompts": {
                "base_prompt": prompts["base_prompt"],
                "image_prompt": prompts["image_prompt"],
            },
            "records": records,
        }

        with output_file.open("w", encoding="utf-8") as out_f:
            json.dump(summary, out_f, indent=2)
        print(f"Tier 1 results saved to {output_file}")
