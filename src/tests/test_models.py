import logging

from dataclasses import dataclass, field
from typing import List

from pvecontrol.models import api_kwargs, format_fields


@dataclass
class SampleData:
    name: str = field(default="")
    next_run: int = field(default=0)
    items: List = field(default_factory=list)


def test_dashed_api_keys_are_mapped():
    assert api_kwargs(SampleData, {"next-run": 42}) == {"next_run": 42}


def test_default_factory_fields_are_kept():
    # those have no class attribute, a hasattr() based filter would drop them
    assert api_kwargs(SampleData, {"items": [1]}) == {"items": [1]}


def test_unknown_keys_are_dropped_and_logged(caplog):
    with caplog.at_level(logging.DEBUG):
        assert api_kwargs(SampleData, {"name": "a", "zzz": 1, "aaa": 2}) == {"name": "a"}

    assert "SampleData: ignoring api keys ['aaa', 'zzz']" in caplog.text


def test_format_fields():
    assert format_fields(SampleData(name="a", next_run=42)) == "Name: a\nNext-run: 42\nItems: []"
