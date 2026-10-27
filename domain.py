"""
Lab 13: Discipline-Specific Agent (CSE / AI scholarly publishing)

Domain knowledge the generic agents do not have:
  * VenueSpec        - parses a free-text venue ("IEEE conference, IMRAD, 6-page limit") into
                       citation style, section structure and word/page limits
  * CitationFormatter- IEEE / ACM / APA reference strings and BibTeX export
  * OriginalityChecker- n-gram overlap of a draft against the known corpus + the researcher's library
                       (flags text that is too close to existing work; never claims "no plagiarism")
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List

WORDS_PER_PAGE = {"IEEE": 750, "ACM": 800, "SPRINGER": 450, "ELSEVIER": 600, "GRANT": 500}

IMRAD = ["Abstract & Introduction", "Related Work", "Methodology",
         "Experimental Setup & Results", "Discussion", "Conclusion & Future Work"]
SURVEY = ["Abstract & Introduction", "Background", "Taxonomy of Existing Work",
          "Comparative Analysis", "Open Challenges", "Conclusion"]
GRANT = ["Project Summary", "Background & Motivation", "Objectives", "Work Plan & Milestones",
         "Expected Outcomes", "Budget Justification"]


@dataclass
class VenueSpec:
    raw: str
    kind: str = "conference"          # conference | journal | grant
    citation_style: str = "IEEE"
    structure: str = "IMRAD"
    page_limit: int = 6
    word_limit: int = 4500
    sections: List[str] = field(default_factory=lambda: list(IMRAD))


def parse_venue(venue: str) -> VenueSpec:
    """Interpret a free-text venue description."""
    v = (venue or "").lower()
    style = ("ACM" if "acm" in v else "SPRINGER" if ("springer" in v or "lncs" in v)
             else "ELSEVIER" if "elsevier" in v else "APA" if "apa" in v else "IEEE")
    kind = "grant" if any(k in v for k in ("grant", "funding", "proposal", "nsf", "dst")) else \
           "journal" if "journal" in v or "transactions" in v else "conference"
    m = re.search(r"(\d+)\s*-?\s*page", v)
    pages = int(m.group(1)) if m else (12 if kind == "journal" else 6)
    words = pages * WORDS_PER_PAGE.get(style, 650)
    if kind == "grant":
        structure, sections, style = "GRANT", list(GRANT), ("IEEE" if style == "APA" else style)
    elif "survey" in v or "review" in v:
        structure, sections = "SURVEY", list(SURVEY)
    else:
        structure, sections = "IMRAD", list(IMRAD)
    return VenueSpec(venue, kind, style, structure, pages, words, sections)


class CitationFormatter:
    """Formats one reference dict in the target style. Never invents missing fields: gaps are shown as [missing X]."""

    @staticmethod
    def _authors(p: Dict[str, Any]) -> List[str]:
        a = p.get("authors") or []
        return a if isinstance(a, list) else [str(a)]

    @staticmethod
    def _initials(name: str) -> str:
        parts = name.replace(".", ". ").split()
        return " ".join(parts) if len(parts) < 2 else f"{' '.join(x[0] + '.' for x in parts[:-1])} {parts[-1]}"

    def format(self, p: Dict[str, Any], style: str = "IEEE", n: int = 1) -> str:
        authors = self._authors(p) or ["[missing authors]"]
        title = p.get("title") or "[missing title]"
        venue = p.get("venue") or "[missing venue]"
        year = p.get("year") or "[missing year]"
        doi = p.get("doi")
        doi_s = f" doi: {doi}" if doi and doi != "N/A" else ""
        if style == "ACM":
            names = ", ".join(authors[:3]) + (", et al." if len(authors) > 3 else "")
            return f"[{n}] {names}. {year}. {title}. {venue}.{doi_s.replace('doi: ', ' https://doi.org/')}"
        if style == "APA":
            names = ", ".join(authors[:6])
            return f"{names} ({year}). {title}. {venue}.{doi_s.replace('doi: ', ' https://doi.org/')}"
        names = ", ".join(self._initials(a) for a in authors[:3]) + (" et al." if len(authors) > 3 else "")
        return f"[{n}] {names}, \"{title},\" {venue}, {year}.{doi_s}"

    def format_all(self, refs: List[Dict[str, Any]], style: str = "IEEE") -> List[str]:
        return [self.format(r, style, i) for i, r in enumerate(refs, 1)]

    def to_bibtex(self, refs: List[Dict[str, Any]]) -> str:
        out = []
        for i, p in enumerate(refs, 1):
            key = re.sub(r"\W", "", (self._authors(p) or ["ref"])[0].split()[-1]) + str(p.get("year", "")) + f"_{i}"
            out.append(
                f"@inproceedings{{{key},\n  author = {{{' and '.join(self._authors(p))}}},\n"
                f"  title = {{{p.get('title', '')}}},\n  booktitle = {{{p.get('venue', '')}}},\n"
                f"  year = {{{p.get('year', '')}}},\n  doi = {{{p.get('doi', 'N/A')}}}\n}}")
        return "\n\n".join(out)


class OriginalityChecker:
    """Word 5-gram overlap between draft text and known sources. A screening aid, not proof of originality."""

    def __init__(self, n: int = 5):
        self.n = n

    def _grams(self, text: str) -> set:
        w = re.findall(r"[a-z0-9]+", text.lower())
        return {" ".join(w[i:i + self.n]) for i in range(max(len(w) - self.n + 1, 0))}

    def check(self, draft_sections: Dict[str, str], sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Scores each section against source abstracts/titles; high overlap => rewrite or quote+cite."""
        results, flagged = [], []
        src_grams = {s.get("id", s.get("title", "?")): self._grams(f"{s.get('title', '')}. {s.get('abstract') or s.get('summary', '')}")
                     for s in sources}
        for name, text in draft_sections.items():
            # Cited/quoted lines are attributed on purpose; score only the prose we wrote
            body = "\n".join(l for l in text.splitlines()
                             if "Summary:" not in l and "DOI:" not in l and not re.search(r"\[\d+\]", l))
            g = self._grams(body)
            best_id, best = None, 0.0
            for sid, sg in src_grams.items():
                if g and sg:
                    ov = len(g & sg) / len(g)
                    if ov > best:
                        best_id, best = sid, ov
            row = {"section": name, "max_overlap": round(best, 3), "closest_source": best_id,
                   "flag": best >= 0.25}
            results.append(row)
            if row["flag"]:
                flagged.append(name)
        return {"sections": results, "flagged_sections": flagged,
                "passed": not flagged,
                "disclaimer": "Screens against the loaded corpus/library only; not a substitute for a full "
                              "plagiarism service (e.g., iThenticate/Turnitin)."}


