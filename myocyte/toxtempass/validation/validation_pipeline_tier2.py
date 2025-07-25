import json
import os
import sys
from datetime import datetime
from pathlib import Path
import logging
from langchain_openai import ChatOpenAI

# Ensure project root is on PYTHONPATH so 'toxtempass' imports work
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# --- Section: Django Environment Setup ---
# Ensures Django settings are loaded so ORM calls work in this standalone script.
def setup_django():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myocyte.settings")
    import django

    django.setup()


setup_django()

from toxtempass import config, LLM_API_KEY, LLM_ENDPOINT
from toxtempass.validation.utils import has_answer_not_found
from toxtempass.fixtures.factories import AssayFactory, DocumentDictFactory
from toxtempass.models import Answer, Question
from toxtempass.views import process_llm_async

# different test cases

# Tier 1: Positive Control
# input_tier1 = Path("/Users/johannehouweling/ToxTempAssistant/myocyte/toxtempass/validation/validation_documents/tier1_positive").glob("*.pdf")

# Get logger
logger = logging.getLogger("llm")

# Initialize language models based on environment variables
llm = None
repeat = False # set to True if you want to repeat the analysis for all models
def_temp = config.temperature
for model,temp in zip(["gpt-4o", "gpt-4.1-nano", "o3-mini"], [def_temp, def_temp, None], strict=True):

    if LLM_API_KEY and LLM_ENDPOINT:
        llm = ChatOpenAI(
            api_key=LLM_API_KEY,
            base_url=config.url,
            temperature=temp,
            model=model,
            default_headers=config.extra_headers,
            # base_url=config.url,
        )
        logger.info(f"Using ({model}) at {LLM_ENDPOINT}.")
    else:
        logger.error("Required environment variables are missing")



    # Tier 2: Negative Control
    files_tier2 = list(
        Path("/Users/johannehouweling/Desktop/ToxTempAssistant_Validation/Tier2").glob(
            "*.pdf"
        )
    )
    output_tier2 = Path(
        f"/Users/johannehouweling/Desktop/ToxTempAssistant_Validation/Tier2_results/{model}/"
    )
    if output_tier2.exists():
        #print(f"{output_tier2.name:s} exists, sure you want to repeat the analysis for {model}?")
        if repeat:
            pass
        else:
            continue

    # no images
    input_tier2_dict = DocumentDictFactory(document_filenames=files_tier2, num_bytes=0)

    records = []

    for document_name in input_tier2_dict:
        pdf_file = Path(document_name).name
        assay = AssayFactory(title=pdf_file, description="")
        # 1) Seed one blank Answer per Question, in the app done via AssayAnswerForm.save()
        questions = Question.objects.order_by("id")
        for q in questions:
            Answer.objects.get_or_create(assay=assay, question=q)
        # 2) Call LLM
        process_llm_async(
            assay.id,
            {key: value for key, value in input_tier2_dict.items() if document_name in key},
            chatopenai=llm,
        )
        print(f"Success: {assay.status}")
        # 4) Retrieve generated answers for this specific assay
        answers = Answer.objects.filter(assay=assay)
        total = answers.count()
        # 5) Compute refusal pass rate for this assay
        passes = sum(1 for a in answers if has_answer_not_found(a.answer_text))
        pass_rate = round(100 * passes / total, 2) if total else 0.0
        # 5a) Capture detailed failure info for this assay
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

    # 6) Save summary results to JSON with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    output_file = output_tier2 / f"tier2_summary_{timestamp}.json"
    output_folder = output_file.parent
    if not output_folder.exists():
        output_folder.mkdir(parents=True)
    with open(output_file, "w", encoding="utf-8") as out_f:
        json.dump({"timestamp": timestamp, "records": records}, out_f, indent=2)
    print(f"Tier 2 results saved to {output_file}")
