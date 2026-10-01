import re

import pytest

from app.transform.helpers import base32_id, base32_id_decode, slug_to_regex, slugify


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
