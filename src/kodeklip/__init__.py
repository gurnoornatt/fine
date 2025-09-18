"""
KodeKlip - Surgical Code Context Management Tool

Fight context bloat with precision code extraction for LLM interactions.
"""

__version__ = "0.1.0"
__author__ = "KodeKlip Team"
__email__ = "contact@kodeklip.dev"

# Import main components for easier access
try:
    from .main import app

    __all__ = ["app", "__version__"]
except ImportError:
    # During development, main.py might not be ready yet
    __all__ = ["__version__"]
