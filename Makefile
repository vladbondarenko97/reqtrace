# make demo            live run via your Claude Code login (no API key needed)
# make demo MOCK=1     replay recorded fixtures (no model, no key)
# make demo HYBRID=1   parse on the local oMLX model, judgement on Claude (needs oMLX running)
# make demo BACKEND=omlx        everything on the local model
# make demo BACKEND=anthropic   use the Anthropic API (needs ANTHROPIC_API_KEY, pip install -e '.[anthropic]')
# make compare         run all three routings live, score each into evals/ledger.jsonl, rebuild the dashboard
# make dashboard       rebuild docs/dashboard.html from evals/ledger.jsonl
BACKEND ?= claude-code
FLAGS = $(if $(MOCK),--mock,--backend $(BACKEND) $(if $(HYBRID),--hybrid))
EVALFLAGS = $(if $(MOCK),--mock,)
PY ?= python

install:
	$(PY) -m pip install -q -e '.[dev]'

# PAUSE=n clears the screen and waits n seconds between stages (used to record docs/demo.gif).
PAUSE ?= 0
STAGE = @$(if $(filter-out 0,$(PAUSE)),sleep $(PAUSE); clear;,)

demo:
	reqtrace run $(FLAGS) --out out
	$(STAGE) echo "=== findings (out/findings.md) ==="; cat out/findings.md
	$(STAGE) echo "=== trace matrix (out/trace_matrix.csv) ==="; cut -c1-110 out/trace_matrix.csv | head -22
	$(STAGE) echo "=== draft protocol (out/draft_protocol.md) ==="; sed -n '1,16p' out/draft_protocol.md | cut -c1-200; echo ...; grep -A12 "^## Retired" out/draft_protocol.md | cut -c1-170
	$(STAGE) echo "=== eval ==="; $(PY) evals/run_eval.py $(EVALFLAGS)

test:
	ruff check . && pytest -q

dashboard:
	reqtrace dashboard

# Three live runs of the same pipeline, differing only in routing. Frontier-only is the reference
# the other two are scored against (parse fidelity). Takes several minutes: the local model is slow on long outputs.
compare:
	reqtrace run --out out/frontier
	$(PY) evals/run_eval.py --out out/frontier --label "Frontier only" --note "compare: all steps on the frontier model"
	reqtrace run --hybrid --out out/hybrid
	$(PY) evals/run_eval.py --out out/hybrid --label "Hybrid" --reference-out out/frontier --note "compare: parse on local model"
	reqtrace run --backend omlx --out out/local
	-$(PY) evals/run_eval.py --out out/local --label "Local only" --reference-out out/frontier --note "compare: all steps on local model"
	reqtrace dashboard

.PHONY: install demo test dashboard compare
