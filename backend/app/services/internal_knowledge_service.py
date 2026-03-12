"""
Local internal knowledge ingestion for exported SharePoint documents.

Drop exported intranet files into backend/data/internal_knowledge and this service
will extract relevant snippets for customer profile generation.
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

import pandas as pd
from bs4 import BeautifulSoup
from docx import Document

from app.core.config import settings

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".txt", ".md", ".html", ".htm", ".json", ".csv", ".docx", ".pdf", ".xlsx", ".xls"}
TOPIC_KEYWORDS: Dict[str, Sequence[str]] = {
    "service": ("service", "spare", "repair", "maintenance", "field service", "workshop", "shutdown"),
    "inspection": ("inspection", "acceptance", "acceptence", "audit", "checklist", "quality gate", "finding"),
    "modernization": ("revamp", "upgrade", "modernization", "replacement", "retrofit", "rebuild"),
    "digital": ("digital", "automation", "level 2", "optimization", "process data", "condition monitoring"),
    "decarbonization": ("decarbonization", "hydrogen", "co2", "emission", "green steel", "eaf", "electrification"),
    "project": ("project", "commissioning", "site", "timeline", "milestone", "proposal", "contract"),
    "quality": ("quality", "claim", "issue", "non-conform", "risk", "warranty", "defect"),
}

try:
    from pypdf import PdfReader
    PDF_AVAILABLE = True
except Exception:
    PDF_AVAILABLE = False


@dataclass
class KnowledgeHit:
    source: str
    score: int
    snippet: str


class InternalKnowledgeService:
    def __init__(self):
        self.base_dir = settings.INTERNAL_KNOWLEDGE_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._text_cache: Dict[str, tuple[float, str]] = {}
        self.manifest_path = self.base_dir / "p_drive_manifest.csv"
        self.summary_path = self.base_dir / "p_drive_crawl_summary.md"
        self.index_path = self.base_dir / "keyword_index.json"  # Inverted index for fast lookup
        self.network_root = settings.INTERNAL_KNOWLEDGE_NETWORK_ROOT
        self.index_targets = list(settings.INTERNAL_KNOWLEDGE_INDEX_TARGETS)
        # Cache for analyze_customer results (30 minute TTL)
        self._analysis_cache: Dict[str, tuple[float, Dict[str, Any]]] = {}
        self._cache_ttl_seconds = 30 * 60  # 30 minutes
        # Load inverted keyword index into memory
        self._keyword_index: Dict[str, List[str]] = self._load_keyword_index()
        # Manifest entries cache: (mtime_float, entries_list)
        self._manifest_entries_cache: tuple[float, List[Dict[str, Any]]] | None = None

    def list_documents(self) -> List[Path]:
        local_docs = [
            p for p in self.base_dir.rglob("*")
            if p.is_file()
            and p.suffix.lower() in ALLOWED_EXTENSIONS
            and p.name.lower() not in {"manifest.csv", "p_drive_manifest.csv", "test_manifest.csv"}
        ]

        # IMPORTANT: avoid Path.exists() checks for large network manifests here.
        # Runtime profile generation must stay fast and predictable; network path
        # validation across 10k+ rows can block for minutes.
        manifest_docs: List[Path] = []

        seen = set()
        all_docs: List[Path] = []
        for path in local_docs + manifest_docs:
            key = str(path).lower()
            if key not in seen:
                seen.add(key)
                all_docs.append(path)

        return sorted(all_docs, key=lambda p: str(p).lower())

    def get_status(self) -> Dict[str, Any]:
        manifest_rows = 0
        last_indexed_at = None
        targets = self.index_targets

        if self.manifest_path.exists():
            try:
                manifest_df = pd.read_csv(self.manifest_path)
                manifest_rows = int(len(manifest_df))
                if not manifest_df.empty and "IndexedAt" in manifest_df.columns:
                    last_indexed_at = str(manifest_df["IndexedAt"].dropna().astype(str).iloc[-1])
            except Exception as exc:
                logger.warning("Failed to read manifest status from %s: %s", self.manifest_path, exc)

        return {
            "network_root": str(self.network_root),
            "manifest_path": str(self.manifest_path),
            "summary_path": str(self.summary_path),
            "manifest_exists": self.manifest_path.exists(),
            "manifest_rows": manifest_rows,
            "last_indexed_at": last_indexed_at,
            "targets": targets,
            "local_document_count": len([
                p for p in self.base_dir.rglob("*")
                if p.is_file() and p.suffix.lower() in ALLOWED_EXTENSIONS
            ]),
        }

    def reindex_network_documents(self, targets: Sequence[str] | None = None) -> Dict[str, Any]:
        scan_targets = [t for t in (targets or self.index_targets) if t]
        rows: List[Dict[str, Any]] = []
        indexed_at = datetime.now(timezone.utc).isoformat()
        scanned_targets: List[str] = []
        missing_targets: List[str] = []

        for target in scan_targets:
            target_path = Path(target)
            if not target_path.is_absolute():
                target_path = self.network_root / target_path

            if not target_path.exists():
                missing_targets.append(str(target_path))
                continue

            scanned_targets.append(str(target_path))
            for path in target_path.rglob("*"):
                if not path.is_file() or path.suffix.lower() not in ALLOWED_EXTENSIONS:
                    continue
                try:
                    stat = path.stat()
                    relative_path = ""
                    try:
                        relative_path = str(path.relative_to(self.network_root))
                    except Exception:
                        relative_path = str(path)
                    rows.append({
                        "SourcePath": str(path),
                        "SourceName": path.name,
                        "Extension": path.suffix.lower(),
                        "RelativePath": relative_path.replace("\\", "/"),
                        "Target": str(target).replace("\\", "/"),
                        "SizeBytes": int(stat.st_size),
                        "ModifiedAt": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                        "IndexedAt": indexed_at,
                    })
                except Exception as exc:
                    logger.warning("Failed to index internal knowledge file %s: %s", path, exc)

        manifest_df = pd.DataFrame(rows)
        if not manifest_df.empty:
            manifest_df = manifest_df.sort_values(["Target", "RelativePath", "SourceName"]).reset_index(drop=True)
        manifest_df.to_csv(self.manifest_path, index=False)
        # Invalidate manifest entries cache so next call picks up the fresh CSV
        self._manifest_entries_cache = None

        # ── Build keyword index for fast future lookups ─────────────────
        indexed_docs = self.list_documents()
        if indexed_docs:
            keyword_index = self._build_keyword_index(indexed_docs)
            self._save_keyword_index(keyword_index)
            self._keyword_index = keyword_index  # Update in-memory index
            logger.info(f"Built keyword index with {len(keyword_index)} keywords for {len(indexed_docs)} documents")

        summary = {
            "indexed_at": indexed_at,
            "network_root": str(self.network_root),
            "manifest_path": str(self.manifest_path),
            "document_count": int(len(manifest_df)),
            "scanned_targets": scanned_targets,
            "missing_targets": missing_targets,
        }
        self._write_summary(summary)
        return summary

    def analyze_customer(
        self,
        customer_name: str,
        equipment_types: Sequence[str] | None = None,
        country: str | None = None,
        limit: int = 6,
    ) -> Dict[str, Any]:
        # ── CACHE CHECK ───────────────────────────────────────────────────
        # Generate cache key from inputs
        cache_key = self._make_cache_key(customer_name, equipment_types, country, limit)
        
        # Check if cache entry exists and is still valid (not expired)
        if cache_key in self._analysis_cache:
            timestamp, cached_result = self._analysis_cache[cache_key]
            age_seconds = (datetime.now(timezone.utc) - datetime.fromtimestamp(timestamp, tz=timezone.utc)).total_seconds()
            if age_seconds < self._cache_ttl_seconds:
                logger.debug(f"Using cached analysis for '{customer_name}' (age: {age_seconds:.0f}s)")
                return cached_result
            else:
                # Cache expired, remove it
                del self._analysis_cache[cache_key]
        
        # ── CACHE MISS: COMPUTE ANALYSIS ──────────────────────────────────
        docs = self.list_documents()
        if not docs:
            result = {
                "context": "",
                "references": [],
                "evidence": [],
                "signals": self._empty_signals(),
            }
            self._analysis_cache[cache_key] = (datetime.now(timezone.utc).timestamp(), result)
            return result

        keywords = self._build_keywords(customer_name, equipment_types or [], country)
        hits = self._collect_hits(docs, keywords)
        hits.sort(key=lambda h: h.score, reverse=True)
        top_hits = hits[:limit]

        if not top_hits:
            generic_snippets = []
            for doc in docs[:5]:
                try:
                    text = self._read_text(doc)
                except Exception:
                    continue
                clean = self._clean_text(text)
                if clean:
                    generic_snippets.append(f"SOURCE: {doc.name}\n{clean[:1200]}")
            result = {
                "context": "\n\n".join(generic_snippets[:3]),
                "references": [],
                "evidence": [],
                "signals": self._empty_signals(),
            }
        else:
            result = {
                "context": "\n\n".join(f"SOURCE: {Path(hit.source).name}\n{hit.snippet}" for hit in top_hits),
                "references": [f"Internal knowledge ({hit.score}): {Path(hit.source).name}" for hit in top_hits],
                "evidence": [self._format_hit(hit) for hit in top_hits],
                "signals": self._build_topic_signals(top_hits),
            }
        
        # Store result in cache
        self._analysis_cache[cache_key] = (datetime.now(timezone.utc).timestamp(), result)
        return result

    def build_context(self, customer_name: str, equipment_types: Sequence[str] | None = None, country: str | None = None) -> str:
        return self.analyze_customer(customer_name, equipment_types, country).get("context", "")

    def get_source_references(self, customer_name: str, equipment_types: Sequence[str] | None = None, country: str | None = None, limit: int = 8) -> List[str]:
        return self.analyze_customer(customer_name, equipment_types, country, limit=limit).get("references", [])

    def get_profile_evidence(self, customer_name: str, equipment_types: Sequence[str] | None = None, country: str | None = None, limit: int = 6) -> List[Dict[str, Any]]:
        return self.analyze_customer(customer_name, equipment_types, country, limit=limit).get("evidence", [])

    def get_company_feature_signals(self, customer_name: str, equipment_types: Sequence[str] | None = None, country: str | None = None, limit: int = 6) -> Dict[str, float]:
        return self.analyze_customer(customer_name, equipment_types, country, limit=limit).get("signals", self._empty_signals())

    def get_manager_briefing_context(self, max_chars: int = 12000) -> Dict[str, str]:
        """Return manager briefing text that should be injected into all profiles.

        Looks for local internal knowledge files with 'briefing' in the filename,
        prioritizing PDFs and newest files.
        """
        candidates = [
            p for p in self.base_dir.rglob("*")
            if p.is_file() and "briefing" in p.name.lower() and p.suffix.lower() in ALLOWED_EXTENSIONS
        ]
        if not candidates:
            return {"source": "", "content": ""}

        # Prefer PDFs, then newest modified file
        candidates.sort(key=lambda p: (0 if p.suffix.lower() == ".pdf" else 1, -p.stat().st_mtime))
        source = candidates[0]
        try:
            text = self._clean_text(self._read_text(source))
        except Exception as exc:
            logger.warning("Failed to read manager briefing file %s: %s", source, exc)
            return {"source": str(source), "content": ""}

        return {
            "source": str(source),
            "content": text[:max_chars],
        }

    def _load_keyword_index(self) -> Dict[str, List[str]]:
        """Load the pre-built keyword inverted index from disk (empty dict if missing)."""
        if not self.index_path.exists():
            return {}
        try:
            with open(self.index_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Convert document path strings back (they are keys in the JSON)
                return {keyword: paths for keyword, paths in data.items()}
        except Exception as exc:
            logger.warning(f"Failed to load keyword index: {exc}")
            return {}

    def _build_keyword_index(self, docs: List[Path]) -> Dict[str, List[str]]:
        """
        Build an inverted keyword index: map keywords -> list of document paths.
        This is created during reindex and is then queried to find candidate documents.
        """
        index: Dict[str, List[str]] = {}
        
        # Extract keywords from document names and snippets
        for doc in docs:
            try:
                # Extract keywords from filename
                name_words = re.findall(r"\b\w{3,}\b", doc.stem.lower())
                text = self._read_text(doc)[:5000]  # First 5000 chars for speed
                text_words = re.findall(r"\b\w{3,}\b", text.lower())
                
                # Combine and deduplicate keywords
                keywords = set(name_words + text_words)
                
                for keyword in keywords:
                    if keyword not in index:
                        index[keyword] = []
                    if str(doc) not in index[keyword]:
                        index[keyword].append(str(doc))
            except Exception as exc:
                logger.warning(f"Failed to index document {doc}: {exc}")
                continue
        
        return index

    def _save_keyword_index(self, index: Dict[str, List[str]]) -> None:
        """Persist the keyword index to disk for fast future lookups."""
        try:
            with open(self.index_path, "w", encoding="utf-8") as f:
                json.dump(index, f, indent=2)
            logger.info(f"Saved keyword index with {len(index)} keywords to {self.index_path}")
        except Exception as exc:
            logger.warning(f"Failed to save keyword index: {exc}")

    def _get_candidate_documents(self, keywords: Sequence[str]) -> set[str]:
        """
        Use the keyword index to quickly find candidate documents that might match.
        Returns a set of document paths.
        """
        candidates = set()
        for keyword in keywords:
            keyword_lower = keyword.lower()
            if keyword_lower in self._keyword_index:
                candidates.update(self._keyword_index[keyword_lower])
        return candidates

    def build_training_feature_frame(
        self,
        items_df: pd.DataFrame,
        company_col: str,
        equipment_col: str | None = None,
        country_col: str | None = None,
    ) -> pd.DataFrame:
        if items_df.empty:
            return pd.DataFrame()

        manifest_entries = self._load_manifest_entries()

        # ── Aggregate at unique-company level to avoid O(n*m) repetition ──
        # Many BCG rows share the same company. Compute knowledge features once
        # per unique company, then join back by position.
        companies = items_df[company_col].fillna("").astype(str)
        equipment = items_df[equipment_col].fillna("").astype(str) if equipment_col else pd.Series("", index=items_df.index)
        countries = items_df[country_col].fillna("").astype(str) if country_col else pd.Series("", index=items_df.index)

        # Build a lookup key: (company, equipment_type, country) per row
        # – use company-only key for deduplication since manifest matching is company-driven
        unique_keys: dict[str, Dict[str, float]] = {}
        row_keys: List[str] = []

        for company, eq, country in zip(companies, equipment, countries):
            key = company  # manifest features are company-level
            row_keys.append(key)
            if key not in unique_keys:
                unique_keys[key] = self._build_training_features(
                    company_name=company,
                    equipment_type=eq,
                    country=country,
                    manifest_entries=manifest_entries,
                )

        feature_rows = [unique_keys[k] for k in row_keys]
        return pd.DataFrame(feature_rows)

    def _collect_hits(self, docs: Sequence[Path], keywords: Sequence[str]) -> List[KnowledgeHit]:
        hits: List[KnowledgeHit] = []
        started_at = time.monotonic()
        scan_budget_seconds = 18.0
        max_docs_to_scan = 140
        
        # ── FAST PATH: Use index to filter candidate documents ──────────
        candidate_paths = self._get_candidate_documents(keywords)
        
        if candidate_paths:
            # Score only the candidate documents found by index
            logger.debug(f"Using index: {len(candidate_paths)} candidates out of {len(docs)} total documents")
            candidates = [Path(p) for p in candidate_paths if Path(p).exists()]
        else:
            # FALLBACK: no index hits. Do not scan all files (can be 10k+ docs).
            logger.debug(f"No index hits, scanning limited subset ({len(docs)} docs total)")
            candidates = list(docs)

        # Prioritize likely-relevant, lighter formats and manager briefing files.
        def _priority(path: Path):
            suffix = path.suffix.lower()
            name = path.name.lower()
            format_rank = {
                ".pdf": 0,
                ".docx": 1,
                ".txt": 2,
                ".md": 3,
                ".html": 4,
                ".htm": 5,
                ".json": 6,
                ".csv": 7,
                ".xlsx": 8,
                ".xls": 9,
            }.get(suffix, 10)
            briefing_rank = 0 if "briefing" in name else 1
            size = path.stat().st_size if path.exists() else 0
            return (briefing_rank, format_rank, size)

        candidates = sorted(candidates, key=_priority)[:max_docs_to_scan]
        
        for doc in candidates:
            if time.monotonic() - started_at > scan_budget_seconds:
                logger.debug("Internal knowledge scan budget reached (%.1fs)", scan_budget_seconds)
                break
            try:
                text = self._read_text(doc)
            except Exception as exc:
                logger.warning("Failed to read internal knowledge file %s: %s", doc, exc)
                continue
            if not text.strip():
                continue
            score, snippet = self._score_text(text, keywords)
            title_bonus = self._title_bonus(doc.name, keywords)
            total_score = score + title_bonus
            if total_score > 0 and snippet:
                hits.append(KnowledgeHit(source=str(doc), score=total_score, snippet=snippet))
        return hits

    def _make_cache_key(
        self,
        customer_name: str,
        equipment_types: Sequence[str] | None,
        country: str | None,
        limit: int,
    ) -> str:
        """Generate a stable cache key from analyze_customer parameters."""
        eq = tuple(sorted(equipment_types or []))
        return f"{customer_name}|{eq}|{country or ''}|{limit}"

    def _build_training_features(
        self,
        company_name: Any,
        equipment_type: Any,
        country: Any,
        manifest_entries: Sequence[Dict[str, Any]],
    ) -> Dict[str, float]:
        signals = self._empty_signals()
        if not manifest_entries:
            return signals

        company_value = str(company_name or "").strip()
        company_tokens = [token for token in self._company_tokens(company_value) if token]
        equipment_tokens = [token for token in re.split(r"\W+", str(equipment_type or "").lower()) if len(token) > 2]
        country_tokens = [token for token in re.split(r"\W+", str(country or "").lower()) if len(token) > 2]

        match_scores: List[int] = []
        weighted_topics = {key: 0.0 for key in TOPIC_KEYWORDS}

        for entry in manifest_entries:
            text = entry["text"]
            base_score = 0
            if company_value:
                normalized_company = self._normalise_name(company_value)
                if normalized_company and normalized_company in text:
                    base_score += 6
            base_score += sum(2 for token in company_tokens if token and token in text)
            base_score += sum(1 for token in equipment_tokens if token and token in text)
            base_score += sum(1 for token in country_tokens if token and token in text)
            if base_score <= 0:
                continue

            match_scores.append(base_score)
            for topic, keywords in TOPIC_KEYWORDS.items():
                topic_hits = sum(1 for keyword in keywords if keyword.lower() in text)
                if topic_hits:
                    weighted_topics[topic] += base_score * topic_hits

        if not match_scores:
            return signals

        signals["knowledge_doc_count"] = float(len(match_scores))
        signals["knowledge_best_match_score"] = float(max(match_scores))
        signals["knowledge_avg_match_score"] = float(sum(match_scores) / len(match_scores))
        total_topic_weight = sum(weighted_topics.values()) or 1.0
        for topic, weight in weighted_topics.items():
            signals[f"knowledge_{topic}_signal"] = float(weight / total_topic_weight)
        return signals

    def _load_manifest_entries(self) -> List[Dict[str, Any]]:
        """Return manifest entries, refreshing the in-memory cache only when the
        CSV has changed on disk (checked via mtime)."""
        if not self.manifest_path.exists():
            return []

        try:
            mtime = self.manifest_path.stat().st_mtime
        except Exception:
            mtime = 0.0

        # Return cached version if file has not changed
        if self._manifest_entries_cache is not None:
            cached_mtime, cached_entries = self._manifest_entries_cache
            if mtime == cached_mtime:
                return cached_entries

        try:
            manifest_df = pd.read_csv(self.manifest_path)
        except Exception as exc:
            logger.warning("Failed to read manifest entries from %s: %s", self.manifest_path, exc)
            return []

        entries: List[Dict[str, Any]] = []
        for _, row in manifest_df.iterrows():
            source_name = str(row.get("SourceName", "") or "")
            relative_path = str(row.get("RelativePath", "") or "")
            target = str(row.get("Target", "") or "")
            text = self._clean_text(" ".join([source_name, relative_path, target]).lower())
            if text:
                entries.append({"text": text})

        self._manifest_entries_cache = (mtime, entries)
        logger.info("Refreshed manifest entries cache: %d entries from %s", len(entries), self.manifest_path)
        return entries

    def _write_summary(self, summary: Dict[str, Any]) -> None:
        lines = [
            "# Internal Knowledge Crawl Summary",
            "",
            f"- Indexed at: {summary.get('indexed_at', 'n/a')}",
            f"- Network root: {summary.get('network_root', 'n/a')}",
            f"- Documents indexed: {summary.get('document_count', 0)}",
            "- Scanned targets:",
        ]
        for target in summary.get("scanned_targets", []):
            lines.append(f"  - {target}")
        if summary.get("missing_targets"):
            lines.append("- Missing targets:")
            for target in summary["missing_targets"]:
                lines.append(f"  - {target}")
        self.summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _format_hit(self, hit: KnowledgeHit) -> Dict[str, Any]:
        path = Path(hit.source)
        return {
            "source": hit.source,
            "source_name": path.name,
            "folder": str(path.parent),
            "score": int(hit.score),
            "snippet": hit.snippet,
            "topics": self._extract_topics(f"{path.name} {hit.snippet}"),
        }

    def _extract_topics(self, text: str) -> List[str]:
        lowered = text.lower()
        topics = []
        for topic, keywords in TOPIC_KEYWORDS.items():
            if any(keyword.lower() in lowered for keyword in keywords):
                topics.append(topic)
        return topics

    def _build_topic_signals(self, hits: Sequence[KnowledgeHit]) -> Dict[str, float]:
        signals = self._empty_signals()
        if not hits:
            return signals

        signals["knowledge_doc_count"] = float(len(hits))
        signals["knowledge_best_match_score"] = float(max(hit.score for hit in hits))
        signals["knowledge_avg_match_score"] = float(sum(hit.score for hit in hits) / len(hits))

        topic_weights = {key: 0.0 for key in TOPIC_KEYWORDS}
        for hit in hits:
            text = f"{Path(hit.source).name} {hit.snippet}".lower()
            for topic, keywords in TOPIC_KEYWORDS.items():
                if any(keyword.lower() in text for keyword in keywords):
                    topic_weights[topic] += float(hit.score)

        total_weight = sum(topic_weights.values()) or 1.0
        for topic, weight in topic_weights.items():
            signals[f"knowledge_{topic}_signal"] = float(weight / total_weight)
        return signals

    def _empty_signals(self) -> Dict[str, float]:
        signals = {
            "knowledge_doc_count": 0.0,
            "knowledge_best_match_score": 0.0,
            "knowledge_avg_match_score": 0.0,
        }
        for topic in TOPIC_KEYWORDS:
            signals[f"knowledge_{topic}_signal"] = 0.0
        return signals

    def _company_tokens(self, customer_name: str) -> List[str]:
        normalized = self._normalise_name(customer_name)
        tokens = [token for token in normalized.split() if len(token) > 3]
        if normalized:
            tokens.append(normalized)
        return tokens

    def _normalise_name(self, name: str) -> str:
        name = str(name).lower()
        name = re.sub(r"\b(gmbh|co|kg|inc|ltd|llc|corp|ag|sa|spa|nv|bv|as|ab|oy|plc)\b\.?", "", name)
        name = re.sub(r"[^a-z0-9 ]", " ", name)
        return re.sub(r"\s+", " ", name).strip()

    def _build_keywords(self, customer_name: str, equipment_types: Sequence[str], country: str | None) -> List[str]:
        keywords = {
            customer_name.strip(),
            *(et.strip() for et in equipment_types if et and et.strip()),
            *(part for part in re.split(r"\W+", customer_name) if len(part) > 3),
            "SMS group",
            "steel",
            "metallurgy",
            "decarbonization",
            "EAF",
            "BOF",
            "caster",
            "rolling mill",
            "service",
            "digitalization",
        }
        if country and str(country).strip():
            keywords.add(str(country).strip())
        return [k for k in keywords if k]

    def _title_bonus(self, name: str, keywords: Iterable[str]) -> int:
        lowered = name.lower()
        return sum(3 for keyword in keywords if keyword.lower() in lowered)

    def _score_text(self, text: str, keywords: Iterable[str]) -> tuple[int, str]:
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
        best_score = 0
        best_snippet = ""
        for para in paragraphs:
            clean_para = self._clean_text(para)
            if len(clean_para) < 120:
                continue
            score = sum(clean_para.lower().count(keyword.lower()) for keyword in keywords)
            if score > best_score:
                best_score = score
                best_snippet = clean_para[:1800]
        return best_score, best_snippet

    def _read_text(self, path: Path) -> str:
        cache_key = str(path)
        try:
            mtime = path.stat().st_mtime
        except Exception:
            mtime = 0.0

        cached = self._text_cache.get(cache_key)
        if cached and cached[0] == mtime:
            return cached[1]

        suffix = path.suffix.lower()
        if suffix in {".txt", ".md"}:
            text = path.read_text(encoding="utf-8", errors="ignore")
        elif suffix in {".html", ".htm"}:
            text = BeautifulSoup(path.read_text(encoding="utf-8", errors="ignore"), "html.parser").get_text("\n")
        elif suffix == ".json":
            data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
            text = json.dumps(data, indent=2, ensure_ascii=False)
        elif suffix == ".csv":
            df = pd.read_csv(path)
            text = df.astype(str).head(120).to_csv(index=False)
        elif suffix in {".xlsx", ".xls"}:
            xls = pd.ExcelFile(path)
            parts = []
            for sheet in xls.sheet_names[:5]:
                try:
                    sdf = pd.read_excel(path, sheet_name=sheet).head(60)
                    parts.append(f"SHEET: {sheet}\n" + sdf.astype(str).to_csv(index=False))
                except Exception:
                    continue
            text = "\n\n".join(parts)
        elif suffix == ".docx":
            doc = Document(str(path))
            text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        elif suffix == ".pdf" and PDF_AVAILABLE:
            reader = PdfReader(str(path))
            pages = []
            for page in reader.pages[:20]:
                try:
                    pages.append(page.extract_text() or "")
                except Exception:
                    continue
            text = "\n".join(pages)
        else:
            text = ""

        self._text_cache[cache_key] = (mtime, text)
        return text

    def _clean_text(self, text: str) -> str:
        text = re.sub(r"\s+", " ", text)
        return text.strip()


internal_knowledge_service = InternalKnowledgeService()