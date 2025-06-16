from toxtempass.fixtures.factories import AssayFactory, DocumentDictFactory
from toxtempass.models import Question, Answer
from pathlib import Path

from toxtempass.views import process_llm_async
from toxtempass import config
# if config.not_found_string in Answer

# generate Assay
# assay = AssayFactory(title="", description="")
# text_dict = DocumentDictFactory()

# # run llm on assay
# process_llm_async(assay.id, text_dict)


# different test cases

# Tier 1: Positive Control
# input_tier1 = Path("/Users/johannehouweling/ToxTempAssistant/myocyte/toxtempass/validation/validation_documents/tier1_positive").glob("*.*")


# Tier 2: Negative Control
input_tier2 = list(
    Path("myocyte/toxtempass/validation/validation_documents/tier2_negative").glob(
        "*.*"
    )

    /Users/johannehouweling/ToxTempAssistant/myocyte/toxtempass/validation/validation_documents/tier2_negative