# make demo            live run via your Claude Code login (no API key needed)
# make demo MOCK=1     replay recorded fixtures (no model, no key)
# make demo BACKEND=anthropic   use the Anthropic API (needs ANTHROPIC_API_KEY, pip install -e '.[anthropic]')
BACKEND ?= claude-code
FLAGS = $(if $(MOCK),--mock,--backend $(BACKEND))
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

.PHONY: install demo test
