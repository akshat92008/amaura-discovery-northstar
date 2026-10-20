"""
Root conftest.py — ensures the repository root is on sys.path for test discovery (TEST-1).
"""
import os
import sys

# Ensure repository root is on sys.path
repo_root = os.path.dirname(os.path.abspath(__file__))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)
