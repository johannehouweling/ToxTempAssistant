# ruff: noqa: W293, W291, E501
import logging
import os

from django.conf import settings
from toxtempass.prompts import (
    build_base_prompt,
    get_prompt_hash,
    prompt_version as prompt_stack_version,
)

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

logging.basicConfig(
    level=logging.WARNING, format="%(asctime)s - %(levelname)s - %(message)s"
)


class Config:
    """Put all parameters below here."""

    debug = settings.DEBUG
    # degbug = settings.DEBUG
    ## IMPORTANT ALL PARAMETERS ARE DUMPED INTO THE METADATA OF THE USER EXPORT, UNLESS MARKED WITH _ or __ (underscore or double underscore) ##
    # See https://openrouter.ai/models for available models.
    # Make sure to pick a model with multimodal capabilities if you want to not break image inputs.
    model = "gpt-4o-mini" if OPENAI_API_KEY == LLM_API_KEY else "openai/gpt-4o-mini"
    model_info_url = (
        f"https://platform.openai.com/docs/models/{model}"
        if OPENAI_API_KEY
        else f"https://openrouter.ai/{model}"
    )
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
    not_found_string = "Answer not found in documents."
    prompt_version = prompt_stack_version
    base_prompt = build_base_prompt(not_found_string)
    prompt_hash = get_prompt_hash(not_found_string)
    image_description_prompt = (
        "You are a scientific assistant. Describe in detail (up to 20 sentences) the provided assay-related image so that downstream questions can rely on your text as their only context.\n\n"
        "You may draw on three sources only:\n"
        "- the IMAGE itself\n"
        "- any OCR text extracted from the image\n"
        "- PAGE CONTEXT provided below (text near the image in the source document)\n\n"
        "Do not use external knowledge. If a detail is not visible or not stated, explicitly say so.\n"
        "If the image is decorative, contains only logos/branding, or provides no assay-relevant scientific content, respond with the single token IGNORE_IMAGE.\n\n"
        "Your output must follow this template exactly:\n"
        "TITLE: <one-sentence statement of figure type and purpose>\n"
        "SUMMARY: <15-20 sentence neutral description covering axes/titles/units, groups or conditions, sample sizes, error bars/statistics, observable trends, notable cell morphology or equipment, scale bars/magnification, and legible labels>\n"
        "PANELS:\n"
        "- Panel A: <summary or '(same as above)'>\n"
        "- Panel B: <...> (add entries for each panel; use only Panel A if single-panel)\n"
        "NOTES: <bullet list of exactly transcribed on-image text (preserve case, Greek letters, subscripts) and any ambiguities marked [illegible]>\n"
    )
    min_image_width = 25
    min_image_height = 25
    license = "AGPL"
    # obsfuscated email for scraper 'privacy'
    maintainer_email = "".join(
        [
            chr(c)
            for c in [
                74,
                101,
                110,
                116,
                101,
                46,
                72,
                111,
                117,
                119,
                101,
                108,
                105,
                110,
                103,
                64,
                114,
                105,
                118,
                109,
                46,
                110,
                108,
            ]
        ]
    )
    image_accept_files = [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp"]
    text_accept_files = [
        ".pdf",
        ".docx",
        ".txt",
        ".md",
        ".html",
        ".json",
        ".csv",
        ".xlsx",
    ]
    allowed_mime_types = [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
        "text/plain",
        "text/markdown",
        "text/html",
        "image/png",
        "image/jpeg",
        "image/gif",
        "image/bmp",
        "image/tiff",
        "image/webp",
        "application/json",
        "text/csv",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ]
    license_url = "https://www.gnu.org/licenses/agpl-3.0.html"
    version = os.getenv("GIT_TAG", "") + "-beta"
    reference_toxtempassistant_zenodo_code = "https://doi.org/10.5281/zenodo.15607642"
    reference_toxtempassistant_zenodo_code_svg = (
        "https://zenodo.org/badge/DOI/10.5281/zenodo.15607642.svg"
    )
    reference_toxtempassistant_zenodo_publication = ""
    github_repo_url = "https://github.com/johannehouweling/ToxTempAssistant"
    git_hash = os.getenv("GIT_HASH", "")
    reference_toxtemp = "https://doi.org/10.14573/altex.1909271"
    max_size_mb = 30
    single_answer_timeout = 60  # seconds
    max_workers_threading = 4
    max_workers_django_q = settings.Q_CLUSTER[
        "workers"
    ]  # 1 worker for django_q, we use threading for parallelism
    # this is just for security purposes, to add a new type you also need to
    # define a template for it in export.py
    allowed_export_types = {"json", "md", "pdf", "html", "docx", "xml"}

    _orcid_client_id = os.getenv("ORCID_CLIENT_ID")
    _orcid_client_secret = os.getenv("ORCID_CLIENT_SECRET")

    # Validation settings
    # These are used in the validation pipeline to estimate performance of the LLM
    # Not used in the actual application, but for validation purposes only.

    _validation_embedding_model = (
        "text-embedding-3-large"
        if OPENAI_API_KEY == LLM_API_KEY
        else "openai/text-embedding-3-large"
    )
    _validation_bert_score_model = "microsoft/deberta-xlarge-mnli"
    _validation_cos_similarity_threshold = 0.7
    user_onboarding_help = {
        # URL name : list of [element selector, help text]
        "overview": [
            [
                "#id_headline",
                "You can always click on the app title to return to the main page.",
            ],
            [
                "#id_user_menu",
                "In the top right you find a user menu. Here you can logout, or access some information like this help tour.",
            ],
            [
                "td .btn-group a.btn-outline-primary:first-of-type",
                "Click here to view a ToxTemp",
            ],
            [
                "#id_btn_new",
                "Whenever you are ready, click here to create a new ToxTemp.",
            ],
        ],
        "add_new": [
            # id_question_set", "Choose which version of the ToxTemp template to use."],
            [
                "#id_investigation",
                "Use this dropdown to select an Investigation. The buttons next to it allow you to edit or delete.",
            ],
            ["#id_study", "Select or create a Study within your Investigation."],
            [
                "#id_assay",
                "Select or create an Assay - this is what your ToxTemp will describe.",
            ],
            ["#id_assay_btn0", "Click here to create a new assay."],
            [
                "#id_files",
                "Upload relevant documents here to provide context for the LLM.",
            ],
            [
                "#id_overwrite",
                "Check this box to regenerate the ToxTemp for this Assay. Warning: This will replace any existing answers with new LLM-generated content.",
            ],
            [
                "#startButton",
                "Ready to go! Click here to start generating your draft ToxTemp. The LLM will extract relevant information from your documents to prefill the template.",
            ],
        ],
        "create_assay": [
            ["#id_study", "Select which Study this Assay belongs to."],
            ["#id_title", "Give your Assay a clear, descriptive title."],
            [
                "#id_description",
                "Important! The LLM uses this description to understand the scope of the cell-based toxicological test method you want to descibe.",
            ],
            [
                "button[type='submit']",
                "Click here to create your Assay and return to the main form.",
            ],
        ],
        "answer_assay_questions": [
            [
                "#question-content label:first-of-type",
                "Each subsection contains questions. This is the question text that the LLM has attempted to answer.",
            ],
            [
                "#question-content textarea:first-of-type",
                "This field shows the LLM-generated answer. If no relevant information was found, it will say 'Answer not found in documents.'. You can edit this answer as needed.",
            ],
            [
                "button[data-bs-target='#versionHistoryModal']",
                "Click here to view the answer history for this question, including earlier LLM-generated responses.",
            ],
            [
                "#question-content input[type='checkbox']:first-of-type",
                "Check this box to mark questions for an LLM update. You can select one or multiple questions, then use 'Options' → 'Update selected questions'.",
            ],
            [
                "#question-content .form-check-input[role='switch']:first-of-type",
                "Toggle 'Accepted' when satisfied with an answer. This tracks your progress through the ToxTemp.",
            ],
            [
                "#progress",
                "This progress bar shows how many answers you have accepted out of the total number of questions.",
            ],
            [
                "#button[type='submit']",
                "Changes are not automatically saved. Click 'Save' to preserve your edits.",
            ],
            [
                ".btn-group:last-of-type .dropdown-toggle",
                "Once you are finished, use 'Export' to download your completed or draft ToxTemp in various formats. You will be asked to provide brief feedback before export.",
            ],
        ],
    }


config = Config()
