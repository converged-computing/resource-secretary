import ast
import json
import re
import shlex


def format_calls(calls_block):
    """
    The secretary agent can return calls. We need to ensure we try
    to get and parse them correctly.
    """
    calls = []
    try:
        return json.loads(extract_code_block(calls_block))
    except:
        return calls


def ensure_command(command):
    """
    Ensure the command if provided as string is split into list.
    """
    if isinstance(command, str):
        command = shlex.split(command)
    return command


import ast
import re


def parse_args(args_str):
    pattern = r"(\w+)\s*=\s*(\{.*?\}|'[^']*'|\"[^\"]*\"|[^,]+)"
    matches = re.findall(pattern, args_str)
    result = {}
    for key, value in matches:
        value = value.strip()
        try:
            result[key] = ast.literal_eval(value)
        except:
            result[key] = value.strip("'\"")
    return result


def from_string_arg(val):
    """
    When we parse a call (from string) we need to convert into Python types.
    """
    if isinstance(val, str):
        try:
            return ast.literal_eval(val)
        except:
            pass

    # None
    if val is None or val.strip().lower() in ["none", "null"]:
        return None

    if val in [True, False]:
        return val

    # Dict
    if val.startswith("{"):
        try:
            return extract_code_block(val)
        except:
            pass

    # Booleans
    lower_val = val.strip().lower()
    if lower_val in ("true", "yes", "t", "on"):
        return True
    if lower_val in ("false", "no", "f", "off"):
        return False

    # numeric conversions (int, float, original)
    try:
        return int(val)
    except ValueError:
        try:
            return float(val)
        except ValueError:
            return val


def ensure_bool(value):
    """
    Overly verbose function to ensure numerical
    """
    if value is None:
        return value
    if value in ["True", "true", "yes", "t", "T", "y", 1, "1", True]:
        return True
    if value in ["False", "false", "no", "f", "F", "n", 0, "0", False]:
        return False


def ensure_int(number):
    """
    Overly verbose function to ensure numerical
    """
    if number is None:
        return number
    try:
        return int(number)
    except:
        return number


def ensure_dict(obj):
    if obj is None or not obj:
        return obj
    if isinstance(obj, dict):
        return obj
    if isinstance(obj, str):
        try:
            return extract_code_block(obj)
        except:
            pass
    return obj


def extract_code_block(text):
    """
    Match block of code, assuming llm returns as markdown or code block.

    This is (I think) a better variant.
    """
    match = re.search(r"```(?:\w+)?\s*\n(.*?)\n\s*```", text, re.DOTALL)
    # Extract content from ```json ... ``` blocks if present
    if match:
        return match.group(1).strip()
    # Fall back to returning stripped text
    return text.strip()


def get_code_block(content, code_type=None):
    """
    Parse a code block from the response
    """
    code_type = code_type or r"[\w\+\-\.]*"
    pattern = f"```(?:{code_type})?\n(.*?)```"
    match = re.search(pattern, content, re.DOTALL)
    if match:
        return match.group(1).strip()
    if content.startswith(f"```{code_type}"):
        content = content[len(f"```{code_type}") :]
    if content.startswith("```"):
        content = content[len("```") :]
    if content.endswith("```"):
        content = content[: -len("```")]
    return content.strip()
