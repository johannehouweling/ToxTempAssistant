import sys
import os
# Ensure project root is on PYTHONPATH so 'toxtempass' imports work
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
# Point Django to your settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myocyte.settings')
import django
django.setup()

# === validation_pipeline.py: Tier 2 Negative Controls Validation ===
# This script sets up and runs the LLM-based validation for off-target PDFs.

# --- Section: Imports & Dependencies ---
from toxtempass.filehandling import get_text_or_bytes_perfile_dict
from toxtempass.models import Investigation, Study, Assay, Question, Answer, Person
import os
from pathlib import Path
import json
import re
from toxtempass import config
from toxtempass.views import process_llm_async

from toxtempass.llm import chain
from langchain_core.messages import SystemMessage, HumanMessage

# --- Section: Synchronous LLM Invocation Helper ---
# Direct invocation of the LLM for validation

def llm_call(question: str, context: str) -> str:
    messages = [
        SystemMessage(content=config.base_prompt),
        SystemMessage(content=f"ASSAY DESCRIPTION:\n{context}"),
        HumanMessage(content=question),
    ]
    response = chain.invoke(messages)
    return response.content.strip()

# ------------------ Tier 2 Negative Controls Validation ------------------

not_found_string = config.not_found_string
REFUSAL_RE = re.compile(re.escape(not_found_string), re.I)


# --- Section: Django Environment Setup ---
# Ensures Django settings are loaded so ORM calls work in this standalone script.
def setup_django():
    from django.apps import apps
    if apps.ready:
        return
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myocyte.settings")
    import django
    django.setup()

# --- Section: PDF Text Extraction ---
# Converts a PDF file into plain text via your existing filehandling utility.
def pdf_to_text(pdf_path: str) -> str:
    # Use filehandling.get_text_or_bytes_perfile_dict to extract text from local PDFs
    text_dict = get_text_or_bytes_perfile_dict([pdf_path])
    # text_dict maps file paths to {'text': ...} or other keys
    entry = text_dict.get(pdf_path)
    if isinstance(entry, dict) and 'text' in entry:
        return entry['text']
    # Fallback to empty string if no text found
    return ""

# --- Section: Answer Refusal Check ---
# Determines whether the model refused to answer (i.e. 'Answer not found...').
def is_refusal(text: str) -> bool:
    return bool(REFUSAL_RE.search(text))

# --- Section: Tier 2 Validation Main Routine ---
# Loops through each PDF, creates an Assay, invokes the LLM, and computes pass rates.
def run_tier2(docs_dir: str, output_json: str):
    setup_django()

    # --- Reset previous Validation run ---
    Investigation.objects.filter(title="Validation").delete()

    # --- Section: Create Validation Investigation & Study ---
    # Recreate the Investigation and Study for this run
    validator_user, _ = Person.objects.get_or_create(
        email="validator@yourdomain.com",  # change to a real or placeholder email
        defaults={"password": ""}
    )
    investigation, _ = Investigation.objects.get_or_create(
        owner=validator_user,
        title="Validation",
        defaults={"description": "LLM validation run"}
    )
    study, _ = Study.objects.get_or_create(
        investigation=investigation,
        title="Tier 2 Negative Control Validation",
        defaults={"description": ""}
    )

    questions = Question.objects.order_by("id")
    # DEBUG: list all PDF files detected for Tier 2
    pdf_paths = sorted(Path(docs_dir).glob("*.pdf"))
    print(f"[DEBUG] Found {len(pdf_paths)} PDF(s) in '{docs_dir}': {[p.name for p in pdf_paths]}")
    records = []
    for pdf_file in pdf_paths:
        print(f"Processing {pdf_file.name}...")
        # 1) Load and preprocess PDF
        context = pdf_to_text(str(pdf_file))
        print(f"[PDF TEXT DEBUG] Extracted {len(context)} chars from PDF {pdf_file.name}")
        print(f"[PDF TEXT DEBUG] Snippet: {context[:200]!r}")
        # 2) Create or get Assay record for this PDF
        assay, _ = Assay.objects.get_or_create(
            study=study,
            title=pdf_file.stem,
            defaults={"description": ""},
        )
        # 3a) Pre-seed Answer objects for each Question if they don't exist
        for q in questions:
            Answer.objects.get_or_create(assay=assay, question=q)

        # 3) Generate answers synchronously for each question
        print(f"[LOOP DEBUG] Running through {len(questions)} questions...")
        for idx, q in enumerate(questions, start=1):
            print(f"[LOOP DEBUG] Question index {idx}/{len(questions)}: Q{q.id}")
            resp = llm_call(q.question_text, context)
            print(f"[LLM DEBUG] Q{q.id} → {resp[:80]!r}…")
            ans_obj = Answer.objects.get(assay=assay, question=q)
            ans_obj.answer_text = resp
            ans_obj.save()
            print("[DB DEBUG] ", Answer.objects.get(assay=assay, question=q).answer_text[:80])
        # 4) Retrieve generated answers for this specific assay
        answers = Answer.objects.filter(assay=assay)
        total = answers.count()
        # 5) Compute refusal pass rate for this assay
        passes = sum(1 for a in answers if is_refusal(a.answer_text or ""))
        pass_rate = round(100 * passes / total, 2) if total else 0.0
        # 5a) Capture detailed failure info for this assay
        failures = [
            {
                "question_id": a.question.id,
                "question_text": a.question.question_text,
                "answer_text": a.answer_text,
            }
            for a in answers
            if not is_refusal(a.answer_text or "")
        ]
        records.append({
            "file": pdf_file.name,
            "passes": passes,
            "total": total,
            "pass_rate": pass_rate,
            "failures": failures,
        })
        print(f"{pdf_file.name}: {pass_rate}%")
    # 6) Save summary results to JSON
    with open(output_json, "w", encoding="utf-8") as out_f:
        json.dump(records, out_f, indent=2)
    print("Tier 2 results saved to", output_json)
