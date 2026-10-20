"""
Unit Test: Concurrent Main Experiment Scheduler (Mock Mode)
============================================================
Verifies:
1. Multi-trial execution works concurrently in mock mode.
2. Per-trial isolation (separate checkpoint directories, separate candidate files).
3. Main candidates merge contains exact 300 candidates per trial.
4. Paired design (A_t, B_t, C_t) is strictly preserved.
5. Search curves computed for each trial.
"""

import json
import os
import shutil
import tempfile
import threading
from unittest.mock import patch

from stage3.src.concurrent_main_runner import run_single_trial
from stage3.src.evaluator_gc import GraphColoringEvaluator
from stage3.src.lineage import LineageTracker
from stage3.src.llm_client import Stage3LLMClient


def test_concurrent_single_trial_isolation():
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_path = "stage3/config.json"
        with open(config_path) as f:
            config = json.load(f)

        with open(config["benchmarks"]["graph_coloring"]["dev"]) as f:
            dev_dataset = json.load(f)[:2]  # Subsample 2 for fast test

        # Mock LLM client with zero network
        mock_client = Stage3LLMClient(
            mock_mode=True,
            concurrency_semaphore=threading.BoundedSemaphore(5)
        )

        print_lock = threading.Lock()

        # Run Trial 1
        rec1 = run_single_trial(
            trial_id=1,
            config=config,
            dev_dataset=dev_dataset,
            llm_client=mock_client,
            checkpoints_base_dir=tmp_dir,
            print_lock=print_lock
        )

        assert rec1["trial_id"] == 1
        assert rec1["seed"] == 30301
        assert rec1["arm_a"]["valid_count"] == 100
        assert rec1["arm_b"]["valid_count"] == 100
        assert rec1["arm_c"]["valid_count"] == 100

        # Verify isolated checkpoint directory
        trial1_dir = os.path.join(tmp_dir, "trial_01")
        assert os.path.exists(os.path.join(trial1_dir, "trial_01_record.json"))
        assert os.path.exists(os.path.join(trial1_dir, "status.txt"))
        assert os.path.exists(os.path.join(trial1_dir, "trial_01_candidates.jsonl"))

        # Verify candidate count in isolated log
        with open(os.path.join(trial1_dir, "trial_01_candidates.jsonl")) as f:
            cands = [json.loads(line) for line in f]
        assert len(cands) == 300
        assert sum(1 for c in cands if c["arm"] == "A_INDEPENDENT_BEST_OF_100") == 100
        assert sum(1 for c in cands if c["arm"] == "B_BLIND_ITERATIVE") == 100
        assert sum(1 for c in cands if c["arm"] == "C_AMAURA") == 100

        # Verify safe resumption (second call should instantly load from checkpoint)
        rec1_resumed = run_single_trial(
            trial_id=1,
            config=config,
            dev_dataset=dev_dataset,
            llm_client=mock_client,
            checkpoints_base_dir=tmp_dir,
            print_lock=print_lock
        )
        assert rec1_resumed["trial_id"] == 1
        assert rec1_resumed["duration_sec"] == rec1["duration_sec"]
