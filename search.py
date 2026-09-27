"""
Lab 2: Search Tools (Phase A - Foundations)
Replaces LLM memory hallucinations with typed tools that read from mock scholarly data stores.
"""

import json
import os

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

if __name__ == "__main__":
    tools = SearchTools()
    res = tools.read_corpus("edge AI")
    print(f"Search tool test returned {len(res)} papers for 'edge AI'")