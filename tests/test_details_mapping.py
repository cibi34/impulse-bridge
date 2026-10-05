"""`mapping.details`: extra facts for the asset dialog, label by label."""

from app.config.schema import FilterCfg, MappingCfg
from app.transform.engine import detail_text, transform_item


def test_details_become_ordered_label_value_pairs():
    mapping = MappingCfg.model_validate({
        "fields": {"assetID": {"expr": "id"}, "title": {"expr": "title"}},
        "details": {
            "Credit line": {"expr": "credit"},
            "Dimensions": {"expr": "dims"},
            "Tags": {"expr": "tags"},
            "Missing": {"expr": "nothing"},
            "Nested": {"expr": "obj"},
            "Notes": {"expr": "html", "transform": "strip_html"},
        },
    })
    raw = {
        "id": "1", "title": "T", "credit": " Gift of X ", "dims": 42, "tags": ["a", "b", None],
        "obj": {"k": "v"}, "html": "<p>Hi&nbsp;there</p>",
    }

    asset = transform_item(raw, mapping, FilterCfg())

    assert asset["details"] == [
        {"label": "Credit line", "value": "Gift of X"},
        {"label": "Dimensions", "value": "42"},
        {"label": "Tags", "value": "a, b"},
        {"label": "Notes", "value": "Hi there"},
    ]


def test_no_details_means_no_key():
    mapping = MappingCfg.model_validate({"fields": {"assetID": {"expr": "id"}}, "details": {"X": {"expr": "nope"}}})
    assert "details" not in transform_item({"id": "1"}, mapping, FilterCfg())


def test_detail_text():
    assert detail_text(None) is None
    assert detail_text("  ") is None
    assert detail_text(True) == "yes"
    assert detail_text([1, "two", [3]]) == "1, two, 3"
    assert detail_text({"a": 1}) is None
