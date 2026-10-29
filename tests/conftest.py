"""Shared pytest configuration.

The real desktop is not available in every test environment, so UI tests run on
Qt's offscreen platform.  The configuration override also guarantees that tests
never read or write the user's real settings.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault(
    "PCW_CONFIG_DIR", tempfile.mkdtemp(prefix="pcw-pytest-config-")
)

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
