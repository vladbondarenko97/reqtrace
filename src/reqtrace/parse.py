"""SRS markdown -> list[Requirement] (LLM, schema-validated, one retry with the error fed back)."""
import re
from pathlib import Path

from .llm import LLM
from .models import ParseOut, Requirement

REQ_HEADING = re.compile(r"^### (NP-REQ-\d{3})\b", re.MULTILINE)


def parse_srs(llm: LLM, srs_path: Path) -> list[Requirement]:
    md = Path(srs_path).read_text()
    expected = REQ_HEADING.findall(md)

    def same_ids(out: ParseOut):  # cheap cross-check: the model must not drop, add or reorder requirements
        got = [r.id for r in out.requirements]
        if got != expected:
            raise ValueError(f"requirement IDs {got} do not match the document headings {expected}")

    return llm.ask("parse", md, ParseOut, check=same_ids).requirements


def parse_sys_ids(path: Path) -> set[str]:
    """System requirements are a flat list; a regex is enough (no AI needed)."""
    return set(re.findall(r"^- \*\*(NP-SYS-\d{3})\*\*", Path(path).read_text(), re.MULTILINE))
