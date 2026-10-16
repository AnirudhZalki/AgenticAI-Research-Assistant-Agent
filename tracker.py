"""
Research tracker / repository (Export & Repository Agent storage, Lab 12 rollback support)

Keeps version history for every draft with source links, status (DRAFT / APPROVED / ROLLED_BACK) and a
content hash. Optionally persisted to a JSON file so the history survives restarts.
"""

import hashlib
import json
import os
import time
from typing import Any, Dict, List, Optional


class ResearchTracker:
    def __init__(self, path: Optional[str] = None):
        self.path = path
        self.versions: List[Dict[str, Any]] = []
        if path and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.versions = json.load(f)
            except (OSError, ValueError):
                self.versions = []

    def _save(self):
        if self.path:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.versions, f, indent=2)

    def log_version(self, topic: str, venue: str, text: str, references: List[Dict[str, Any]],
                    status: str = "DRAFT", approved_by: str = "", note: str = "") -> Dict[str, Any]:
        major = sum(1 for v in self.versions if v["status"] == "APPROVED")
        minor = sum(1 for v in self.versions if v["topic"] == topic)
        label = f"v{major + (1 if status == 'APPROVED' else 0)}.{minor}" + ("-approved" if status == "APPROVED" else "-draft")
        entry = {
            "version": label,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "topic": topic, "venue": venue, "status": status,
            "approved_by": approved_by, "note": note,
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "source_links": [self._link(r) for r in references],
            "text": text,
        }
        self.versions.append(entry)
        self._save()
        return entry

    @staticmethod
    def _link(ref: Dict[str, Any]) -> str:
        doi = ref.get("doi")
        return f"https://doi.org/{doi}" if doi and doi != "N/A" else f"(no DOI) {ref.get('title', '')}"

    def history(self, topic: str = "") -> List[Dict[str, Any]]:
        return [{k: v for k, v in e.items() if k != "text"} for e in self.versions
                if not topic or e["topic"] == topic]

    def get(self, version: str) -> Optional[Dict[str, Any]]:
        return next((v for v in self.versions if v["version"] == version), None)

    def rollback(self, version: str, reason: str = "") -> Optional[Dict[str, Any]]:
        """Restore an earlier version as a new entry (history is append-only, nothing is deleted)."""
        old = self.get(version)
        if not old:
            return None
        entry = self.log_version(old["topic"], old["venue"], old["text"], [],
                                 status="DRAFT", note=f"ROLLBACK to {version}. {reason}".strip())
        entry["source_links"] = list(old["source_links"])
        self._save()
        return entry
