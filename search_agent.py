import json
import os

from agents import Agent, ModelSettings, function_tool
from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv(override=True)
MODEL_NAME = os.getenv("DEFAULT_MODEL_NAME", "gpt-5.4-mini")
client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

INSTRUCTIONS = """
You are a research assistant. Given a search term, you search the web for that term and
produce a concise summary of the results. The summary must 2-3 paragraphs and less than 300 words.
Capture the main points and be succinct. Reply only with the summary.
"""

settings = ModelSettings(tool_choice="required")


@function_tool
def search_web_tool(query: str) -> str:
    """
    Search the web using Tavily and return relevant results as JSON.

    Args:
        query: The search term to look up.
    """
    try:
        response = client.search(
            query=query,
            search_depth="basic",
            max_results=5
        )
    except Exception as e:
        return f"Search failed for '{query}': {e}"

    results = []

    for item in response.get("results", []):
        results.append({
            "title": item.get("title"),
            "url": item.get("url"),
            "content": item.get("content")
        })

    return json.dumps(results)


search_agent = Agent(name="Search Agent", instructions=INSTRUCTIONS, tools=[search_web_tool], model=MODEL_NAME, model_settings=settings)
