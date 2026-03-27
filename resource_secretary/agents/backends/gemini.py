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
        Main function to generate a response. We currently are not parsing tools
        from the client call, but can add this back.
        """
        # Separate system instructions from conversation history
        history = []
        system_instruction = None

        for m in messages:
            role = m.get("role")
            content = m.get("content") or ""

            if role == "system":
                system_instruction = content
            else:
                # Convert role 'assistant' to 'model' for Gemini
                gemini_role = "model" if role == "assistant" else "user"
                history.append({"role": gemini_role, "parts": [{"text": content}]})

        # Build config with system instruction
        config_kwargs = {}
        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction

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
            config_kwargs["tools"] = gemini_tools

        config = self.types.GenerateContentConfig(**config_kwargs)

        return self.client.models.generate_content(
            model=self.model_name, contents=history, config=config
        )

    def extract_content_and_calls(self, response: Any) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Extract content and calls. This was moved to be internal to the Gemini client mostly
        because of the OpenAI requirement to include tools, period.
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
                            "id": None,
                            "name": part.function_call.name,
                            "args": part.function_call.args,
                        }
                    )
        return text_content, tool_calls

    def format_assistant_message(self, response: Any) -> Any:
        """
        Save as a standard dict for our SecretaryAgent history
        Returns the content object from Gemini to be placed in history.
        """
        content = response.candidates[0].content
        text = "".join([p.text for p in content.parts if p.text])
        return {"role": "assistant", "content": text}

    def format_tool_result(self, tool_call_id: Any, name: str, result: Any) -> Any:
        """
        Formats a function response for Gemini's content sequence.
        In our 'manual' loop, results are just fed back as user text
        """
        return {"role": "user", "content": f"OBSERVATION from {name}:\n{result}"}
