"""Runs the whole research pipeline offline with a fake model and a fake Tavily client."""

import json
import os
import re

os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("TAVILY_API_KEY", "test-key")

import pytest
from agents import ModelSettings, set_tracing_disabled
from agents.items import ModelResponse
from agents.models.interface import Model
from agents.usage import Usage
from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText

import email_agent
import guardrails
import planner_agent
import research_manager
import search_agent
import writer_agent

set_tracing_disabled(True)

# Two searches share a URL, so 3 unique sources are expected.
TAVILY_RESULTS = {
    "q0": [
        {"title": "Shared page", "url": "https://shared.com/a", "content": "shared facts"},
        {"title": "Only in q0", "url": "https://q0.com", "content": "q0 facts"},
    ],
    "q1": [
        {"title": "Shared page", "url": "https://shared.com/a/", "content": "shared facts"},
        {"title": "Only in q1", "url": "https://q1.com", "content": "q1 facts"},
    ],
}


class FakeTavily:
    async def search(self, query, **kwargs):
        return {"results": TAVILY_RESULTS[query]}


def message(text: str) -> ModelResponse:
    content = [ResponseOutputText(type="output_text", text=text, annotations=[])]
    output = [ResponseOutputMessage(id="m", type="message", role="assistant", status="completed", content=content)]
    return ModelResponse(output=output, usage=Usage(), response_id=None)


def tool_call(name: str, args: dict) -> ModelResponse:
    call = ResponseFunctionToolCall(type="function_call", call_id="c1", name=name, arguments=json.dumps(args))
    return ModelResponse(output=[call], usage=Usage(), response_id=None)


def tool_output(input_items) -> str | None:
    if isinstance(input_items, str):
        return None
    for item in input_items:
        if isinstance(item, dict) and item.get("type") == "function_call_output":
            return item["output"]
    return None


class FakeModel(Model):
    def __init__(self, agent_name: str):
        self.agent_name = agent_name

    async def get_response(self, system_instructions, input, *args, **kwargs):
        if self.agent_name == "Query Checker":
            return message(json.dumps({"is_allowed": True, "reason": "ok"}))
        if self.agent_name == "Planner Agent":
            searches = [{"reason": "r", "query": q} for q in TAVILY_RESULTS]
            return message(json.dumps({"searches": searches}))
        if self.agent_name == "Search Agent":
            results = tool_output(input)
            if results is None:
                query = re.search(r"Search term: (\w+)", json.dumps(input)).group(1)
                return tool_call("search_web_tool", {"query": query})
            ids = re.findall(r"^\[(\d+)\]", results, re.MULTILINE)
            return message(" ".join(f"Fact [{i}]." for i in ids))
        if self.agent_name == "Writer Agent":
            # Cites a real source, an invalid id, and adds its own Sources section.
            report = "# Report\n\nShared claim [1]. Q1 claim [3]. Bogus claim [99].\n\n## Sources\n- https://fake.example"
            return message(json.dumps({"short_summary": "s", "markdown_report": report, "follow_up_questions": []}))
        raise AssertionError(f"Unexpected agent {self.agent_name}")

    def stream_response(self, *args, **kwargs):
        raise NotImplementedError


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(search_agent, "client", FakeTavily())
    monkeypatch.setattr(research_manager, "USE_EMAIL", False)
    agents_to_fake = [
        guardrails.query_checker,
        planner_agent.planner_agent,
        search_agent.search_agent,
        writer_agent.writer_agent,
        email_agent.email_agent,
    ]
    for agent in agents_to_fake:
        monkeypatch.setattr(agent, "model", FakeModel(agent.name))
    # The fake model decides itself when to call the tool.
    monkeypatch.setattr(search_agent.search_agent, "model_settings", ModelSettings())


async def test_report_has_linked_citations_and_references():
    updates = [u async for u in research_manager.ResearchManager().run("query")]
    report = updates[-1]

    assert any("found 3 unique sources across 2 searches (0 failed)" in u for u in updates)
    assert any("citing 2 sources" in u for u in updates)

    assert "Shared claim [[1]](https://shared.com/a)." in report
    assert "Q1 claim [[2]](https://q1.com)." in report
    assert "99" not in report
    assert "fake.example" not in report

    references = report.split("## References", 1)[1]
    assert "1. [Shared page](https://shared.com/a)" in references
    assert "2. [Only in q1](https://q1.com)" in references
    assert "q0.com" not in references


class EmptyTavily:
    async def search(self, query, **kwargs):
        return {"results": []}


async def test_run_stops_when_no_sources_found(monkeypatch):
    monkeypatch.setattr(search_agent, "client", EmptyTavily())
    updates = [u async for u in research_manager.ResearchManager().run("query")]
    assert "returned no sources" in updates[-1]
