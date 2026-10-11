"""Shapes every lane imports. Frozen at 12:45; change only after telling all lanes."""

from datetime import datetime
from typing import Literal, NotRequired, TypedDict

Split = Literal["train", "gate", "test"]
Status = Literal["candidate", "champion", "rejected"]
MissKind = Literal["late", "over_cap", "missed_event"]

TRAIN_CAP_KW = 700.0
LATE_PENALTY = 400.0
OVER_CAP_PENALTY_PER_KWH = 2.0
EVENT_PAYMENT = 3000.0

SPLITS: dict[Split, tuple[str, str]] = {
    "train": ("2026-04-01", "2026-08-15"),
    "gate": ("2026-08-16", "2026-08-29"),
    "test": ("2026-08-30", "2026-09-28"),
}
TEST_DB = "flex_holdout"
DB = "flex"


class Job(TypedDict):
    id: str
    arrive_h: int
    deadline_h: int
    work_kwh: float


class World(TypedDict):
    split: Split
    start: str
    price: list[float]
    inference_kw: list[float]
    event: list[bool]
    event_cap_kw: float
    jobs: list[Job]


class Obs(TypedDict, total=False):
    hour_of_day: int
    price: float
    prices_ahead: list[float]
    event_now: bool
    event_in_h: int | None
    slack_h: float
    need_h: float
    inference_kw: float
    recent_misses: list[str]


OBS_FIELDS: tuple[str, ...] = tuple(Obs.__annotations__)


class Guardrails(TypedDict):
    max_train_frac: float
    zero_during_event: bool


class Totals(TypedDict):
    energy_cost: float
    late_h: int
    missed_events: int
    over_cap_kwh: float
    net: float


class HarnessVersion(TypedDict):
    _id: str
    parent: str | None
    code: str
    context_fields: list[str]
    guardrails: Guardrails
    tools: list[str]
    rationale: str
    predicted: str
    scores: dict[str, Totals]
    status: Status
    created_at: datetime


class HourRecord(TypedDict):
    h: int
    ts: datetime
    price: float
    train_kw: float
    inference_kw: float
    event: bool
    cost: float


class Miss(TypedDict):
    run: str
    version: str
    split: Split
    h: int
    ts: datetime
    kind: MissKind
    context: Obs
    post_mortem: NotRequired[str]


class Run(TypedDict):
    _id: str
    version: str
    split: Split
    totals: Totals
    created_at: datetime


class SimResult(TypedDict):
    totals: Totals
    hours: list[HourRecord]
    misses: list[Miss]
