from typing import Optional, Any
from auicommon.adapter.meta import AdapterMeta
from auicommon.audio.types import PcmAudio
from auicommon.util.async_utils import CancellationToken  # bei dir vorhanden

DTMF_CHARS = set("0123456789*#")

class PcAdapter:
    def __init__(self, name: str = "pc") -> None:
        self._name = name
        self._busy = False

    def meta(self) -> AdapterMeta:
        return AdapterMeta(name='pc', version='0.0.1', vendor="CoPiCo2Co", description='')
    """Abstraktion für Audio-Ausgabe/Transporte (z. B. PC, ARI, SIP…)."""

    async def init(self, **kwargs: Any) -> None:
        return None

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def play(self, audio: PcmAudio, *, wait: bool = False,
                   cancel: Optional[CancellationToken] = None) -> None:
        return None
    
    """Audio wiedergeben. Falls `wait=True`, erst zurückkehren, wenn Ausgabe beendet."""

    async def stop_audio(self) -> None:
        return None
    """Laufende Audioausgabe umgehend abbrechen (Not-Aus)."""
