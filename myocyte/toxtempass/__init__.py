# ruff: noqa: W293, W291, E501
import logging
import os
from types import MappingProxyType
from typing import Final, Mapping

from django.conf import settings

logger = logging.getLogger("llm")

LLM_ENDPOINT = None
LLM_API_KEY = None

# ── Azure AI Foundry (preferred) ──────────────────────────────────────────────
# Auto-discovered from AZURE_E{n}_* env vars; see azure_registry.py for the
# naming convention.  The registry is built lazily so import-time cost is zero.
from toxtempass.azure_registry import get_registry as _get_azure_registry  # noqa: E402

# Prompt text lives in toxtempass/tools/prompts.py; Config re-exports it below so
# existing call sites (config.base_prompt etc.) keep working unchanged.
from toxtempass.tools import prompts as _prompts  # noqa: E402

_azure_endpoints = _get_azure_registry()
if _azure_endpoints:
    # Pick the first endpoint's first model as the boot-time default.
    # The admin can override this via the LLMConfig model at runtime.
    _default_ep = _azure_endpoints[0]
    LLM_ENDPOINT = _default_ep.endpoint
    LLM_API_KEY = _default_ep.api_key

# ── Legacy fallback (OpenAI) ──────────────────────────────────────────────────
BASEURL_OPENAI = "https://api.openai.com/v1"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not LLM_ENDPOINT:
    if OPENAI_API_KEY and BASEURL_OPENAI:
        LLM_ENDPOINT = BASEURL_OPENAI
        LLM_API_KEY = OPENAI_API_KEY

logging.basicConfig(
    level=logging.WARNING, format="%(asctime)s - %(levelname)s - %(message)s"
)


