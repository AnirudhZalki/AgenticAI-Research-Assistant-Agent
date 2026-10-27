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


def clean_text(t: str) -> str:
    """Strip XML/JATS tags and entities that scholarly APIs leave in abstracts."""
    import html
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t or ""))).strip()


_EN_WORDS = set("the of and to in a is for on with that this are as by an be from we our which can it at or was have "
                "has been using results show based into their these".split())


def looks_english(t: str) -> bool:
    w = re.findall(r"[a-z']+", (t or "").lower())
    return len(w) < 12 or sum(x in _EN_WORDS for x in w) / len(w) >= 0.12


def sentences(text: str, k: int = 1) -> str:
    parts = [x.strip() for x in re.split(r"(?<=[.!?])\s+", clean_text(text)) if len(x.strip()) > 25]
    return " ".join(parts[:k])


METRIC_WORDS = ["latency", "throughput", "accuracy", "energy", "memory", "sram", "power", "precision", "recall",
                "f1", "speedup", "bandwidth", "robustness", "convergence", "perplexity", "error", "cost", "scalability"]


def analyze_literature(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Facts derived only from the retrieved papers: years, venues, recurring themes, metrics, term coverage."""
    from collections import Counter
    refs = [p for p in ctx.get("reading_list", [])]
    tset = set(terms(ctx.get("topic", "")))
    years = [year_of(p) for p in refs if year_of(p)]
    venues = [v for v, _ in Counter(p["venue"] for p in refs if p.get("venue") and "Unknown" not in p["venue"]).most_common(3)]
    cnt: Counter = Counter()
    for p in refs:
        for w in set(terms(_paper_text(p))):
            if w not in tset and len(w) > 4:
                cnt[w] += 1
    theme_terms = [w for w, c in cnt.most_common(12) if c >= 2][:4]
    themes = {w: [] for w in theme_terms}
    other = []
    for p in refs:
        words = set(terms(_paper_text(p)))
        hits = [w for w in theme_terms if w in words]
        if hits:
            themes[max(hits, key=lambda w: cnt[w])].append(p["ref_num"])
        else:
            other.append(p["ref_num"])
    metrics = {m: [p["ref_num"] for p in refs if re.search(rf"\b{m}\b", _paper_text(p))] for m in METRIC_WORDS}
    metrics = {m: r for m, r in metrics.items() if r}
    return {"n": len(refs), "years": (min(years), max(years)) if years else None, "venues": venues,
            "themes": {k: v for k, v in themes.items() if v}, "other": other, "metrics": metrics,
            "coverage": ctx.get("gap_analysis", {}).get("term_coverage", {})}


def roman(n: int) -> str:
    out = ""
    for v, r in ((10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")):
        while n >= v:
            out, n = out + r, n - v
    return out


def cite(nums) -> str:
    return ", ".join(f"[{n}]" for n in nums)


def writing_boxes(ctx: Dict[str, Any], kind: str, label: str) -> str:
    """Reserved (empty, clearly labelled) writing space the authors fill with their own method/results text.
    Added only when the evidence-derived text alone cannot reach the venue's minimum page count; never filler text."""
    inches = float((ctx.get("writing_space") or {}).get(kind, 0))
    boxes, n = [], 1
    while inches > 0.4:
        h = min(inches, 8.0)
        boxes.append(f"[[BOX: AUTHORS TO WRITE: {label} (reserved space, part {n}) | {h:.1f}]]")
        inches -= h
        n += 1
    return "\n\n".join(boxes)


def table(rows: List[List[Any]]) -> str:
    """Section-text table markup: lines starting with '|' (first row is the header)."""
    return "\n".join("| " + " | ".join(str(c).replace("|", "/") for c in r) for r in rows)


# ---------------------------------------------------------------------------------------------------------------------
class LiteratureDiscoveryAgent:
    """Agent 1: ranked reading list from scholarly sources (live APIs when available, else the local corpus)."""

    target_count = 6

    def step(self, ctx: Dict[str, Any], connector: ResearchDataConnector) -> Dict[str, Any]:
        topic = ctx.get("topic", "edge AI hardware porting frameworks")
        warnings: List[str] = []
        self.target_count = int(ctx.get("target_refs", 6))        # a 6-8 page paper needs a longer reading list

        print(f"    [LiteratureDiscoveryAgent] Querying scholarly sources for: '{topic}'")
        live = connector.search_online_papers(expand_query(topic), max_results=max(self.target_count, 10), agent_id="LiteratureDiscoveryAgent")
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
                "authors": ([str(x).strip() for x in (p.get("authors") if isinstance(p.get("authors"), list) else [p.get("authors")])
                             if x and str(x).strip()] or ["Unknown"]),
                "summary": (strip_cites(clean_text(p.get("abstract") or "")) if looks_english(clean_text(p.get("abstract") or ""))
                            else "No English abstract available.") or "No abstract available.",
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
        """Build ONE section (also used by the self-healer). `depth` (0-4) controls how much evidence-derived
        material is included; nothing is ever invented: results/methods stay as marked author placeholders."""
        topic = ctx.get("topic", "Research Topic")
        venue = ctx.get("venue", "IEEE Conference")
        refs = ctx.get("reading_list", [])
        gap = ctx.get("gap_analysis", {})
        d = int(ctx.get("depth", 1))
        pack = get_pack(ctx.get("domain") or detect_domain(topic))
        kind = self._kind(title)
        info = analyze_literature(ctx)
        usable = [p for p in refs if not p["summary"].startswith("No ")]
        cov = gap.get("term_coverage", {})
        thin = [w for w, c in cov.items() if c <= 1]
        well = [w for w, c in cov.items() if c >= max(3, len(refs) // 2)]
        main = topic

        if kind == "lit":
            if d == 0:
                lines = [AI_TAG, f"The retrieved literature on {topic} comprises {len(refs)} papers:"]
                for p in refs:
                    lines.append(
                        f"  - [{p['ref_num']}] {', '.join(p['authors'][:3])}{' et al.' if len(p['authors']) > 3 else ''} "
                        f"({p['year']}), \"{p['title']}\", {p['venue']}. DOI: {p['doi']} [Source: {p['source']}]\n"
                        f"    Summary: {first_sentence(p['summary'])}")
                return "\n".join(lines)
            yrs = f"between {info['years'][0]} and {info['years'][1]}" if info["years"] else "in recent years"
            out = [AI_TAG,
                   f"We reviewed {len(refs)} papers on {topic}, published {yrs}"
                   + (f" in venues including {', '.join(info['venues'])}" if info["venues"] else "")
                   + f". They were retrieved from {', '.join(sorted({p['source'] for p in refs}))} and ranked by topical relevance. "
                   f"{len(usable)} of them provide an abstract that is quoted below; claims are attributed to the paper that makes them."]
            sents = 2 if d >= 2 else 1
            for term, nums in info["themes"].items():
                out.append(f"### Work on {term}")
                for n in nums:
                    p = refs[n - 1]
                    if p["summary"].startswith("No "):
                        out.append(f"{p['authors'][0]}{' et al.' if len(p['authors']) > 1 else ''} [{n}] ({p['year']}) address this theme; no English abstract was available to summarise.")
                    else:
                        out.append(f"{p['authors'][0]}{' et al.' if len(p['authors']) > 1 else ''} [{n}] ({p['year']}): {sentences(p['summary'], sents)}")
            if info["other"]:
                out.append("### Other related work")
                for n in info["other"]:
                    p = refs[n - 1]
                    out.append(f"{p['authors'][0]}{' et al.' if len(p['authors']) > 1 else ''} [{n}] ({p['year']}): "
                               + (sentences(p['summary'], sents) if not p["summary"].startswith("No ") else "no English abstract available."))
            if d >= 2:
                out.append("### Comparison of Retrieved Studies")
                rows = [["Ref", "Year", "Venue", "Source", "Rel."]]
                for p in refs:
                    rows.append([f"[{p['ref_num']}]", p["year"], (p["venue"] or "n.p.")[:34], p["source"].split(" ")[0], p["relevance"]])
                out.append(table(rows))
            if d >= 3 and cov:
                out.append("### Coverage of the Topic Terms")
                out.append("Number of retrieved papers whose title, abstract or keywords contain each topic term:")
                out.append(table([["Term", "Papers"]] + [[w, c] for w, c in cov.items()]))
                out.append("### Evidence Summary")
                out.append(table([["Ref", "Supporting sentence from the cited paper"]] +
                                 [[f"[{p['ref_num']}]", sentences(p["evidence"]["supporting_sentence"] or p["summary"], 1)[:150] or "-"]
                                  for p in usable]))
            if d >= 4:
                out.append("### Relevance of Each Study to This Work")
                tset = set(terms(topic))
                for p in refs:
                    matched = sorted(tset & set(terms(_paper_text(p))))
                    out.append(f"[{p['ref_num']}] matches the topic terms {', '.join(matched) or 'none'} (relevance {p['relevance']}).")
            return "\n\n".join(out)

        if kind == "unique":
            base = (f"{AI_TAG}\nPRELIMINARY NOVELTY ASSESSMENT: {gap.get('novelty_flag', 'n/a')}\n"
                    f"Closest prior work: {'; '.join(gap.get('closest_prior_work', [])) or 'none'}\n"
                    f"Candidate angles:\n" + "\n".join(f"  - {a}" for a in gap.get("why_our_work_is_unique", []))
                    + f"\nUNCERTAINTY: {gap.get('uncertainty', '')}")
            if d >= 1 and cov:
                base += "\n\n" + table([["Topic term", "Papers covering it"]] + [[w, c] for w, c in cov.items()])
            if d >= 2:
                base += ("\n\nThe assessment is lexical: it counts how many retrieved papers contain each topic term. A term covered by at most one "
                         f"paper ({', '.join(thin) or 'none'}) marks a candidate angle; heavily covered terms ({', '.join(well) or 'none'}) "
                         "must not be claimed as novel. The authors must confirm every novelty claim against a full literature search.")
            return base

        if kind == "intro":
            out = [AI_TAG, f"This work addresses {topic}, targeting {venue}. "
                           f"Preliminary novelty assessment: {gap.get('novelty_flag', 'n/a')}. Contributions must be stated by the authors."]
            if d >= 1 and refs:
                yrs = f" published between {info['years'][0]} and {info['years'][1]}" if info["years"] else ""
                themes = ", ".join(info["themes"]) or "no dominant theme"
                out.append(f"### Background\nThe {len(refs)} papers retrieved for this study{yrs} recur on the themes of {themes} "
                           f"{cite(sum(info['themes'].values(), [])[:6])}. Section II reviews them in detail.")
                coverage = (f"the terms {', '.join(thin)} are covered by at most one retrieved paper" if thin
                            else "every topic term is covered by several retrieved papers, so novelty must come from the angle rather than the topic")
                coverage += (f", whereas {', '.join(well)} are covered by many" if thin and well else "")
                out.append(f"### Problem Statement\nWithin this literature, {coverage}. The authors should state precisely which "
                           f"open problem on {main} this work addresses and why existing studies "
                           f"{cite([int(x.split(']')[0][1:]) for x in gap.get('closest_prior_work', [])[:3]])} do not already solve it.")
            if d >= 2:
                rqs = thin[:3] or list(cov)[:2]
                out.append("### Research Questions\n" + "\n".join(
                    f"RQ{i}. [AUTHORS TO CONFIRM] How does {t} affect {main}?" for i, t in enumerate(rqs, 1)))
                out.append("### Contributions\n[AUTHORS TO STATE: list the contributions this work claims. The assistant does not assert contributions.]")
                titles = [t.split(". ", 1)[-1] for t in self.make_outline(ctx)]
                out.append("### Organization\nThe remainder of this paper is organized as follows. " + " ".join(
                    f"Section {roman(i)} covers {t.lower()}." for i, t in enumerate(titles[1:], 2)))
            return "\n\n".join(out)

        if kind == "method":
            out = [AI_TAG, f"[AUTHORS TO COMPLETE: describe the proposed method for {topic}. {pack.guidance_text()}. "
                           f"The assistant does not invent design details.]"]
            if d >= 1:
                out.append("### Problem Formulation\n[AUTHORS TO COMPLETE: define the inputs, outputs, constraints and objective of the problem, "
                           f"using the terminology of the related work {cite([p['ref_num'] for p in refs[:3]])}.]")
            if d >= 2 and info["themes"]:
                out.append("### Design Dimensions Suggested by the Literature")
                out.append(table([["Dimension", "Studies", "What the authors must specify"]] +
                                 [[t, cite(n[:4]), f"how the method handles {t}"] for t, n in info["themes"].items()]))
            wb = writing_boxes(ctx, "method", "methodology")
            if wb:
                out.append(wb)
            if d >= 3:
                out.append("### System Overview\n[[BOX: Figure 1 - AUTHORS TO INSERT: architecture / workflow diagram | 2.6]]")
            return "\n\n".join(out)

        if kind == "experiment":
            base_refs = cite([p["ref_num"] for p in refs[:4]])
            out = [AI_TAG, f"[AUTHORS TO COMPLETE: experimental setup, baselines drawn from {base_refs}, metrics and measured results. "
                           f"No results are claimed by the assistant.]"]
            if d >= 1:
                out.append("### Evaluation Protocol")
                out.append("Candidate baselines from the retrieved literature (the authors choose which to run):\n" +
                           "\n".join(f"- {p['title']} [{p['ref_num']}]" for p in refs[:6]))
                if info["metrics"]:
                    out.append("Metrics mentioned in the retrieved abstracts: " + "; ".join(
                        f"{m} {cite(r[:3])}" for m, r in list(info["metrics"].items())[:6]) + ".")
                out.append(pack.guidance_text() + ".")
            if d >= 2:
                cols = list(info["metrics"])[:3] or ["Metric 1", "Metric 2"]
                rows = [["Method"] + cols] + [[f"Baseline [{p['ref_num']}]"] + ["TBD"] * len(cols) for p in refs[:3]] + [["Proposed"] + ["TBD"] * len(cols)]
                out.append("### Results\nTABLE I (values to be measured and entered by the authors; the assistant reports no results):\n" + table(rows))
            wb = writing_boxes(ctx, "experiment", "experimental setup and results")
            if wb:
                out.append(wb)
            if d >= 4:
                abl = [["Variant"] + cols + ["Notes"]] + [[f"{v}"] + ["TBD"] * len(cols) + ["-"] for v in ("Full method", "Without component A", "Without component B")]
                out.append("TABLE II (ablation; values to be measured and entered by the authors):\n" + table(abl))
            if d >= 3:
                out.append("[[BOX: Figure 2 - AUTHORS TO INSERT: main result plot | 3.0]]")
                out.append("[[BOX: Figure 3 - AUTHORS TO INSERT: ablation or sensitivity plot | 3.0]]")
            return "\n\n".join(out)

        if kind == "domain":
            out = [AI_TAG, f"[AUTHORS TO COMPLETE: {title}. {pack.guidance_text()}.]"]
            if d >= 1:
                out.append(table([["Checklist item", "Status"]] + [[g, "authors to complete"] for g in pack.method_guidance]))
            return "\n\n".join(out)

        if kind == "conclusion":
            out = [AI_TAG, f"[AUTHORS TO COMPLETE: summarize validated findings and future work on {topic} once results exist.]"]
            if d >= 1:
                out.append("### Threats to Validity\n" + "\n".join([
                    f"- Literature coverage: conclusions rest on {len(refs)} retrieved papers; relevant work outside the searched sources may exist.",
                    "- Novelty estimate: the gap analysis is lexical and does not understand meaning; it must be verified manually.",
                    "- Abstract-level evidence: statements are attributed from abstracts, not full texts.",
                ] + (["- Data source: references come from the local MOCK corpus and must not be cited in a real submission."]
                     if all("mock" in p["source"] for p in refs) else [])))
            if d >= 2:
                out.append("### Future Work\n" + "\n".join(f"- Investigate {t} in the context of {main}." for t in (thin[:3] or list(cov)[:2])))
            return "\n\n".join(out)

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
