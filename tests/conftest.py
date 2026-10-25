"""Pytest configuration and fixtures."""
import sys
import pathlib

# Make slothops package importable from the project root
ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
