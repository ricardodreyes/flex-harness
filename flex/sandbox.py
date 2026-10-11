import builtins
import math
from typing import Callable

from flex.contract import Obs


class PolicyError(Exception):
    pass


def cheapest_hours(prices: list[float], n: int) -> list[int]:
    return sorted(sorted(range(len(prices)), key=prices.__getitem__)[:n])


def hours_until_price_below(prices: list[float], threshold: float) -> int | None:
    return next((i for i, p in enumerate(prices) if p < threshold), None)


TOOLS: dict[str, Callable] = {f.__name__: f for f in (cheapest_hours, hours_until_price_below)}

SAFE_BUILTINS = {n: getattr(builtins, n) for n in
                 "min max abs sum len sorted range round float int bool enumerate zip any all list dict tuple".split()}


def compile_policy(code: str, tools: list[str]) -> Callable[[Obs], float]:
    unknown = [t for t in tools if t not in TOOLS]
    if unknown:
        raise PolicyError(f"unknown tools: {unknown}")
    env = {"__builtins__": SAFE_BUILTINS, "math": math, **{t: TOOLS[t] for t in tools}}
    try:
        exec(code, env)
    except Exception as e:
        raise PolicyError(f"compile: {type(e).__name__}: {e}") from e
    decide = env.get("decide")
    if not callable(decide):
        raise PolicyError("no decide(obs) defined")

    def call(obs: Obs) -> float:
        try:
            out = decide(obs)
        except Exception as e:
            raise PolicyError(f"decide: {type(e).__name__}: {e}") from e
        if not isinstance(out, (int, float)) or not math.isfinite(out):
            raise PolicyError(f"decide returned non-number: {out!r}")
        return float(out)

    return call
