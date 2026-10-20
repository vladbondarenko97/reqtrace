# make demo            live run via your Claude Code login (no API key needed)
# make demo MOCK=1     replay recorded fixtures (no model, no key)
# make demo BACKEND=anthropic   use the Anthropic API (needs ANTHROPIC_API_KEY, pip install -e '.[anthropic]')
BACKEND ?= claude-code
FLAGS = $(if $(MOCK),--mock,--backend $(BACKEND))
EVALFLAGS = $(if $(MOCK),--mock,)
PY ?= python

install:
	$(PY) -m pip install -q -e '.[dev]'

demo:
	reqtrace run $(FLAGS) --out out
	@echo; echo "=== findings ==="; sed -n '1,200p' out/findings.md
	@echo; echo "=== trace matrix (head) ==="; head -12 out/trace_matrix.csv
	@echo; echo "=== draft protocol (head) ==="; sed -n '1,22p' out/draft_protocol.md
	@echo; $(PY) evals/run_eval.py $(EVALFLAGS)

test:
	ruff check . && pytest -q

.PHONY: install demo test
