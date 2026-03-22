import functools
import inspect
from typing import Any, Callable, Dict, Optional


def secretary_tool(func: Callable):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    wrapper.is_secretary_tool = True
    wrapper.tool_name = func.__name__
    wrapper.tool_doc = func.__doc__ or "No description provided."

    sig = inspect.signature(func)
    wrapper.tool_args = {
        name: {
            "type": (
                param.annotation.__name__
                if param.annotation != inspect.Parameter.empty
                else "string"
            ),
            "default": param.default if param.default != inspect.Parameter.empty else None,
            "required": param.default == inspect.Parameter.empty,
        }
        for name, param in sig.parameters.items()
        if name != "self"
    }
    return wrapper


class BaseProvider:
    """
    All providers inherit from this. Default is to be discoverable.
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
        tool_manifest = {}
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            if hasattr(attr, "is_secretary_tool"):
                tool_manifest[attr.tool_name] = {
                    "description": attr.tool_doc,
                    "parameters": attr.tool_args,
                    "handler": attr,
                }
                self.tools[attr.tool_name] = attr
        return tool_manifest
