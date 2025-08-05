import json
import os
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


# --- Section: Django Environment Setup ---
# Ensures Django settings are loaded so ORM calls work in this standalone script.
def setup_django():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myocyte.settings")
    import django
    django.setup()


setup_django()

from toxtempass import config, LLM_API_KEY, LLM_ENDPOINT
from toxtempass.fixtures.factories import AssayFactory, DocumentDictFactory
from toxtempass.models import Answer, Question, Assay
from toxtempass.views import process_llm_async
from toxtempass.validation.utils import has_answer_not_found, generate_comparison_csv
import logging
from langchain_openai import ChatOpenAI

logger = logging.getLogger("llm")


llm = None
repeat = False
def_temp = config.temperature
for model, temp in zip(
    ["gpt-4o-mini","gpt-4.1-nano","o3-mini"],
    [0,0, None],
    strict=True,
):
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

    # get a json with question answers pairs ground truth
    # get a pdf that is the source of grond trutht to run through toxtempass and generate
    # answers, then we have to compare both for semantiv similarity

    gtruth_jsons = Path(
        "/Users/johannehouweling/Desktop/ToxTempAssistant_Validation/Tier1/processed/scored/"
    ).glob("*.json")
    gtruth_pdfs = Path(
        "/Users/johannehouweling/Desktop/ToxTempAssistant_Validation/Tier1/raw/"
    ).glob("*.pdf")
    output_tier1 = Path(
        f"/Users/johannehouweling/Desktop/ToxTempAssistant_Validation/Tier1_results/{model}"
    )
    output_summary = list(output_tier1.glob("tier1_summary*.json"))
    if output_summary:
        # print(f"{output_tier2.name:s} exists, sure you want to repeat the analysis for {model}?")
        if repeat:
            pass
        else:
            continue
    # 1) build a stem → pdf lookup
    pdf_by_stem = {pdf.stem: pdf for pdf in gtruth_pdfs}

    # 2) map each json to its matching pdf (if any)
    json_pdf_dict = {
        json_path: pdf_by_stem[json_path.stem]
        for json_path in gtruth_jsons
        if json_path.stem in pdf_by_stem
    }

    records = []

    for json_file, pdf_file_path in tqdm(
        json_pdf_dict.items(), desc="Processing files"
    ):

        # if pdf_file_path.name != "NPC2-5.pdf":
        #     continue
        pdf_file = pdf_file_path.name
        input_pdf_dict = DocumentDictFactory(
            document_filenames=[pdf_file_path], num_bytes=0
        )
        assay = AssayFactory(title=pdf_file, description="")
        # 1) Seed one blank Answer per Question, in the app done via AssayAnswerForm.save()
        questions = Question.objects.order_by("id")
        for q in questions:
            Answer.objects.get_or_create(assay=assay, question=q)
        # 2) Call LLM
        process_llm_async(assay.id, input_pdf_dict, llm)
        print(f"Success: {assay.status}")
        # 4) Retrieve generated answers for this specific assay
        answers = Answer.objects.filter(assay=assay)
        # 5) Generate comparison CSV ALSO SAVES THE FILE
        if not output_tier1.exists():
            (output_tier1).mkdir(parents=True)
        df = generate_comparison_csv(json_file, answers, output_tier1, pdf_file, model=llm, overwrite=False)
        # df is file with [question, gtruth_answer, llm_answer, cos_similarity, bert_precision, bert_recall, bert_f1]
        # now using this file to create a summary of the results
        # 6) Collect summary results
        # Total number of questions with ground truth answers
        total = int(df[df["gtruth_answer"]!=""].dropna().shape[0]) 
        # df filter empty answers   
        # Filter out failures for summary statistics
        passed_mask = (
            (df["gtruth_answer"]!="").astype(bool) & df["gtruth_answer"].notna()
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
        # Passes: LLM answers that are not empty/nan and not refusal
        passes = df_passed.shape[0]
        pass_rate = float(passes) / total * 100 if total > 0 else 0.0
        # 5b) Capture detailed failure info for this assay
        failures = [
            {
                "question_id": a.question.id,
                "question_text": a.question.question_text,
                "answer_text": a.answer_text,
            }
            for a in answers
            if not a.answer_text or has_answer_not_found(a.answer_text)
        ]
        # Compute aggregated statistics for similarity and BERT metrics
        metrics = ["cos_similarity", "bert_precision", "bert_recall", "bert_f1"]
        # Aggregate mean, std, min, max, median using only valid rows
        agg_stats = (
            df_passed[metrics].agg(["mean", "std", "min", "max", "median"]).to_dict()
        )

        for m in metrics:
            agg_stats[m]["percent_above_threshold"] = float(
                (df_passed[m] > config._validation_cos_similarity_threshold).mean()
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

    # 7) Save summary results to JSON with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    output_file = output_tier1 / f"tier1_summary_{timestamp}.json"
    with open(output_file, "w", encoding="utf-8") as out_f:
        json.dump({"timestamp": timestamp, "records": records}, out_f, indent=2)
    print(f"Tier 1 results saved to {output_file}")
