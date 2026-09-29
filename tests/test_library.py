import pytest

from serum_preset_generator.library import AmbiguousPreset, PresetNotFound, find_preset


@pytest.fixture
def library(tmp_path):
    for relative in ("Bass/808 Boom.fxp", "Bass/808 Boom Soft.fxp", "Leads/LD Glass.fxp"):
        path = tmp_path / relative
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(b"")
    (tmp_path / "Bass/readme.txt").write_text("not a preset")
    return tmp_path


def test_an_exact_name_wins_over_partial_matches(library):
    assert find_preset("808 boom", library) == library / "Bass/808 Boom.fxp"


def test_a_partial_name_finds_the_only_match(library):
    assert find_preset("glass", library) == library / "Leads/LD Glass.fxp"


def test_several_matches_are_listed_not_guessed(library):
    with pytest.raises(AmbiguousPreset) as raised:
        find_preset("808", library)

    assert raised.value.candidates == [
        library / "Bass/808 Boom Soft.fxp",
        library / "Bass/808 Boom.fxp",
    ]
    assert "808 Boom Soft" in str(raised.value) and "Bass/808 Boom.fxp" in str(raised.value)


def test_no_match_says_where_it_looked(library):
    with pytest.raises(PresetNotFound, match=str(library)):
        find_preset("kick", library)


def test_a_path_is_used_as_is(library, tmp_path):
    elsewhere = tmp_path / "somewhere" / "My Bass.fxp"
    elsewhere.parent.mkdir()
    elsewhere.write_bytes(b"")

    assert find_preset(str(elsewhere), library) == elsewhere
