import sys
from pathlib import Path

# The eval package lives at the repo root (see the repository layout in
# SPEC.md), outside the backend src tree; make it importable for its tests.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
