import logging

from jinja2 import BaseLoader, Environment

logger = logging.getLogger(__name__)


def resolve_templates(inputs: dict, context: dict) -> dict:
    """
    Resolves Jinja2 templates in a dictionary against a context.
    Handles UserDicts and raw dicts.
    """
    if not inputs:
        return {}

    # Flatten context
    data = getattr(context, "data", context)
    env = Environment(loader=BaseLoader())
    resolved = {}
    for k, v in inputs.items():
        if isinstance(v, str) and "{{" in v:
            try:
                resolved[k] = env.from_string(v).render(**data)
            except Exception as e:
                logger.warning(f"Jinja render failed for key '{k}': {e}")
                # Fallback to raw string on failure
                resolved[k] = v
        else:
            # Pass through other stuff
            resolved[k] = v

    return resolved
