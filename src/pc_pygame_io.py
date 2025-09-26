# pc_pygame_io.py
from __future__ import annotations

import asyncio
from typing import Callable, Optional, Tuple, List

import pygame  # pip install pygame
from auicommon.audio.types import PcmAudio  # nutzt dein Typobjekt

_ALLOWED = set("0123456789*#")


class _Button:
    def __init__(self, label: str, rect: pygame.Rect) -> None:
        self.label = label
        self.rect = rect
        self.active_until_ms: int = 0  # kurze Klick-Animation


class PcPygameIO:
    """
    Pygame helper: On-screen DTMF keypad + optional PCM playback.

    - run_forever(): asyncio-Task, pollt Pygame-Events (Fenster braucht Fokus).
    - on_key(char): Callback für '0'..'9','*','#' bei Maus oder Tastatur.
    - play(audio: PcmAudio): spielt 16-bit signed mono PCM; Samplerate wird aus audio.rate übernommen.
    """

    def __init__(
        self,
        on_key: Callable[[str], None],
        *,
        sample_rate: int = 8000,                               # Default-Rate (erstes Init)
        show_window: bool = True,
        window_size: Tuple[int, int] = (360, 480),
        title: str = "DTMF Keypad (click or type)"
    ) -> None:
        self._on_key = on_key
        self._default_rate = sample_rate
        self._show_window = show_window
        self._window_size = window_size
        self._title = title

        self._mixer_ready = False
        self._mixer_rate: Optional[int] = None  # aktuell gesetzte Mixer-Rate
        self._stop = False
        self._started = False

        # UI
        self._screen: Optional[pygame.Surface] = None
        self._font_btn: Optional[pygame.font.Font] = None
        self._font_hdr: Optional[pygame.font.Font] = None
        self._buttons: List[_Button] = []

        # Farben (RGB)
        self._bg = (245, 245, 245)
        self._btn = (220, 220, 220)
        self._btn_hover = (205, 205, 205)
        self._btn_active = (180, 180, 180)
        self._frame = (100, 100, 100)
        self._text = (20, 20, 20)

    # --------------------------------------------------------------------- #
    # Public API
    # --------------------------------------------------------------------- #
    async def run_forever(self) -> None:
        """Als asyncio-Task starten. Endet per stop() oder Fenster schließen."""
        if self._started:
            return
        self._started = True
        try:
            pygame.init()
            if self._show_window:
                self._screen = pygame.display.set_mode(self._window_size)
                pygame.display.set_caption(self._title)
            else:
                self._screen = pygame.Surface(self._window_size)

            # Fonts
            self._font_btn = pygame.font.SysFont(None, 48)
            self._font_hdr = pygame.font.SysFont(None, 24)

            # Mixer initial auf Default-Rate (Fehlschlag ist ok; wir können später nachinitialisieren)
            self._try_init_mixer(self._default_rate)

            self._build_keypad_layout()
            clock = pygame.time.Clock()

            while not self._stop:
                now_ms = pygame.time.get_ticks()
                for ev in pygame.event.get():
                    if ev.type == pygame.QUIT:
                        self._stop = True
                        break
                    if ev.type == pygame.KEYDOWN:
                        ch = getattr(ev, "unicode", "")
                        if ch in _ALLOWED:
                            self._send_key(ch, now_ms)
                    if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                        self._handle_click(ev.pos, now_ms)

                self._render(now_ms)
                clock.tick(100)
                await asyncio.sleep(0.005)

        finally:
            self._shutdown_pygame()
            self._started = False
            self._screen = None

    def stop(self) -> None:
        """Signalisiert der Eventschleife das Ende (Task läuft bis zum nächsten Tick aus)."""
        self._stop = True

    def play_pcm(self, audio: PcmAudio) -> None:
        """
        Spielt Roh-PCM aus PcmAudio:
          - erwartet 16-bit signed, mono (little-endian)
          - nutzt audio.rate als Samplerate; Mixer wird bei Bedarf neu initialisiert.
        """
        if not audio or not audio.data:
            return
        if not isinstance(audio.rate, int) or audio.rate <= 0:
            return

        # Mixer ggf. auf Zielrate bringen
        if not self._ensure_mixer(audio.rate):
            # Mixer nicht verfügbar -> nichts abspielen
            return

        # Minimalprüfung: gerade Byteanzahl (16-bit Frames)
        if (len(audio.data) % 2) != 0:
            # Zur Sicherheit verwerfen wir „krumme“ Daten; alternativ könnte man hier padding einfügen.
            return

        try:
            snd = pygame.mixer.Sound(buffer=audio.data)
            snd.play()
        except Exception:
            # robust bleiben
            pass

    # --------------------------------------------------------------------- #
    # Internals
    # --------------------------------------------------------------------- #
    def _build_keypad_layout(self) -> None:
        """Layout 4x3: 1 2 3 / 4 5 6 / 7 8 9 / * 0 #"""
        assert self._screen is not None

        w, h = self._screen.get_size()
        top = 70
        margin = 12
        rows, cols = 4, 3

        cell_w = (w - (cols + 1) * margin)
        cell_h = (h - top - (rows + 1) * margin)
        size = min(cell_w // cols, cell_h // rows)
        x0 = (w - (cols * size + (cols - 1) * margin)) // 2
        y0 = top

        labels = [
            "1", "2", "3",
            "4", "5", "6",
            "7", "8", "9",
            "*", "0", "#",
        ]

        self._buttons.clear()
        for r in range(rows):
            for c in range(cols):
                idx = r * cols + c
                lab = labels[idx]
                x = x0 + c * (size + margin)
                y = y0 + r * (size + margin)
                rect = pygame.Rect(x, y, size, size)
                self._buttons.append(_Button(lab, rect))

    def _handle_click(self, pos: Tuple[int, int], now_ms: int) -> None:
        for btn in self._buttons:
            if btn.rect.collidepoint(pos):
                self._send_key(btn.label, now_ms)
                break

    def _send_key(self, ch: str, now_ms: int) -> None:
        # kurze „Pressed“-Animation (120 ms)
        for btn in self._buttons:
            if btn.label == ch:
                btn.active_until_ms = now_ms + 120
                break
        try:
            self._on_key(ch)
        except Exception:
            pass

    def _render(self, now_ms: int) -> None:
        assert self._screen is not None and self._font_btn is not None and self._font_hdr is not None
        self._screen.fill(self._bg)

        # Header
        hdr = self._font_hdr.render("Click or type 0-9   (*=Stern,  #=Raute)", True, self._text)
        self._screen.blit(hdr, (12, 20))

        # Buttons
        mouse_pos = pygame.mouse.get_pos()
        for btn in self._buttons:
            hovered = btn.rect.collidepoint(mouse_pos)
            pressed = now_ms < btn.active_until_ms

            color = self._btn
            if pressed:
                color = self._btn_active
            elif hovered:
                color = self._btn_hover

            pygame.draw.rect(self._screen, color, btn.rect, border_radius=10)
            pygame.draw.rect(self._screen, self._frame, btn.rect, width=2, border_radius=10)

            label = self._font_btn.render(btn.label, True, self._text)
            lw, lh = label.get_size()
            self._screen.blit(label, (btn.rect.x + (btn.rect.w - lw) // 2,
                                      btn.rect.y + (btn.rect.h - lh) // 2))

        pygame.display.flip()

    # --- Mixer-Handling ---------------------------------------------------- #
    def _try_init_mixer(self, rate: int) -> None:
        """Silent init; setzt Flags, aber wirft nichts hoch."""
        try:
            pygame.mixer.init(frequency=rate, size=-16, channels=1, buffer=512)
            self._mixer_ready = True
            self._mixer_rate = rate
        except Exception:
            self._mixer_ready = False
            self._mixer_rate = None

    def _ensure_mixer(self, rate: int) -> bool:
        """
        Stellt sicher, dass der Mixer aktiv ist und auf 'rate' läuft.
        Reinitialisiert bei Bedarf.
        """
        if self._mixer_ready and self._mixer_rate == rate:
            return True
        # bestehenden Mixer schließen (falls aktiv), dann auf neuer Rate öffnen
        try:
            if self._mixer_ready:
                pygame.mixer.quit()
        except Exception:
            pass
        self._try_init_mixer(rate)
        return self._mixer_ready

    # --- Shutdown ---------------------------------------------------------- #
    def _shutdown_pygame(self) -> None:
        try:
            if self._mixer_ready:
                pygame.mixer.quit()
        except Exception:
            pass
        try:
            pygame.display.quit()
        except Exception:
            pass
        try:
            pygame.quit()
        except Exception:
            pass
        self._mixer_ready = False
        self._mixer_rate = None
