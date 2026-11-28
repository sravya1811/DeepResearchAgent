from agents import Runner, trace, gen_trace_id,InputGuardrailTripwireTriggered
from search_agent import search_agent
from planner_agent import planner_agent, WebSearchItem, WebSearchPlan
from writer_agent import writer_agent, ReportData
from email_agent import email_agent, USE_EMAIL
from sources import SourceRegistry, finalize_report
import asyncio
import logging

logger = logging.getLogger(__name__)

class ResearchManager:

    async def run(self, query: str):
        """ Run the deep research process, yielding the status updates and the final report"""
        trace_id = gen_trace_id()
        registry = SourceRegistry()
        with trace("Research trace", trace_id=trace_id):
            yield f"Starting research. Trace: https://platform.openai.com/traces/trace?trace_id={trace_id}"
            try:
                search_plan = await self.plan_searches(query)
            except InputGuardrailTripwireTriggered as e:
                reason = e.guardrail_result.output.output_info.reason
                yield f"Research query denied: {reason}"
                return

            yield f"Searches planned, starting {len(search_plan.searches)} searches..."     
            search_results = await self.perform_searches(search_plan, registry)
            failed = len(search_plan.searches) - len(search_results)
            if not search_results or len(registry) == 0:
                yield "All searches failed or returned no sources. Please check your API keys / network and try again."
                return
            yield (
                f"Searches complete: found {len(registry)} unique sources across "
                f"{len(search_results)} searches ({failed} failed). Writing report..."
            )
            report = await self.write_report(query, search_results, registry)
            report.markdown_report, cited = finalize_report(report.markdown_report, registry)
            yield f"Report written, citing {len(cited)} sources."
            if USE_EMAIL:
                yield "Report written, sending email..."
                await self.send_email(report)
                yield "Email sent, research complete"
            else:
                yield "Report written. Email was skipped and cannot be sent because the email option is disabled."
            yield report.markdown_report

    async def plan_searches(self, query: str) -> WebSearchPlan:
        """ Plan the searches to perform for the query """
        result = await Runner.run(planner_agent, f"Query: {query}")
        return result.final_output

    async def perform_searches(self, search_plan: WebSearchPlan, registry: SourceRegistry) -> list[str]:
        """ Perform the searches to perform for the query """
        tasks = [self.search(item, registry) for item in search_plan.searches]
        results = await asyncio.gather(*tasks)
        return [r for r in results if r is not None]

    async def search(self, item: WebSearchItem, registry: SourceRegistry) -> str | None:
        """ Perform a search for the query """
        input_message = f"Search term: {item.query}\nReason for searching: {item.reason}"
        try:
            result = await Runner.run(search_agent, input_message, context=registry)
            return result.final_output
        except Exception as e:
            logger.warning("Search failed for %r: %s", item.query, e)
            return None

    async def write_report(self, query: str, search_results: list[str], registry: SourceRegistry) -> ReportData:
        """ Write the report for the query """
        source_list = "\n".join(f"[{s.id}] {s.title}" for s in registry.sources)
        summaries = "\n\n---\n\n".join(search_results)
        input_message = (
            f"Original query: {query}\n\n"
            f"Available sources:\n{source_list}\n\n"
            f"Summarized search results:\n\n{summaries}"
        )
        result = await Runner.run(writer_agent, input_message)
        return result.final_output
    
    async def send_email(self, report: ReportData) -> None:
        await Runner.run(email_agent, report.markdown_report)