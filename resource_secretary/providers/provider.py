import functools
import inspect
from typing import Any, Callable, Dict, Optional


def _base_tool_decorator(func: Callable, category: str):
    """
    Wrapper for a base tool. We can add this to provider functions to label
    them as tools that a secretary agent should be able to call to discover
    stuff.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    # Attach categorical metadata
    wrapper.is_tool = True
    # Right now this can be secretary or dispatch
    wrapper.tool_category = category

    # Force metadata to basic types to avoid proxy/object issues
    wrapper.tool_name = str(func.__name__)
    doc = func.__doc__
    wrapper.tool_doc = str(doc).strip() if isinstance(doc, str) else "No description."

    # Parse arguments for the tool manifest
    sig = inspect.signature(func)
    args_manifest = {}
    for name, param in sig.parameters.items():
        if name == "self":
            continue

        # Extract type name safely, handling Annotated or standard types
        ptype = "string"
        annotation = param.annotation
        if annotation != inspect.Parameter.empty:
            # Handle Annotated[type, metadata]
            if hasattr(annotation, "__origin__"):
                ptype = getattr(annotation.__origin__, "__name__", str(annotation.__origin__))
            else:
                ptype = getattr(annotation, "__name__", str(annotation))

        args_manifest[str(name)] = {
            "type": str(ptype).lower(),
            "required": param.default == inspect.Parameter.empty,
        }

    wrapper.tool_args = args_manifest
    return wrapper


def secretary_tool(func: Callable):
    """
    Labels a method as a tool for discovery and status retrieval.
    Used by the secretary agent primarily. We don't want the secretary to make
    system changes, it's like read only.
    """
    return _base_tool_decorator(func, "secretary")


def dispatch_tool(func: Callable):
    """
    Labels a method as a tool for actions and state changes.
    Used by the dispatcher agent to actually interact with a system (submit, cancel, etc).
    """
    return _base_tool_decorator(func, "dispatch")


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

    def get_prompt_vocabulary(self):
        """
        Provider-specific flags that can be used in prompts.
        """
        return {}

    def discover_tools(
        self, tool_types: list = ["secretary", "dispatch"]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Scans provider methods for tool decorators matching the specified tool_type.

        Args:
            tool_type: The category of tools to discover.
                       Defaults to "secretary" (observation/read-only).
                       Set to "dispatch" for action/write tools.

        Returns:
            Dict mapping tool names to their manifest (description, parameters, handler).
        """
        tool_manifest = {}

        for attr_name, attr in inspect.getmembers(self, predicate=inspect.ismethod):
            # Filter down to tools in the category we want
            if not getattr(attr, "is_tool", False):
                continue
            tool_category = getattr(attr, "tool_category", None)
            if tool_category not in tool_types:
                continue

            # Safely extract and validate manifest data
            raw_args = getattr(attr, "tool_args", None)
            args = raw_args if isinstance(raw_args, dict) else {}

            raw_doc = getattr(attr, "tool_doc", None)
            doc = str(raw_doc) if isinstance(raw_doc, str) else "No description."

            t_name = str(getattr(attr, "tool_name", attr_name))

            tool_manifest[t_name] = {
                "description": doc,
                "category": tool_category,
                "parameters": args,
                "handler": attr,
            }

            # Cache the actual callable in the tools map
            self.tools[t_name] = attr

        return tool_manifest
