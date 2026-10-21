"""SRS markdown -> list[Requirement].

The document is cut into small pieces and each piece is transcribed on its own. That is what makes a
100-200 page SRS workable on a small local model: every call has a short input, a short output, and
a precise check (the IDs that come back must be exactly the IDs in the piece). Pieces are independent,
so they run in parallel.
"""
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .models import MeasureOut, ParseOut, Requirement

REQ_HEADING = re.compile(r"^### (NP-REQ-\d{3})\b", re.MULTILINE)
CHUNK_REQS = 7   # requirements per model call
WORKERS = 4      # pieces in flight at once


def split_srs(md: str, size: int = CHUNK_REQS) -> list[str]:
    """Cut the document just before each requirement heading, then group `size` requirements per piece.
    Anything before the first requirement (title, intro) is dropped: the parse prompt does not need it."""
    starts = [m.start() for m in REQ_HEADING.finditer(md)] + [len(md)]
    sections = [md[a:b] for a, b in zip(starts, starts[1:], strict=False)]
    return ["".join(sections[i : i + size]) for i in range(0, len(sections), size)]


def parse_srs(llm, srs_path: Path) -> list[Requirement]:
    pieces = split_srs(Path(srs_path).read_text())

    def parse_piece(piece: str) -> list[Requirement]:
        expected = REQ_HEADING.findall(piece)

        def same_ids(out: ParseOut):  # the model must not drop, add or reorder requirements
            got = [r.id for r in out.requirements]
            if got != expected:
                raise ValueError(f"requirement IDs {got} do not match the document headings {expected}")

        return llm.ask("parse", piece, ParseOut, check=same_ids).requirements

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        return [r for part in pool.map(parse_piece, pieces) for r in part]


def parse_sys_ids(path: Path) -> set[str]:
    """System requirements are a flat list; a regex is enough (no AI needed)."""
    return set(re.findall(r"^- \*\*(NP-SYS-\d{3})\*\*", Path(path).read_text(), re.MULTILINE))


MEASURE_CHUNK = 40  # requirements per measurability call


def judge_measurability(llm, reqs: list[Requirement]) -> list[Requirement]:
    """Mark requirements that no tester could verify. This is a judgement, so it goes to the strong model
    (a small local model transcribes faithfully but misjudged this in testing, see DECISIONS D-17). The input
    is just id + text and the output is a short list of IDs, so the call is cheap."""
    def judge(group: list[Requirement]) -> set[str]:
        known = {r.id for r in group}

        def only_known(out: MeasureOut):
            if set(out.not_measurable) - known:
                raise ValueError(f"unknown requirement IDs {sorted(set(out.not_measurable) - known)}")

        payload = json.dumps([{"id": r.id, "text": r.text} for r in group], indent=1)
        return set(llm.ask("measure", payload, MeasureOut, check=only_known).not_measurable)

    groups = [reqs[i : i + MEASURE_CHUNK] for i in range(0, len(reqs), MEASURE_CHUNK)]
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        bad = set().union(*pool.map(judge, groups))
    return [r.model_copy(update={"measurable": r.id not in bad}) for r in reqs]
