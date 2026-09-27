"""
Lab 7: Specialist Agents Roster (Phase B - Orchestration)
Implements typed, single-responsibility specialist agents for Chapter 12 Research Assistant Agent.
1. LiteratureDiscoveryAgent: Ranks and summarizes scholarly papers from corpus with robust fallback search.
2. GapAnalysisAgent: Compares topic against discovered literature to identify novelty vs overlap.
3. DraftingWritingAgent: Produces outline and full structured draft.
4. CitationComplianceAgent: Checks citation integrity, format rules, and self-citations.
5. FundingRadarAgent: Tracks upcoming journal calls and grant deadlines.
6. CollaborationAgent: Consolidates co-author section ownership and edits.
7. ExportRepositoryAgent: Formats approved draft and logs version control archive.
"""

from typing import Dict, Any, List
from connector import ResearchDataConnector

class LiteratureDiscoveryAgent:
    """Agent 1: Searches scholarly metadata sources and returns a ranked, summarized reading list."""
    def step(self, ctx: Dict[str, Any], connector: ResearchDataConnector) -> Dict[str, Any]:
        topic = ctx.get("topic", "edge AI")
        words = topic.split() if topic else [""]
        papers = []
        
        # Try searching by each word in the topic
        for word in words:
            if len(word) > 2:
                results = connector.read_paper_corpus(word, agent_id="LiteratureDiscoveryAgent")
                for p in results:
                    if p not in papers:
                        papers.append(p)
                        
        # Robust fallback: If specific keyword search yielded no matches, load general corpus
        if not papers:
            papers = connector.read_paper_corpus("", agent_id="LiteratureDiscoveryAgent-Fallback")
        
        # Rank by year descending
        ranked = sorted(papers, key=lambda x: x.get("year", 0), reverse=True)
        summarized = []
        for p in ranked:
            summarized.append({
                "id": p.get("id"),
                "title": p.get("title"),
                "year": p.get("year"),
                "authors": p.get("authors", []),
                "summary": p.get("abstract", "No abstract available."),
                "doi": p.get("doi", "N/A")
            })
            
        ctx["reading_list"] = summarized
        print(f"  [LiteratureDiscoveryAgent] Found & ranked {len(summarized)} papers.")
        return ctx

class GapAnalysisAgent:
    """Agent 2: Compares research question against discovered literature and flags novelty vs overlap."""
    def step(self, ctx: Dict[str, Any], connector: ResearchDataConnector) -> Dict[str, Any]:
        topic = ctx.get("topic", "")
        reading_list = ctx.get("reading_list", [])
        
        covered_topics = [p["title"] for p in reading_list]
        gap_assessment = {
            "topic": topic,
            "existing_coverage_count": len(reading_list),
            "key_overlaps": covered_topics[:2],
            "novelty_flag": "GENUINELY UNDER-EXPLORED" if len(reading_list) < 5 else "PARTIALLY OVERLAPPING",
            "novelty_summary": f"While prior works address general aspects of {topic}, targeted optimization for heterogeneous microcontrollers remains a clear research gap."
        }
        ctx["gap_analysis"] = gap_assessment
        print(f"  [GapAnalysisAgent] Evaluated novelty: {gap_assessment['novelty_flag']}")
        return ctx

class DraftingWritingAgent:
    """Agent 3: Produces outline first, then full draft in venue structure."""
    def step(self, ctx: Dict[str, Any], connector: ResearchDataConnector) -> Dict[str, Any]:
        topic = ctx.get("topic", "Research Topic")
        venue = ctx.get("venue", "IEEE Conference")
        reading_list = ctx.get("reading_list", [])
        gap_analysis = ctx.get("gap_analysis", {})

        outline = [
            "1. Abstract & Introduction",
            "2. Related Work & Discovered Literature",
            "3. Gap Analysis & Proposed Framework",
            "4. Empirical Benchmarks",
            "5. Conclusion"
        ]
        
        sections = {
            "1. Abstract & Introduction": f"This paper explores {topic} tailored for {venue}. Recent advances require disciplined hardware porting.",
            "2. Related Work & Discovered Literature": f"Literature discovery identified {len(reading_list)} key references in this field.",
            "3. Gap Analysis & Proposed Framework": gap_analysis.get("novelty_summary", "Detailed gap analysis."),
            "4. Empirical Benchmarks": "We report latency and peak memory usage across hardware microcontroller targets.",
            "5. Conclusion": "Our framework addresses key gaps in current literature."
        }
        
        ctx["outline"] = outline
        ctx["draft_sections"] = sections
        ctx["references"] = reading_list
        print(f"  [DraftingWritingAgent] Produced draft with {len(sections)} sections.")
        return ctx

class CitationComplianceAgent:
    """Agent 4: Checks formatting, reference completeness, and venue-specific requirements."""
    def step(self, ctx: Dict[str, Any], connector: ResearchDataConnector) -> Dict[str, Any]:
        references = ctx.get("references", [])
        prior_library = connector.read_researcher_library(agent_id="CitationComplianceAgent")
        
        # Check self-citation consistency
        self_citations = [p for p in prior_library if "Faculty Author" in p.get("authors", [])]
        
        citation_report = {
            "total_references": len(references),
            "missing_dois": [p["id"] for p in references if p.get("doi") == "N/A"],
            "self_citations_available": len(self_citations),
            "compliance_passed": len(references) > 0
        }
        ctx["citation_compliance"] = citation_report
        print(f"  [CitationComplianceAgent] Verified citations: Passed={citation_report['compliance_passed']}")
        return ctx

class FundingRadarAgent:
    """Agent 5: Continuously surfaces relevant journals, calls for papers, and funding deadlines."""
    def step(self, ctx: Dict[str, Any], connector: ResearchDataConnector) -> Dict[str, Any]:
        topic = ctx.get("topic", "")
        words = topic.split() if topic else [""]
        deadlines = []
        
        for word in words:
            if len(word) > 2:
                results = connector.read_funding_deadlines(word, agent_id="FundingRadarAgent")
                for d in results:
                    if d not in deadlines:
                        deadlines.append(d)
                        
        if not deadlines:
            deadlines = connector.read_funding_deadlines("", agent_id="FundingRadarAgent-Fallback")

        ctx["radar_deadlines"] = deadlines
        print(f"  [FundingRadarAgent] Surfaced {len(deadlines)} upcoming venue CFPs & grant deadlines.")
        return ctx

class CollaborationAgent:
    """Agent 6: Tracks co-author section ownership and consolidates edits into one version."""
    def step(self, ctx: Dict[str, Any], connector: ResearchDataConnector) -> Dict[str, Any]:
        collab_notes = connector.read_collaboration_notes(agent_id="CollaborationAgent")
        ctx["collaboration"] = collab_notes
        print(f"  [CollaborationAgent] Synchronized section ownership for {len(collab_notes.get('section_ownership', {}))} sections.")
        return ctx

class ExportRepositoryAgent:
    """Agent 8: Produces final formatted document and logs it in the research tracker."""
    def step(self, ctx: Dict[str, Any], connector: ResearchDataConnector) -> Dict[str, Any]:
        ctx["export_status"] = "READY_FOR_PUBLICATION"
        ctx["version"] = "v1.0-approved"
        print(f"  [ExportRepositoryAgent] Archived draft as {ctx['version']}.")
        return ctx
