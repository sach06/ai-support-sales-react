"""
Mapping service for AI-assisted company name matching
Uses fuzzy matching + LLM verification to join CRM and BCG data
"""
import json
import logging
from typing import Dict, List, Tuple, Optional
from thefuzz import fuzz, process
from openai import AzureOpenAI
from app.core.config import settings

logger = logging.getLogger(__name__)

class MappingService:
    """Service to map company names between different datasets using AI"""
    
    def __init__(self):
        self.client = None
        if settings.use_azure_openai:
            self.client = AzureOpenAI(
                api_key=settings.AZURE_OPENAI_API_KEY,
                api_version=settings.AZURE_OPENAI_API_VERSION,
                azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
                timeout=30.0
            )
            self.model = settings.AZURE_OPENAI_DEPLOYMENT
        
    def find_best_match(self, name: str, choices: List[str], threshold: int = 85) -> Optional[Tuple[str, int]]:
        """
        Identify potential matches using fuzzy matching and verify with LLM.
        Always uses LLM for verification if fuzzy score is below 95 to ensure zero poor matches.
        """
        if not name or not choices:
            return None
            
        # 1. Direct Fuzzy matching
        best_match, score = process.extractOne(name, choices, scorer=fuzz.token_sort_ratio)
        
        # If very high score, trust it
        if score >= 98:
            return best_match, score
            
        # 2. LLM Verification for all other possible matches
        if self.client:
            # Get top 10 potential candidates for LLM to decide
            candidates = process.extract(name, choices, scorer=fuzz.token_sort_ratio, limit=10)
            potential_names = [c[0] for c in candidates]
            
            match_result = self._verify_with_llm_detailed(name, potential_names)
            if match_result:
                matched_name, confidence = match_result
                return matched_name, confidence
        
        # If no LLM result or no high confidence fuzzy match
        if score >= threshold:
            return best_match, score
            
        return None

    def _verify_with_llm_detailed(self, name: str, candidates: List[str]) -> Optional[Tuple[str, int]]:
        """Use LLM to verify and select the best match from candidates"""
        prompt = f"""Task: Company Entity Resolution
Target Name: '{name}'
Candidates: {json.dumps(candidates)}

Rules:
1. Determine if '{name}' is the same company as any in the candidates list.
2. Consider abbreviations (e.g., 'SMS' for 'SMS group'), legal suffixes ('GmbH', 'Ltd', 'AG'), and common misspellings.
3. If a match is found, return the exact name from the candidates list.
4. Set confidence to 100 if you are certain, or lower if there's ambiguity.

Respond ONLY with JSON: {{"match_found": true/false, "matched_name": "exact candidate name", "confidence": 0-100}}"""

        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert in industrial company entity resolution and master data management."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            result = json.loads(completion.choices[0].message.content)
            if result.get("match_found"):
                return result.get("matched_name"), result.get("confidence", 90)
        except Exception as e:
            logger.error(f"Error in detailed LLM verification: {e}")
        return None

    def _verify_with_llm(self, name: str, candidates: List[str]) -> bool:
        """Use LLM to verify if a name matches any of the candidates"""
        prompt = f"""Compare the company name '{name}' with the following list of candidates:
{json.dumps(candidates, indent=2)}

Are any of these candidates the same company as '{name}'? 
They might be shorthand, misspelled, or have different legal suffixes (GmbH vs AG vs Ltd).

If there is a match, specify which one. 
Respond ONLY with a JSON object: {{"match_found": true/false, "matched_name": "name from candidates or null"}}"""

        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a master of business entity resolution and company name matching."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            result = json.loads(completion.choices[0].message.content)
            return result.get("match_found", False)
        except Exception as e:
            logger.error(f"Error in LLM verification: {e}")
            return False

# Initialize singleton
mapping_service = MappingService()
