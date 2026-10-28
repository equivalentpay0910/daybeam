"""Shared data formats for DayBeam. Everyone imports from here so the pieces fit.
If you need to change a format, tell the group first (it affects all three parts)."""
from typing import Literal, Optional
from pydantic import BaseModel, Field

Time = str  # "HH:MM", 24-hour clock, e.g. "09:30"


class Place(BaseModel):
    """One row of data/places.csv (Kami)."""
    id: str                      # e.g. "P_cafe_07"
    name: str
    category: str                # e.g. "farmers_market", "restaurant", "cafe", "library", "park", "home"
    lat: float
    lon: float
    price_usd: float = 0.0       # typical cost of a visit (0 for free places)
    open: Time = "00:00"
    close: Time = "23:59"


class StopRequest(BaseModel):
    """One thing the user wants to do. Either a fixed place or 'any place of this category'."""
    id: str                                      # "s1", "s2", ...
    kind: Literal["fixed", "flexible"]
    place_id: Optional[str] = None               # required if kind == "fixed"
    category: Optional[str] = None               # required if kind == "flexible"
    max_price_usd: Optional[float] = None        # optional price cap for this stop
    window: Optional[tuple[Time, Time]] = None   # must ARRIVE within this window, e.g. ("09:00","12:00")
    duration_min: int = 30                       # time spent at the stop


class Task(BaseModel):
    """A planning request. Kami writes 30-50 of these in data/tasks/*.json."""
    id: str
    request_text: str                 # the natural-language version shown to the LLM
    start_place_id: str               # usually a "home" place
    end_place_id: str                 # usually the same home
    day_start: Time                   # leave the start place at this time
    day_end: Time                     # must be back at the end place by this time
    budget_usd: float                 # total spend across all stops
    max_drive_min: float              # total driving time cap
    stops: list[StopRequest]          # order NOT fixed; the planner chooses the order
    difficulty: Literal["easy", "medium", "hard"] = "medium"


class PlannedStop(BaseModel):
    stop_id: str                      # which StopRequest this fulfils
    place_id: str                     # which actual place (for flexible stops, the planner picks)


class Plan(BaseModel):
    """What every planner returns. Only the ORDER and the PLACE choices.
    Arrival times are NOT written by the LLM: check_plan() computes them with route()."""
    task_id: str
    stops: list[PlannedStop]


class Violation(BaseModel):
    rule: Literal["missing_stop", "wrong_category", "unknown_place", "closed",
                  "window", "over_budget", "over_drive_cap", "late_end", "price_cap"]
    stop_id: Optional[str] = None
    detail: str


class CheckResult(BaseModel):
    """What check_plan() returns (Kami)."""
    passed: bool
    violations: list[Violation] = Field(default_factory=list)
    total_drive_min: float = 0.0
    total_cost_usd: float = 0.0
    end_time: Optional[Time] = None
    timeline: list[dict] = Field(default_factory=list)   # [{stop_id, place_id, arrive, depart}] for the app


class SearchNode(BaseModel):
    """One node in the planner's search tree (for David's tree view)."""
    node_id: int
    parent_id: Optional[int] = None
    depth: int
    partial_plan: list[PlannedStop]
    score: Optional[float] = None     # LLM's 1-10 score, if this planner scores
    kept: bool = True                 # False = pruned by beam search


class PlanResult(BaseModel):
    """What plan() returns (Esha). The eval runner logs these fields."""
    plan: Optional[Plan]              # None if the planner failed to produce a valid-format plan
    method: Literal["one_shot", "react", "beam", "bfs", "mcts"]
    search_log: list[SearchNode] = Field(default_factory=list)
    llm_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    seconds: float = 0.0
    error: Optional[str] = None
