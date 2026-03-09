"""
Mapping service for AI-assisted company name matching.
Uses a 4-tier strategy:
  1. Exact match (fast O(1) dict lookup)
  2. Cleaned/normalised name match (strip legal suffixes)
  3. Fuzzy token-sort match (thefuzz)
  4. LLM verification via standard OpenAI OR Azure OpenAI
"""
import json
import logging
import re
from typing import Dict, List, Tuple, Optional

from thefuzz import fuzz, process
from app.core.config import settings

logger = logging.getLogger(__name__)


# ── Legal-suffix normaliser ───────────────────────────────────────────────────
# Only strips truly generic legal/corporate form words, NOT industry-meaningful
# words like 'steel', 'metals', 'works', 'plant' (which are distinctive).
_LEGAL_SUFFIXES = re.compile(
    r'\b(gmbh\s*&\s*co\.?\s*kg|gmbh\s*&\s*co\.?|gmbh|s\.p\.a\.?|spa|ltd\.?|corp\.?|'
    r'inc\.?|ag|s\.a\.?|nv|oy|oyj|as|ab|plc|pty\.?\s*ltd\.?|'
    r'limited|corporation|holding|holdings|international|intl)\b\.?',
    re.IGNORECASE,
)

def _normalize(name: str) -> str:
    """Strip legal suffixes, punctuation and extra whitespace for comparison."""
    if not name:
        return ""
    cleaned = _LEGAL_SUFFIXES.sub("", str(name))
    cleaned = re.sub(r'[^a-zA-Z0-9\s]', ' ', cleaned)
    return re.sub(r'\s+', ' ', cleaned).strip().lower()


# ── LLM client builder ────────────────────────────────────────────────────────
def _build_llm_client():
    """Return (client, model) for Azure OpenAI or standard OpenAI, whichever is configured."""
    # Priority 1: Azure OpenAI
    if settings.use_azure_openai:
        try:
            from openai import AzureOpenAI
            client = AzureOpenAI(
                api_key=settings.AZURE_OPENAI_API_KEY,
                api_version=settings.AZURE_OPENAI_API_VERSION,
                azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
                timeout=30.0,
            )
            return client, settings.AZURE_OPENAI_DEPLOYMENT
        except Exception as e:
            logger.warning(f"Azure OpenAI init failed: {e}")

    # Priority 2: Standard OpenAI
    if settings.use_openai:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=30.0)
            return client, "gpt-4o"
        except Exception as e:
            logger.warning(f"Standard OpenAI init failed: {e}")

    return None, None


