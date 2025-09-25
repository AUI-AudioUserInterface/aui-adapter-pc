
DTMF_CHARS = set("0123456789*#")

class PcAdapter:
    def __init__(self, name: str = "pc") -> None:
        self._name = name
        self._busy = False

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    def is_busy(self) -> bool:
        return False
