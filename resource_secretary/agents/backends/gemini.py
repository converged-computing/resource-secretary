import json
import os
from typing import Any, Dict, List, Tuple


class GeminiBackend:
    """
    Gemini backend handling Google's native content/part structures.

    I am planning for this to be instantiated in the scope of a single job request.
    We would not want to preserve history between them because that could lead to
    security issues or similar.
    """

    def __init__(self, model_name: str = "gemini-2.0-flash"):
        from google import genai
        from google.genai import types

        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not set.")

        self.client = genai.Client(api_key=self.api_key)
        self.model_name = model_name
        self.types = types

    def generate_response(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]] = None,
    ) -> Any:
        """
        Sends the request using Gemini's generate_content.
        This is a refactor from the fractale base, with the metrics removed.
        """
        # Note: Gemini messages in our history are already formatted by our helpers
        config = None
        if tools:
            gemini_tools = [
                self.types.Tool(
                    function_declarations=[
                        self.types.FunctionDeclaration(
                            name=t["function"]["name"],
                            description=t["function"]["description"],
                            parameters=t["function"]["parameters"],
                        )
                        for t in tools
                    ]
                )
            ]
            config = self.types.GenerateContentConfig(tools=gemini_tools)

        return self.client.models.generate_content(
            model=self.model_name, contents=messages, config=config
        )

    def extract_content_and_calls(self, response: Any) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Extracts text and function calls from a Gemini response.
        """
        text_content = ""
        tool_calls = []
        if response.candidates:
            for part in response.candidates[0].content.parts:
                if part.text:
                    text_content += part.text
                if part.function_call:
                    tool_calls.append(
                        {
                            "id": None,  # Gemini doesn't use unique call IDs
                            "name": part.function_call.name,
                            "args": part.function_call.args,
                        }
                    )
        return text_content, tool_calls

    def format_assistant_message(self, response: Any) -> Any:
        """
        Returns the content object from Gemini to be placed in history.
        """
        return response.candidates[0].content

    def format_tool_result(self, tool_call_id: Any, name: str, result: Any) -> Any:
        """
        Formats a function response for Gemini's content sequence.
        """
        return self.types.Content(
            role="user",
            parts=[
                self.types.Part(
                    function_response=self.types.FunctionResponse(
                        name=name, response={"result": result}
                    )
                )
            ],
        )
