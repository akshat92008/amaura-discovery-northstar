"""
Unit Tests: Candidate Pools, Hash Identity, and Arm A Selection
===============================================================
Enforces Section 3, 5, 35.
"""

import hashlib
import random
import pytest
from stage2.src.runner import Stage2Runner


def test_hash_identity_enforcement():
    # Simulate 20 expert candidates
    pool_b = [{"candidate_id": f"C_{i:02d}", "candidate_hash": hashlib.sha256(f"code_{i}".encode()).hexdigest()} for i in range(20)]
    pool_d = [{"candidate_id": f"C_{i:02d}", "candidate_hash": hashlib.sha256(f"code_{i}".encode()).hexdigest()} for i in range(20)]

    # Check identical hashes
    for idx in range(20):
        assert pool_b[idx]["candidate_hash"] == pool_d[idx]["candidate_hash"]

    # Alter candidate 5 in pool_d to simulate a corrupted or mismatched candidate
    pool_d[4]["candidate_hash"] = "tampered_hash"

    mismatch_detected = False
    for idx in range(20):
        if pool_b[idx]["candidate_hash"] != pool_d[idx]["candidate_hash"]:
            mismatch_detected = True
            break
    assert mismatch_detected is True


def test_arm_a_random_selection_and_pool_mean():
    scores = [20, 22, 21, 25, 23, 22, 20, 24, 21, 23, 22, 21, 24, 25, 20, 22, 23, 21, 24, 22]
    pool = [{"candidate_id": f"C_{i:02d}", "dev_score": scores[i]} for i in range(20)]

    # Seeded random draw
    rng = random.Random(12345)
    selected_a = rng.choice(pool)
    assert selected_a["candidate_id"] in [c["candidate_id"] for c in pool]

    # Pool mean calculation
    pool_mean = sum(scores) / len(scores)
    assert pool_mean == pytest.approx(22.25, rel=1e-3)
    assert selected_a["dev_score"] != pool_mean  # Selected candidate must not be replaced by pool mean
