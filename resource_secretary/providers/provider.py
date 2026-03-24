import functools
import inspect
from typing import Any, Callable, Dict, Optional


def secretary_tool(func: Callable):
    """
    Wrapper for secretary tool! We can add this to provider functions to label
    them as tools that a secretary agent should be able to call to discover
    stuff.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    # Force doc to string immediately
    doc = func.__doc__
    wrapper.is_secretary_tool = True
    wrapper.tool_name = str(func.__name__)
    wrapper.tool_doc = str(doc) if isinstance(doc, str) else "No description."

    sig = inspect.signature(func)
    args_manifest = {}
    for name, param in sig.parameters.items():
        if name == "self":
            continue

        # Map types to strings
        ptype = "string"
        if param.annotation != inspect.Parameter.empty:
            ptype = getattr(param.annotation, "__name__", "string")

        args_manifest[str(name)] = {
            "type": str(ptype),
            "required": param.default == inspect.Parameter.empty,
        }

    wrapper.tool_args = args_manifest
    return wrapper


class BaseProvider:
    """
    BaseProvider is that - a base provider class. Note that we set is_provider by default
    to true, because most subclasses are providers. The exception are shared interface
    classes, e.g., for maybe a flavor of MPI or similar workload managers. This is my
    preference to using an Abstract class. Note that for the subclasses of that parent,
    is_provider DOES need to be set to True, if their parent was set to False!
    """

    is_provider = True

    def __init__(self):
        self.tools: Dict[str, Callable] = {}
        self.category: str = "unknown"

    @property
    def name(self) -> str:
        raise NotImplementedError

    def probe(self) -> bool:
        raise NotImplementedError

    @property
    def metadata(self) -> Dict[str, Any]:
        return {}

    def discover_tools(self) -> Dict[str, Dict[str, Any]]:
        """
        Scans methods and strictly validates metadata types to avoid flux proxy junk.
        """
        import inspect

        tool_manifest = {}

        for attr_name, attr in inspect.getmembers(self, predicate=inspect.ismethod):
            # 1. Use getattr safely
            is_tool = getattr(attr, "is_secretary_tool", False)
            if is_tool is not True:
                continue

            # Fetch the values and check if they are the correct Python types.
            # If Flux returns an ErrorPrinter, isinstance(x, dict) will be False.
            raw_args = getattr(attr, "tool_args", None)
            args = raw_args if isinstance(raw_args, dict) else {}

            raw_doc = getattr(attr, "tool_doc", None)
            doc = str(raw_doc) if isinstance(raw_doc, str) else "No description."

            t_name = str(getattr(attr, "tool_name", attr_name))

            tool_manifest[t_name] = {"description": doc, "parameters": args, "handler": attr}
            self.tools[t_name] = attr

        return tool_manifest
