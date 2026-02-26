"""
AI Service for enriching company data (CEO, FTE) using LLM
"""
import json
import pandas as pd
from typing import Dict, List, Optional
from openai import AzureOpenAI, OpenAI
from app.core.config import settings

class EnrichmentService:
    """Enrich company data with AI-searched information"""
    
    def __init__(self):
        self.client = None
        self.model: Optional[str] = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize OpenAI client (Azure or Standard)"""
        if settings.use_azure_openai:
            self.client = AzureOpenAI(
                api_key=settings.AZURE_OPENAI_API_KEY,
                api_version=settings.AZURE_OPENAI_API_VERSION,
                azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
                timeout=60.0
            )
            self.model = settings.AZURE_OPENAI_DEPLOYMENT
        elif settings.use_openai:
            self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
            self.model = "gpt-4o"
        
    def enrich_locations(self, companies: List[str]) -> Dict[str, Dict]:
        """
        Search for geographical coordinates (lat/lon) and full business HQ country for companies
        Returns a mapping of company name to its enriched location data
        """
        if not self.client or not companies:
            return {}
        
        batch_size = 10
        all_results = {}
        
        for i in range(0, len(companies), batch_size):
            batch = companies[i:i+batch_size]
            prompt = f"""For the following companies, find their headquarters or primary plant location:
            - Latitude and Longitude (decimal degrees)
            - Official Country Name
            
            Companies:
            {', '.join(batch)}
            
            Return ONLY a JSON object where keys are the company names exactly as provided, and values are objects with "latitude", "longitude", and "country" keys.
            Example:
            {{
                "SMS group GmbH": {{"latitude": 51.196, "longitude": 6.786, "country": "Germany"}},
                "ThyssenKrupp AG": {{"latitude": 51.455, "longitude": 7.011, "country": "Germany"}}
            }}
            """
            
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a professional business researcher specializing in corporate intelligence and global industrial locations."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.0,
                    response_format={"type": "json_object"}
                )
                
                batch_results = json.loads(response.choices[0].message.content)
                all_results.update(batch_results)
            except Exception as e:
                print(f"Error enriching locations for batch {batch}: {e}")
                
        return all_results

    def enrich_companies(self, companies: List[str]) -> Dict[str, Dict]:
        """
        Search for CEO and Employee count for a list of companies
        Returns a mapping of company name to its enriched data
        """
        if not self.client or not companies:
            return {}
        
        batch_size = 10
        all_results = {}
        
        for i in range(0, len(companies), batch_size):
            batch = companies[i:i+batch_size]
            prompt = f"""For the following companies, find the current CEO name and the approximate total number of full-time employees (FTE).
            
            Companies:
            {', '.join(batch)}
            
            Return ONLY a JSON object where keys are the company names exactly as provided, and values are objects with "ceo" and "fte" keys.
            Example:
            {{
                "Apple Inc": {{"ceo": "Tim Cook", "fte": 164000}},
                "Microsoft": {{"ceo": "Satya Nadella", "fte": 221000}}
            }}
            
            If you are not sure, provide your best estimate based on latest knowledge or use null.
            """
            
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a professional business researcher specializing in corporate intelligence."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.0,
                    response_format={"type": "json_object"}
                )
                
                batch_results = json.loads(response.choices[0].message.content)
                all_results.update(batch_results)
            except Exception as e:
                print(f"Error enriching batch {batch}: {e}")
                
        return all_results

# Singleton instance
enrichment_service = EnrichmentService()
