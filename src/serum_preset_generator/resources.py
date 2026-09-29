from importlib.resources import files


def default_template() -> bytes:
    """The owner's Init preset from Serum 1.368, shipped with the package."""
    return files("serum_preset_generator").joinpath("templates/init.fxp").read_bytes()
