"""Option direito segurado = falar. Escuta só eventos de tecla modificadora com um CGEventTap.

Não usa pynput: ele consulta o layout do teclado (TSMGetInputSourceProperty) fora da thread
principal, e o macOS atual derruba o processo inteiro por isso.
"""
import threading
from collections.abc import Callable

import Quartz

RIGHT_OPTION = 61  # keycode da tecla Option direita
OPTION_FLAG = Quartz.kCGEventFlagMaskAlternate


def watch_right_option(on_press: Callable[[], None], on_release: Callable[[], None]) -> bool:
    """Começa a escutar numa thread própria. Retorna False se o macOS não deu permissão."""
    held = [False]

    def callback(_proxy, kind, event, _refcon):
        if kind in (Quartz.kCGEventTapDisabledByTimeout, Quartz.kCGEventTapDisabledByUserInput):
            Quartz.CGEventTapEnable(tap, True)  # o macOS desliga taps lentos; religa
            return event
        if Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode) == RIGHT_OPTION:
            down = bool(Quartz.CGEventGetFlags(event) & OPTION_FLAG)
            if down != held[0]:
                held[0] = down
                try:
                    (on_press if down else on_release)()
                except Exception as exc:
                    print(f"  atalho falhou: {exc}")
        return event

    tap = Quartz.CGEventTapCreate(Quartz.kCGSessionEventTap, Quartz.kCGHeadInsertEventTap,
                                  Quartz.kCGEventTapOptionListenOnly,
                                  Quartz.CGEventMaskBit(Quartz.kCGEventFlagsChanged), callback, None)
    if tap is None:
        return False  # sem permissão de Monitoramento de Entrada / Acessibilidade

    def run() -> None:
        source = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
        Quartz.CFRunLoopAddSource(Quartz.CFRunLoopGetCurrent(), source, Quartz.kCFRunLoopCommonModes)
        Quartz.CGEventTapEnable(tap, True)
        Quartz.CFRunLoopRun()

    threading.Thread(target=run, daemon=True, name="hotkey").start()
    return True
