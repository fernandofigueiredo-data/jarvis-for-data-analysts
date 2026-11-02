from fastapi.testclient import TestClient

from jarvis.server import create_app


class FakeJarvis:
    brain_ready, mode = True, "off"

    def __init__(self):
        self.received = []

    async def on_client(self, msg):
        self.received.append(msg)


def test_malformed_message_keeps_the_connection():
    jarvis = FakeJarvis()
    with TestClient(create_app(jarvis)).websocket_connect("/ws") as ws:
        assert ws.receive_json()["type"] == "snapshot"
        ws.send_text("isto não é json")
        ws.send_text("[1, 2]")
        ws.send_json({"type": "say", "text": "oi"})
        ws.send_json({"type": "ptt", "down": False})  # só para garantir que o "say" já foi processado
    assert jarvis.received[0] == {"type": "say", "text": "oi"}


def test_foreign_origin_is_refused():
    client = TestClient(create_app(FakeJarvis()))
    try:
        with client.websocket_connect("/ws", headers={"origin": "http://evil.example.com"}):
            raise AssertionError("conectou")
    except Exception as exc:  # o Starlette recusa antes do accept
        assert "403" in str(exc) or "4403" in str(exc) or type(exc).__name__ == "WebSocketDisconnect"
