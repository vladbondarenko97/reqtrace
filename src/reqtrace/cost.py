"""What a run costs, what a bigger run would cost, and where the money goes. No AI.

Two kinds of numbers live here, and the dashboard keeps them visibly apart:

  measured   read straight from a run's llm_log.jsonl (tokens, seconds, and for Claude Code the
             `cost_usd_list` the CLI itself reports for each call).
  projected  a document-size what-if: take the measured token profile of the demo SRS and scale it
             to N pages. The rates come from pricing.json and are illustrative.

The projection scales a document's *content* tokens with its size, but charges the fixed system
prompt once per call (and a long document needs more calls, either because it is parsed in pieces or
because it no longer fits one context window). Scaling the whole prompt linearly would overstate cost.
"""
import json
import math
from collections import defaultdict
from pathlib import Path

PRICING = json.loads((Path(__file__).parent / "pricing.json").read_text())
TASKS = ("parse", "measure", "analyze", "draft")
TIERS = ("frontier", "local")


def _who(row: dict) -> str:
    """Which backend actually produced this row (a replayed row remembers who recorded it)."""
    return row.get("recorded_backend") or row["backend"]


def tier(backend: str) -> str:
    return "local" if backend == "omlx" else "frontier"


# ------------------------------------------------------------------------------------------ measured
def by_backend(rows: list[dict]) -> dict[str, dict]:
    """Totals per backend for one run: calls, tokens, seconds, and the CLI-reported cost if there is one."""
    out: dict[str, dict] = defaultdict(lambda: {"calls": 0, "input_tokens": 0, "output_tokens": 0,
                                                "latency_s": 0.0, "cost_usd_list": 0.0})
    for r in rows:
        o = out[_who(r)]
        o["calls"] += 1
        o["input_tokens"] += r["input_tokens"]
        o["output_tokens"] += r["output_tokens"]
        o["latency_s"] += r.get("recorded_latency_s", r["latency_s"])
        o["cost_usd_list"] += r.get("cost_usd_list") or 0.0
    return {k: {**v, "latency_s": round(v["latency_s"], 1), "cost_usd_list": round(v["cost_usd_list"], 4)} for k, v in out.items()}


def by_task(rows: list[dict]) -> dict[str, dict]:
    """Per task: who ran it, tokens and time. This is what the profile and the dashboard table use."""
    out: dict[str, dict] = {}
    for r in rows:
        o = out.setdefault(r["task"], {"backend": _who(r), "calls": 0, "input_tokens": 0, "output_tokens": 0, "latency_s": 0.0})
        o["calls"] += 1
        o["input_tokens"] += r["input_tokens"]
        o["output_tokens"] += r["output_tokens"]
        o["latency_s"] = round(o["latency_s"] + r.get("recorded_latency_s", r["latency_s"]), 1)
    return out


def list_cost(rows: list[dict]) -> float:
    return round(sum(r.get("cost_usd_list") or 0.0 for r in rows), 4)


def token_cost(tokens_in: float, tokens_out: float, which: str) -> float:
    """Dollars for a token volume at the illustrative rates."""
    if which == "local":
        return (tokens_in + tokens_out) / 1e6 * PRICING["local"]["usd_per_mtok"]
    p = PRICING["frontier_usd_per_mtok"]
    return tokens_in / 1e6 * p["input"] + tokens_out / 1e6 * p["output"]


def energy_cost(seconds: float) -> float:
    """Electricity for the seconds the local machine spent generating."""
    loc = PRICING["local"]
    return seconds / 3600 * loc["machine_watts"] / 1000 * loc["usd_per_kwh"]


# ----------------------------------------------------------------------------------------- projected
def profile(rows: list[dict]) -> dict:
    """Split a run's tokens into content (grows with the document) and overhead (the system prompt, paid per call)."""
    tasks: dict[str, dict] = {}
    for r in rows:
        if r["attempt"] != 1 or r["task"] not in TASKS:  # first attempts only: a failed attempt still shows the real token volume
            continue
        total_chars = r["system_chars"] + r["user_chars"]
        content = r["input_tokens"] * r["user_chars"] / total_chars
        t = tasks.setdefault(r["task"], {"content_in": 0.0, "sys_in": 0.0, "out": 0.0, "calls": 0})
        t["content_in"] += content
        t["sys_in"] += r["input_tokens"] - content
        t["out"] += r["output_tokens"]
        t["calls"] += 1
    for t in tasks.values():  # system prompt tokens for a single call
        t["sys_in"] = t["sys_in"] / t["calls"]
    return {k: {m: round(v, 1) for m, v in t.items()} for k, t in tasks.items()}


def project(prof: dict, pages: int, routing: dict[str, str]) -> dict:
    """Cost of one run on a `pages`-page SRS, given routing = {task: 'frontier' | 'local'}.

    Returns per-task token volumes, dollars and, for the local tier, the electricity cost.
    """
    a = PRICING["assumptions"]
    scale = pages * a["tokens_per_page"] / prof["parse"]["content_in"]  # measured doc tokens -> target doc tokens
    tasks, total = {}, 0.0
    for name in TASKS:
        t = prof[name]
        content_in = t["content_in"] * scale
        # parse is cut into pieces (calls grow with the document); the rest need more calls only once they overflow a window
        calls = t["calls"] * scale if name == "parse" else max(1, math.ceil(content_in / a["context_window_tokens"]))
        tin, tout = content_in + calls * t["sys_in"], t["out"] * scale
        which = routing[name]
        usd = token_cost(tin, tout, which)
        tasks[name] = {"tier": which, "calls": round(calls), "input_tokens": round(tin), "output_tokens": round(tout), "usd": round(usd, 2)}
        total += usd
    return {"pages": pages, "tasks": tasks, "usd": round(total, 2)}


SCENARIOS = {
    "All frontier": {"parse": "frontier", "measure": "frontier", "analyze": "frontier", "draft": "frontier"},
    "Hybrid (parse on local model)": {"parse": "local", "measure": "frontier", "analyze": "frontier", "draft": "frontier"},
}


def scenarios(prof: dict, pages: int) -> dict[str, dict]:
    return {name: project(prof, pages, routing) for name, routing in SCENARIOS.items()}
