"""Vercel Python serverless entrypoint for the FastAPI backend.

Vercel's Python runtime discovers the ASGI ``app`` exported here and serves it.
The backend service is mounted at the ``/_/backend`` route prefix (see the root
``vercel.json``), so requests arrive here with that prefix already stripped by
Vercel's router and reach the same routes defined in ``main.py``.
"""

import os
import sys

# Ensure the backend package root (one level up from this ``api/`` folder) is on
# the import path so ``import api`` / ``import Script_Generation_Pipeline`` resolve
# the same way they do when running ``python main.py`` locally.
BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from main import app  # noqa: E402  (path setup must happen first)

# Vercel's ASGI handler looks for a module-level ``app``.
__all__ = ["app"]
