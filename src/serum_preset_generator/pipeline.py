"""The design pipeline: Sound Description → Patch Recipe + Preset (ADR 0002).

A LangGraph graph: plan → draft → validate → (retry draft with the errors) → write.
No retrieval step in v1 (ADR 0003).
"""

import logging
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Literal, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from . import fxp
from .constraints import CONSTRAINTS, Constraint
from .constraints import check as check_constraint
from .parameter_reference import (
    DESIGNABLE_MOD_SOURCES,
    MOD_DESTINATIONS,
    parameters_by_module,
)
from .patch import Patch, Routing
from .validator import validate

log = logging.getLogger(__name__)

PRESET_NAME_LIMIT = 31  # Serum stores up to 31 characters


class Brief(BaseModel):
    """What `plan` makes of the Sound Description."""

    category: str = Field(description="Sound category, e.g. bass, lead, pad, pluck, FX")
    character: str = Field(description="Short description of the sound's character")
    language: Literal["en", "ru"] = Field(description="Language of the Sound Description")
    preset_name: str = Field(
        description="Short preset name in Latin letters (transliterate Russian), max 31 chars"
    )
    constraints: list[Constraint] = Field(
        default_factory=list,
        description="Hard requirements the Sound Description states; only these: "
        + "; ".join(f"{name} = {c.meaning}" for name, c in CONSTRAINTS.items()),
    )


class ParameterValue(BaseModel):
    name: str = Field(description="Parameter name exactly as in the Parameter Reference")
    value: float | str = Field(description="Number in the parameter's unit, or an option name")


class RoutingDraft(BaseModel):
    source: str = Field(description="A modulation source from the list, e.g. LFO 1, Env 2")
    destination: str = Field(description="A modulation destination from the list")
    amount: float = Field(description="-100 to 100 percent")
    bipolar: bool = Field(default=False, description="Modulate around the knob's position")


class Draft(BaseModel):
    """What `draft` proposes: the Patch values and the Patch Recipe explaining them."""

    values: list[ParameterValue]
    routings: list[RoutingDraft] = Field(
        default_factory=list, description="Modulation matrix, in slot order (max 32)"
    )
    wavetable_a: str | None = Field(description="Factory wavetable for Osc A, or null for default")
    wavetable_b: str | None = Field(description="Factory wavetable for Osc B, or null for default")
    recipe: str = Field(
        description="Step-by-step Patch Recipe, module by module, with the reasoning for each "
        "choice, then each routing (source → destination, amount) and why, in the Sound "
        "Description's language, using Serum's on-screen names"
    )


@dataclass(frozen=True)
class DesignConfig:
    output_dir: Path
    template: bytes
    max_retries: int = 3
    wavetables: frozenset[str] | None = None  # None: don't check wavetable names


@dataclass
class ValidationReport:
    passed: bool
    retries: int
    errors: list[str] = field(default_factory=list)
    # Each constraint from the brief, and whether the last draft kept it. Empty
    # when the last draft failed before its constraints could be checked.
    constraints: dict[Constraint, bool] = field(default_factory=dict)


@dataclass
class DesignResult:
    recipe: str | None
    preset_path: Path | None
    model: str
    validation: ValidationReport


class _State(TypedDict, total=False):
    description: str
    brief: Brief
    draft: Draft | None  # None when the response didn't match the Draft schema
    parse_error: str
    served_by: str  # the model that actually answered the latest draft
    errors: list[str]
    constraint_results: dict[Constraint, bool]
    draft_count: int
    preset_path: Path


def design_patch(
    sound_description: str, *, model: BaseChatModel, config: DesignConfig
) -> DesignResult:
    graph = _build_graph(model, config)
    state: _State = graph.invoke({"description": sound_description, "draft_count": 0, "errors": []})
    errors = state.get("errors", [])
    draft = state.get("draft")
    return DesignResult(
        recipe=draft.recipe if draft is not None and not errors else None,
        preset_path=state.get("preset_path"),
        model=state.get("served_by") or _model_name(model),
        validation=ValidationReport(
            passed=not errors,
            retries=state["draft_count"] - 1,
            errors=errors,
            constraints=state.get("constraint_results", {}),
        ),
    )


