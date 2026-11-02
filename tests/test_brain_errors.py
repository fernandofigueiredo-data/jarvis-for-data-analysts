import pytest
from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock

from jarvis.brain.agent import Brain, BrainError

MODEL_ERROR = "There's an issue with the selected model (x). It may not exist or you may not have access to it."


class FakeClient:
    """Repete o que o Claude Code manda num erro de API: nada em stream, só AssistantMessage e o result."""

    def __init__(self, messages):
        self.messages = messages

    async def query(self, _text):
        pass

    async def receive_response(self):
        for m in self.messages:
            yield m


def result(is_error: bool, text: str | None) -> ResultMessage:
    return ResultMessage(subtype="success", duration_ms=1, duration_api_ms=1, is_error=is_error, num_turns=1,
                         session_id="s", result=text)


@pytest.mark.asyncio
async def test_api_error_is_raised_not_swallowed():
    b = Brain()
    b.client = FakeClient([AssistantMessage([TextBlock(MODEL_ERROR)], "x", error="invalid_request"),
                           result(True, MODEL_ERROR)])
    with pytest.raises(BrainError, match="selected model"):
        await b.ask("oi")


@pytest.mark.asyncio
async def test_success_without_stream_returns_empty_and_no_error():
    b = Brain()
    b.client = FakeClient([result(False, "ok")])
    assert await b.ask("oi") == ""
