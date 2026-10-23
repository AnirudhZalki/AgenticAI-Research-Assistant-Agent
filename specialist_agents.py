"""
Lab 7: Specialist Agents Roster (Phase B - Orchestration)
Typed, single-responsibility agents that follow the proposal's guardrails:

  * never fabricate a citation, abstract or result  (no synthesized papers; no invented numbers)
  * state uncertainty about novelty instead of asserting it
  * mark AI-drafted text clearly; leave results/methods for the authors to complete
  * flag missing/inconsistent citations instead of inventing them
  * timestamp radar alerts; preserve co-author attribution (never overwrite silently)
  * keep version history with source links

Agents: LiteratureDiscovery, GapAnalysis, DraftingWriting, CitationCompliance, FundingRadar,
Collaboration, ExportRepository.  Each exposes step(ctx, connector) -> ctx.
"""

import re
import time
from datetime import date, datetime
from typing import Any, Dict, List

from connector import ResearchDataConnector
from domain import (CitationFormatter, OriginalityChecker, all_pack_abbreviations, detect_domain, get_pack,
                    parse_venue)
from tracker import ResearchTracker

AI_TAG = "[AI-DRAFTED - pending faculty review]"
_STOP = set("a an and are as at be by for from in into is it of on or the to with using use via based "
            "towards toward their its this that these those over under study approach method".split())


def terms(text: str) -> List[str]:
    """Lower-cased content words (len > 2, no stop words), order-preserving and de-duplicated."""
    seen, out = set(), []
    for w in re.findall(r"[a-z0-9][a-z0-9\-]+", (text or "").lower()):
        if len(w) > 2 and w not in _STOP and w not in seen:
            seen.add(w)
            out.append(w)
    return out


def _paper_text(p: Dict[str, Any]) -> str:
    return f"{p.get('title', '')} {p.get('abstract', '')} {' '.join(p.get('keywords', []) or [])}".lower()


ABBREV = {
    "gru": ["gated recurrent unit"], "lstm": ["long short-term memory", "long short term memory"],
    "rnn": ["recurrent neural network"], "cnn": ["convolutional neural network"],
    "gan": ["generative adversarial network"], "gnn": ["graph neural network"],
    "nlp": ["natural language processing"], "llm": ["large language model"],
    "rag": ["retrieval-augmented generation", "retrieval augmented generation"],
    "iot": ["internet of things"], "rl": ["reinforcement learning"], "svm": ["support vector machine"],
    "tinyml": ["tiny machine learning"], "bert": ["bidirectional encoder representations"],
    "vit": ["vision transformer"], "nas": ["neural architecture search"],
}


for _k, _v in all_pack_abbreviations().items():          # domain packs extend the acronym table (XRD, PCR, ...)
    ABBREV.setdefault(_k, _v)

DEFAULT_APPROVED_SOURCES = ["SemanticScholar", "CrossRef", "OpenAlex", "LocalCorpus (mock dataset)", "ResearcherLibrary"]


def make_evidence(p: Dict[str, Any], topic: str, approved: List[str]) -> Dict[str, Any]:
    """Evidence record for one retrieved item: provenance, scope, tags and the sentence that supports relevance."""
    abstract = p.get("abstract") or ""
    sents = [x for x in re.split(r"(?<=[.!?])\s+", abstract) if len(x) > 25]
    tset = set(terms(topic))
    best = max(sents, key=lambda x: len(tset & set(terms(x))), default="")
    has_record = bool(p.get("title")) and (bool(abstract) or (p.get("doi") not in (None, "", "N/A")))
    in_scope = p.get("source") in approved
    tags = list(p.get("keywords") or []) or sorted(tset & set(terms(_paper_text(p))))
    return {"source": p.get("source"), "scope": "approved corpus" if in_scope else "OUT OF SCOPE",
            "tags": tags, "retrieved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "supporting_sentence": strip_cites(best), "in_scope": in_scope,
            "grounded": in_scope and has_record}


