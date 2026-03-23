import json
from typing import Any, Dict, List


class SecretaryAgent:
    """
    Orchestrates the investigation loop using a provided backend.
    """

    def __init__(self, providers: List[Any], backend: Any):
        self.providers = providers
        self.backend = backend
        self.tool_map = {}
        self.history = []

    def build_tool_schemas(self) -> List[Dict[str, Any]]:
        """
        Maps provider tools to LLM schemas.
        """
        schemas = []
        for provider in self.providers:
            provider_tools = provider.discover_tools()
            for name, info in provider_tools.items():
                namespaced_name = f"{provider.name}_{name}"
                self.tool_map[namespaced_name] = info["handler"]
                schemas.append(
                    {
                        "type": "function",
                        "function": {
                            "name": namespaced_name,
                            "description": info["description"],
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    k: {"type": v["type"]} for k, v in info["parameters"].items()
                                },
                                "required": [
                                    k for k, v in info["parameters"].items() if v["required"]
                                ],
                            },
                        },
                    }
                )
        return schemas

    def dispatch_tool_call(self, name: str, args: Dict[str, Any]) -> Any:
        """
        Executes the actual Python logic for a tool.
        """
        if name not in self.tool_map:
            return f"Error: Tool {name} not found."
        try:
            return self.tool_map[name](**args)
        except Exception as e:
            return f"Error: {str(e)}"

    async def negotiate(self, request: str) -> str:
        """
        The core loop: orchestrates calls and feeds them back via the backend.
        """
        tools = self.build_tool_schemas()

        # Initialize history (using a structure compatible with both)
        self.history = [{"role": "user", "content": request}]

        for _ in range(10):
            # 1. Get raw response from model
            raw_response = self.backend.generate_response(self.history, tools=tools)

            # 2. Extract standardized data for our loop
            content, calls = self.backend.extract_content_and_calls(raw_response)

            # 3. Add the assistant message to history (formatted by backend)
            self.history.append(self.backend.format_assistant_message(raw_response))

            if not calls:
                return content

            # 4. Handle tool calls
            for call in calls:
                observation = self.dispatch_tool_call(call["name"], call["args"])

                # 5. Format and add the result to history (formatted by backend)
                result_message = self.backend.format_tool_result(
                    call["id"], call["name"], observation
                )
                self.history.append(result_message)

        return "Negotiation timed out."
