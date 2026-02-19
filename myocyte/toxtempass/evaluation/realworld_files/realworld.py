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
from toxtempass.evaluation.post_processing.utils import (
    generate_comparison_csv,
    has_answer_not_found,
)
from toxtempass.evaluation.utils import select_question_set
from toxtempass.models import Answer, Question
from toxtempass.tests.fixtures.factories import AssayFactory, DocumentDictFactory
from toxtempass.views import process_llm_async
from tqdm.auto import tqdm

logger = logging.getLogger("llm")

style = make_style()


def run(
    question_set_label: str | None = None,
    repeat: bool = False,
    input_dir: Path | None = None,
    output_base_dir: Path | None = None,
    experiment: str | None = None,
    stdout: TextIO | None = None,
) -> None:
    """Run Tier3 pipeline for all configured models.

    Args:
        question_set_label: Optional QuestionSet label to use
        repeat: Re-run even if output already exists for a model
        input_dir: Tier3 input PDF directory
        output_base_dir: Tier3 output base directory
        experiment: Name of experiment configuration to use (from eval_config.experiments)
    """
    stdout.write(eval_config.summarize_experiment_config(experiment=experiment))
    llm = None
    # Use config paths with optional overrides
    input_dir = input_dir or eval_config.realworld_input
    output_base_dir = output_base_dir or eval_config.realworld_output

    # Get model configurations from centralized config
    models = eval_config.get_models(tier=3, experiment=experiment)

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
            stdout.write(
                style.SUCCESS(
                    f"Using ({model_name}) at {LLM_ENDPOINT} with temperature={temp}."
                )
            )
        else:
            stdout.write(style.ERROR("Required environment variables are missing"))

        files_tier3 = list(input_dir.glob("*.pdf" or "*.docx"))

        # Create output directory name that includes temperature for experiments
        if temp is not None:
            output_dir_name = f"{model_name}_temp{temp}"
        else:
            output_dir_name = model_name
        output_tier3 = output_base_dir / output_dir_name
        if not output_tier3.exists():
            output_tier3.mkdir(parents=True)
        output_summary_tier3 = list(output_tier3.glob("tier3_summary*.json"))
        if output_summary_tier3 and not repeat:
            continue

        input_tier3_dict = DocumentDictFactory(
            document_filenames=files_tier3,
            num_bytes=0,
            extract_images=eval_config.get_extract_images(experiment),
        )

        records = []

        for document_name in tqdm(
            input_tier3_dict, desc="realworld documents", position=0, leave=True
        ):
            pdf_file = Path(document_name).name
            input_pdf_dict = DocumentDictFactory(
                document_filenames=[document_name],
                num_bytes=0,
                extract_images=eval_config.get_extract_images(experiment),
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
                {
                    key: value
                    for key, value in input_tier3_dict.items()
                    if document_name in key
                },
                extract_images=eval_config.get_extract_images(experiment),
                chatopenai=llm,
                verbose=True
            )
            answers = Answer.objects.filter(assay=assay)
            total = answers.count()
            passes = sum(1 for a in answers if has_answer_not_found(a.answer_text))
            pass_rate = round(100 * passes / total, 2) if total else 0.0
            failures = [
                {
                    "question_id": a.question.id,
                    "question_text": a.question.question_text,
                    "answer_text": a.answer_text,
                }
                for a in answers
                if has_answer_not_found(a.answer_text)
            ]
            records.append(
                {
                    "file": pdf_file,
                    "passes": passes,
                    "total": total,
                    "pass_rate": pass_rate,
                    "failures": failures,
                }
            )
            stdout.write(style.SUCCESS(f"{pdf_file}: {pass_rate}%"))

        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        output_file = output_tier3 / f"tier3_summary_{timestamp}.json"
        output_folder = output_file.parent
        if not output_folder.exists():
            output_folder.mkdir(parents=True)

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

        with open(output_file, "w", encoding="utf-8") as out_f:
            json.dump(summary, out_f, indent=2)
        stdout.write(style.SUCCESS(f"Realworld results saved to {output_file}."))