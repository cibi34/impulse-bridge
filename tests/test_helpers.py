import re

import pytest

from app.transform.helpers import (
    base32_id,
    base32_id_decode,
    file_title,
    matches_pattern,
    slug_to_regex,
    slugify,
)


@pytest.mark.parametrize(
    "url",
    [
        "https://iiif.example.org/image/V0014272/info.json",
        "https://iiif.example.org/image/V0014272/full/300,/0/default.jpg",
        "https://iiif.example.org/image/V0014272/full/!1024,1024/0/default.png",
        "https://iiif.example.org/image/V0014272/square/max/90/gray.tif",
        "https://iiif.example.org/image/V0014272",
    ],
)
def test_iiif_transforms_resize_any_image_api_url(url):
    from app.transform.helpers import iiif_large, iiif_preview

    assert iiif_large(url) == "https://iiif.example.org/image/V0014272/full/!2048,2048/0/default.jpg"
    assert iiif_preview(url) == "https://iiif.example.org/image/V0014272/full/!400,400/0/default.jpg"


def test_strip_html_decodes_entities_and_collapses_whitespace():
    from app.transform.helpers import strip_html

    assert strip_html("<p>Kinora&nbsp;viewer &amp; more.</p>\n<p>Second</p>") == "Kinora viewer & more. Second"
    assert strip_html("") == ""


@pytest.mark.parametrize(
    "original",
    [
        "/90402/SK_A_3262",
        "/2024903/photography_ProvidedCHO_KU_Leuven_9990940230101488",
        "edanmdm-nmah_1234",
        "  Leading and trailing!  ",
        "multiple___separators--here",
    ],
)
def test_slug_to_regex_inverts_slugify(original):
    slug = slugify(original)
    pattern = slug_to_regex(slug)
    assert re.fullmatch(pattern, original), (slug, pattern)


def test_slug_to_regex_rejects_other_ids():
    pattern = slug_to_regex("90402-sk-a-3262")
    assert not re.fullmatch(pattern, "/90402/SK_A_3263")
    assert not re.fullmatch(pattern, "/90402/SK_A_326")
    assert not re.fullmatch(pattern, "/90403/SK_A_3262")
    assert not re.fullmatch(pattern, "SK_A_3262")  # dataset prefix missing


def test_slug_to_regex_is_solr_safe():
    # Only character classes and quantifiers — no slashes (which delimit Solr
    # regex literals) and no characters that need escaping in Lucene RegExp.
    pattern = slug_to_regex("90402-sk-a-3262")
    assert "/" not in pattern
    assert pattern == (
        "[^a-zA-Z0-9]*90402[^a-zA-Z0-9]+[sS][kK][^a-zA-Z0-9]+[aA]"
        "[^a-zA-Z0-9]+3262[^a-zA-Z0-9]*"
    )


@pytest.mark.parametrize(
    "original",
    ["/90402/SK_A_3262", "edanmdm-nmah_1981.0296.06", "ld1-1643407190095-1643407198918-2", "Ünïcode ✓"],
)
def test_base32_id_roundtrip_and_id_schema(original):
    encoded = base32_id(original)
    assert re.fullmatch(r"[a-z0-9][a-z0-9-]*", encoded), encoded
    assert "=" not in encoded
    assert base32_id_decode(encoded) == original


def test_base32_id_decode_rejects_non_base32():
    assert base32_id_decode("does-not-exist-evaluation") is None
    assert base32_id_decode("90402-sk-a-3262") is None
    assert base32_id_decode("") is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("File:1665 Girl with a Pearl Earring.jpg", "1665 Girl with a Pearl Earring"),
        ("File:A_Young_Hare,_Albrect_Durer.JPG", "A Young Hare, Albrect Durer"),
        ("File:Model.glb", "Model"),
        ("Version 1.10", "Version 1.10"),  # not a media extension
        ("St. Peter", "St. Peter"),
        ("Plain title", "Plain title"),
    ],
)
def test_file_title(value, expected):
    assert file_title(value) == expected


@pytest.mark.parametrize(
    ("pattern", "expected"),
    [(None, True), ("*", True), ("sunflower", True), ("van*sun", True), ("sun*van", False), ("rose", False)],
)
def test_matches_pattern(pattern, expected):
    asset = {"title": "Sunflowers", "creator": "Vincent van Gogh", "rights": 1}
    assert matches_pattern(asset, pattern, ("creator", "title", "rights")) is expected