def _build_graph(model: BaseChatModel, config: DesignConfig):  # type: ignore[no-untyped-def]
    planner = model.with_structured_output(Brief, method="json_schema")
    drafter = model.with_structured_output(Draft, method="json_schema", include_raw=True)
    init = fxp.read(config.template)

    def plan(state: _State) -> _State:
        brief = planner.invoke(_plan_messages(state["description"]))
        assert isinstance(brief, Brief)
        log.info("plan: %s", brief.model_dump_json())
        return {"brief": brief}

    def draft(state: _State) -> _State:
        attempt = state["draft_count"] + 1
        out = drafter.invoke(
            _draft_messages(
                state["description"],
                state["brief"],
                state.get("errors", []),
                config.wavetables,
                init,
            )
        )
        assert isinstance(out, dict)
        served_by = out["raw"].response_metadata.get("model_name") or _model_name(model)
        proposal = out["parsed"]
        if not isinstance(proposal, Draft):
            log.info("draft %d (%s): unparseable: %s", attempt, served_by, out["parsing_error"])
            return {
                "draft": None,
                "parse_error": str(out["parsing_error"]),
                "draft_count": attempt,
                "served_by": served_by,
            }
        log.info(
            "draft %d (%s): %s", attempt, served_by, proposal.model_dump_json(exclude={"recipe"})
        )
        return {"draft": proposal, "draft_count": attempt, "served_by": served_by}

    def validate_draft(state: _State) -> _State:
        proposal = state["draft"]
        constraints = state["brief"].constraints
        if proposal is None:
            errors = [f"the response didn't match the required JSON schema: {state['parse_error']}"]
            return {"errors": errors, "constraint_results": {}}
        patch = _to_patch(proposal, "draft")
        errors = validate(patch, config.wavetables)
        results: dict[Constraint, bool] = {}
        if not errors:  # constraints only make sense for a Patch Serum can hold
            whole = replace(patch, params={**init.params, **patch.params})
            for constraint in constraints:
                problems = check_constraint(constraint, whole)
                results[constraint] = not problems
                errors += problems
        log.info("validate draft %d: %s", state["draft_count"], errors or "ok")
        return {"errors": errors, "constraint_results": results}

    def write(state: _State) -> _State:
        proposal = state["draft"]
        assert proposal is not None  # validation passed
        config.output_dir.mkdir(parents=True, exist_ok=True)
        path = _write_new_preset(
            config.output_dir,
            _safe_name(state["brief"].preset_name),
            lambda name: fxp.write(_to_patch(proposal, name), base=config.template),
        )
        log.info("write: %s", path)
        return {"preset_path": path}

    def after_validate(state: _State) -> Literal["write", "draft", "__end__"]:
        if not state["errors"]:
            return "write"
        if state["draft_count"] <= config.max_retries:
            return "draft"
        return "__end__"

    graph = StateGraph(_State)
    graph.add_node("plan", plan)
    graph.add_node("draft", draft)
    graph.add_node("validate", validate_draft)
    graph.add_node("write", write)
    graph.add_edge(START, "plan")
    graph.add_edge("plan", "draft")
    graph.add_edge("draft", "validate")
    graph.add_conditional_edges("validate", after_validate)
    graph.add_edge("write", END)
    return graph.compile()


_PLAN_SYSTEM = """\
You are a sound designer helping a producer program Xfer Serum 1.
Read the producer's Sound Description and summarise it as a brief: the sound's
category, its character, the language it is written in, and a short preset name
in Latin letters (transliterate if the description is in Russian).

Also list the constraints the description clearly demands, using only the
defined names ({constraint_names}). Leave the list empty if it demands none;
don't infer constraints it doesn't state."""

