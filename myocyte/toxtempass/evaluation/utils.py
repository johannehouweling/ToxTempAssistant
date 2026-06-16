from django.core.exceptions import ObjectDoesNotExist

from toxtempass.models import QuestionSet


def resolve_eval_llm(
    model_name: str, temperature: float | int | None
) -> tuple[object | None, str, str | None]:
    """Resolve a chat client for an evaluation model id.

    Single source of truth for model resolution across all eval tiers (was
    copy-pasted in pcontrol/ncontrol). Tries the Azure registry first (by model
    id), then falls back to legacy ``OPENAI_*`` credentials.

    Returns ``(llm, info, key)`` where ``info`` is a short human-readable
    description for logging and ``key`` is the ``"idx:tag"`` deployment key (or
    ``None`` for the legacy fallback) — pass it as ``process_llm_async(...,
    llm_model=key)`` so the model's *own* context window is used for truncation.
    Returns ``(None, reason, None)`` when the model cannot be resolved.
    """
    # Imported lazily to avoid import-time races (this module is imported early).
    from langchain_openai import ChatOpenAI

    from toxtempass import LLM_API_KEY, LLM_ENDPOINT, config
    from toxtempass.azure_registry import find_by_model_id, get_registry
    from toxtempass.llm import get_llm_for_endpoint

    resolved = find_by_model_id(model_name) if get_registry() else None
    if resolved is not None:
        ep, model_entry = resolved
        llm = get_llm_for_endpoint(
            ep.index,
            model_entry.tag,
            temperature=temperature if temperature is not None else 0,
        )
        info = (
            f"E{ep.index}:{model_entry.tag} [{model_entry.api}] "
            f"temperature={temperature}"
        )
        return llm, info, f"{ep.index}:{model_entry.tag}"
    if LLM_API_KEY and LLM_ENDPOINT:
        llm = ChatOpenAI(
            api_key=LLM_API_KEY,
            base_url=config.url,
            temperature=temperature,
            model=model_name,
            default_headers=config.extra_headers,
        )
        return llm, f"{LLM_ENDPOINT} (legacy) temperature={temperature}", None
    return None, (
        f"{model_name!r} not found in Azure registry and no legacy "
        "OPENAI_API_KEY configured"
    ), None


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
