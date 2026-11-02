
import os
from dotenv import load_dotenv
from tavily import TavilyClient

# Load environment variables from .env
load_dotenv()

# Initialize Tavily client
client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))


def search_web(query: str):
    """
    Search the web using Tavily and return relevant results.
    """
    response = client.search(
        query=query,
        search_depth="basic",
        max_results=5
    )

    results = []

    for item in response.get("results", []):
        results.append({
            "title": item.get("title"),
            "url": item.get("url"),
            "content": item.get("content")
        })

    return results
