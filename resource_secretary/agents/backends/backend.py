import os
from typing import Any, Optional


def get_backend(
    backend_type: Optional[str] = None,
    model_name: Optional[str] = None,
    api_base: Optional[str] = None,
) -> Any:
    """
    Factory to resolve and instantiate the LLM backend.

    Order of precedence:
    1. Explicit arguments passed to this function.
    2. Environment variables (RESOURCE_SECRETARY_LLM, RESOURCE_SECRETARY_MODEL).
    3. Defaults (gemini, gemini-2.0-flash).
    """
    # Resolve backend type from environment (this is like fractale)
    llm_type = (backend_type or os.getenv("RESOURCE_SECRETARY_LLM", "gemini")).lower()

    # Resolve model name, Gemini is the best so let's use that for default
    # Note that this can be provided via command line or environment too.
    default_models = {"gemini": "gemini-2.0-flash", "openai": "gpt-4o"}

    resolved_model = (
        model_name
        or os.getenv("RESOURCE_SECRETARY_MODEL")
        or default_models.get(llm_type, "unknown")
    )

    # API Base (mostly for OpenAI/Local models)
    resolved_base = api_base or os.getenv("RESOURCE_SECRETARY_API_BASE")

    # Make it so!
    if llm_type == "gemini":
        from .gemini import GeminiBackend

        return GeminiBackend(model_name=resolved_model)

    if llm_type == "openai":
        from .openai import OpenAIBackend

        return OpenAIBackend(model_name=resolved_model, api_base=resolved_base)

    raise ValueError(f"Unsupported backend type: {llm_type}")