def expand_query(topic: str) -> str:
    """Append the spelled-out form of known acronyms (GRU -> gated recurrent unit) so searches find real papers."""
    extra = []
    for w in re.findall(r"[A-Za-z0-9\-]+", topic or ""):
        for phrase in ABBREV.get(w.lower(), [])[:1]:
            if phrase not in topic.lower():
                extra.append(phrase)
    return f"{topic} {' '.join(extra)}".strip()


def relevance(topic: str, paper: Dict[str, Any]) -> float:
    """Fraction of topic terms found in the paper's title/abstract/keywords (acronyms match their expansion)."""
    t = terms(topic)
    if not t:
        return 0.0
    text = _paper_text(paper)
    words = set(re.findall(r"[a-z0-9\-]+", text))

    def hit(w: str) -> bool:
        if w in words or any(ph in text for ph in ABBREV.get(w, [])):
            return True
        return len(w) > 4 and any(x.startswith(w[:len(w) - 2]) for x in words)   # plurals / suffixes
    return round(sum(1 for w in t if hit(w)) / len(t), 3)


def year_of(p: Dict[str, Any]) -> int:
    """Publication year as int; 0 when missing/garbled (real APIs return None or strings)."""
    m = re.search(r"\d{4}", str(p.get("year") or ""))
    return int(m.group()) if m else 0


def strip_cites(text: str) -> str:
    """Remove the source's own bracketed citation markers ([12], [3, 4], [1-3]) so they are not mistaken for ours."""
    return re.sub(r"\[\s*\d+(?:\s*[,;\u2013-]\s*\d+)*\s*\]", "", text or "")


def first_sentence(text: str, limit: int = 240) -> str:
    s = re.split(r"(?<=[.!?])\s", (text or "").strip())[0]
    return s if len(s) <= limit else s[:limit].rsplit(" ", 1)[0] + "..."


# ---------------------------------------------------------------------------------------------------------------------
class LiteratureDiscoveryAgent:
    """Agent 1: ranked reading list from scholarly sources (live APIs when available, else the local corpus)."""

    target_count = 6

    def step(self, ctx: Dict[str, Any], connector: ResearchDataConnector) -> Dict[str, Any]:
        topic = ctx.get("topic", "edge AI hardware porting frameworks")
        warnings: List[str] = []

        print(f"    [LiteratureDiscoveryAgent] Querying scholarly sources for: '{topic}'")
        live = connector.search_online_papers(expand_query(topic), max_results=self.target_count, agent_id="LiteratureDiscoveryAgent")
        local = connector.read_paper_corpus("", agent_id="LiteratureDiscoveryAgent")

        pool: Dict[str, Dict[str, Any]] = {}
        swarm = (ctx.get("swarm_results") or {}).get("consolidated_papers", [])
        for p in list(live) + list(swarm) + list(local):
            key = re.sub(r"\W+", " ", (p.get("title") or "").lower()).strip()
            if key and key not in pool:
                q = dict(p)
                q.setdefault("source", "LocalCorpus (mock dataset)")
                pool[key] = q
        approved = list(ctx.get("approved_sources") or DEFAULT_APPROVED_SOURCES)
        rejected, kept = [], {}
        for key, p in pool.items():                       # grounding step (Lab 9): ungrounded/out-of-scope items are rejected
            ev = make_evidence(p, topic, approved)
            if ev["grounded"]:
                kept[key] = p
            else:
                rejected.append({"title": p.get("title"), "source": p.get("source"),
                                 "reason": "out of approved scope" if not ev["in_scope"] else "no abstract or DOI to ground it"})
        ctx["rejected_references"] = rejected
        ranked = sorted(kept.values(), key=lambda p: (relevance(topic, p), year_of(p)), reverse=True)
        strong = [p for p in ranked if relevance(topic, p) >= 0.3]
        weak = [p for p in ranked if 0 < relevance(topic, p) < 0.3]
        chosen = (strong + weak)[: self.target_count]          # papers sharing no topic term are never listed

        summarized = []
        for idx, p in enumerate(chosen, start=1):
            rel = relevance(topic, p)
            doi = p.get("doi") or "N/A"
            summarized.append({
                "ref_num": idx, "id": p.get("id", f"REF_{idx}"), "title": p.get("title", "Untitled"),
                "year": year_of(p) or "n.d.", "venue": p.get("venue", "Unknown Venue"),
                "authors": p.get("authors") or ["Unknown"],
                "summary": strip_cites(p.get("abstract") or "") or "No abstract available.",
                "keywords": p.get("keywords", []), "doi": doi,
                "source": p["source"], "relevance": rel, "topic_match": rel >= 0.3,
                "source_link": f"https://doi.org/{doi}" if doi != "N/A" else "",
                "retrieved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "evidence": make_evidence(p, topic, approved),
            })

        on_topic = sum(1 for p in summarized if p["topic_match"])
        if not summarized:
            warnings.append(f"NO relevant sources found for '{topic}'. Turn on 'Use live academic APIs' (the offline mock "
                            f"corpus only covers a few demo topics) or broaden the topic.")
        elif len(summarized) < self.target_count:
            warnings.append(f"Only {len(summarized)} relevant papers found (target {self.target_count}); "
                            f"no references were invented or padded.")
        if on_topic < len(summarized):
            warnings.append(f"{len(summarized) - on_topic} of {len(summarized)} references are weakly related to the topic "
                            f"(relevance < 0.30) - review before citing.")
        if summarized and all("mock" in p["source"] for p in summarized):
            warnings.append("All references come from the local MOCK corpus. Enable live academic APIs for real citations.")

        if rejected:
            warnings.append(f"{len(rejected)} candidate(s) rejected by the grounding step (see evidence log).")
        ctx["reading_list"] = summarized
        ctx["literature_warnings"] = warnings
        print(f"  [LiteratureDiscoveryAgent] Ranked {len(summarized)} papers ({on_topic} on-topic).")
        return ctx