class Config:
    """Put all parameters below here."""

    debug = settings.DEBUG
    # degbug = settings.DEBUG
    ## IMPORTANT ALL PARAMETERS ARE DUMPED INTO THE METADATA OF THE USER EXPORT, UNLESS MARKED WITH _ or __ (underscore or double underscore) ##

    # Model defaults — resolved at import time from the Azure registry or
    # legacy OpenAI env vars.  The admin can override the active
    # endpoint+model at runtime via the LLMConfig singleton.
    if _azure_endpoints:
        _default_model_entry = (
            _azure_endpoints[0].models[0] if _azure_endpoints[0].models else None
        )
        model = _default_model_entry.model_id if _default_model_entry else "gpt-4o-mini"
        _deployment_name = (
            _default_model_entry.deployment_name if _default_model_entry else None
        )
    else:
        model = "gpt-4o-mini"
        _deployment_name = None

    model_info_url = ""
    extra_headers = {}
    url = LLM_ENDPOINT
    temperature = 0
    # Prompts re-exported from toxtempass/tools/prompts.py (single source of
    # truth). base_prompt and suggestion_prompt share the inline _(Source: X)_
    # Markdown citation annotation via prompts.CITATION_FORMAT.
    not_found_string = _prompts.NOT_FOUND_STRING
    base_prompt = _prompts.BASE_PROMPT
    suggestion_prompt = _prompts.SUGGESTION_PROMPT
    image_prompt = _prompts.IMAGE_PROMPT
    min_image_width = 50
    min_image_height = 50
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
    # ── Upload control surface ────────────────────────────────────────────────
    # What users may upload: image/text suffixes drive the HTML `accept=` hint,
    # ALLOWED_MIME_TYPES gates server-side validation. Immutable containers so
    # these can't be mutated at runtime from anywhere in the app.
    IMAGE_ACCEPT_FILES: Final[tuple[str, ...]] = (
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bmp",
        ".tiff",
        ".webp",
    )
    TEXT_ACCEPT_FILES: Final[tuple[str, ...]] = (
        ".pdf",
        ".docx",
        ".txt",
        ".md",
        ".html",
        ".json",
        ".csv",
        ".xlsx",
        ".xls",
        ".pptx",
    )
    ALLOWED_MIME_TYPES: Final[frozenset[str]] = frozenset(
        {
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
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
            "application/vnd.ms-excel",  # legacy .xls
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",  # .pptx
        }
    )

    # ── Export control surface ────────────────────────────────────────────────
    # What the app may export: EXPORT_MIME_SUFFIX gives MIME + filename suffix
    # per type, EXPORT_MAPPING gives the trusted Pandoc options. Security-
    # relevant: adding a new export type means adding an entry here and nowhere
    # else. MappingProxyType makes the mappings read-only at runtime — `Final`
    # and the `Mapping` hint alone only guard rebinding / static-type mistakes,
    # not `Config.EXPORT_MAPPING["pdf"] = (...)` at runtime.
    _mime_type_docx = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    EXPORT_MIME_SUFFIX: Final[Mapping[str, Mapping[str, str]]] = MappingProxyType(
        {
            "html": MappingProxyType({"mime_type": "text/html", "suffix": ".html"}),
            "xml": MappingProxyType({"mime_type": "application/xml", "suffix": ".xml"}),
            "pdf": MappingProxyType({"mime_type": "application/pdf", "suffix": ".pdf"}),
            "docx": MappingProxyType({"mime_type": _mime_type_docx, "suffix": ".docx"}),
            "json": MappingProxyType(
                {"mime_type": "application/json", "suffix": ".json"}
            ),
            "md": MappingProxyType({"mime_type": "text/markdown", "suffix": ".md"}),
            "tex": MappingProxyType({"mime_type": "application/x-tex", "suffix": ".tex"}),
        }
    )
    EXPORT_MAPPING: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
        {
            "json": (),
            "md": ("--to=gfm+smart",),
            "pdf": ("--pdf-engine=lualatex", "--standalone"),
            "docx": ("--to=docx+auto_identifiers",),
            "html": ("--embed-resources", "--standalone", "--to=html5+smart"),
            "xml": ("--to=docbook",),
            "tex": ("--to=latex", "--standalone"),
        }
    )
    # Subset of EXPORT_MAPPING types that require Pandoc (JSON is serialized inline).
    PANDOC_EXPORT_TYPES: Final[frozenset[str]] = frozenset(EXPORT_MAPPING) - {"json"}
    status_error_max_len = 8192
    license_url = "https://www.gnu.org/licenses/agpl-3.0.html"
    version = os.getenv("GIT_TAG", "") + "-beta"
    reference_toxtempassistant_paper = "https://doi.org/10.1080/2833373X.2026.2638036"
    reference_toxtempassistant_paper_svg = (
        "https://zenodo.org/badge/DOI/10.1080/2833373X.2026.2638036.svg"
    )
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
    # How often (ms) the client syncs accumulated active time to the server.
    # A value of 60 000 ms means at most ~1 min of time can be lost per
    # collaborator if the browser is closed unexpectedly.
    time_sync_interval_ms = 60_000
    # Tokens reserved for system messages, per-question instructions, and the
    # model's generated answer.  This headroom is subtracted from the model's
    # advertised context-window (``context-window`` tag) to derive the token
    # budget available for the PDF/document context.
    # When the model has no ``context-window`` tag, the fallback budget is
    # ``context_window_fallback_tokens - context_window_headroom_tokens``.
    context_window_headroom_tokens = 10_000
    # Conservative fallback context-window size used when the active model has
    # no ``context-window`` tag.  Most modern LLMs support at least 128 k tokens,
    # so 128,000 is a safe lower bound.
    context_window_fallback_tokens = 128_000
    # Safety margin applied when computing the character budget from the token
    # limit.  A value of 0.95 means we keep 95 % of the proportionally-computed
    # length, leaving a 5 % buffer to compensate for imprecision in the
    # character-to-token ratio.
    truncation_safety_margin = 0.95
    max_workers_django_q = settings.Q_CLUSTER[
        "workers"
    ]  # 1 worker for django_q, we use threading for parallelism
    # How often to reload the overview page to check for busy/scheduled assays
    # (in milliseconds)
    reload_busy_interval_seconds = 10000
    reload_busy_max_retries = 30  # e.g., 30 × 10s = 5 minutes
    # ROR organization lookup settings
    ror_organization_api_url = "https://api.ror.org/v2/organizations"
    ror_lookup_timeout_seconds = 3
    ror_domain_lookup_min_query_length = 1
    ror_general_lookup_min_query_length = 3
    ror_lookup_help_text = (
        f"Type at least {ror_domain_lookup_min_query_length} "
        f"{'character' if ror_domain_lookup_min_query_length == 1 else 'characters'} "
        "with your email filled in, otherwise "
        f"{ror_general_lookup_min_query_length} characters, to search ROR "
        "organizations."
    )
    ror_max_query_length = 120
    ror_max_suggestions = 10
    # ORCID settings
    _orcid_client_id = os.getenv("ORCID_CLIENT_ID")
    _orcid_client_secret = os.getenv("ORCID_CLIENT_SECRET")

    # ── Password reset rate-limiting ──────────────────────────────────────────
    # Minimum wait in seconds between consecutive reset requests.
    # Index 0 → wait before 2nd attempt, index 1 → before 3rd, etc.
    # Schedule: 1 min → 5 min → 1 hour → 1 day
    _pw_reset_wait_periods: Final[tuple[int, ...]] = (60, 300, 3600, 86400)
    # Keep only the most recent N attempt timestamps in Person.preferences.
    _pw_reset_max_stored: Final[int] = 10

    # Validation settings
    # These are used in the validation pipeline to estimate performance of the LLM
    # Not used in the actual application, but for validation purposes only.

    _validation_embedding_model = "text-embedding-3-large"
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
                "This progress bar shows how many answers you have accepted out of the total number of questions. The indigo segment marks questions with a suggested answer awaiting your review.",
            ],
            [
                ".border-indigo",
                "Indigo cards are suggestions drawn from general toxicology knowledge — NOT from your documents. Check the certainty score, then 'Use this answer' to accept it into the answer (you can still edit it) or 'Dismiss' to discard it.",
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
