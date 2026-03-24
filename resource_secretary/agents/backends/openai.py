import json
import os
from typing import Any, Dict, List, Tuple


class OpenAIBackend:
    """
    OpenAI backend handling strict tool-calling message sequences.

    Note that I refactored this from fractale, and specifically moved the logic
    to handle the tool calls internal here. The difference is that openai type
    backends REQUIRE you to give it back, which is annoying.
    """

    def __init__(self, model_name: str = "gpt-4o", api_base: str = None):
        from openai import OpenAI

        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set.")

        self.client = OpenAI(api_key=self.api_key, base_url=api_base)
        self.model_name = model_name

    def generate_response(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]] = None,
    ) -> Any:
        """
        Sends the request and returns the raw response message object.
        """
        kwargs = {"model": self.model_name, "messages": messages}
        if tools:
            kwargs["tools"] = tools

        response = self.client.chat.completions.create(**kwargs)
        return response.choices[0].message

    def extract_content_and_calls(self, message: Any) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Extracts text and tool calls from an OpenAI message object.
        No native tool calls in manual mode.
        """
        return (message.content or ""), []

    def format_assistant_message(self, message: Any) -> Dict[str, Any]:
        """
        Converts the raw OpenAI message into a dict for history.
        Parse the message.content into the response
        """
        return {"role": "assistant", "content": message.content}

    def format_tool_result(self, tool_call_id: Any, name: str, result: Any) -> Dict[str, Any]:
        """
        Formats a tool execution result for OpenAI history.
        """
        return {"role": "user", "content": f"OBSERVATION from {name}:\n{result}"}
