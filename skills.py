"""
Lab 3: Reusable Skills (Phase A - Foundations)
Packages repeatable capabilities into schema-typed skills.
1. ResearchPlanSkill: Expands clarified inputs into a locked research blueprint object.
2. FormattingSkill: Formats structured drafts into target venue guidelines (IEEE, ACM, IMRAD).
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any

@dataclass
class PlanBlueprint:
    title: str
    venue: str
    deadline: str
    collaborators: List[str]
    sections: List[str]
    word_limit: int = 4000
    citation_style: str = "IEEE"
    locked: bool = False

class ResearchPlanSkill:
    """Skill to generate and lock standard research plan blueprints."""
    
    def execute(self, inputs: Dict[str, Any]) -> PlanBlueprint:
        topic = inputs.get("topic", "General Research")
        venue = inputs.get("venue", "IEEE Conference")
        deadline = inputs.get("deadline", "TBD")
        collaborators_raw = inputs.get("collaborators", "Lead Author")
        
        if isinstance(collaborators_raw, str):
            collaborators = [c.strip() for c in collaborators_raw.split(",")]
        else:
            collaborators = collaborators_raw

        sections = [
            "1. Abstract & Introduction",
            "2. Literature Review & Discovered Prior Work (5-6 Cited References)",
            "3. Uniqueness & Novelty Decision (Why Our Work Is Unique)",
            "4. Proposed Methodology & Architecture",
            "5. Experimental Setup & Benchmarks",
            "6. Conclusion & Future Outlook"
        ]
        
        bp = PlanBlueprint(
            title=f"A Systematic Investigation into {topic.title()}",
            venue=venue,
            deadline=deadline,
            collaborators=collaborators,
            sections=sections,
            word_limit=5000 if "journal" in venue.lower() else 3000,
            citation_style="ACM" if "acm" in venue.lower() else "IEEE",
            locked=True
        )
        return bp

class FormattingSkill:
    """Skill to format research drafts according to venue template specifications."""
    
    def execute(self, draft_data: Dict[str, Any], venue_spec: str = "IEEE") -> str:
        title = draft_data.get("title", "Untitled Draft")
        authors = draft_data.get("collaborators", ["Faculty Author"])
        abstract = draft_data.get("abstract", "No abstract provided.")
        sections = draft_data.get("sections", {})
        references = draft_data.get("references", [])
        
        formatted = []
        formatted.append("==========================================================================")
        formatted.append(f"[{venue_spec.upper()} FORMATTED PAPER DRAFT]")
        formatted.append("==========================================================================")
        formatted.append(f"TITLE: {title}")
        formatted.append(f"AUTHORS: {', '.join(authors)}")
        formatted.append("--------------------------------------------------------------------------")
        formatted.append("ABSTRACT:")
        formatted.append(f"  {abstract}")
        formatted.append("--------------------------------------------------------------------------")
        
        for sec_name, content in sections.items():
            formatted.append(f"\n{sec_name.upper()}")
            formatted.append(f"{content}")
            
        formatted.append("\n--------------------------------------------------------------------------")
        formatted.append(f"REFERENCES (TOTAL CITED: {len(references)}):")
        if references:
            for idx, ref in enumerate(references, start=1):
                if isinstance(ref, dict):
                    authors_list = ref.get('authors', ['Anon'])
                    authors_str = ", ".join(authors_list) if isinstance(authors_list, list) else str(authors_list)
                    formatted.append(f"  [{idx}] {authors_str}, \"{ref.get('title')}\", {ref.get('venue', 'Conf.')}, {ref.get('year', '2024')}. DOI: {ref.get('doi', 'N/A')}")
                else:
                    formatted.append(f"  [{idx}] {ref}")
        else:
            formatted.append("  [1] No references cited.")
            
        formatted.append("==========================================================================\n")
        return "\n".join(formatted)

if __name__ == "__main__":
    plan_skill = ResearchPlanSkill()
    fmt_skill = FormattingSkill()
    
    bp = plan_skill.execute({"topic": "edge AI hardware porting", "venue": "IEEE Conference"})
    print(f"Plan skill produced locked blueprint: {bp.title} (Locked={bp.locked})")
    
    doc = fmt_skill.execute({"title": bp.title, "abstract": "Test abstract", "sections": {"1. Intro": "Hello world"}})
    print(doc[:300])
