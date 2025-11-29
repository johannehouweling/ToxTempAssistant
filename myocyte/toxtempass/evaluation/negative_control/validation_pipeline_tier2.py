import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from django.core.exceptions import ObjectDoesNotExist
from langchain_openai import ChatOpenAI

# Ensure project root is on PYTHONPATH so 'toxtempass' imports work
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from toxtempass import LLM_API_KEY, LLM_ENDPOINT, config
from toxtempass.evaluation.config import config as eval_config
from toxtempass.tests.fixtures.factories import AssayFactory, DocumentDictFactory
from toxtempass.models import Answer, Question, QuestionSet
from toxtempass.evaluation.post_processing.utils import has_answer_not_found
from toxtempass.views import process_llm_async

# different test cases

# Tier 1: Positive Control
# input_tier1 = Path("/Users/johannehouweling/ToxTempAssistant/myocyte/toxtempass/validation/validation_documents/tier1_positive").glob("*.pdf")

# Get logger
logger = logging.getLogger("llm")


def select_question_set(label: str | None = None) -> QuestionSet:
    """Pick the question set by label or fallback to latest visible."""
    if label:
        try:
            return QuestionSet.objects.get(label=label)
        except ObjectDoesNotExist as exc:
            raise ValueError(f"QuestionSet with label '{label}' not found") from exc

    qs = QuestionSet.objects.filter(is_visible=True).order_by("-created_at").first()
    if not qs:
        raise ValueError("No visible QuestionSet found; cannot run evaluation.")
    return qs


def run(
    question_set_label: str | None = None,
    repeat: bool = False,
    input_dir: Path | None = None,
    output_base_dir: Path | None = None,
    experiment: str | None = None,
) -> None:
    """Run Tier2 pipeline for all configured models.
    
    Args:
        question_set_label: Optional QuestionSet label to use
        repeat: Re-run even if output already exists for a model
        input_dir: Tier2 input PDF directory
        output_base_dir: Tier2 output base directory
        experiment: Name of experiment configuration to use (from eval_config.experiments)
    """
    llm = None
    # Use config paths with optional overrides
    input_dir = input_dir or eval_config.tier2_input
    output_base_dir = output_base_dir or eval_config.tier2_output
    
    # Get model configurations from centralized config
    models = eval_config.get_models(tier=2, experiment=experiment)
    
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
            logger.info(f"Using ({model_name}) at {LLM_ENDPOINT} with temperature={temp}.")
        else:
            logger.error("Required environment variables are missing")

        files_tier2 = list(input_dir.glob("*.pdf"))
        
        # Create output directory name that includes temperature for experiments
        if temp is not None:
            output_dir_name = f"{model_name}_temp{temp}"
        else:
            output_dir_name = model_name
        output_tier2 = output_base_dir / output_dir_name
        if output_tier2.exists() and not repeat:
            continue

        input_tier2_dict = DocumentDictFactory(
            document_filenames=files_tier2, num_bytes=0
        )

        records = []

        for document_name in input_tier2_dict:
            pdf_file = Path(document_name).name
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
                    for key, value in input_tier2_dict.items()
                    if document_name in key
                },
                extract_images=eval_config.extract_images,
                chatopenai=llm,
            )
            print(f"Success: {assay.status}")
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
                if not has_answer_not_found(a.answer_text)
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
            print(f"{pdf_file}: {pass_rate}%")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        output_file = output_tier2 / f"tier2_summary_{timestamp}.json"
        output_folder = output_file.parent
        if not output_folder.exists():
            output_folder.mkdir(parents=True)
        with open(output_file, "w", encoding="utf-8") as out_f:
            json.dump({"timestamp": timestamp, "records": records}, out_f, indent=2)
        print(f"Tier 2 results saved to {output_file}")
