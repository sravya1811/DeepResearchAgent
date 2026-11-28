from sources import SourceRegistry, finalize_report, format_results_for_agent


def make_registry() -> SourceRegistry:
    registry = SourceRegistry()
    registry.add("Alpha", "https://alpha.com/page")
    registry.add("Beta", "https://beta.com")
    registry.add("Gamma", "https://gamma.com")
    return registry


def test_ids_start_at_one_and_increment():
    registry = make_registry()
    assert [s.id for s in registry.sources] == [1, 2, 3]
    assert registry.get(2).title == "Beta"
    assert registry.get(0) is None
    assert registry.get(4) is None


def test_same_url_gets_same_id():
    registry = make_registry()
    duplicate = registry.add("Alpha again", "https://ALPHA.com/page/#section")
    assert duplicate.id == 1
    assert len(registry) == 3


def test_agent_view_has_ids_but_no_urls():
    registry = make_registry()
    text = format_results_for_agent(registry.sources)
    assert "[1] Alpha" in text
    assert "https://" not in text
    assert format_results_for_agent([]) == "No results found."


def test_citations_become_links_and_are_renumbered_by_first_use():
    report, cited = finalize_report("First [3]. Then [1].", make_registry())
    assert "First [[1]](https://gamma.com)." in report
    assert "Then [[2]](https://alpha.com/page)." in report
    assert [s.title for s in cited] == ["Gamma", "Alpha"]


def test_grouped_citations():
    report, cited = finalize_report("Both [2, 3].", make_registry())
    assert "Both [[1]](https://beta.com)[[2]](https://gamma.com)." in report
    assert len(cited) == 2


def test_repeated_citation_keeps_its_number():
    report, cited = finalize_report("A [2]. B [2].", make_registry())
    assert report.count("[[1]](https://beta.com)") == 2
    assert len(cited) == 1


def test_unknown_ids_are_dropped():
    report, cited = finalize_report("Real [1]. Fake [99]. Mixed [99, 2].", make_registry())
    assert "99" not in report
    assert "Fake." in report
    assert "Mixed [[2]](https://beta.com)." in report
    assert [s.id for s in cited] == [1, 2]


def test_references_list_only_cited_sources():
    report, _ = finalize_report("Only gamma [3].", make_registry())
    references = report.split("## References", 1)[1]
    assert "1. [Gamma](https://gamma.com)" in references
    assert "alpha.com" not in references
    assert "beta.com" not in references


def test_model_written_references_section_is_replaced():
    markdown = "Claim [1].\n\n## Sources\n\n- https://made-up.example.com"
    report, _ = finalize_report(markdown, make_registry())
    assert "made-up" not in report
    assert report.count("## References") == 1


def test_markdown_links_are_left_alone():
    report, cited = finalize_report("See [2](https://other.com) and [docs](https://x.com).", make_registry())
    assert "[2](https://other.com)" in report
    assert cited == []
    assert "## References" not in report


def test_link_text_brackets_are_escaped():
    registry = SourceRegistry()
    registry.add("Title [draft]", "https://a.com")
    report, _ = finalize_report("X [1].", registry)
    assert "1. [Title \\[draft\\]](https://a.com)" in report
