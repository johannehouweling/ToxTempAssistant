import os
import logging

logger = logging.getLogger("llm")

LLM_ENDPOINT = None
LLM_API_KEY = None

# Endpoints
BASEURL_OPENAI = "https://api.openai.com/v1"
BASEURL_OPENROUTER = "https://openrouter.ai/api/v1"

# Access environment variables (.env file defined in settings.py)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Use
if OPENAI_API_KEY and BASEURL_OPENAI:
    LLM_ENDPOINT = BASEURL_OPENAI
    LLM_API_KEY = OPENAI_API_KEY

elif OPENROUTER_API_KEY and BASEURL_OPENROUTER:
    LLM_ENDPOINT = BASEURL_OPENROUTER
    LLM_API_KEY = OPENROUTER_API_KEY


class Config:
    """Put all parameters below here."""

    ## IMPORTANT ALL PARAMETERS ARE DUMPED INTO THE METADATA OF THE USER EXPORT, UNLESS MARKED WITH __ (double underscore) ##
    # See https://openrouter.ai/models for available models.
    model = "gpt-4o-mini" if OPENAI_API_KEY == LLM_API_KEY else "openai/gpt-4o-mini"
    # openrouter allows us to identify the site and title for rankings so that in billing we see which app
    extra_headers = (
        {
            "HTTP-Referer": os.getenv(
                "SITE_URL"
            ),  # Optional. Site URL for rankings on openrouter.ai.
            "X-Title": "ToxTempAssistant",  # Optional. Site title for rankings on openrouter.ai.
        }
        if LLM_ENDPOINT == BASEURL_OPENROUTER
        else {}
    )
    url = LLM_ENDPOINT
    temperature = 0
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
    license = "AGPL"
    license_url = "https://www.gnu.org/licenses/agpl-3.0.html"
    version = "0.1"
    reference = "tbd"
    github_repo_url = "https://github.com/johannehouweling/ToxTempAssistant"
    reference_toxtemp = "https://doi.org/10.14573/altex.1909271"
    max_size_mb = 20
    __orcid_client_id = os.getenv("ORCID_CLIENT_ID")
    __orcid_client_secret = os.getenv("ORCID_CLIENT_SECRET")


config = Config()
