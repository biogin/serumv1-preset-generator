"""Finding a Preset in Serum's preset library by name (or taking a path as is)."""

from pathlib import Path


class PresetNotFound(LookupError):
    pass


class AmbiguousPreset(LookupError):
    def __init__(self, query: str, candidates: list[Path], library: Path) -> None:
        self.candidates = candidates
        listed = "\n".join(f"- {p.relative_to(library)}" for p in candidates)
        super().__init__(f"{len(candidates)} presets match {query!r}; which one?\n{listed}")


def find_preset(query: str, library: Path) -> Path:
    """The Preset `query` names: an existing .fxp path, else a name searched in `library`.

    Names match case-insensitively; an exact name wins over partial matches.
    Several partial matches raise AmbiguousPreset rather than guess.
    """
    as_path = Path(query).expanduser()
    if as_path.suffix.lower() == ".fxp" and as_path.is_file():
        return as_path
    wanted = query.lower().removesuffix(".fxp").strip()
    presets = sorted(library.rglob("*.fxp"))
    exact = [p for p in presets if p.stem.lower() == wanted]
    matches = exact or [p for p in presets if wanted in p.stem.lower()]
    if not matches:
        raise PresetNotFound(f"no preset named like {query!r} in {library}")
    if len(matches) > 1:
        raise AmbiguousPreset(query, matches, library)
    return matches[0]
