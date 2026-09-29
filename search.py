"""
Lab 2: Search Tools (Phase A - Foundations)
Replaces LLM memory hallucinations with typed tools that read from mock scholarly data stores.
Also provides live online search via Semantic Scholar API (with CrossRef fallback).
"""

import json
import os
import urllib.request
import urllib.parse
import urllib.error

# Semantic Scholar public API — no key required for basic use
_S2_API = "https://api.semanticscholar.org/graph/v1/paper/search"
_S2_FIELDS = "title,authors,year,venue,abstract,externalIds"

# CrossRef fallback API — no key required
_CROSSREF_API = "https://api.crossref.org/works"

# OpenAlex fallback API — no key required
_OPENALEX_API = "https://api.openalex.org/works"

_HTTP_TIMEOUT = 10  # seconds


class SearchTools:
    def __init__(self, data_dir=None):
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(__file__), 'data')
        self.data_dir = data_dir
        self.corpus = self._load_json('corpus.json', [])
        self.library = self._load_json('library.json', [])
        self.deadlines = self._load_json('deadlines.json', [])
        self.notes = self._load_json('notes_drafts.json', {})

    def _load_json(self, filename, fallback):
        filepath = os.path.join(self.data_dir, filename)
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        return fallback

    def read_corpus(self, keyword: str = "") -> list:
        """Searches mock scholarly database for papers matching keyword in title, abstract, or keywords."""
        if not keyword:
            return self.corpus
        kw = keyword.lower()
        results = []
        for p in self.corpus:
            title_match = kw in p.get('title', '').lower()
            abstract_match = kw in p.get('abstract', '').lower()
            kw_match = any(kw in k.lower() for k in p.get('keywords', []))
            if title_match or abstract_match or kw_match:
                results.append(p)
        return results

    def read_library(self) -> list:
        """Returns the researcher's personal prior papers library."""
        return self.library

    def read_deadlines(self, topic_keyword: str = "") -> list:
        """Returns upcoming journal calls for papers and funding deadlines."""
        if not topic_keyword:
            return self.deadlines
        kw = topic_keyword.lower()
        return [d for d in self.deadlines if any(kw in t.lower() for t in d.get('topics', []))]

    def read_notes(self) -> dict:
        """Returns collaborator section ownership and notes."""
        return self.notes

    # ------------------------------------------------------------------
    # LIVE ONLINE SEARCH — Semantic Scholar → CrossRef → OpenAlex chain
    # ------------------------------------------------------------------

    def search_online(self, query: str, max_results: int = 6) -> list:
        """
        Fetches real scholarly papers from live academic APIs.
        Priority: Semantic Scholar → CrossRef → OpenAlex → local corpus fallback.
        Returns a list of normalised paper dicts (same schema as corpus.json).
        """
        papers = self._search_semantic_scholar(query, max_results)
        if papers:
            print(f"    [SearchTools:Online] Semantic Scholar returned {len(papers)} papers.")
            return papers

        papers = self._search_crossref(query, max_results)
        if papers:
            print(f"    [SearchTools:Online] CrossRef returned {len(papers)} papers.")
            return papers

        papers = self._search_openalex(query, max_results)
        if papers:
            print(f"    [SearchTools:Online] OpenAlex returned {len(papers)} papers.")
            return papers

        print("    [SearchTools:Online] All live APIs failed — falling back to local corpus.")
        return self.read_corpus(query)

    # --- Semantic Scholar ---

    def _search_semantic_scholar(self, query: str, max_results: int) -> list:
        try:
            params = urllib.parse.urlencode({
                "query": query,
                "fields": _S2_FIELDS,
                "limit": max_results
            })
            url = f"{_S2_API}?{params}"
            req = urllib.request.Request(url, headers={"User-Agent": "ResearchAssistantAgent/1.0"})
            with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            raw_papers = data.get("data", [])
            return [self._normalise_s2(p) for p in raw_papers if p.get("title")]
        except Exception as e:
            print(f"    [SearchTools:SemanticScholar] Error: {e}")
            return []

    def _normalise_s2(self, p: dict) -> dict:
        authors = [a.get("name", "Unknown") for a in p.get("authors", [])]
        doi = (p.get("externalIds") or {}).get("DOI", "N/A")
        paper_id = p.get("paperId", "S2_UNKNOWN")
        return {
            "id": f"S2_{paper_id[:8].upper()}",
            "title": p.get("title", "Untitled"),
            "authors": authors if authors else ["Unknown"],
            "year": p.get("year") or 2024,
            "venue": p.get("venue") or "Unknown Venue",
            "abstract": p.get("abstract") or "No abstract available.",
            "keywords": [],
            "doi": doi,
            "source": "SemanticScholar"
        }

    # --- CrossRef ---

    def _search_crossref(self, query: str, max_results: int) -> list:
        try:
            params = urllib.parse.urlencode({
                "query": query,
                "rows": max_results,
                "select": "title,author,published,container-title,abstract,DOI"
            })
            url = f"{_CROSSREF_API}?{params}"
            req = urllib.request.Request(url, headers={"User-Agent": "ResearchAssistantAgent/1.0"})
            with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            items = data.get("message", {}).get("items", [])
            return [self._normalise_crossref(it) for it in items if it.get("title")]
        except Exception as e:
            print(f"    [SearchTools:CrossRef] Error: {e}")
            return []

    def _normalise_crossref(self, it: dict) -> dict:
        title = it["title"][0] if it.get("title") else "Untitled"
        authors = [
            f"{a.get('given', '')} {a.get('family', '')}".strip()
            for a in it.get("author", [])
        ]
        pub_parts = it.get("published", {}).get("date-parts", [[2024]])
        year = pub_parts[0][0] if pub_parts and pub_parts[0] else 2024
        venue = it.get("container-title", ["Unknown Venue"])
        venue = venue[0] if venue else "Unknown Venue"
        abstract = it.get("abstract", "No abstract available.")
        doi = it.get("DOI", "N/A")
        return {
            "id": f"CR_{doi.replace('/', '_')[:12].upper()}",
            "title": title,
            "authors": authors if authors else ["Unknown"],
            "year": year,
            "venue": venue,
            "abstract": abstract,
            "keywords": [],
            "doi": doi,
            "source": "CrossRef"
        }

    # --- OpenAlex ---

    def _search_openalex(self, query: str, max_results: int) -> list:
        try:
            params = urllib.parse.urlencode({
                "search": query,
                "per-page": max_results,
                "select": "id,title,authorships,publication_year,primary_location,abstract_inverted_index,doi"
            })
            url = f"{_OPENALEX_API}?{params}"
            req = urllib.request.Request(url, headers={"User-Agent": "ResearchAssistantAgent/1.0"})
            with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            results = data.get("results", [])
            return [self._normalise_openalex(r) for r in results if r.get("title")]
        except Exception as e:
            print(f"    [SearchTools:OpenAlex] Error: {e}")
            return []

    def _normalise_openalex(self, r: dict) -> dict:
        authors = [
            auth.get("author", {}).get("display_name", "Unknown")
            for auth in r.get("authorships", [])
        ]
        venue_obj = (r.get("primary_location") or {}).get("source") or {}
        venue = venue_obj.get("display_name", "Unknown Venue")
        doi = r.get("doi", "N/A") or "N/A"
        # Reconstruct abstract from inverted index
        abstract = self._reconstruct_abstract(r.get("abstract_inverted_index"))
        oa_id = r.get("id", "OA_UNKNOWN").replace("https://openalex.org/", "")
        return {
            "id": f"OA_{oa_id[:8].upper()}",
            "title": r.get("title", "Untitled"),
            "authors": authors if authors else ["Unknown"],
            "year": r.get("publication_year") or 2024,
            "venue": venue,
            "abstract": abstract,
            "keywords": [],
            "doi": doi,
            "source": "OpenAlex"
        }

    def _reconstruct_abstract(self, inverted_index: dict) -> str:
        """Reconstruct abstract text from OpenAlex inverted index format."""
        if not inverted_index:
            return "No abstract available."
        try:
            word_positions = []
            for word, positions in inverted_index.items():
                for pos in positions:
                    word_positions.append((pos, word))
            word_positions.sort()
            return " ".join(w for _, w in word_positions)
        except Exception:
            return "No abstract available."


if __name__ == "__main__":
    tools = SearchTools()
    # Test local
    res = tools.read_corpus("edge AI")
    print(f"[Local] Search returned {len(res)} papers for 'edge AI'")
    # Test online
    print("\n[Online] Testing Semantic Scholar for 'federated learning healthcare'...")
    online_res = tools.search_online("federated learning healthcare", max_results=3)
    for p in online_res:
        print(f"  - [{p.get('source','local')}] {p['title']} ({p['year']}) — {p['venue']}")