_DRAFT_SYSTEM = """\
You are a sound designer programming Xfer Serum 1 (v1.368). Turn the brief into
concrete parameter values. You may only set the parameters listed in the Parameter
Reference below, within their ranges or options; everything you don't set keeps
the Init value shown next to it.

Modules are switched off in Init unless shown as On. A module only sounds when
you switch it on: the filter needs "Filter On", Osc B "Osc B On", the sub
oscillator "Osc S On", noise "Osc N On", and each effect its "<name> Enable" in
FX Rack. Route an oscillator through the filter with its "Osc?>Fil" switch.
Tempo-synced knobs (LFO rates, delay times) take note values such as 1/4.

Movement comes from the modulation matrix: a routing sends a source (an LFO,
an envelope, a macro...) to a destination by an amount from -100 to 100 %.
An LFO or Env 2/3 does nothing until it is routed; Env 1 always shapes the
volume. For a wobble, route an LFO to Fil Cutoff; for a filter pluck, route
Env 2 to Fil Cutoff. Set "bipolar" to modulate both ways around the knob.

Also write the Patch Recipe: step-by-step instructions, module by module, that
a producer could follow in Serum's interface, with a short reason for each
choice, then a "Modulation" step listing each routing (source → destination,
amount) and what it does to the sound. Write it in the language of the Sound
Description, but keep Serum's
on-screen names (module, knob and option names) in English exactly as Serum
shows them.

Parameter Reference:
{reference}

Modulation sources: {mod_sources}

Modulation destinations: {mod_destinations}

Oscillator wavetables: use one of these factory wavetables, or null for Serum's default:
{wavetables}"""


def _plan_messages(description: str) -> list[BaseMessage]:
    system = _PLAN_SYSTEM.format(constraint_names=", ".join(CONSTRAINTS))
    return [SystemMessage(system), HumanMessage(f"Sound Description:\n{description}")]


def _draft_messages(
    description: str,
    brief: Brief,
    errors: list[str],
    wavetables: frozenset[str] | None,
    init: Patch,
) -> list[BaseMessage]:
    system = _DRAFT_SYSTEM.format(
        reference=_reference_text(init),
        mod_sources=", ".join(DESIGNABLE_MOD_SOURCES),
        mod_destinations=", ".join(MOD_DESTINATIONS),
        wavetables="\n".join(sorted(wavetables)) if wavetables else "(any factory wavetable)",
    )
    request = f"Sound Description:\n{description}\n\nBrief:\n{brief.model_dump_json(indent=2)}"
    if errors:
        request += "\n\nYour previous draft was rejected. Fix these problems:\n" + "\n".join(
            f"- {e}" for e in errors
        )
    # The system prompt is identical across calls, so cache it.
    return [
        SystemMessage([{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]),
        HumanMessage(request),
    ]


def _reference_text(init: Patch) -> str:
    """The designable parameters by module, with allowed values and Init values."""
    sections = []
    for module, params in parameters_by_module().items():
        designable = [p for p in params if p.designable]
        if designable:
            lines = [f"{module}:"] + [
                f"- {p.name}: {p.describe()} (Init: {p.format(init.params[p.name])})"
                for p in designable
            ]
            sections.append("\n".join(lines))
    return "\n\n".join(sections)


def _to_patch(draft: Draft, name: str) -> Patch:
    return Patch(
        name=name,
        params={s.name: s.value for s in draft.values},
        wavetable_a=draft.wavetable_a,
        wavetable_b=draft.wavetable_b,
        routings=[Routing(r.source, r.destination, r.amount, r.bipolar) for r in draft.routings],
    )


def _safe_name(proposed: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", proposed).encode("ascii", "ignore").decode()
    ascii_name = ascii_name.replace("/", "-")  # "1/8" stays readable as "1-8"
    cleaned = re.sub(r"[^A-Za-z0-9 _\-()\[\]]+", "", ascii_name).strip()
    return cleaned[:PRESET_NAME_LIMIT].strip() or "AI Patch"


def _write_new_preset(directory: Path, name: str, render: Callable[[str], bytes]) -> Path:
    """Write the Preset under `name`, or `name_2`, `name_3`, ... ; never overwrite.

    Names are trimmed so name plus suffix still fits Serum's limit. Files are
    created exclusively, so a file appearing between check and write is skipped.
    """
    n = 1
    while True:
        suffix = "" if n == 1 else f"_{n}"
        stem = name[: PRESET_NAME_LIMIT - len(suffix)].rstrip() + suffix
        path = directory / f"{stem}.fxp"
        try:
            with path.open("xb") as f:
                f.write(render(stem))
            return path
        except FileExistsError:
            n += 1


def _model_name(model: BaseChatModel) -> str:
    return str(
        getattr(model, "model", None) or getattr(model, "model_name", None) or model._llm_type
    )
