# aui_adapter_pc.py
from __future__ import annotations

import asyncio
import logging
from enum import Enum
from typing import Any, Optional

from auicommon.adapter.meta import AdapterMeta
from auicommon.audio.types import PcmAudio, AudioFormat
from auicommon.input.dtmf import Dtmf, DtmfKey
from pc_pygame_io import PcPygameIO  # separate pygame helper (async task)

log = logging.getLogger(__name__)


def map_dtmf_key(ch: str) -> Optional[DtmfKey]:
    """Map a single character to DtmfKey enum."""
    return {
        "0": DtmfKey.KEY_0,
        "1": DtmfKey.KEY_1,
        "2": DtmfKey.KEY_2,
        "3": DtmfKey.KEY_3,
        "4": DtmfKey.KEY_4,
        "5": DtmfKey.KEY_5,
        "6": DtmfKey.KEY_6,
        "7": DtmfKey.KEY_7,
        "8": DtmfKey.KEY_8,
        "9": DtmfKey.KEY_9,
        "*": DtmfKey.KEY_STAR,
        "#": DtmfKey.KEY_HASH,
    }.get(ch)


class PcAdapter:
    """PC adapter: pygame-based DTMF keyboard + basic PCM playback."""

    class AdapterState(Enum):
        UNKNOWN = 0
        INITIALIZED = 1
        RUNNING = 2
        STOPPED = 3

    def __init__(self, name: str = "pc") -> None:
        self._name = name
        self._state = self.AdapterState.UNKNOWN

        # DTMF buffer/queue (provided by your auicommon)
        self._dtmf = Dtmf()

        # pygame helper (runs as asyncio task, no extra thread)
        self._pg: Optional[PcPygameIO] = None
        self._pg_task: Optional[asyncio.Task] = None

    # -------------------------------------------------------------------------
    # Meta
    # -------------------------------------------------------------------------
    def meta(self) -> AdapterMeta:
        return AdapterMeta(
            name="pc",
            version="0.0.1",
            vendor="CoPiCo2Co",
            description="PC adapter with pygame DTMF input and basic audio out.",
        )

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------
    async def init(self, **kwargs: Any) -> None:
        if self._state != self.AdapterState.UNKNOWN:
            return

        # Pygame callback: executed within asyncio task context
        def on_key(ch: str) -> None:
            key = map_dtmf_key(ch)
            if key:
                self._dtmf.add(key)

        # 8 kHz mono PCM for telephony-like audio
        self._pg = PcPygameIO(on_key=on_key, sample_rate=8000, show_window=True)
        self._state = self.AdapterState.INITIALIZED
        log.info("PcAdapter initialized.")

    async def start(self) -> None:
        if self._state not in (self.AdapterState.INITIALIZED, self.AdapterState.STOPPED):
            log.warning("Cannot start: invalid state %s", self._state.name)
            return

        # start pygame event loop task
        if self._pg and (self._pg_task is None or self._pg_task.done()):
            self._pg_task = asyncio.create_task(self._pg.run_forever())

        self._state = self.AdapterState.RUNNING
        log.info("PcAdapter started.")

    async def stop(self) -> None:
        if self._state != self.AdapterState.RUNNING:
            log.warning("Adapter not running.")
            return

        # stop pygame task
        if self._pg and self._pg_task:
            self._pg.stop()  # signal loop to exit
            try:
                await self._pg_task
            except asyncio.CancelledError:
                pass
            finally:
                self._pg_task = None

        self._state = self.AdapterState.STOPPED
        log.info("PcAdapter stopped.")

    # -------------------------------------------------------------------------
    # Audio out (basic)
    # -------------------------------------------------------------------------
    async def play(self, audio: PcmAudio) -> None:
        """Play raw PCM (16-bit mono @ 8 kHz)."""
        if self._state != self.AdapterState.RUNNING or not self._pg:
            log.error("Service is not running or pygame not available.")
            return
        if not audio or not audio.data:
            return
        self._pg.play_pcm(audio)

    async def is_playing(self) -> bool:
        # Minimal version: no global playback state exposed.
        return False

    async def stop_playing(self) -> None:
        # Not implemented in minimal version.
        pass

    # -------------------------------------------------------------------------
    # Audio in (not required)
    # -------------------------------------------------------------------------
    async def record(
        self,
        duration: Optional[float] = 0.0,
        pcm_settings: Optional[AudioFormat] = AudioFormat(rate=8000),
    ) -> Optional[PcmAudio]:
        log.info("Recording not implemented in PcAdapter/pygame.")
        return None

    async def is_recording(self) -> bool:
        return False

    async def stop_recording(self) -> None:
        pass

    # -------------------------------------------------------------------------
    # DTMF interface
    # -------------------------------------------------------------------------
    async def get_dtmf_key(self) -> Optional[DtmfKey]:
        """Non-blocking: returns next key or None (consumes one if present)."""
        return self._dtmf.get()

    async def has_dtmf_key(self) -> bool:
        """
        Non-consuming check: True if at least one key is buffered, else False.
        Requires Dtmf.has() implementation that does not consume.
        """
        return self._dtmf.has()

    async def flush_dtmf_keys(self) -> None:
        self._dtmf.flush()
