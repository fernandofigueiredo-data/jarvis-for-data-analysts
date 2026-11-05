"""Janela nativa (WebKit do macOS) com o painel. Precisa rodar na thread principal."""
import time

import httpx


def open_window(url: str) -> None:
    import webview

    for _ in range(50):  # espera o servidor subir
        try:
            httpx.get(url + "/api/health", timeout=0.5)
            break
        except Exception:
            time.sleep(0.1)
    webview.create_window("J.A.R.V.I.S.", url, width=1280, height=760, min_size=(900, 600),
                          background_color="#101522")  # Navy do design system, até o painel carregar
    webview.start()
