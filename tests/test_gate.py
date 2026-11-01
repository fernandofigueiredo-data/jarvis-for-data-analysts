from jarvis.brain.gate import decide_tool


def test_builtins():
    assert decide_tool("WebSearch", False)
    assert not decide_tool("Bash", False)
    assert decide_tool("Bash", True)


def test_own_servers_always_allowed():
    assert decide_tool("mcp__mac__open_app", False)
    assert decide_tool("mcp__jarvis__news_latest", False)


def test_mcp_verbs():
    assert not decide_tool("mcp__gmail__send_message", False)
    assert decide_tool("mcp__gmail__search_threads", False)
    assert not decide_tool("mcp__twilio__make_outbound_call", False)
    assert not decide_tool("mcp__todoist__complete-tasks", False)
    assert decide_tool("mcp__todoist__find-tasks", False)
    assert not decide_tool("mcp__whatever__do_thing", False)
    assert decide_tool("mcp__whatever__do_thing", True)