class MappingService:
    """Service to map company names between different datasets using AI.

    Matching strategy (stops at first success):
      Tier 1 – Exact string match
      Tier 2 – Normalised (suffix-stripped) exact match
      Tier 3 – Fuzzy token_sort_ratio >= threshold
      Tier 4 – LLM entity resolution on top-10 fuzzy candidates
    """

    def __init__(self):
        self.client, self.model = _build_llm_client()
        if self.client:
            logger.info(f"MappingService: LLM ready (model={self.model})")
        else:
            logger.info("MappingService: No LLM available — fuzzy-only mode")

    # ── Public API ──────────────────────────────────────────────────────────────

    def find_best_match(
        self,
        name: str,
        choices: List[str],
        threshold: int = 75,
    ) -> Optional[Tuple[str, float]]:
        """
        Return (matched_name, score) or None if no good match found.

        Tiers:
          1. Exact match → score 100
          2. Normalised exact match → score 97
          3a. Fuzzy token_sort_ratio ≥ 95  → accept without LLM
          3b. Fuzzy token_set_ratio  ≥ 90  → accept without LLM (handles reordered words)
          4. LLM on top-10 fuzzy candidates (if fuzzy ≥ 50 or acronym hit)
          5. Fuzzy fallback if ≥ threshold
        """
        if not name or not choices:
            return None

        choices_lower = {str(c).lower(): c for c in choices}

        # ── Tier 1: exact ──────────────────────────────────────────────────────
        name_lower = str(name).lower()
        if name_lower in choices_lower:
            return choices_lower[name_lower], 100.0

        # ── Tier 2: normalised exact ───────────────────────────────────────────
        norm_name = _normalize(name)
        norm_map = {_normalize(c): c for c in choices}
        if norm_name and norm_name in norm_map:
            return norm_map[norm_name], 97.0

        # ── Tier 3a: fuzzy token_sort_ratio ──────────────────────────────────
        best_match, score = process.extractOne(
            name, choices, scorer=fuzz.token_sort_ratio
        )
        if score >= 95:
            return best_match, float(score)

        # ── Tier 3b: fuzzy token_set_ratio (handles word reorder / subset) ───
        best_set_match, set_score = process.extractOne(
            name, choices, scorer=fuzz.token_set_ratio
        )
        if set_score >= 90:
            return best_set_match, float(set_score)

        # ── Tier 3c: normalised token_sort on cleaned names ───────────────────
        norm_choices = list(norm_map.keys())
        if norm_name and norm_choices:
            best_norm, norm_score = process.extractOne(
                norm_name, norm_choices, scorer=fuzz.token_sort_ratio
            )
            if norm_score >= 90:
                return norm_map[best_norm], float(norm_score)

        # ── Tier 4: LLM ───────────────────────────────────────────────────────
        # Collect candidates from both scorers for LLM
        fuzzy_score = max(score, set_score)
        if self.client and fuzzy_score >= 45:
            candidates = process.extract(
                name, choices, scorer=fuzz.token_sort_ratio, limit=10
            )
            # Also include token_set_ratio candidates
            candidates_set = process.extract(
                name, choices, scorer=fuzz.token_set_ratio, limit=5
            )
            candidate_names = list({
                c[0] for c in (candidates + candidates_set) if c[1] >= 35
            })
            # Acronym check: if BCG name looks like initials, try to find full-form
            if not candidate_names or len(name.replace(' ', '')) <= 6:
                acro_candidates = self._acronym_candidates(name, choices)
                candidate_names = list(set(candidate_names) | set(acro_candidates))
            if candidate_names:
                llm_result = self._verify_with_llm(name, candidate_names)
                if llm_result:
                    return llm_result

        # ── Tier 5 fallback: best fuzzy score if above threshold ──────────────
        best_overall_match = best_match if score >= set_score else best_set_match
        best_overall_score = max(score, set_score)
        if best_overall_score >= threshold:
            return best_overall_match, float(best_overall_score)

        return None

    def _acronym_candidates(self, name: str, choices: List[str]) -> List[str]:
        """Find CRM entries whose initials match `name` (e.g. 'HKM' → 'Huetten- und Kapitalwerk Marxloh')."""
        name_up = name.strip().upper().replace(' ', '').replace('.', '')
        if len(name_up) < 2:
            return []
        matches = []
        for choice in choices:
            words = re.sub(r'[^a-zA-Z0-9 ]', ' ', choice).split()
            initials = ''.join(w[0].upper() for w in words if w)
            if initials == name_up or initials.startswith(name_up) or name_up.startswith(initials):
                matches.append(choice)
        return matches[:5]  # limit to avoid LLM overload

    # ── LLM helpers ────────────────────────────────────────────────────────────

    def _verify_with_llm(
        self, name: str, candidates: List[str]
    ) -> Optional[Tuple[str, float]]:
        """Ask the LLM to pick the best candidate for `name`."""
        prompt = f"""Task: Steel-industry company entity resolution.

Target name: "{name}"
Candidates (from CRM):
{json.dumps(candidates, indent=2)}

Rules:
1. Decide if "{name}" is the SAME legal entity as any candidate.
2. Account for: abbreviations, legal-form differences (GmbH/AG/Ltd/Oyj/NV/AS),
   holding-vs-operating company names, national spelling variants.
3. ONLY match if you are confident they refer to the exact same company.
4. If matched, set confidence proportional to certainty (70–100).

Respond ONLY with JSON:
{{"match_found": true/false, "matched_name": "<exact string from candidates or null>", "confidence": <0-100>}}"""

        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert in industrial master data management "
                            "and steel-industry company entity resolution."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0,
            )
            result = json.loads(completion.choices[0].message.content)
            if result.get("match_found") and result.get("matched_name"):
                return result["matched_name"], float(result.get("confidence", 85))
        except Exception as e:
            logger.error(f"LLM entity resolution error: {e}")

        return None


# ── Singleton ─────────────────────────────────────────────────────────────────
mapping_service = MappingService()