# ---------------------------------------------------------------------------------------------------------------------
class GapAnalysisAgent:
    """Agent 2: evidence-based novelty vs overlap, with explicit uncertainty."""

    def step(self, ctx: Dict[str, Any], connector: ResearchDataConnector) -> Dict[str, Any]:
        topic = ctx.get("topic", "Research Topic")
        refs = ctx.get("reading_list", [])
        t = terms(topic)

        close = [p for p in refs if p["relevance"] >= 0.8]
        partial = [p for p in refs if 0.4 <= p["relevance"] < 0.8]
        coverage = {w: sum(1 for p in refs if w in _paper_text(p)) for w in t}
        thin = [w for w, c in coverage.items() if c <= 1]
        well = [w for w, c in coverage.items() if c >= max(3, len(refs) // 2)]

        if not refs:
            flag, level = "NOT ASSESSABLE - no sources were retrieved", "NONE"
        elif len(close) >= 3:
            flag, level = "LIKELY WELL-COVERED - needs a sharply differentiated contribution", "LOW"
        elif close or len(partial) >= 2:
            flag, level = "PARTIALLY COVERED - novelty must come from a specific angle", "MEDIUM"
        else:
            flag, level = "NO CLOSE MATCH FOUND in the sources searched (possible gap - verify manually)", "HIGH"

        library = connector.read_researcher_library(agent_id="GapAnalysisAgent")
        related_own = [l["title"] for l in library if relevance(topic, l) >= 0.2]
        angles = []
        if thin:
            angles.append(f"Terms covered by at most one retrieved paper (candidate angles): {', '.join(thin)}.")
        if well:
            angles.append(f"Heavily covered terms (avoid claiming novelty here): {', '.join(well)}.")
        if related_own:
            angles.append(f"Build on your own prior work: {'; '.join(related_own)}.")
        if not angles:
            angles.append("No distinguishing angle detected automatically; authors must articulate the contribution.")

        closest = sorted(refs, key=lambda p: p["relevance"], reverse=True)[:3]
        ctx["gap_analysis"] = {
            "topic": topic, "total_cited_references": len(refs),
            "novelty_flag": flag, "novelty_level": level,
            "closest_prior_work": [f"[{p['ref_num']}] {p['title']} (relevance {p['relevance']})" for p in closest],
            "term_coverage": coverage,
            "existing_literature_summary": (
                f"{len(close)} close and {len(partial)} partial matches among {len(refs)} retrieved papers."),
            "identified_research_gap": (
                f"Under-covered aspects: {', '.join(thin) if thin else 'none detected'}. "
                f"This is a lexical overlap estimate, not a semantic proof."),
            "why_our_work_is_unique": angles,
            "uncertainty": (
                f"Based only on {len(refs)} retrieved papers from "
                f"{', '.join(sorted({p['source'] for p in refs})) or 'no source'}. Absence of a match is not proof "
                f"of novelty; authors must verify with a full literature search."),
            "novelty_positioning_statement": (
                f"Preliminary assessment ({level} novelty confidence): {flag}."),
            "novelty_summary": (
                f"This draft investigates {topic}. Preliminary novelty assessment against {len(refs)} retrieved papers: "
                f"{flag}. Authors must confirm novelty claims."),
        }
        print(f"  [GapAnalysisAgent] Novelty: {flag}")
        return ctx


# ---------------------------------------------------------------------------------------------------------------------
class DraftingWritingAgent:
    """Agent 3: outline first, then a draft that only states what the retrieved evidence supports."""

    def make_outline(self, ctx: Dict[str, Any]) -> List[str]:
        if ctx.get("confirmed_outline"):
            return list(ctx["confirmed_outline"])
        if ctx.get("plan_sections"):
            return list(ctx["plan_sections"])
        spec = parse_venue(ctx.get("venue", ""))
        return [f"{i}. {s}" for i, s in enumerate(spec.sections, 1)]

    @staticmethod
    def _kind(title: str) -> str:
        t = title.lower()
        for kind, keys in (("domain", ("reproducib", "ethic", "consent", "synthesis", "characteriz", "availability")),
                           ("lit", ("literature", "related", "background", "prior", "taxonomy")),
                           ("unique", ("unique", "novel", "gap", "challenge", "differentiat")),
                           ("intro", ("abstract", "introduction", "summary", "motivation")),
                           ("method", ("method", "architecture", "approach", "work plan", "objective")),
                           ("experiment", ("experiment", "result", "evaluat", "benchmark", "outcome", "budget")),
                           ("conclusion", ("conclusion", "future", "discussion"))):
            if any(k in t for k in keys):
                return kind
        return "generic"

    def build_section(self, ctx: Dict[str, Any], title: str) -> str:
        """Build ONE section (also used by the self-healer to regenerate only a failing section)."""
        topic = ctx.get("topic", "Research Topic")
        venue = ctx.get("venue", "IEEE Conference")
        refs = ctx.get("reading_list", [])
        gap = ctx.get("gap_analysis", {})
        pack = get_pack(ctx.get("domain") or detect_domain(topic))
        kind = self._kind(title)
        if kind == "lit":
            lines = [AI_TAG, f"The retrieved literature on {topic} comprises {len(refs)} papers:"]
            for p in refs:
                lines.append(
                    f"  - [{p['ref_num']}] {', '.join(p['authors'][:3])}{' et al.' if len(p['authors']) > 3 else ''} "
                    f"({p['year']}), \"{p['title']}\", {p['venue']}. DOI: {p['doi']} [Source: {p['source']}]\n"
                    f"    Summary: {first_sentence(p['summary'])}")
            return "\n".join(lines)
        if kind == "unique":
            return (f"{AI_TAG}\nPRELIMINARY NOVELTY ASSESSMENT: {gap.get('novelty_flag', 'n/a')}\n"
                    f"Closest prior work: {'; '.join(gap.get('closest_prior_work', [])) or 'none'}\n"
                    f"Candidate angles:\n" + "\n".join(f"  - {a}" for a in gap.get("why_our_work_is_unique", []))
                    + f"\nUNCERTAINTY: {gap.get('uncertainty', '')}")
        if kind == "intro":
            return (f"{AI_TAG}\nThis work addresses {topic}, targeting {venue}. "
                    f"Preliminary novelty assessment: {gap.get('novelty_flag', 'n/a')}. "
                    f"Contributions must be stated by the authors.")
        if kind == "method":
            return (f"{AI_TAG}\n[AUTHORS TO COMPLETE: describe the proposed method for {topic}. {pack.guidance_text()}. "
                    f"The assistant does not invent design details.]")
        if kind == "experiment":
            base = ", ".join("[" + str(p["ref_num"]) + "]" for p in refs[:4])
            return (f"{AI_TAG}\n[AUTHORS TO COMPLETE: experimental setup, baselines drawn from {base}, metrics and "
                    f"measured results. No results are claimed by the assistant.]")
        if kind == "domain":
            return f"{AI_TAG}\n[AUTHORS TO COMPLETE: {title}. {pack.guidance_text()}.]"
        if kind == "conclusion":
            return (f"{AI_TAG}\n[AUTHORS TO COMPLETE: summarize validated findings and future work on {topic} "
                    f"once results exist.]")
        return f"{AI_TAG}\n[AUTHORS TO COMPLETE: content for this section on {topic}.]"

    def _ensure_all_cited(self, ctx: Dict[str, Any], sections: Dict[str, str], outline: List[str]):
        refs = ctx.get("reading_list", [])
        cited = {int(n) for body in sections.values() for n in re.findall(r"\[(\d+)\]", body)}
        missing = [p["ref_num"] for p in refs if p["ref_num"] not in cited]
        if missing and sections:
            first = next((t for t in outline if self._kind(t) in ("intro", "lit")), outline[0])
            sections[first] += "\nAdditional references considered: " + ", ".join(f"[{n}]" for n in missing) + "."

    def step(self, ctx: Dict[str, Any], connector: ResearchDataConnector) -> Dict[str, Any]:
        refs = ctx.get("reading_list", [])
        outline = self.make_outline(ctx)
        sections = {title: self.build_section(ctx, title) for title in outline}
        self._ensure_all_cited(ctx, sections, outline)
        ctx["outline"] = outline
        ctx["draft_sections"] = sections
        ctx["references"] = refs
        # every drafted claim is paired with the reference (and evidence record) that supports it
        ctx["claims"] = [{"text": first_sentence(p["summary"]), "ref": p["ref_num"]} for p in refs]
        print(f"  [DraftingWritingAgent] Drafted {len(sections)} sections citing {len(refs)} references.")
        return ctx


# ---------------------------------------------------------------------------------------------------------------------
class CitationComplianceAgent:
    """Agent 4: reference completeness, in-text consistency, venue style/limits, originality screening."""

    def step(self, ctx: Dict[str, Any], connector: ResearchDataConnector) -> Dict[str, Any]:
        refs = ctx.get("references", ctx.get("reading_list", []))
        sections = ctx.get("draft_sections", {})
        spec = parse_venue(ctx.get("venue", ""))
        library = connector.read_researcher_library(agent_id="CitationComplianceAgent")
        errors: List[str] = []
        warnings: List[str] = []

        if len(refs) < 5:
            errors.append(f"only {len(refs)} relevant reference(s) found; at least 5 are required - enable live "
                          f"academic APIs or broaden the topic")
        seen_titles = set()
        for p in refs:
            tag = f"[{p.get('ref_num')}]"
            if not p.get("title"):
                errors.append(f"{tag} missing title")
            for fld in ("authors", "year"):
                if not p.get(fld) or p.get(fld) in ("Unknown", ["Unknown"], "n.d."):
                    warnings.append(f"{tag} missing {fld} - verify at the source (not invented)")
            if "synth" in str(p.get("source", "")).lower():
                errors.append(f"{tag} synthesized (unverifiable) reference - remove")
            if p.get("doi") in (None, "", "N/A"):
                warnings.append(f"{tag} no DOI - verify it exists")
            if not p.get("topic_match", True):
                warnings.append(f"{tag} weakly related to the topic")
            k = (p.get("title") or "").lower()
            if k in seen_titles:
                errors.append(f"{tag} duplicate reference")
            seen_titles.add(k)

        full_text = "\n".join(sections.values())
        own_text = "\n".join(l for l in full_text.splitlines() if "Summary:" not in l)
        cited = {int(n) for n in re.findall(r"\[(\d+)\]", own_text)}
        listed = {p.get("ref_num") for p in refs}
        for n in sorted(cited - listed):
            errors.append(f"in-text citation [{n}] has no reference entry")
        for n in sorted(listed - cited):
            warnings.append(f"reference [{n}] is never cited in the text")

        words = len(re.findall(r"\w+", full_text))
        if words > spec.word_limit:
            warnings.append(f"draft has {words} words, over the {spec.word_limit}-word limit ({spec.page_limit} pages)")

        formatter = CitationFormatter()
        formatted = formatter.format_all(refs, spec.citation_style)
        originality = OriginalityChecker().check(sections, refs + list(library))
        if originality["flagged_sections"]:
            warnings.append(f"high text overlap with known sources in: {', '.join(originality['flagged_sections'])}")

        pack = get_pack(ctx.get("domain") or detect_domain(ctx.get("topic", "")))
        domain_checks = pack.checks(sections)
        for dc in domain_checks:
            if dc["status"] != "PASS":
                warnings.append(f"[{pack.name}] {dc['check']}: {dc['status'].replace('_', ' ').lower()} (needs {dc['needs']})")
        self_cite = [l for l in library if relevance(ctx.get("topic", ""), l) >= 0.2]
        report = {
            "total_references": len(refs),
            "missing_dois": [p["id"] for p in refs if p.get("doi") in (None, "", "N/A")],
            "self_citations_available": len(library),
            "suggested_self_citations": [l["title"] for l in self_cite],
            "citation_style": spec.citation_style, "word_count": words, "word_limit": spec.word_limit,
            "errors": errors, "warnings": warnings,
            "formatted_references": formatted, "originality": originality,
            "domain": pack.key, "domain_checks": domain_checks,
            "compliance_passed": len(refs) >= 5 and not errors,
        }
        ctx["citation_compliance"] = report
        ctx["formatted_references"] = formatted
        print(f"  [CitationComplianceAgent] {len(errors)} errors, {len(warnings)} warnings: Passed={report['compliance_passed']}")
        return ctx


# ---------------------------------------------------------------------------------------------------------------------
class FundingRadarAgent:
    """Agent 5: timestamped, topic-ranked journal/CFP/grant deadlines."""

    def step(self, ctx: Dict[str, Any], connector: ResearchDataConnector) -> Dict[str, Any]:
        topic = ctx.get("topic", "")
        tset = set(terms(topic))
        alerts: Dict[str, Dict[str, Any]] = {}
        for w in tset:
            for d in connector.read_funding_deadlines(w, agent_id="FundingRadarAgent"):
                alerts.setdefault(d["id"], dict(d))
        matched = bool(alerts)
        if not alerts:
            for d in connector.read_funding_deadlines("", agent_id="FundingRadarAgent-Fallback"):
                alerts[d["id"]] = dict(d)

        user_deadline = None
        try:
            user_deadline = datetime.strptime(str(ctx.get("deadline", "")), "%Y-%m-%d").date()
        except ValueError:
            pass
        today = date.today()
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        out = []
        for d in alerts.values():
            try:
                dd = datetime.strptime(d.get("deadline", ""), "%Y-%m-%d").date()
                days = (dd - today).days
            except ValueError:
                dd, days = None, None
            overlap = len(tset & set(terms(" ".join(d.get("topics", [])))))
            d.update({
                "checked_at": now, "days_remaining": days,
                "status": "EXPIRED" if days is not None and days < 0 else "UPCOMING",
                "topic_relevance": overlap if matched else 0,
                "before_your_deadline": bool(dd and user_deadline and dd <= user_deadline),
            })
            out.append(d)
        out.sort(key=lambda d: (d["status"] == "EXPIRED", d["days_remaining"] if d["days_remaining"] is not None else 9999))
        ctx["radar_deadlines"] = out
        print(f"  [FundingRadarAgent] {len(out)} alerts ({'topic-matched' if matched else 'unfiltered fallback'}).")
        return ctx


# ---------------------------------------------------------------------------------------------------------------------
class CollaborationAgent:
    """Agent 6: section ownership + attributed edits. Never overwrites: conflicts are surfaced to the owner."""

    @staticmethod
    def _norm(s: str) -> str:
        return re.sub(r"^\d+\.\s*", "", s).lower().strip()

    def _owner(self, section: str, ownership: Dict[str, str]) -> str:
        n = set(terms(self._norm(section)))
        best, score = "", 0
        for sec, owner in ownership.items():
            s = len(n & set(terms(self._norm(sec))))
            if s > score:
                best, score = owner, s
        return best

    def step(self, ctx: Dict[str, Any], connector: ResearchDataConnector) -> Dict[str, Any]:
        notes = dict(connector.read_collaboration_notes(agent_id="CollaborationAgent"))
        ownership = dict(notes.get("section_ownership", {}))
        edits = list(notes.get("coauthor_edits", [])) + list(ctx.get("coauthor_edits", []))
        sections = list(ctx.get("draft_sections", {}).keys()) or list(ownership.keys())

        attribution, conflicts, unassigned = [], [], []
        for sec in sections:
            owner = self._owner(sec, ownership)
            sec_edits = [e for e in edits if set(terms(self._norm(e.get("section", "")))) &
                         set(terms(self._norm(sec)))]
            authors = {e["author"] for e in sec_edits}
            status = "OK"
            if not owner:
                unassigned.append(sec)
                status = "UNASSIGNED"
            if len(authors) > 1:
                status = "CONFLICT"
                conflicts.append({"section": sec, "authors": sorted(authors), "action": "owner must reconcile; nothing overwritten"})
            elif authors and owner and not any(owner.startswith(a) or a.startswith(owner) for a in authors):
                status = "PENDING_OWNER_CONFIRMATION"
            attribution.append({"section": sec, "owner": owner or "-", "edits": sec_edits, "status": status})

        notes_out = {}
        for a in attribution:
            for e in a["edits"]:
                notes_out.setdefault(a["section"], []).append(
                    f"[Edit by {e['author']} - {a['status']}] {e.get('note', '')}")
        ctx["collab_annotations"] = notes_out
        ctx["collaboration"] = {
            "collaborators": notes.get("collaborators", []),
            "section_ownership": ownership, "attribution": attribution,
            "conflicts": conflicts, "unassigned_sections": unassigned,
            "policy": "Edits are attributed and kept alongside the draft; no co-author text is silently overwritten.",
        }
        print(f"  [CollaborationAgent] {len(attribution)} sections tracked, {len(conflicts)} conflicts, "
              f"{len(unassigned)} unassigned.")
        return ctx


# ---------------------------------------------------------------------------------------------------------------------
class ExportRepositoryAgent:
    """Agent 7: logs the approved document into the research tracker with version history and source links."""

    def __init__(self, tracker: ResearchTracker = None):
        self.tracker = tracker if tracker is not None else ResearchTracker()

    def step(self, ctx: Dict[str, Any], connector: ResearchDataConnector) -> Dict[str, Any]:
        entry = self.tracker.log_version(
            ctx.get("topic", ""), ctx.get("venue", ""), ctx.get("formatted_paper", ""),
            ctx.get("references", ctx.get("reading_list", [])),
            status="APPROVED", approved_by=ctx.get("approved_by", "Faculty Examiner"),
            note="Exported after faculty approval")
        ctx["export_status"] = "READY_FOR_PUBLICATION"
        ctx["version"] = entry["version"]
        ctx["tracker_entry"] = {k: v for k, v in entry.items() if k != "text"}
        print(f"  [ExportRepositoryAgent] Archived draft as {entry['version']} (sha256 {entry['sha256'][:10]}...).")
        return ctx
