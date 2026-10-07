from datetime import datetime, timezone
from typing import Dict, List, Optional
from services.api.app.agents.research.research_models import EvidenceCategory, ResearchEvidence


class EvidenceCollector:
    """Collects, aggregates, and deduplicates verified observable evidence during research."""

    def __init__(self):
        self._evidence_list: List[ResearchEvidence] = []
        self._seen_signatures: set = set()

    def add_evidence(
        self,
        category: str,
        statement: str,
        source_url: str,
        source_type: str = "PAGE_OBSERVATION",
        confidence: float = 0.85,
    ) -> ResearchEvidence:
        """Adds a verified evidence entry if not a duplicate statement for the same URL."""
        statement_clean = statement.strip()
        signature = (category, statement_clean.lower(), source_url)

        if signature in self._seen_signatures:
            for ev in self._evidence_list:
                if (ev.category, ev.statement.lower(), ev.source_url) == signature:
                    return ev

        ev = ResearchEvidence(
            category=category,
            statement=statement_clean,
            source_url=source_url,
            source_type=source_type,
            observed_at=datetime.now(timezone.utc),
            confidence=max(0.0, min(1.0, confidence)),
        )
        self._evidence_list.append(ev)
        self._seen_signatures.add(signature)
        return ev

    def get_all(self) -> List[ResearchEvidence]:
        return list(self._evidence_list)

    def get_by_category(self, category: str) -> List[ResearchEvidence]:
        return [ev for ev in self._evidence_list if ev.category == category]

    def to_dict_list(self) -> List[Dict[str, any]]:
        return [ev.model_dump(mode="json") for ev in self._evidence_list]
