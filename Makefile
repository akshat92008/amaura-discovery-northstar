.PHONY: help test test-unit test-stage4 test-stage2 test-flaws reproduce-stage2 reproduce-stage3-closure clean

PYTHON ?= python3
PYTEST ?= pytest

help:
	@echo "Amaura Labs — Offline Reproduction & Verification Suite"
	@echo "=========================================================="
	@echo "All default targets are strictly offline, deterministic, and make ZERO network calls."
	@echo ""
	@echo "Available targets:"
	@echo "  make test                      Run all safe offline unit and regression tests (118 tests)"
	@echo "  make test-stage4               Run Stage 4 offline regression and safety tests (109 tests)"
	@echo "  make test-stage2               Run Stage 2 offline regression tests (29 tests)"
	@echo "  make test-flaws                Run regression test demonstrating the PFSP penalty flaw"
	@echo "  make reproduce-stage2          Reproduce Stage 2 statistical analysis from raw data (0 API calls)"
	@echo "  make reproduce-stage3-closure  Reproduce Stage 3 closure recomputation from raw data (0 API calls)"
	@echo "  make clean                     Remove local __pycache__ and test artifacts"

test:
	$(PYTEST) tests/ -v

test-stage4:
	$(PYTEST) tests/test_stage4*.py -v

test-stage2:
	$(PYTEST) stage2/tests/ -v

test-flaws:
	$(PYTEST) tests/test_pfsp_penalty_flaw.py -v

reproduce-stage2:
	$(PYTHON) reproduce_stage2_analysis.py

reproduce-stage3-closure:
	$(PYTHON) stage3/audit/closure/recompute_closure.py

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
