from __future__ import annotations

import importlib.util
from pathlib import Path


LIGHTWEIGHT_INIT = '''"""Runtime-only public API for AutoVoiceClipper."""

__version__ = "0.2"

from .models import SegmentationModel, SegmentationModelConfig

__all__ = ["SegmentationModel", "SegmentationModelConfig"]
'''


def patch_diarizers() -> Path:
    spec = importlib.util.find_spec("diarizers")
    if spec is None or not spec.submodule_search_locations:
        raise RuntimeError("diarizers package was not found.")

    package_dir = Path(next(iter(spec.submodule_search_locations)))
    init_path = package_dir / "__init__.py"
    if not init_path.is_file():
        raise RuntimeError(f"diarizers package entry point was not found: {init_path}")

    init_path.write_text(LIGHTWEIGHT_INIT, encoding="utf-8")
    return init_path


if __name__ == "__main__":
    patched_path = patch_diarizers()
    print(f"Patched diarizers runtime entry point: {patched_path}")
