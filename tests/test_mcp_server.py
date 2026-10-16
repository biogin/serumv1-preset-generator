"""Smoke tests: an in-process MCP client talks to the server, which wraps `design`."""

import anyio
from mcp import Client
from test_edit_patch import BOOM

from serum_preset_generator import fxp
from serum_preset_generator.mcp_server import build_server
from serum_preset_generator.resources import default_template


def list_tools(server):
    async def session():
        async with Client(server) as client:
            return (await client.list_tools()).tools

    return anyio.run(session)


def call_tool(server, name, arguments):
    async def session():
        async with Client(server) as client:
            return await client.call_tool(name, arguments)

    return anyio.run(session)


def text_of(result):
    return "\n".join(block.text for block in result.content if block.type == "text")


def boom_library(tmp_path):
    library = tmp_path / "library" / "Bass"
    library.mkdir(parents=True)
    for name in ("808 Boom", "808 Boom Soft"):
        (library / f"{name}.fxp").write_bytes(fxp.write(BOOM, base=default_template()))
    return library.parent


def test_the_server_offers_the_four_tools(config):
    tools = {t.name: t for t in list_tools(build_server(config=config))}

    assert sorted(tools) == ["describe_preset", "edit_patch", "list_parameters", "write_patch"]
    assert "patch" in tools["write_patch"].input_schema["properties"]
    assert {"preset", "changes"} <= set(tools["edit_patch"].input_schema["properties"])


def test_write_patch_returns_the_summary_and_where_the_preset_is(config):
    result = call_tool(
        build_server(config=config),
        "write_patch",
        {
            "patch": {"name": "Cyber Bass", "params": {"Fil Cutoff": 180.0}},
            "constraints": ["no_reverb"],
        },
    )

    text = text_of(result)
    assert not result.is_error
    assert "Fil Cutoff: 180" in text
    assert str(config.output_dir / "Cyber Bass.fxp") in text
    assert "User → AI" in text  # where to find it in Serum's browser
    assert "no reverb ✓" in text


def test_write_patch_accepts_a_routing(config):
    result = call_tool(
        build_server(config=config),
        "write_patch",
        {
            "patch": {
                "name": "Routed",
                "params": {},
                "routings": [{"source": "LFO 1", "destination": "Fil Cutoff", "amount": 15.0}],
            }
        },
    )

    assert not result.is_error
    assert "LFO 1" in text_of(result) and "Fil Cutoff" in text_of(result)


def test_an_invalid_patch_is_a_readable_tool_result_not_a_crash(config):
    result = call_tool(
        build_server(config=config),
        "write_patch",
        {"patch": {"name": "x", "params": {"Nope": 1.0}}},
    )

    assert result.is_error
    assert "Nope" in text_of(result)


def test_edit_patch_returns_the_changes(config, tmp_path):
    server = build_server(config=config, library=boom_library(tmp_path))

    result = call_tool(
        server,
        "edit_patch",
        {"preset": "808 boom", "changes": {"params": {"Dist_Drv": 55.0}}},
    )

    assert not result.is_error
    assert "Dist_Drv: 20 % → 55 %" in text_of(result)
    assert "808 Boom_v2.fxp" in text_of(result)


def test_edit_patch_asks_which_preset_when_ambiguous(config, tmp_path):
    server = build_server(config=config, library=boom_library(tmp_path))

    result = call_tool(server, "edit_patch", {"preset": "808", "changes": {"params": {}}})

    assert result.is_error
    assert "808 Boom Soft" in text_of(result)


def test_edit_patch_reports_a_broken_constraint_not_just_an_exception(config, tmp_path):
    server = build_server(config=config, library=boom_library(tmp_path))

    result = call_tool(
        server,
        "edit_patch",
        {
            "preset": "808 boom",
            "changes": {"params": {"Dist_Drv": 60.0}},
            "constraints": ["clean_sub"],
        },
    )

    assert result.is_error
    assert "clean sub" in text_of(result)


def test_edit_patch_reports_a_missing_preset_instead_of_crashing(config, tmp_path):
    server = build_server(config=config, library=boom_library(tmp_path))

    result = call_tool(
        server, "edit_patch", {"preset": "Nonexistent Pad", "changes": {"params": {}}}
    )

    assert result.is_error
    assert "Nonexistent Pad" in text_of(result)


def test_describe_preset_reports_a_missing_preset_instead_of_crashing(config, tmp_path):
    server = build_server(config=config, library=boom_library(tmp_path))

    result = call_tool(server, "describe_preset", {"preset": "Nonexistent Pad"})

    assert result.is_error
    assert "Nonexistent Pad" in text_of(result)


def test_describe_preset_asks_which_preset_when_ambiguous(config, tmp_path):
    server = build_server(config=config, library=boom_library(tmp_path))

    result = call_tool(server, "describe_preset", {"preset": "808"})

    assert result.is_error
    assert "808 Boom Soft" in text_of(result)


def test_write_patch_reports_an_unexpected_failure_instead_of_crashing(config, tmp_path):
    """A write-time failure (bad config, full disk, permission error, ...) must

    reach the caller as a readable tool error, never a silent write-nowhere
    or a crashed MCP connection — that's exactly how the serum_root
    misconfiguration bug went unnoticed.
    """
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory")
    broken_config = config.__class__(
        output_dir=blocker / "AI",
        template=config.template,
        wavetables=config.wavetables,
    )

    result = call_tool(
        build_server(config=broken_config),
        "write_patch",
        {"patch": {"name": "x", "params": {}}},
    )

    assert result.is_error
    assert "write_patch failed" in text_of(result)


def test_edit_patch_reports_an_unexpected_write_failure_instead_of_crashing(config, tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory")
    broken_config = config.__class__(
        output_dir=blocker / "AI",
        template=config.template,
        wavetables=config.wavetables,
    )
    library = boom_library(tmp_path)

    result = call_tool(
        build_server(config=broken_config, library=library),
        "edit_patch",
        {"preset": "808 boom", "changes": {"params": {}}},
    )

    assert result.is_error
    assert "edit_patch failed" in text_of(result)


def test_list_parameters_lists_the_designable_reference(config):
    result = call_tool(build_server(config=config), "list_parameters", {})

    text = text_of(result)
    assert not result.is_error
    assert "FX Distortion:" in text and "- Dist_Mode: one of: Tube, SoftClip" in text
    assert "- Filter On: one of: Off, On (Init: Off)" in text
    assert "Mod 1 amt" not in text  # the mod matrix arrives with ticket 05
    assert "Analog/PWM Juno.wav" in text


def test_describe_preset_reads_an_existing_preset(config, tmp_path):
    server = build_server(config=config, library=boom_library(tmp_path))

    result = call_tool(server, "describe_preset", {"preset": "808 boom soft"})

    text = text_of(result)
    assert not result.is_error
    assert "Dist_Drv: 20 %" in text
    assert "Env 2 → Sub Osc Level 30 %" in text