# =====================================================================================================================
# Lab 13: pluggable domain packs (registry) - each pack carries a CHECKABLE scheme, not just prose
# =====================================================================================================================
@dataclass
class DomainPack:
    key: str
    name: str
    detect_terms: List[str]
    extra_sections: List[str]                    # inserted into the outline when missing
    method_guidance: List[str]                   # what the authors must state in methods/experiments
    abbreviations: Dict[str, List[str]]          # acronym -> expansions used for search + relevance
    required_checks: List[Dict[str, Any]]        # {"name", "section_keywords", "must_contain": [terms]}

    def checks(self, sections: Dict[str, str]) -> List[Dict[str, Any]]:
        """Checkable scheme: each rule needs a matching section containing at least one required term (or an
        explicit AUTHORS TO COMPLETE placeholder naming it, which is reported as 'pending authors')."""
        out = []
        for rule in self.required_checks:
            keys = rule["section_keywords"]
            raw = " ".join(t for s, t in sections.items() if any(k in s.lower() for k in keys)).lower()
            body = re.sub(r"\[authors to complete[^\]]*\]", " ", raw)       # a placeholder is not compliance
            present = bool(raw)
            hit = present and any(w in body for w in rule["must_contain"])
            out.append({"pack": self.key, "check": rule["name"],
                        "status": "PASS" if hit else ("PENDING_AUTHORS" if present else "MISSING_SECTION"),
                        "needs": ", ".join(rule["must_contain"][:3])})
        return out

    def guidance_text(self) -> str:
        return "Domain checklist (" + self.name + "): " + "; ".join(self.method_guidance)


