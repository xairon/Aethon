"""TTS — Interface abstraite pour les backends TTS."""

from __future__ import annotations

from typing import Protocol, Generator, runtime_checkable

import numpy as np


@runtime_checkable
class TTSBackend(Protocol):
    """Interface commune pour tous les backends TTS."""

    @property
    def SAMPLE_RATE(self) -> int: ...

    def load(self) -> None: ...

    def synthesize_stream(self, text: str) -> Generator[np.ndarray, None, None]: ...

    def unload(self) -> None: ...
