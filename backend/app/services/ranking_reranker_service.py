"""Bounded recent-signal reranker for ranking outputs."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional, Tuple

from app.services.web_enrichment_service import web_enrichment_service

logger = logging.getLogger(__name__)

MAX_ABS_ADJUSTMENT = 8.0
RECENT_WINDOW_DAYS = 45

POSITIVE_SIGNALS = {
    "capex": {
        "keywords": ["investment", "capex", "expand", "expansion", "new plant", "new line", "capacity increase"],
        "weight": 4.0,
        "label": "Recent capex or expansion signal",
    },
    "modernization": {
        "keywords": ["modernization", "upgrade", "revamp", "retrofit", "automation upgrade"],
        "weight": 3.0,
        "label": "Recent modernization signal",
    },
    "decarbonization": {
        "keywords": ["decarbonization", "green steel", "hydrogen", "co2", "electrification", "cbam"],
        "weight": 2.5,
        "label": "Recent decarbonization signal",
    },
}

NEGATIVE_SIGNALS = {
    "shutdown": {
        "keywords": ["shutdown", "closure", "closed", "halt production", "idle plant", "bankruptcy", "insolvency"],
        "weight": -5.0,
        "label": "Recent shutdown or distress signal",
    },
    "restructuring": {
        "keywords": ["restructuring", "layoff", "cost cutting", "reorganization", "divestment", "asset sale"],
        "weight": -3.0,
        "label": "Recent restructuring signal",
    },
}


def _parse_date(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


class RankingRerankerService:
    """Apply bounded score adjustments from recent high-confidence public signals."""

    def __init__(self) -> None:
        self._cache: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self._cache_ttl = timedelta(minutes=30)

    def clear_cache(self) -> None:
        self._cache.clear()

    def score_recent_signals(self, company_name: str, country: str | None = None) -> Dict[str, Any]:
        cache_key = (str(company_name or "").strip().lower(), str(country or "").strip().lower())
        now = datetime.now(timezone.utc)
        cached = self._cache.get(cache_key)
        if cached and now - cached.get("cached_at", now - self._cache_ttl - timedelta(seconds=1)) < self._cache_ttl:
            return cached["payload"]

        try:
            news_items = web_enrichment_service.get_recent_news(company_name, limit=10) or []
        except Exception as exc:
            logger.warning("Recent rerank news fetch failed for %s: %s", company_name, exc)
            news_items = []

        recent_items: List[Dict[str, Any]] = []
        cutoff = now - timedelta(days=RECENT_WINDOW_DAYS)
        for item in news_items:
            published_at = _parse_date(str(item.get("published_date", "") or ""))
            if published_at is not None and published_at < cutoff:
                continue
            recent_items.append(item)

        signal_hits: List[Tuple[str, float]] = []
        unique_sources = set()
        for item in recent_items:
            text = " ".join([
                str(item.get("title", "") or ""),
                str(item.get("description", "") or ""),
            ]).lower()
            source = str(item.get("source", "") or "").strip().lower()
            if source:
                unique_sources.add(source)

            for spec in POSITIVE_SIGNALS.values():
                if any(keyword in text for keyword in spec["keywords"]):
                    signal_hits.append((spec["label"], float(spec["weight"])))
            for spec in NEGATIVE_SIGNALS.values():
                if any(keyword in text for keyword in spec["keywords"]):
                    signal_hits.append((spec["label"], float(spec["weight"])))

        source_multiplier = 1.0
        if len(unique_sources) >= 3:
            source_multiplier = 1.15
        elif len(unique_sources) >= 2:
            source_multiplier = 1.08

        raw_adjustment = sum(weight for _, weight in signal_hits) * source_multiplier
        adjustment = max(-MAX_ABS_ADJUSTMENT, min(MAX_ABS_ADJUSTMENT, raw_adjustment))

        reasons: List[str] = []
        seen = set()
        for label, weight in sorted(signal_hits, key=lambda item: abs(item[1]), reverse=True):
            if label in seen:
                continue
            seen.add(label)
            reasons.append(label)
            if len(reasons) >= 3:
                break

        payload = {
            "rerank_adjustment": float(round(adjustment, 2)),
            "rerank_recent_mentions": int(len(recent_items)),
            "rerank_recent_sources": int(len(unique_sources)),
            "rerank_reasons": reasons,
        }
        self._cache[cache_key] = {"cached_at": now, "payload": payload}
        return payload


ranking_reranker_service = RankingRerankerService()