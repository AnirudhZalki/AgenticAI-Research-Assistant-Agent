"""
Lab 9: Deep Research Agent - iterative retrieval, evidence table, cited synthesis

Loop (plan -> search -> read -> expand -> stop when saturated):
  round 1 : search the topic
  round k : expand the query with the most frequent keywords of what was just found; stop when a round
            adds no new papers (saturation) or max_rounds is reached
Every claim in the briefing comes from an extractive evidence row (sentence copied from the paper's own abstract)
so each statement is traceable to [n]; nothing is generated that the sources do not say.
"""

import re
from collections import Counter
from typing import Any, Dict, List

from specialist_agents import ABBREV, expand_query, relevance, terms


def _sentences(text: str) -> List[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text or "") if len(s.strip()) > 25]


class DeepResearchAgent:
    def __init__(self, connector, max_rounds: int = 3, per_query: int = 6):
        self.connector = connector
        self.max_rounds = max_rounds
        self.per_query = per_query

    def _search(self, query: str, use_online: bool) -> List[Dict[str, Any]]:
        found: List[Dict[str, Any]] = []
        if use_online:
            found += self.connector.search_online_papers(expand_query(query), max_results=self.per_query,
                                                         agent_id="DeepResearchAgent")
        for w in terms(expand_query(query)):        # corpus matching is substring-per-keyword, so query per term
            found += self.connector.read_paper_corpus(w, agent_id="DeepResearchAgent")
        return [p for p in found if relevance(query, p) > 0]   # drop papers sharing no topic term

    def run(self, topic: str, use_online: bool = True) -> Dict[str, Any]:
        papers: Dict[str, Dict[str, Any]] = {}
        trace, query = [], topic
        used_queries = set()
        for rnd in range(1, self.max_rounds + 1):
            used_queries.add(query.lower())
            new = 0
            for p in self._search(query, use_online):
                key = re.sub(r"\W+", " ", p.get("title", "").lower()).strip()
                if key and key not in papers:
                    papers[key] = dict(p)
                    papers[key].setdefault("source", "LocalCorpus (mock dataset)")
                    new += 1
            trace.append({"round": rnd, "query": query, "new_papers": new, "total": len(papers)})
            if rnd > 1 and new == 0:
                trace[-1]["stop_reason"] = "saturation: no new papers"
                break
            # expand with the most frequent keywords not already in the topic
            kw = Counter(k.lower() for p in papers.values() for k in p.get("keywords", [])
                         if k.lower() not in topic.lower())
            expansion = [k for k, _ in kw.most_common(2)]
            if not expansion:
                trace[-1]["stop_reason"] = "no expansion terms available"
                break
            query = f"{topic} {' '.join(expansion)}"
            if query.lower() in used_queries:
                trace[-1]["stop_reason"] = "query repeated"
                break
        else:
            trace[-1]["stop_reason"] = "max rounds reached"

        ranked = sorted(papers.values(), key=lambda p: (relevance(topic, p), p.get("year", 0)), reverse=True)
        refs = []
        for i, p in enumerate(ranked[:10], 1):
            refs.append({**p, "ref_num": i, "relevance": relevance(topic, p)})

        tset = set(terms(topic))
        evidence = []
        for p in refs:
            sents = _sentences(p.get("abstract", ""))
            scored = sorted(sents, key=lambda s: len(tset & set(terms(s))), reverse=True)
            if not scored:
                evidence.append({"ref": p["ref_num"], "claim": "(no abstract available - cannot extract evidence)",
                                 "paper": p["title"], "year": p.get("year"), "doi": p.get("doi", "N/A"),
                                 "source": p["source"], "confidence": "LOW"})
                continue
            conf = "HIGH" if p["relevance"] >= 0.6 and p.get("doi", "N/A") != "N/A" else \
                   "MEDIUM" if p["relevance"] >= 0.3 else "LOW"
            evidence.append({"ref": p["ref_num"], "claim": scored[0], "paper": p["title"], "year": p.get("year"),
                             "doi": p.get("doi", "N/A"), "source": p["source"], "confidence": conf})

        themes: Dict[str, List[int]] = {}
        for p in refs:
            for k in p.get("keywords", []):
                themes.setdefault(k.lower(), []).append(p["ref_num"])
        top_themes = sorted(((k, v) for k, v in themes.items() if len(v) >= 2), key=lambda kv: -len(kv[1]))[:5]

        lines = [f"# Evidence briefing: {topic}", ""]
        if not refs:
            lines.append("No sources were retrieved; no claims can be made.")
        for k, v in top_themes:
            cites = ", ".join(f"[{n}]" for n in v)
            lines.append(f"- **{k}** is a recurring theme across {len(v)} papers {cites}.")
        for e in evidence[:6]:
            if e["confidence"] != "LOW":
                lines.append(f"- {e['claim']} [{e['ref']}]")
        low = [e for e in evidence if e["confidence"] == "LOW"]
        limits = [f"{len(refs)} papers from {', '.join(sorted({p['source'] for p in refs})) or 'no source'}; "
                  f"lexical relevance only.",
                  f"{len(low)} evidence row(s) are LOW confidence (weak topical match or no abstract)."]
        if any("mock" in p["source"] for p in refs):
            limits.append("Includes MOCK-corpus entries: do not cite them in a real submission.")
        gaps = [w for w in terms(topic) if sum(1 for p in refs if w in (p.get("title", "") + p.get("abstract", "")).lower()) <= 1]
        return {"topic": topic, "trace": trace, "references": refs, "evidence_table": evidence,
                "themes": top_themes, "briefing_markdown": "\n".join(lines),
                "limitations": limits, "evidence_gaps": gaps,
                "stopped_because": trace[-1].get("stop_reason", "")}
