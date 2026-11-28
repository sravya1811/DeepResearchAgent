from pydantic import BaseModel, Field
from agents import Agent
from dotenv import load_dotenv
import os

load_dotenv(override=True)
MODEL_NAME = os.getenv("DEFAULT_MODEL_NAME", "gpt-5.4-mini")

INSTRUCTIONS = """
You are a senior researcher tasked with writing a cohesive report for a research query.
You will be provided with the original query, and some research.
Generate a comprehensive report based on the research and the query.
The final output should be in markdown format, and it should be lengthy and detailed. Aim 
for 5-10 pages of content, at least 1000 words.

Citations:
- The research summaries cite sources with ids like [3], and you are given a list of the
  available sources by id and title.
- Back every factual claim with inline citations using those same ids, e.g. "... [3]" or
  "... [1, 4]". Keep the original ids; do not renumber them.
- Use only ids from the source list. Never write URLs.
- Do NOT add a References, Sources or Bibliography section; one is added automatically.
"""


class ReportData(BaseModel):
    short_summary: str = Field(description="A short 2-3 sentence summary of the findings.")
    markdown_report: str = Field(description="The final report")
    follow_up_questions: list[str] = Field(description="Suggested topics to research further")


writer_agent = Agent(name="Writer Agent", instructions=INSTRUCTIONS, model=MODEL_NAME, output_type=ReportData)
