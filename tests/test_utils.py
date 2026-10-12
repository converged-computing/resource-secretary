"""Parsing helpers used to read tool calls and results out of model text."""

import pytest

from resource_secretary.utils import (
    clip,
    ensure_bool,
    ensure_command,
    ensure_dict,
    ensure_int,
    extract_code_block,
    format_calls,
    from_string_arg,
    get_code_block,
    parse_args,
    shuffle,
)


def test_parse_args_handles_strings_numbers_dicts_and_bools():
    assert parse_args("nodes=4, name='x y', opts={'a': 1}, flag=True") == {
        "nodes": 4,
        "name": "x y",
        "opts": {"a": 1},
        "flag": True,
    }
    assert parse_args('path="/usr/bin/lmp"') == {"path": "/usr/bin/lmp"}
    assert parse_args("bare=value") == {"bare": "value"}
    assert parse_args("") == {}


@pytest.mark.parametrize(
    "value,expected",
    [
        ("3", 3),
        ("2.5", 2.5),
        ("yes", True),
        ("off", False),
        ("none", None),
        ("'q'", "q"),
        ("text", "text"),
        (None, None),
    ],
)
def test_from_string_arg(value, expected):
    assert from_string_arg(value) == expected


def test_ensure_helpers():
    assert ensure_bool("yes") is True and ensure_bool("0") is False and ensure_bool(None) is None
    assert ensure_int("4") == 4 and ensure_int("x") == "x" and ensure_int(None) is None
    assert ensure_command("lmp -in a.in") == ["lmp", "-in", "a.in"]
    assert ensure_command(["a"]) == ["a"]
    assert ensure_dict({"a": 1}) == {"a": 1} and ensure_dict(None) is None


def test_code_blocks_and_calls():
    text = 'FINAL PROPOSAL: ok\n```json\n{"verdict": "READY"}\n```'
    assert extract_code_block(text) == '{"verdict": "READY"}'
    assert extract_code_block("plain") == "plain"
    assert get_code_block("```bash\nflux submit a\n```") == "flux submit a"
    assert get_code_block("```json\n{}\n```", "json") == "{}"
    assert format_calls('```json\n[{"provider": "flux", "function": "f"}]\n```') == [
        {"provider": "flux", "function": "f"}
    ]
    assert format_calls("not json") == []


def test_shuffle_and_clip():
    assert sorted(shuffle([3, 1, 2])) == [1, 2, 3]
    assert shuffle({"a": 1, "b": 2}) == {"a": 1, "b": 2}
    with pytest.raises(ValueError):
        shuffle("abc")
    assert clip([1, 2, 3], 2) == [1, 2] and clip("abc", 5) == "abc"
    assert clip({"a": 1, "b": 2}, 1) == {"a": 1}
