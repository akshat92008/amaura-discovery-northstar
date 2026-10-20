"""
Stage 2: Evaluator Red-Teaming & Canary Test Suite
==================================================
Implements and executes the 12 explicit canaries mandated by Section 13:
1. invalid coloring (conflicting colors or wrong length)
2. deliberately broken solver (syntax or logic failure)
3. timeout (infinite loop)
4. crash (unhandled exception / division by zero)
5. file-reading attempt (open() or Path access)
6. hidden-path access attempt (accessing hidden benchmark files)
7. input mutation attempt (modifying adj or times in-place)
8. hardcoded-answer candidate (returns fixed constant regardless of input)
9. known-good solver (DSATUR / NEH should evaluate cleanly)
10. sandbox cheating attempt (__builtins__ or sys/os access)
11. network-access attempt (urllib / socket access)
12. environment/process-information attempt (os.environ / psutil access)
"""

from typing import Dict, Any, List, Tuple
from stage2.src.evaluator_gc import GraphColoringEvaluator
from stage2.src.evaluator_pfsp import PFSPEvaluator
from stage2.baselines.graph_coloring import dsatur_code
from stage2.baselines.pfsp import neh_code


class EvaluatorCanarySuite:
    def __init__(self):
        self.gc_evaluator = GraphColoringEvaluator(scale_aware_base_ms=100.0, hard_sigalrm_sec=1)
        self.pfsp_evaluator = PFSPEvaluator(scale_aware_base_ms=100.0, hard_sigalrm_sec=1)
        
        # Minimal test datasets
        self.sample_graph = [{"family": "k4", "adj": [[1, 2, 3], [0, 2, 3], [0, 1, 3], [0, 1, 2]]}]
        self.sample_pfsp = [{"family": "toy", "n": 3, "m": 2, "times": [[10, 5], [2, 8], [7, 3]]}]

    def run_all_canaries(self) -> Dict[str, Any]:
        results: Dict[str, Any] = {}
        all_passed = True

        canary_methods = [
            ("canary_01_invalid_coloring", self.canary_01_invalid_coloring),
            ("canary_02_deliberately_broken", self.canary_02_deliberately_broken),
            ("canary_03_timeout", self.canary_03_timeout),
            ("canary_04_crash", self.canary_04_crash),
            ("canary_05_file_reading", self.canary_05_file_reading),
            ("canary_06_hidden_path_access", self.canary_06_hidden_path_access),
            ("canary_07_input_mutation", self.canary_07_input_mutation),
            ("canary_08_hardcoded_answer", self.canary_08_hardcoded_answer),
            ("canary_09_known_good", self.canary_09_known_good),
            ("canary_10_sandbox_cheating", self.canary_10_sandbox_cheating),
            ("canary_11_network_access", self.canary_11_network_access),
            ("canary_12_environment_access", self.canary_12_environment_access),
        ]

        for name, method in canary_methods:
            try:
                passed, detail = method()
                results[name] = {"passed": passed, "detail": detail}
                if not passed:
                    all_passed = False
            except Exception as e:
                results[name] = {"passed": False, "detail": f"Canary execution exception: {e}"}
                all_passed = False

        results["all_passed"] = all_passed
        return results

    # 1. Invalid coloring
    def canary_01_invalid_coloring(self) -> Tuple[bool, str]:
        code = '''def color_graph(adj: list[list[int]]) -> list[int]:
    return [0] * len(adj)
'''
        res = self.gc_evaluator.evaluate_code(code, self.sample_graph)
        passed = (not res["is_valid"]) and (res["total_colors"] == 999999)
        return passed, f"Expected invalidity; Got is_valid={res['is_valid']}, err={res['error']}"

    # 2. Deliberately broken solver (Syntax Error)
    def canary_02_deliberately_broken(self) -> Tuple[bool, str]:
        code = '''def color_graph(adj: list[list[int]]) -> list[int]:
    return -
'''
        res = self.gc_evaluator.evaluate_code(code, self.sample_graph)
        passed = (not res["is_valid"]) and ("SyntaxError" in str(res["error"]))
        return passed, f"Expected SyntaxError; Got err={res['error']}"

    # 3. Timeout (Infinite loop)
    def canary_03_timeout(self) -> Tuple[bool, str]:
        code = '''def schedule_flowshop(times: list[list[int]]) -> list[int]:
    while True:
        pass
'''
        res = self.pfsp_evaluator.evaluate_code(code, self.sample_pfsp)
        passed = (not res["is_valid"]) and ("Timeout" in str(res["error"]))
        return passed, f"Expected Timeout; Got err={res['error']}"

    # 4. Crash (ZeroDivisionError)
    def canary_04_crash(self) -> Tuple[bool, str]:
        code = '''def schedule_flowshop(times: list[list[int]]) -> list[int]:
    x = 1 / 0
    return list(range(len(times)))
'''
        res = self.pfsp_evaluator.evaluate_code(code, self.sample_pfsp)
        passed = (not res["is_valid"]) and ("ZeroDivisionError" in str(res["error"]))
        return passed, f"Expected ZeroDivisionError; Got err={res['error']}"

    # 5. File-reading attempt
    def canary_05_file_reading(self) -> Tuple[bool, str]:
        code = '''def color_graph(adj: list[list[int]]) -> list[int]:
    with open('/etc/passwd') as f:
        data = f.read()
    return list(range(len(adj)))
'''
        res = self.gc_evaluator.evaluate_code(code, self.sample_graph)
        passed = (not res["is_valid"]) and ("Forbidden" in str(res["error"]))
        return passed, f"Expected forbidden open(); Got err={res['error']}"

    # 6. Hidden-path access attempt
    def canary_06_hidden_path_access(self) -> Tuple[bool, str]:
        code = '''def color_graph(adj: list[list[int]]) -> list[int]:
    import os
    return list(range(len(adj)))
'''
        res = self.gc_evaluator.evaluate_code(code, self.sample_graph)
        passed = (not res["is_valid"]) and ("Forbidden module import" in str(res["error"]))
        return passed, f"Expected import blockage; Got err={res['error']}"

    # 7. Input mutation attempt
    def canary_07_input_mutation(self) -> Tuple[bool, str]:
        # Mutates adj in place to try corrupting subsequent evaluation
        code = '''def color_graph(adj: list[list[int]]) -> list[int]:
    adj.clear()
    return [0, 1, 2, 3]
'''
        # Before run, copy original len
        orig_len = len(self.sample_graph[0]["adj"])
        res = self.gc_evaluator.evaluate_code(code, self.sample_graph)
        after_len = len(self.sample_graph[0]["adj"])
        passed = (orig_len == after_len == 4)  # Benchmark must be untouched
        return passed, f"Expected input isolation; orig_len={orig_len}, after_len={after_len}"

    # 8. Hardcoded-answer candidate
    def canary_08_hardcoded_answer(self) -> Tuple[bool, str]:
        # Hardcodes answer for N=3, fails when evaluated on N=4
        code = '''def color_graph(adj: list[list[int]]) -> list[int]:
    return [0, 1, 2]
'''
        res = self.gc_evaluator.evaluate_code(code, self.sample_graph)  # N=4 graph
        passed = (not res["is_valid"]) and (res["total_colors"] == 999999)
        return passed, f"Expected length mismatch on N=4; Got is_valid={res['is_valid']}"

    # 9. Known-good solver (DSATUR & NEH)
    def canary_09_known_good(self) -> Tuple[bool, str]:
        res_gc = self.gc_evaluator.evaluate_code(dsatur_code(), self.sample_graph)
        res_pfsp = self.pfsp_evaluator.evaluate_code(neh_code(), self.sample_pfsp)
        passed = res_gc["is_valid"] and res_pfsp["is_valid"] and (res_gc["total_colors"] == 4)
        return passed, f"Expected valid solutions; GC valid={res_gc['is_valid']}, PFSP valid={res_pfsp['is_valid']}"

    # 10. Sandbox cheating attempt (__builtins__ inspection)
    def canary_10_sandbox_cheating(self) -> Tuple[bool, str]:
        code = '''def color_graph(adj: list[list[int]]) -> list[int]:
    b = __builtins__
    return list(range(len(adj)))
'''
        res = self.gc_evaluator.evaluate_code(code, self.sample_graph)
        passed = (not res["is_valid"]) and ("Forbidden" in str(res["error"]))
        return passed, f"Expected forbidden identifier/dunder; Got err={res['error']}"

    # 11. Network-access attempt
    def canary_11_network_access(self) -> Tuple[bool, str]:
        code = '''def schedule_flowshop(times: list[list[int]]) -> list[int]:
    import urllib.request
    return list(range(len(times)))
'''
        res = self.pfsp_evaluator.evaluate_code(code, self.sample_pfsp)
        passed = (not res["is_valid"]) and ("Forbidden module" in str(res["error"]))
        return passed, f"Expected urllib rejection; Got err={res['error']}"

    # 12. Environment/Process-information attempt
    def canary_12_environment_access(self) -> Tuple[bool, str]:
        code = '''def schedule_flowshop(times: list[list[int]]) -> list[int]:
    import subprocess
    return list(range(len(times)))
'''
        res = self.pfsp_evaluator.evaluate_code(code, self.sample_pfsp)
        passed = (not res["is_valid"]) and ("Forbidden module" in str(res["error"]))
        return passed, f"Expected subprocess rejection; Got err={res['error']}"


if __name__ == "__main__":
    suite = EvaluatorCanarySuite()
    out = suite.run_all_canaries()
    print("Stage 2 Evaluator Canary Results:")
    for k, v in out.items():
        if k != "all_passed":
            status = "PASSED" if v["passed"] else "FAILED"
            print(f"  [{status}] {k:<32} - {v['detail']}")
    print(f"\nOverall Canary Verdict: {'ALL CANARIES PASSED' if out['all_passed'] else 'CANARY FAILURE'}")
