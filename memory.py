"""
Lab 4: Memory & Retrieval Store (Phase A - Foundations)
Separates short-term session run-state from long-term stored reference knowledge.
Supports tag-based filtering and keyword similarity retrieval over scholarly papers and past tasks.
"""

from typing import List, Dict, Any, Optional

class MemoryStore:
    def __init__(self, corpus: List[Dict[str, Any]] = None, library: List[Dict[str, Any]] = None):
        # Short-term session state (current working draft, active plan)
        self.session_state = {
            "active_plan": None,
            "current_draft": None,
            "working_notes": []
        }
        
        # Long-term stored knowledge
        self.paper_corpus = corpus if corpus is not None else []
        self.personal_library = library if library is not None else []
        self.prior_task_history = []  # Log of previously executed research tasks

    def update_session(self, key: str, value: Any):
        """Updates short-term run state."""
        self.session_state[key] = value

    def get_session(self, key: str, default: Any = None) -> Any:
        """Retrieves short-term run state."""
        return self.session_state.get(key, default)

    def archive_task(self, task_summary: Dict[str, Any]):
        """Archives a completed research task to long-term memory."""
        self.prior_task_history.append(task_summary)

    def retrieve_by_tags(self, tags: List[str]) -> List[Dict[str, Any]]:
        """Retrieves papers from corpus matching any of the specified tags/keywords."""
        matched = []
        tags_lower = [t.lower() for t in tags]
        for paper in self.paper_corpus:
            paper_kws = [k.lower() for k in paper.get("keywords", [])]
            if any(t in paper_kws for t in tags_lower):
                matched.append(paper)
        return matched

    def retrieve_by_similarity(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Retrieves top_k papers from corpus matching query via keyword overlap similarity score.
        (Serves as the foundation for vector search / embedding retrieval).
        """
        query_words = set(query.lower().split())
        scored = []
        
        for paper in self.paper_corpus:
            text = f"{paper.get('title', '')} {paper.get('abstract', '')} {' '.join(paper.get('keywords', []))}".lower()
            text_words = set(text.split())
            overlap = len(query_words.intersection(text_words))
            if overlap > 0:
                scored.append((overlap, paper))

        # Sort descending by score
        scored.sort(key=lambda x: x[0], reverse=True)
        return [paper for score, paper in scored[:top_k]]

    def retrieve_prior_tasks(self, query: str) -> List[Dict[str, Any]]:
        """Retrieves similar past research tasks from history to prevent duplicate research."""
        q = query.lower()
        return [t for t in self.prior_task_history if q in t.get("topic", "").lower()]

if __name__ == "__main__":
    sample_corpus = [
        {"id": "P1", "title": "Edge AI Microcontroller Porting", "keywords": ["edge ai", "embedded"]},
        {"id": "P2", "title": "Medical Diagnostic Neural Nets", "keywords": ["healthcare", "diagnostics"]}
    ]
    mem = MemoryStore(corpus=sample_corpus)
    mem.update_session("current_draft", "Draft v1")
    
    tag_results = mem.retrieve_by_tags(["embedded"])
    print(f"Tag retrieval returned {len(tag_results)} items.")
    
    sim_results = mem.retrieve_by_similarity("edge AI porting")
    print(f"Similarity retrieval returned {len(sim_results)} items.")
