"""Smoke tests: an in-process MCP client talks to the server, which wraps the pipeline."""

from dataclasses import replace

import anyio
from fake_model import ScriptedModel
from mcp import Client
from test_design_patch import brief, valid_draft

from serum_preset_generator.mcp_server import build_server
from serum_preset_generator.pipeline import ParameterValue


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


def test_the_server_offers_one_tool_design_patch(config):
    tools = list_tools(build_server(model=ScriptedModel([]), config=config))

    assert [t.name for t in tools] == ["design_patch"]
    assert "sound_description" in tools[0].input_schema["properties"]


def test_design_patch_returns_the_recipe_and_where_the_preset_is(config):
    model = ScriptedModel([brief(constraints=["no_reverb"]), valid_draft()])

    result = call_tool(
        build_server(model=model, config=config),
        "design_patch",
        {"sound_description": "aggressive cyberpunk bass"},
    )

    text = text_of(result)
    assert not result.is_error
    assert valid_draft().recipe in text
    assert str(config.output_dir / "Cyber Bass.fxp") in text
    assert "User → AI" in text  # where to find it in Serum's browser
    assert "no reverb ✓" in text
    assert "scripted" in text  # the model that answered


def test_a_failed_design_is_a_readable_tool_result_not_a_crash(config):
    bad = valid_draft(values=[ParameterValue(name="Nope", value=1.0)])
    model = ScriptedModel([brief(), bad])

    result = call_tool(
        build_server(model=model, config=replace(config, max_retries=0)),
        "design_patch",
        {"sound_description": "bass"},
    )

    assert result.is_error
    assert "Nope" in text_of(result)


def test_a_setup_problem_comes_back_with_its_reason(config, monkeypatch):
    # No model injected: the server builds one from the environment, which is wrong.
    monkeypatch.setenv("SERUM_GEN_PROVIDER", "ollama")

    result = call_tool(build_server(config=config), "design_patch", {"sound_description": "x"})

    assert result.is_error
    assert "SERUM_GEN_PROVIDER" in text_of(result)
