"""The design pipeline: Sound Description → Patch Recipe + Preset (ADR 0002).

A LangGraph graph: plan → draft → validate → (retry draft with the errors) → write.
No retrieval step in v1 (ADR 0003). The same graph makes Revisions: it starts
from an existing Preset instead of Init and drafts only the changes.
"""

import logging
import re
import unicodedata
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field, replace
from itertools import chain, count
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
    routings: list[RoutingDraft] | None = Field(
        default=None,
        description="The whole modulation matrix, in slot order (max 32). A list replaces "
        "the matrix; null means none (new design) or keep the current one (revision)",
    )
    wavetable_a: str | None = Field(
        description="Factory wavetable for Osc A; null means default (new design) or keep the "
        "current one (revision)"
    )
    wavetable_b: str | None = Field(
        description="Factory wavetable for Osc B; null means default (new design) or keep the "
        "current one (revision)"
    )
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
    # For a Revision: each change as "name: old → new", worked out by code.
    changes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _Job:
    """What the graph starts from and how it names its output."""

    producer_text: str  # the Sound Description, or feedback on a preset, as the model reads it
    base: bytes  # the Preset the result is written onto
    current: Patch  # the Patch before any change
    revising: bool
    routings_locked: bool  # an older build's Preset: its matrix can't be rewritten
    locked_parameters: frozenset[str]  # parameters the base Preset can't store
    output_name: Callable[[Brief], str]
    suffixes: Callable[[], Iterator[str]]  # tried in order until a free file name is found


class _State(TypedDict, total=False):
    producer_text: str
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
    job = _Job(
        producer_text=f"Sound Description:\n{sound_description}",
        base=config.template,
        current=fxp.read(config.template),
        revising=False,
        routings_locked=False,
        locked_parameters=frozenset(),
        output_name=lambda brief: _safe_name(brief.preset_name),
        suffixes=lambda: chain([""], (f"_{n}" for n in count(2))),
    )
    return _run(job, model, config)


def revise_patch(
    preset: Path, feedback: str, *, model: BaseChatModel, config: DesignConfig
) -> DesignResult:
    """A Revision of `preset`: a new Preset with `feedback` applied; `preset` is untouched."""
    base = preset.read_bytes()
    current = fxp.read(base)
    stem = re.sub(r"_v\d+$", "", preset.stem)
    job = _Job(
        producer_text=f"Feedback on the preset {current.name!r}:\n{feedback}",
        base=base,
        current=current,
        revising=True,
        routings_locked=not fxp.routings_writable(base),
        locked_parameters=frozenset(current.params) - fxp.writable_parameters(base),
        output_name=lambda _brief: _safe_name(stem),
        suffixes=lambda: (f"_v{n}" for n in count(2)),
    )
    return _run(job, model, config)


def _run(job: _Job, model: BaseChatModel, config: DesignConfig) -> DesignResult:
    graph = _build_graph(model, config, job)
    state: _State = graph.invoke(
        {"producer_text": job.producer_text, "draft_count": 0, "errors": []}
    )
    errors = state.get("errors", [])
    draft = state.get("draft")
    written = state.get("preset_path")
    return DesignResult(
        recipe=draft.recipe if draft is not None and not errors else None,
        preset_path=written,
        model=state.get("served_by") or _model_name(model),
        validation=ValidationReport(
            passed=not errors,
            retries=state["draft_count"] - 1,
            errors=errors,
            constraints=state.get("constraint_results", {}),
        ),
        changes=(
            _changes(job.current, fxp.read(written.read_bytes()))
            if job.revising and written is not None
            else []
        ),
    )


