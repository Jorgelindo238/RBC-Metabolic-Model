"""Author disambiguation must not turn a surname search into source evidence."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from enrich_palsson_proteomics_review import QUERY, author_is_bernhard_palsson


@pytest.mark.parametrize("author,expected", [
    ({"lastName": "Palsson", "initials": "BO"}, True),
    ({"lastName": "Palsson", "initials": "B", "firstName": "Bernhard"}, True),
    ({"lastName": "Palsson", "initials": "R"}, False),
    ({"lastName": "Palsson", "initials": "OS"}, False),
    ({"lastName": "Other", "initials": "BO"}, False),
    ({"lastName": "Palsson", "firstName": "Bernhard O"}, True),
])
def test_author_disambiguation(author, expected):
    assert author_is_bernhard_palsson({"authorList": {"author": [author]}}) is expected


def test_missing_author_metadata_is_not_verified():
    assert not author_is_bernhard_palsson({})


def test_search_field_and_date_are_explicit():
    assert QUERY.startswith("AUTH:Palsson ")
    assert "FIRST_PDATE:[2023-01-01 TO 2026-10-06]" in QUERY
    assert "AUTH_NAME" not in QUERY and "AUTH_LAST_NAME" not in QUERY
