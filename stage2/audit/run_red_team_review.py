"""
Stage 2: Independent Evaluator Red-Team Review Engine
=====================================================
Enforces Section 14:
A second model (nvidia/nvidia/nemotron-3-super-120b-a12b) independently audits the evaluator code
and sandbox implementations.
"""

import json
import os
import sys
import time
import urllib.request

from stage2.src.llm_client import Stage2LLMClient


def run_red_team_audit():
    print("Initiating Independent Evaluator Red-Team Review via secondary model (nemotron-3-super-120b-a12b)...")

    # Read evaluator code
    with open("stage2/src/sandbox.py") as f:
        sandbox_code = f.read()
    with open("stage2/src/evaluator_gc.py") as f:
        gc_code = f.read()
    with open("stage2/src/evaluator_pfsp.py") as f:
        pfsp_code = f.read()

    red_team_prompt = f"""You are an adversarial AI safety auditor, security researcher, and formal verification specialist.
Your task is to conduct an independent, rigorous, unsparing red-team audit of the following automated algorithmic discovery evaluator and execution sandbox.

EVALUATOR CODE UNDER REVIEW:

--- stage2/src/sandbox.py ---
```python
{sandbox_code}
```

--- stage2/src/evaluator_gc.py ---
```python
{gc_code}
```

--- stage2/src/evaluator_pfsp.py ---
```python
{pfsp_code}
```

EXPLICIT AUDIT DIRECTIVE:
Find ways this evaluator could:
1. Accidentally leak hidden data or future test cases to candidates.
2. Reward cheating or allow candidates to bypass algorithmic evaluation.
3. Produce nondeterministic scores or variance across identical runs.
4. Incorrectly score invalid, crashing, or timed-out candidates.
5. Allow candidates to access host files, processes, environment secrets, or networking.
6. Mutate benchmark inputs in-place to tamper with subsequent evaluations.

Format your review as a formal markdown audit report:
- Executive Summary
- Vulnerability Assessment across each of the 6 dimensions
- Evaluator Strengths and Verified Safeguards
- Concrete Recommendations
- Final Independent Security & Scientific Integrity Verdict (PASS / CONDITIONAL / FAIL)
"""

    client = Stage2LLMClient(
        model="nvidia/nvidia/nemotron-3-super-120b-a12b",
        base_url="http://127.0.0.1:20128/v1/chat/completions",
        api_key=os.environ.get("STAGE2_API_KEY") or os.environ.get("OPENAI_API_KEY") or "local-proxy"
    )

    resp = client.query(
        prompt=red_team_prompt,
        system_prompt="You are an uncompromising, independent technical red-team auditor. Be exhaustively thorough and adversarial.",
        temperature=0.2,
        max_tokens=4096
    )

    review_text = resp["raw_response"]
    out_path = "stage2/audit/red_team_review.md"
    with open(out_path, "w") as f:
        f.write("# Stage 2 Independent Evaluator Red-Team Review\n\n")
        f.write(f"**Auditor Model:** `nvidia/nvidia/nemotron-3-super-120b-a12b`  \n")
        f.write(f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}  \n")
        f.write(f"**Prompt SHA-256:** `{resp['prompt_hash']}`  \n\n")
        f.write("---\n\n")
        f.write(review_text)

    print(f"Red-team review completed and saved to {out_path}.")
    return out_path


if __name__ == "__main__":
    run_red_team_audit()