def _build_graph(model: BaseChatModel, config: DesignConfig, job: _Job):  # type: ignore[no-untyped-def]
    planner = model.with_structured_output(Brief, method="json_schema")
    drafter = model.with_structured_output(Draft, method="json_schema", include_raw=True)

    def plan(state: _State) -> _State:
        brief = planner.invoke(_plan_messages(state["producer_text"]))
        assert isinstance(brief, Brief)
        log.info("plan: %s", brief.model_dump_json())
        return {"brief": brief}

    def draft(state: _State) -> _State:
        attempt = state["draft_count"] + 1
        out = drafter.invoke(
            _draft_messages(
                state["brief"],
                state.get("errors", []),
                config.wavetables,
                job,
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
        changes = _changes_only(proposal, "draft")
        errors = validate(changes, config.wavetables)
        errors += [
            f"{name}: this Preset was saved by an older Serum build, which doesn't store "
            f"{name}. Leave it out"
            for name in changes.params
            if name in job.locked_parameters
        ]
        if job.routings_locked and changes.routings is not None:
            if changes.routings != job.current.routings:
                errors.append(
                    "routings: this Preset was saved by an older Serum build, so its "
                    "modulation matrix can't be rewritten. Set routings to null and change "
                    "only parameter values"
                )
        results: dict[Constraint, bool] = {}
        if not errors:  # constraints only make sense for a Patch Serum can hold
            whole = _whole(job, proposal, "draft")
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
            job.output_name(state["brief"]),
            job.suffixes(),
            lambda name: fxp.write(_to_write(job, proposal, name), base=job.base),
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
Read the producer's Sound Description (or their feedback on an existing preset)
and summarise it as a brief: the sound's
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


def _plan_messages(producer_text: str) -> list[BaseMessage]:
    system = _PLAN_SYSTEM.format(constraint_names=", ".join(CONSTRAINTS))
    return [SystemMessage(system), HumanMessage(producer_text)]


_REVISE_SYSTEM = """\
You are a sound designer revising an existing Xfer Serum 1 (v1.368) preset. The
producer gives feedback; change only what the feedback needs and keep the rest
of the sound as it is.

In "values", list only the parameters you change, with their new values. Every
parameter keeps the value shown as "now" unless you list it. A module only
sounds when it is switched on (Filter On, Osc B On, Osc S On, Osc N On, each
effect's "<name> Enable" in FX Rack). Tempo-synced knobs take note values such
as 1/4.

Leave "routings" null to keep the current modulation matrix; to change it,
give the whole new matrix. {routing_note}Leave a wavetable null to keep it.

Write the Patch Recipe as the list of changes only: for each one, the control,
its old and new value (old → new), and why it serves the feedback. Write it in
the language of the feedback, but keep Serum's on-screen names in English.

The preset now (Parameter Reference, with each parameter's current value):
{reference}

Current modulation matrix:
{routings}

Current wavetables: Osc A {wavetable_a}; Osc B {wavetable_b}

Modulation sources: {mod_sources}

Modulation destinations: {mod_destinations}

Factory wavetables:
{wavetables}"""

_LOCKED_ROUTINGS = (
    "This preset was saved by an older Serum build, so its modulation matrix can't "
    "be rewritten: keep routings null. "
)


def _draft_messages(
    brief: Brief,
    errors: list[str],
    wavetables: frozenset[str] | None,
    job: _Job,
) -> list[BaseMessage]:
    common = {
        "mod_sources": ", ".join(DESIGNABLE_MOD_SOURCES),
        "mod_destinations": ", ".join(MOD_DESTINATIONS),
        "wavetables": "\n".join(sorted(wavetables)) if wavetables else "(any factory wavetable)",
    }
    if job.revising:
        current = job.current
        system = _REVISE_SYSTEM.format(
            reference=_reference_text(current, "now", hidden=job.locked_parameters),
            routings="\n".join(f"- {r}" for r in current.routings or []) or "(none)",
            routing_note=_LOCKED_ROUTINGS if job.routings_locked else "",
            wavetable_a=current.wavetable_a or "(default)",
            wavetable_b=current.wavetable_b or "(default)",
            **common,
        )
    else:
        system = _DRAFT_SYSTEM.format(reference=_reference_text(job.current, "Init"), **common)
    request = f"{job.producer_text}\n\nBrief:\n{brief.model_dump_json(indent=2)}"
    if errors:
        request += "\n\nYour previous draft was rejected. Fix these problems:\n" + "\n".join(
            f"- {e}" for e in errors
        )
    # The system prompt is identical across calls, so cache it.
    return [
        SystemMessage([{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]),
        HumanMessage(request),
    ]


def _reference_text(values: Patch, label: str, hidden: frozenset[str] = frozenset()) -> str:
    """The designable parameters by module, with allowed values and `values`' values."""
    sections = []
    for module, params in parameters_by_module().items():
        designable = [p for p in params if p.designable and p.name not in hidden]
        if designable:
            lines = [f"{module}:"] + [
                f"- {p.name}: {p.describe()} ({label}: {p.format(values.params[p.name])})"
                for p in designable
            ]
            sections.append("\n".join(lines))
    return "\n\n".join(sections)


def _changes_only(draft: Draft, name: str) -> Patch:
    """Just what the draft proposes; routings None when it leaves the matrix alone."""
    return Patch(
        name=name,
        params={s.name: s.value for s in draft.values},
        wavetable_a=draft.wavetable_a,
        wavetable_b=draft.wavetable_b,
        routings=(
            None
            if draft.routings is None
            else [Routing(r.source, r.destination, r.amount, r.bipolar) for r in draft.routings]
        ),
    )


def _whole(job: _Job, draft: Draft, name: str) -> Patch:
    """The Patch as Serum will load it: the starting point with the draft applied."""
    changes = _changes_only(draft, name)
    keep = job.revising  # a design's nulls mean "default"; a revision's mean "keep"
    return Patch(
        name=name,
        params={**job.current.params, **changes.params},
        wavetable_a=changes.wavetable_a or (job.current.wavetable_a if keep else None),
        wavetable_b=changes.wavetable_b or (job.current.wavetable_b if keep else None),
        routings=(
            changes.routings
            if changes.routings is not None
            else (job.current.routings if keep else [])
        ),
    )


def _to_write(job: _Job, draft: Draft, name: str) -> Patch:
    """What to hand the writer: the changes, with wavetables and matrix resolved."""
    whole = _whole(job, draft, name)
    changes = _changes_only(draft, name)
    routings = changes.routings if changes.routings is not None else (None if job.revising else [])
    return replace(changes, wavetable_a=whole.wavetable_a, wavetable_b=whole.wavetable_b,
                   routings=routings)  # fmt: skip


def _changes(before: Patch, after: Patch) -> list[str]:
    """Each difference as "name: old → new", in Parameter Reference order."""
    lines = []
    for module_params in parameters_by_module().values():
        for p in module_params:
            if not p.designable:  # e.g. "Mod 1 amt", which mirrors a Routing listed below
                continue
            old, new = before.params[p.name], after.params[p.name]
            if old != new and not (
                isinstance(old, float) and isinstance(new, float) and abs(old - new) < 1e-4
            ):
                lines.append(f"{p.name}: {p.format(old)} → {p.format(new)}")
    for osc, old_table, new_table in (
        ("Osc A wavetable", before.wavetable_a, after.wavetable_a),
        ("Osc B wavetable", before.wavetable_b, after.wavetable_b),
    ):
        if old_table != new_table:
            lines.append(f"{osc}: {old_table or '(default)'} → {new_table or '(default)'}")
    old_routings, new_routings = before.routings or [], after.routings or []
    for slot in range(1, max(len(old_routings), len(new_routings)) + 1):
        old_r = old_routings[slot - 1] if slot <= len(old_routings) else None
        new_r = new_routings[slot - 1] if slot <= len(new_routings) else None
        if old_r == new_r:
            continue
        if (
            old_r
            and new_r
            and (old_r.source, old_r.destination) == (new_r.source, new_r.destination)
        ):
            lines.append(
                f"Routing {slot}: {old_r.source} → {old_r.destination} "
                f"{old_r.amount:g} % → {new_r.amount:g} %"
            )
        else:
            lines.append(f"Routing {slot}: {_routing_text(old_r)} → {_routing_text(new_r)}")
    return lines


def _routing_text(routing: Routing | None) -> str:
    return "(empty)" if routing is None else str(routing)


def _safe_name(proposed: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", proposed).encode("ascii", "ignore").decode()
    ascii_name = ascii_name.replace("/", "-")  # "1/8" stays readable as "1-8"
    cleaned = re.sub(r"[^A-Za-z0-9 _\-()\[\]]+", "", ascii_name).strip()
    return cleaned[:PRESET_NAME_LIMIT].strip() or "AI Patch"


def _write_new_preset(
    directory: Path, name: str, suffixes: Iterator[str], render: Callable[[str], bytes]
) -> Path:
    """Write the Preset as `name` + the first suffix whose file is free; never overwrite.

    Names are trimmed so name plus suffix still fits Serum's limit. Files are
    created exclusively, so a file appearing between check and write is skipped.
    """
    for suffix in suffixes:
        stem = name[: PRESET_NAME_LIMIT - len(suffix)].rstrip() + suffix
        path = directory / f"{stem}.fxp"
        if path.exists():
            continue
        data = render(stem)  # before creating the file: a failed render leaves nothing
        try:
            with path.open("xb") as f:
                f.write(data)
            return path
        except FileExistsError:
            continue
    raise AssertionError("suffixes are endless")


def _model_name(model: BaseChatModel) -> str:
    return str(
        getattr(model, "model", None) or getattr(model, "model_name", None) or model._llm_type
    )
