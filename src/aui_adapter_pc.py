
import sys, os, time, threading
DTMF_CHARS = set("0123456789*#ABCDabcd")
_IS_WIN = (os.name == "nt")
if _IS_WIN:
    try:
        import msvcrt  # type: ignore
    except Exception:
        msvcrt = None
else:
    import termios, tty, select  # type: ignore

class PcAdapter:
    def __init__(self) -> None:
        self.push_digit = lambda ch: None
        self._stop = threading.Event()
        self._th = None
        if os.getenv("AUI_PC_DTMF", "1") not in ("0","false","no"):
            self._start_feeder()

    def _start_feeder(self) -> None:
        if self._th and self._th.is_alive(): return
        self._stop.clear()
        self._th = threading.Thread(target=self._loop, name="pc-dtmf", daemon=True)
        self._th.start()
        print("[PC] DTMF input active. Type digits (0-9,*,#,A-D). Ctrl+C to exit.")

    def _loop(self) -> None:
        if _IS_WIN and 'msvcrt' in globals() and msvcrt:
            while not self._stop.is_set():
                if msvcrt.kbhit():
                    ch = msvcrt.getwch()
                    if ch and ch in DTMF_CHARS: self.push_digit(ch)
                else: time.sleep(0.01)
        else:
            fd = sys.stdin.fileno()
            old = termios.tcgetattr(fd)
            try:
                tty.setcbreak(fd)
                while not self._stop.is_set():
                    r, _, _ = select.select([sys.stdin], [], [], 0.05)
                    if r:
                        ch = sys.stdin.read(1)
                        if ch and ch in DTMF_CHARS: self.push_digit(ch)
            except Exception: pass
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)

    def speak(self, text: str) -> None: print(f"[PC] speak: {text}")
    def stop_speak(self) -> None: print("[PC] stop_speak")
    def play(self, uri: str) -> None: print(f"[PC] play: {uri}")
    def stop_play(self) -> None: print("[PC] stop_play")
    def ring(self) -> None: print("[PC] ring")
    def hangup(self) -> None:
        print("[PC] hangup")
        self._stop.set()
        if self._th and self._th.is_alive():
            try: self._th.join(timeout=0.2)
            except Exception: pass