PACKS: Dict[str, DomainPack] = {
    "cs": DomainPack(
        "cs", "Computer Science / AI",
        ["neural", "learning", "network", "ai", "algorithm", "software", "edge", "embedded", "transformer", "gru", "lstm",
         "language", "vision", "data", "model", "compiler", "iot", "security", "federated"],
        ["Reproducibility & Artifact Availability"],
        ["datasets and train/validation/test splits", "baselines and hyper-parameters", "hardware and software versions",
         "random seeds and number of runs", "metrics with confidence intervals", "code/data availability"],
        {"gru": ["gated recurrent unit"], "lstm": ["long short-term memory"], "cnn": ["convolutional neural network"],
         "mcu": ["microcontroller"], "npu": ["neural processing unit"]},
        [{"name": "Reproducibility statement present", "section_keywords": ["reproducib", "artifact", "experiment"],
          "must_contain": ["seed", "dataset", "code availability", "repository", "split"]}]),
    "biosciences": DomainPack(
        "biosciences", "Biosciences",
        ["gene", "protein", "cell", "clinical", "patient", "dna", "rna", "genom", "crispr", "pcr", "biolog", "disease",
         "drug", "therap", "enzyme", "cancer", "bacteri", "virus"],
        ["Ethics, Consent & Data Availability"],
        ["sample size and power calculation", "inclusion/exclusion criteria", "statistical tests and p-value correction",
         "ethics approval / consent statement", "reagent, strain and instrument identifiers", "data deposition (e.g., GEO)"],
        {"pcr": ["polymerase chain reaction"], "crispr": ["clustered regularly interspaced short palindromic repeats"],
         "dna": ["deoxyribonucleic acid"], "rna": ["ribonucleic acid"], "ngs": ["next-generation sequencing"]},
        [{"name": "Ethics / consent statement present", "section_keywords": ["ethic", "consent"],
          "must_contain": ["ethics", "consent", "irb", "approval"]},
         {"name": "Statistical methods stated", "section_keywords": ["method", "result"],
          "must_contain": ["p-value", "statistic", "confidence", "sample size"]}]),
    "materials": DomainPack(
        "materials", "Materials Science",
        ["alloy", "polymer", "ceramic", "nanomaterial", "composite", "crystal", "semiconductor", "perovskite", "graphene",
         "corrosion", "fatigue", "steel", "thin film", "coating", "xrd", "sem"],
        ["Synthesis & Characterization"],
        ["synthesis route, precursors and conditions (temperature, time, atmosphere)",
         "characterization techniques (XRD, SEM, TEM, XPS) with instrument settings",
         "SI units and measurement uncertainty", "sample preparation and number of specimens",
         "property measurements with standards (e.g., ASTM/ISO)"],
        {"xrd": ["x-ray diffraction"], "sem": ["scanning electron microscopy"], "tem": ["transmission electron microscopy"],
         "xps": ["x-ray photoelectron spectroscopy"], "dsc": ["differential scanning calorimetry"]},
        [{"name": "Characterization methods stated", "section_keywords": ["characteriz", "method"],
          "must_contain": ["xrd", "sem", "tem", "xps", "spectroscop", "diffraction"]},
         {"name": "Units / standards stated", "section_keywords": ["method", "experiment", "characteriz"],
          "must_contain": [" mpa", " gpa", " k ", "°c", "astm", "iso ", "si unit"]}]),
}


def detect_domain(topic: str) -> str:
    """Pick the pack whose vocabulary best matches the topic (defaults to CS)."""
    t = (topic or "").lower()
    scores = {k: sum(1 for w in p.detect_terms if w in t) for k, p in PACKS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "cs"


def get_pack(key: str = "") -> DomainPack:
    return PACKS.get(key or "cs", PACKS["cs"])


def all_pack_abbreviations() -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for p in PACKS.values():
        out.update(p.abbreviations)
    return out


def smart_title(topic: str) -> str:
    """Title-case a topic but keep acronyms (AI, GRU, IoT) as typed."""
    return " ".join(w if (w.isupper() or any(c.isupper() for c in w[1:])) else w[:1].upper() + w[1:] for w in (topic or "").split())
