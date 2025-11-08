#!/usr/bin/env python3
"""Compatibilità: inoltra a tools/backend/check_mcp_integration.py"""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tools.backend.check_mcp_integration import main

if __name__ == "__main__":
    main()
