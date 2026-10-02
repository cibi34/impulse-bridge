"""Translation of Impulse's ?o=offset&c=count into upstream pagination params,
both per style and for the bundled source configs."""

from pathlib import Path

import pytest

from app.adapter.rest import GenericRestSource
from app.config.loader import load_one
from app.config.schema import SourceConfig

SOURCES = Path(__file__).resolve().parent.parent / "configs" / "sources"


def _source(pagination: dict | None = None, query: dict | None = None) -> GenericRestSource:
    return GenericRestSource(
        SourceConfig.model_validate(
            {
                "collection": {
                    "id": "test",
                    "name": "Test",
                    "organization": "Test",
                    "owner_id": "t@example.org",
                },
                "adapter": {"kind": "rest", "base_url": "https://api.example.org"},
                "search": {"pagination": pagination or {}, "query": query or {}},
            }
        )
    )


@pytest.mark.parametrize(
    ("pagination", "offset", "count", "expected"),
    [
        (
            {"style": "offset_limit", "offset_param": "o", "limit_param": "n"},
            40, 20, {"o": "40", "n": "20"},
        ),
        (
            {"style": "offset_limit", "offset_param": "start", "limit_param": "rows", "offset_base": 1},
            0, 5, {"start": "1", "rows": "5"},
        ),
        (
            {"style": "offset_limit", "offset_param": "start", "limit_param": "rows", "offset_base": 1},
            5, 5, {"start": "6", "rows": "5"},
        ),
        (
            {"style": "page_size", "page_param": "page", "size_param": "per_page", "page_base": 1},
            40, 20, {"page": "3", "per_page": "20"},
        ),
        (
            {"style": "offset_limit", "offset_param": "o", "limit_param": "n", "max_size": 50},
            0, 500, {"o": "0", "n": "50"},
        ),
        (
            {"style": "offset_limit", "offset_param": "o", "limit_param": "n", "max_size": 50},
            0, None, {"o": "0", "n": "50"},
        ),
    ],
)
def test_pagination_styles(pagination, offset, count, expected):
    params = _source(pagination)._build_params(query=None, offset=offset, count=count)
    assert {k: params[k] for k in expected} == expected


@pytest.mark.parametrize(
    ("filename", "first_param", "first_page", "second_page"),
    [
        # Europeana's `start` is the 1-based position of the first record.
        ("europeana.yaml", "start", "1", "6"),
        ("wikimedia-commons.yaml", "gsroffset", "0", "5"),
    ],
)
def test_bundled_sources_page_by_item_offset(filename, first_param, first_page, second_page):
    source = GenericRestSource(load_one(SOURCES / filename))
    page1 = source._build_params(query="x", offset=0, count=5)
    page2 = source._build_params(query="x", offset=5, count=5)
    assert page1[first_param] == first_page
    assert page2[first_param] == second_page


def test_pattern_template_wraps_user_searches_only():
    source = _source(
        query={
            "pattern_param": "q",
            "pattern_when_empty": "type:image AND license:cc0",
            "pattern_template": "({pattern}) AND license:cc0",
        }
    )
    assert source._build_params(query="dinosaur", offset=0, count=5)["q"] == "(dinosaur) AND license:cc0"
    assert source._build_params(query=None, offset=0, count=5)["q"] == "type:image AND license:cc0"
