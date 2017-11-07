# Imports
import sys
from pathlib import Path

# Set path (Important for resolving modules)
def setupPath():
    path = str(Path(__file__).resolve().parents[1])
    if path not in sys.path:
        sys.path.insert(0, path)

# Main
setupPath()