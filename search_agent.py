import os

from agents import Agent, ModelSettings, RunContextWrapper, function_tool
from dotenv import load_dotenv
from tavily import AsyncTavilyClient

from sources import SourceRegistry, format_results_for_agent

load_dotenv(override=True)
MODEL_NAME = os.getenv("DEFAULT_MODEL_NAME", "gpt-5.4-mini")
client = AsyncTavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

INSTRUCTIONS = """
You are a research assistant. Given a search term, you search the web for that term and
produce a concise summary of the results. The summary must 2-3 paragraphs and less than 300 words.
Capture the main points and be succinct. Reply only with the summary.

Each search result is labelled with a source id like [3]. Cite the source of every fact inline
using those ids, for example: "Adoption grew 40% in 2025 [3]." or "...as reported by two studies [1, 4]."
Use only ids that appear in the results. Never write URLs or a list of sources.
"""

settings = ModelSettings(tool_choice="required")


@function_tool
async def search_web_tool(ctx: RunContextWrapper[SourceRegistry], query: str) -> str:
    """
    Search the web using Tavily and return relevant results, each labelled with a source id.

    Args:
        query: The search term to look up.
    """
    registry = ctx.context
    try:
        response = await client.search(
            query=query,
            search_depth="basic",
            max_results=5
        )
    except Exception as e:
        return f"Search failed for '{query}': {e}"

    sources = [
        registry.add(
            title=item.get("title") or "",
            url=item["url"],
            snippet=item.get("content") or "",
            query=query,
        )
        for item in response.get("results", [])
        if item.get("url")
    ]
    return format_results_for_agent(sources)


search_agent = Agent[SourceRegistry](
    name="Search Agent",
    instructions=INSTRUCTIONS,
    tools=[search_web_tool],
    model=MODEL_NAME,
    model_settings=settings,
)
