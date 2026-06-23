"""
Centralized path resolution for both development and PyInstaller-frozen contexts.

When frozen (PyInstaller binary):
  - BUNDLE_DIR  → sys._MEIPASS (read-only temp dir with bundled assets like icons)
  - DATA_DIR    → directory where the executable lives (persistent, writable)
  
When running from source:
  - BUNDLE_DIR  → project root (same as DATA_DIR)
  - DATA_DIR    → project root
"""
import sys
from pathlib import Path

_FROZEN = getattr(sys, 'frozen', False)

if _FROZEN:
    # Assets bundled inside the executable (read-only)
    BUNDLE_DIR = Path(sys._MEIPASS)
    # Persistent user data lives next to the executable
    DATA_DIR = Path(sys.executable).resolve().parent
else:
    # Development mode — everything is relative to the project root
    BUNDLE_DIR = Path(__file__).resolve().parent.parent
    DATA_DIR = BUNDLE_DIR
