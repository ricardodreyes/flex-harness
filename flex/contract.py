"""Shapes every lane imports. Re-frozen at 12:55 p.m. after the coordinator correction; supersedes the 12:45 freeze.

Units. One step is one hour, so kW drawn for a step equals kWh. Work is measured in productive training kWh:
a job needing 4,200 kWh finishes after 4,200 kWh of productive power, which is 6 hours at the 700 kW ceiling.

Physics (owned by Lane A, identical for every policy, never editable by a candidate):
- The policy requests a training fraction in [0, 1] of TRAIN_CAP_KW.
- The safety controller limits training to the site cap during events: max(0, event_cap_kw - inference_kw).
  If inference alone exceeds the cap the hour is infeasible for the training controller and reported as such.
- Executed training power is the smallest of the request, the safety limit, and what the queue can absorb
  (remaining work plus outstanding warm-up), so power with no queued work behind it is never drawn or billed.
- Power goes to active jobs earliest-deadline first. A job that receives no power in an hour goes cold.
  Every start of a cold job owes restart_kwh of warm-up first: drawn and billed, but no progress. That is
  the simulated restart model; it consumes energy and, because power is capped, time.
- Idle draw of the training cluster is assumed zero; facility idle draw is inside inference_kw.
- A job is due at the start of hour deadline_h: it is on time iff its last work executes in an hour <= deadline_h - 1.
  Each hour t >= deadline_h - 1 that ends with work remaining counts one late job-hour, so a job finishing in
  hour done_h >= deadline_h has late_h = done_h - deadline_h + 1, and an unfinished job is late every hour from
  deadline_h - 1 to the end of the world.
- Arrivals stop at arrival_cutoff_h. The world continues through a settlement tail that covers the last
  deadline, priced with the real day-ahead prices for those hours. Work still unfinished at the end is
  reported as backlog and counts as a reliability failure.
"""

from datetime import datetime
from typing import Literal, NotRequired, TypedDict

Split = Literal["dev", "validation", "final"]
Status = Literal["candidate", "champion", "rejected", "retired"]
MissKind = Literal["late", "cap_intervention", "infeasible_hour", "unfinished"]
Op = Literal["<", "<=", ">", ">=", "=="]

TRAIN_CAP_KW = 700.0
COST_TOLERANCE = 0.01

DB = "flex"
FINAL_DB = "flex_final"


class Job(TypedDict):
    id: str
    arrive_h: int
    deadline_h: int
    work_kwh: float


class ScenarioSettings(TypedDict):
    """Protected. Set by the scenario manifest; a candidate that touches these is rejected."""
    restart_kwh: float
    event_cap_kw: float
    work_scale: float


class Scenario(TypedDict):
    id: str
    split: Split
    start: str
    arrival_days: int
    tail_h: int
    seed: int
    settings: ScenarioSettings
    note: str


class World(TypedDict):
    scenario: Scenario
    price: list[float]
    inference_kw: list[float]
    event: list[bool]
    jobs: list[Job]
    arrival_cutoff_h: int


class Obs(TypedDict, total=False):
    """Everything an operator knows at hour t. No future arrivals, no prices not yet published."""
    hour_of_day: int
    price: float
    price_pct: float
    event_now: bool
    event_in_h: int | None
    slack_h: float
    need_h: float
    queued_jobs: int
    running: bool
    restart_kwh: float


OBS_FIELDS: tuple[str, ...] = tuple(Obs.__annotations__)
BOOL_FIELDS = frozenset({"event_now", "running"})


class FieldRef(TypedDict):
    field: str
    times: float
    plus: float


class Condition(TypedDict):
    field: str
    op: Op
    value: float | bool | FieldRef


class Rule(TypedDict):
    when: list[Condition]
    power: float


class Policy(TypedDict):
    """The only thing a candidate edits. First matching rule wins; otherwise default_power.

    Bounds: <= 8 rules, <= 4 conditions per rule, <= 4096 bytes as JSON, conditions may only read
    fields listed in context_fields, and the policy only ever receives those fields.
    """
    context_fields: list[str]
    rules: list[Rule]
    default_power: float


class Totals(TypedDict):
    jobs_total: int
    jobs_completed: int
    jobs_late: int
    late_job_hours: int
    work_kwh: float
    productive_kwh: float
    overhead_kwh: float
    unfinished_kwh: float
    starts: int
    restarts: int
    cap_interventions: int
    infeasible_hours: int
    training_energy_cost: float
    total_energy_cost: float


class JobOutcome(TypedDict):
    id: str
    arrive_h: int
    deadline_h: int
    work_kwh: float
    done_h: int | None
    late_h: int
    starts: int
    overhead_kwh: float


class HourRecord(TypedDict):
    h: int
    ts: datetime
    price: float
    requested_kw: float
    executed_kw: float
    productive_kw: float
    overhead_kw: float
    inference_kw: float
    event: bool
    safety_limit_kw: float
    energy_cost: float


class Miss(TypedDict):
    run: str
    version: str
    scenario: str
    h: int
    ts: datetime
    kind: MissKind
    job: NotRequired[str]
    detail: str
    context: Obs


class SimResult(TypedDict):
    totals: Totals
    jobs: list[JobOutcome]
    hours: list[HourRecord]
    misses: list[Miss]
    diagnosis: list[str]


class EvalIdentity(TypedDict):
    evaluator_version: str
    manifest_sha256: str
    policy_sha256: str
    scenario_ids: list[str]


class Verdict(TypedDict):
    accepted: bool
    reasons: list[str]
    fixed: list[str]
    regressed: list[str]
    cost_delta_pct: float | None


class HarnessVersion(TypedDict):
    _id: str
    parent: str | None
    policy: Policy
    rationale: str
    predicted: str
    author: Literal["baseline", "control", "supervisor"]
    status: Status
    verdict: NotRequired[Verdict]
    identity: NotRequired[EvalIdentity]
    created_at: datetime


class Run(TypedDict):
    _id: str
    version: str
    scenario: str
    split: Split
    totals: Totals
    identity: EvalIdentity
    created_at: datetime
