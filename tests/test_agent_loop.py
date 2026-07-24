"""Agent loop tests using a scripted fake tool-calling LLM client."""

import pytest

from doc_agent.agent import DocumentEditor
from doc_agent.agent_loop import AgentSession
from doc_agent.llm.base import ChatResult, LLMClient, ToolCall
from doc_agent.models import EditRequest


class FakeToolLLM(LLMClient):
    """Returns scripted ChatResult objects on each chat() call."""

    def __init__(self, script: list[ChatResult]) -> None:
        self._script = list(script)
        self.calls: list[dict] = []
        self._supports = True

    def is_available(self) -> bool:
        return True

    def supports_tools(self) -> bool:
        return self._supports

    async def generate(self, prompt, system="", max_tokens=4096, temperature=0.7, **kwargs):
        return "fallback single-shot output"

    async def generate_stream(self, prompt, system="", max_tokens=4096, temperature=0.7, **kwargs):
        yield "fallback"

    async def chat(self, messages, system="", tools=None, max_tokens=4096, temperature=0.7, **kwargs):
        self.calls.append({"messages": list(messages), "tools": tools})
        if self._script:
            return self._script.pop(0)
        return ChatResult(text="done")


def _make_session(config, fake_llm, tmp_workspace):
    tmp_workspace.save_document("guide.md", "# Guide\n\noriginal body\n", message="init")
    editor = DocumentEditor(config)
    editor.llm = fake_llm
    return AgentSession(config, editor=editor)


async def _collect(agen):
    events = []
    async for ev in agen:
        events.append(ev)
    return events


class TestAgentLoop:
    @pytest.mark.asyncio
    async def test_tool_then_edit_then_complete(self, sample_config, tmp_workspace):
        script = [
            ChatResult(tool_calls=[ToolCall(id="c1", name="read_document", arguments={"document_id": "guide.md"})]),
            ChatResult(tool_calls=[ToolCall(id="c2", name="apply_edit", arguments={"document_id": "guide.md", "new_content": "# Guide\n\nEDITED body\n"})]),
            ChatResult(text="已完成编辑。"),
        ]
        fake = FakeToolLLM(script)
        session = _make_session(sample_config, fake, tmp_workspace)

        events = await _collect(session.run(EditRequest(document_id="guide.md", instruction="改写正文")))

        types = [e["type"] for e in events]
        assert "tool_call" in types
        assert "tool_result" in types
        assert types[-1] == "complete"

        # tool call names captured in order
        call_names = [e["name"] for e in events if e["type"] == "tool_call"]
        assert call_names == ["read_document", "apply_edit"]

        complete = events[-1]
        assert complete["stop_reason"] == "done"
        er = complete["edit_response"]
        assert "EDITED body" in er["edited_content"]
        assert "original body" in er["original_content"]
        assert er["commit_hash"] is None
        assert er["diff_summary"]  # non-empty diff

    @pytest.mark.asyncio
    async def test_max_steps_guard(self, sample_config, tmp_workspace):
        sample_config.agent.max_steps = 2
        # Always asks for a tool → never completes on its own.
        looping = [
            ChatResult(tool_calls=[ToolCall(id=f"c{i}", name="list_documents", arguments={})])
            for i in range(5)
        ]
        fake = FakeToolLLM(looping)
        session = _make_session(sample_config, fake, tmp_workspace)

        events = await _collect(session.run(EditRequest(document_id="guide.md", instruction="loop")))

        error_events = [e for e in events if e["type"] == "error"]
        assert any("max_steps" in e["message"] for e in error_events)
        # chat called exactly max_steps times
        assert len(fake.calls) == 2
        # still emits a final complete event
        assert events[-1]["type"] == "complete"
        assert events[-1]["stop_reason"] == "max_steps_reached"

    @pytest.mark.asyncio
    async def test_token_budget_guard(self, sample_config, tmp_workspace):
        sample_config.agent.max_steps = 10
        sample_config.agent.token_budget = 5
        script = [
            ChatResult(
                tool_calls=[ToolCall(id="c1", name="list_documents", arguments={})],
                usage={"output_tokens": 10},
            ),
        ]
        fake = FakeToolLLM(script)
        session = _make_session(sample_config, fake, tmp_workspace)

        events = await _collect(session.run(EditRequest(document_id="guide.md", instruction="x")))

        assert any(e["type"] == "error" and "budget" in e["message"] for e in events)
        assert events[-1]["type"] == "complete"
        assert events[-1]["stop_reason"] == "token_budget_exceeded"

    @pytest.mark.asyncio
    async def test_fallback_when_no_tool_support(self, sample_config, tmp_workspace):
        fake = FakeToolLLM([])
        fake._supports = False
        session = _make_session(sample_config, fake, tmp_workspace)

        events = await _collect(session.run(EditRequest(document_id="guide.md", instruction="改写")))

        assert len(events) == 1
        assert events[0]["type"] == "complete"
        er = events[0]["edit_response"]
        assert er["edited_content"] == "fallback single-shot output"
