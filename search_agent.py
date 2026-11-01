from agents import Agent, WebSearchTool, ModelSettings
from dotenv import load_dotenv
import os

load_dotenv(override=True)
MODEL_NAME = os.getenv("DEFAULT_MODEL_NAME", "gpt-5.4-mini")

INSTRUCTIONS = """
You are a research assistant. Given a search term, you search the web for that term and 
produce a concise summary of the results. The summary must 2-3 paragraphs and less than 300 words.
Capture the main points and be succinct. Reply only with the summary.
"""

settings = ModelSettings(tool_choice="required")
tools = [WebSearchTool()]
"""WebsearchTool is a tool that allows the agent to perform web searches and retrieve relevant information. and it is an OPENAI hosted tool, Which is costed per call.
For an alternative tool for websearch use tavily It is designed for AI applications and RAG systems.
It provides search results in a structured format."""


search_agent = Agent(name="Search Agent", instructions=INSTRUCTIONS, tools=tools, model=MODEL_NAME, model_settings=settings)