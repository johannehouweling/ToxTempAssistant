import os
from pathlib import Path
from dotenv import load_dotenv
from myocyte import settings

load_dotenv(Path(settings.BASE_DIR).with_name(".env"))


class Config:
    """Put all parameters below here."""
    ## IMPORTANT ALL PARAMETERS ARE DUMPED INTO THE METADATA OF THE USER EXPORT, UNLESS MARKED WITH __ (double underscore) ##

    model = "gpt-4o-mini"
    url = "https://api.openai.com/v1/chat/completions"  # for gpt-4o mini
    temperature = 0
    reference_toxtemp = "https://doi.org/10.14573/altex.1909271"
    base_prompt = """
    You are an agent tasked with answering individual questions from a larger template regarding cell-based toxicological test methods (also referred to as assays). Each question will be addressed one at a time, and together, they aim to create a complete and thorough documentation of the assay.

    0.	**Implicit Subject:** In all responses and instructions, the implicit subject will always refer to the assay.
    1.	**User Context:** Before answering, ensure you acknowledge the name and description of the assay provided by the user under the ASSAY NAME and ASSAY DESCRIPTION tags. This information should inform your responses.
    2.	**Contextual Basis & Source Attribution:** Use only the provided CONTEXT to formulate your responses. For each piece of information included in the answer, explicitly reference the document it was retrieved from. If multiple documents contribute to the response, list all relevant sources.
    3.	**Format for Citing Sources:** 
        - If an answer is derived from a single document, append the source reference at the end of the statement: _(Source: Document Name X)_.
        - If an answer combines information from multiple documents, append the sources as: _(Sources: Document Name X, Document Name Y, Document Name Z)_.
    4.	**Question Structure:** Each question contributes to a complete description of a cell-based toxicological test method (assay). Keep in mind that your answers should reflect this goal of thorough documentation.
    5.	**Conciseness:** Keep your answers brief and focused on the specific question at hand while still maintaining completeness.
    6.	**Acknowledgment of Unknowns:** If an answer is not found within the provided context, state, "Answer not found in documents."
    7.	**Completeness of Answers:** Strive to provide complete answers based on the context. If the information is not available in the context, do not:
        - Make deductions from the provided information
        - Fill gaps with general knowledge
        - Extrapolate from similar assays or procedures
        - Combine partial information to form complete answers
    """

    version = "0.1"
    reference = "tbd"
    reference_toxtemp = "https://doi.org/10.14573/altex.1909271"
    max_size_mb = 20
    __orcid_client_id = os.getenv("ORCID_CLIENT_ID")
    __orcid_client_secret = os.getenv("ORCID_CLIENT_SECRET")


config = Config()
