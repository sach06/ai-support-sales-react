"""
AI Service for generating customer profiles (Steckbrief) using LLM
"""
import json
import numpy as np
from typing import Dict, Optional
from openai import AzureOpenAI, OpenAI
from app.core.config import settings

class NumpyEncoder(json.JSONEncoder):
    """Custom JSON encoder for NumPy types"""
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.generic):
            return obj.item()
        return super(NumpyEncoder, self).default(obj)


class ProfileGeneratorService:
    """Generate comprehensive customer profiles using AI"""
    
    def __init__(self):
        self.client = None
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
            print("Azure OpenAI client initialized")
        elif settings.use_openai:
            self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
            self.model = "gpt-4o"
            print("OpenAI client initialized")
        else:
            print("No OpenAI API key configured. Profile generation will be limited.")
    
    def generate_profile(
        self,
        customer_data: Dict,
        web_data: Optional[str] = None,
        extra_context: Optional[Dict] = None,
    ) -> Dict:
        """
        Generate a comprehensive customer profile (Steckbrief).

        Args:
            customer_data:  Dictionary containing CRM, BCG, and installed base data
            web_data:       Optional web search results for enrichment
            extra_context:  Optional dict with additional data sources:
                              - priority_ranking: dict with score, rank, drivers
                              - financial_details: dict from financial_service
                              - crm_history:       dict from historical_service
                              - ib_summary:        dict from historical_service.get_ib_summary
                              - country_intelligence: dict from web_enrichment_service
                              - company_news:      list of recent news items

        Returns:
            Dictionary with structured profile fields
        """
        if not self.client:
            return self._generate_fallback_profile(customer_data)

        # Build context from available data
        context = self._build_context(customer_data, web_data, extra_context or {})

        # Create prompt for structured profile generation
        prompt = self._create_profile_prompt(context)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert business analyst and metallurgical sales strategist "
                            "at SMS group, creating comprehensive customer intelligence dossiers "
                            "(Steckbriefe) for B2B sales teams. Use ALL provided data sources."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                response_format={"type": "json_object"},
            )

            profile_json = json.loads(response.choices[0].message.content)
            return profile_json

        except Exception as e:
            print(f"Error generating profile: {e}")
            return self._generate_fallback_profile(customer_data)
    
    def _build_context(
        self,
        customer_data: Dict,
        web_data: Optional[str],
        extra_context: Optional[Dict] = None,
    ) -> str:
        """Build comprehensive context string from all available data sources."""
        context_parts = []
        extra = extra_context or {}

        # ── Core internal data ────────────────────────────────────────────────
        if 'crm' in customer_data:
            context_parts.append("CRM DATA:\n" + json.dumps(customer_data['crm'], indent=2, cls=NumpyEncoder))

        if 'bcg' in customer_data:
            context_parts.append("BCG MARKET DATA:\n" + json.dumps(customer_data['bcg'], indent=2, cls=NumpyEncoder))

        if 'installed_base' in customer_data:
            ib = customer_data['installed_base']
            context_parts.append(
                f"INSTALLED BASE:\n{len(ib)} equipment records (sample of first 5 shown)\n"
                + json.dumps(ib[:5], indent=2, cls=NumpyEncoder)
            )

        # ── Priority ranking ──────────────────────────────────────────────────
        if extra.get('priority_ranking'):
            pr = extra['priority_ranking']
            context_parts.append(
                "PRIORITY RANKING:\n"
                + json.dumps(pr, indent=2, cls=NumpyEncoder)
            )

        # ── Financial details ─────────────────────────────────────────────────
        if extra.get('financial_details'):
            context_parts.append(
                "FINANCIAL DETAILS:\n"
                + json.dumps(extra['financial_details'], indent=2, cls=NumpyEncoder)
            )

        # ── CRM historical performance ────────────────────────────────────────
        if extra.get('crm_history'):
            hist = extra['crm_history']
            metrics = hist.get('metrics', {})
            context_parts.append(
                f"CRM HISTORICAL PERFORMANCE:\n"
                f"  Total Won Value: {metrics.get('total_won_value', 'N/A')} EUR\n"
                f"  Total Projects: {metrics.get('n_projects', 'N/A')}\n"
                f"  Win Rate: {metrics.get('win_rate', 'N/A')}%\n"
                f"  Years of Data: {metrics.get('time_span', 'N/A')}"
            )

        # ── Installed base summary (Axel's IB) ────────────────────────────────
        if extra.get('ib_summary') and extra['ib_summary'].get('n_units', 0) > 0:
            ib_sum = extra['ib_summary']
            context_parts.append(
                f"IB LIST SUMMARY (Axel's data):\n"
                f"  Equipment Units: {ib_sum.get('n_units', 0)}\n"
                f"  Average Age: {ib_sum.get('avg_age', 'N/A')} years\n"
                f"  Types: {', '.join(str(t) for t in ib_sum.get('equipment_types', []))}"
            )

        # ── Country intelligence ───────────────────────────────────────────────
        if extra.get('country_intelligence'):
            ci = extra['country_intelligence']
            country = ci.get('country', 'Unknown')
            # Summarise news headlines only (keep context short)
            def _headlines(news_list, n=3):
                return '; '.join(
                    item.get('title', '') for item in (news_list or [])[:n]
                ) or 'No recent news found'

            context_parts.append(
                f"COUNTRY INTELLIGENCE ({country}):\n"
                f"  Steel industry news: {_headlines(ci.get('steel_news', []))}\n"
                f"  Economic developments: {_headlines(ci.get('economic_developments', []))}\n"
                f"  Tariffs/Trade: {_headlines(ci.get('tariffs_trade', []))}\n"
                f"  Automotive trends: {_headlines(ci.get('automotive_trends', []))}\n"
                f"  Other macro: {_headlines(ci.get('other_macro', []))}"
            )

        # ── Company news ──────────────────────────────────────────────────────
        if extra.get('company_news'):
            news = extra['company_news']
            headlines = '; '.join(item.get('title', '') for item in news[:5])
            context_parts.append(f"RECENT COMPANY NEWS:\n{headlines}")

        # ── Web research ──────────────────────────────────────────────────────
        if web_data:
            context_parts.append(f"WEB RESEARCH:\n{web_data}")

        return "\n\n".join(context_parts)


    def _create_profile_prompt(self, context: str) -> str:
        """Create the prompt for profile generation with expanded JSON schema."""
        return f"""Based on ALL of the following customer data sources, generate a comprehensive customer intelligence dossier (Steckbrief) in JSON format.

{context}

Generate a JSON object with the following structure (include ALL sections):
{{
    "basic_data": {{
        "name": "Company name",
        "hq_address": "Headquarters address",
        "latitude": "Latitude as float or null",
        "longitude": "Longitude as float or null",
        "owner": "Owner/Parent company",
        "management": "Key management personnel (CEO, CFO, etc.)",
        "ceo": "Specific name of the CEO",
        "fte": "Number of employees (total FTE)",
        "financials": "Financial status/revenue (latest available)",
        "buying_center": "Buying center information",
        "company_focus": "Company focus, vision, strategy",
        "embargos_esg": "Any embargos or ESG concerns",
        "frame_agreements": "Existing frame agreements with SMS group",
        "recent_facts": "Notable recent news, mergers, or strategic shifts from the last 1-2 years",
        "ownership_history": "Brief ownership history with dates (e.g., Pre-2016: X, 2016-2019: Y, 2020-present: Z)"
    }},
    "locations": [
        {{
            "address": "Location address",
            "city": "City",
            "country": "Country",
            "latitude": "Latitude as float or null",
            "longitude": "Longitude as float or null",
            "installed_base": [
                {{
                    "equipment_type": "Type of equipment",
                    "manufacturer": "OEM/Manufacturer",
                    "year_of_startup": "Year",
                    "status": "Operational/Idle"
                }}
            ],
            "final_products": "Products manufactured",
            "tons_per_year": "Production capacity"
        }}
    ],
    "history": {{
        "latest_projects": "Recent projects with SMS group",
        "realized_projects": "Completed projects",
        "crm_rating": "CRM rating",
        "key_person": "Key contact person",
        "sms_relationship": "Best SMS contact/relationship",
        "latest_visits": "Recent visits",
        "total_won_value_eur": "Total won value in EUR (from CRM history)",
        "win_rate_pct": "Overall win rate %",
        "n_projects": "Total number of projects tracked"
    }},
    "context": {{
        "end_customer": "Who is the end customer",
        "market_position": "Market position and trends"
    }},
    "financial_history": [
        {{"year": 2015, "revenue_m_eur": 100, "ebitda_m_eur": 10}},
        {{"year": 2024, "revenue_m_eur": 150, "ebitda_m_eur": 20}}
    ],
    "latest_balance_sheet": {{
        "assets": "Brief summary",
        "liabilities": "Brief summary",
        "equity": "Brief summary"
    }},
    "metallurgical_insights": {{
        "process_efficiency": "Analysis of current production efficiency based on technology age and type",
        "modernization_potential": "Specific technical areas where SMS group solutions (HybrEx, X-Pact, Lifecycle Services) could add value",
        "carbon_footprint_strategy": "Green steel initiatives or ESG targets relevant to SMS group's decarbonization portfolio",
        "technical_bottlenecks": "Likely pain points based on equipment age and type"
    }},
    "sales_strategy": {{
        "recommended_portfolio": "Specific SMS group products recommended for this customer",
        "value_proposition": "Tailored sales pitch for this specific customer",
        "competitive_landscape": "Competitors likely active at this site",
        "suggested_next_steps": "Actionable advice for the sales manager"
    }},
    "market_intelligence": {{
        "financial_health": "Current financial stability, debt levels, cash flow, recent financial performance",
        "recent_developments": "Recent announcements, projects, events (last 12-24 months)",
        "market_position": "Market share, strategic advantages, industry positioning",
        "strategic_outlook": "Future growth plans, potential investments, long-term strategy",
        "risk_assessment": "Key business risks based on market trends and company stability"
    }},
    "priority_analysis": {{
        "priority_score": "AI priority/ranking score (0-100) based on provided ranking data",
        "priority_rank": "Rank among all customers in the dataset",
        "key_opportunity_drivers": "Top 3 factors driving priority ranking (e.g. equipment age, win rate, market signal)",
        "engagement_recommendation": "Short recommendation on urgency and engagement strategy"
    }},
    "country_intelligence": {{
        "steel_market_summary": "Summary of the steel market situation in the customer's country",
        "economic_context": "Relevant economic developments (GDP, industrial output, investment climate)",
        "trade_tariff_context": "Relevant tariffs or trade measures affecting the customer's market",
        "automotive_sector": "Automotive industry trends relevant to steel demand",
        "investment_drivers": "Key factors likely to drive or delay capital investment decisions",
        "sms_positioning": "How SMS group can best position itself given the country-level market dynamics"
    }}
}}

CRITICAL INSTRUCTIONS:
1. Use ALL provided context data as primary sources — CRM, BCG, installed base, priority ranking, financial details, CRM history, country intelligence, company news.
2. THINK LIKE AN SMS GROUP METALLURGIST AND SALES MANAGER: Focus on technical modernization, lifecycle services, and sustainability (Green Steel).
3. For missing facts (CEO name, FTE, financial history), use your internal training knowledge to provide accurate information.
4. For 'financial_history', provide data for the last 10 years if possible. Use Millions of EUR/USD.
5. For 'priority_analysis', base the score and drivers on the provided PRIORITY RANKING data if available.
6. For 'country_intelligence', base the analysis on the provided COUNTRY INTELLIGENCE data headlines and your knowledge.
7. If information is absolutely not available, use "Not available" for strings or null for numbers.
8. Be concise, highly technical, and strategic."""
    
    def _generate_fallback_profile(self, customer_data: Dict) -> Dict:
        """Generate a basic profile without AI when API is not available"""
        profile = {
            "basic_data": {},
            "locations": [],
            "history": {},
            "context": {}
        }
        
        # Extract what we can from raw data
        if 'crm' in customer_data:
            crm = customer_data['crm']
            profile['basic_data'] = {
                "name": crm.get('name', crm.get('customer_name', 'Unknown')),
                "hq_address": crm.get('address', 'Not available'),
                "owner": crm.get('owner', 'Not available'),
                "management": crm.get('management', 'Not available'),
                "fte": str(crm.get('employees', crm.get('fte', 'Not available'))),
                "financials": crm.get('revenue', 'Not available'),
                "buying_center": crm.get('buying_center', 'Not available'),
                "company_focus": crm.get('focus', 'Not available'),
                "embargos_esg": crm.get('esg_notes', 'Not available'),
                "frame_agreements": crm.get('agreements', 'Not available'),
                "ownership_history": "Not available"
            }
        
        if 'installed_base' in customer_data:
            for item in customer_data['installed_base'][:5]:  # Limit to 5 locations
                profile['locations'].append({
                    "address": item.get('location', 'Not available'),
                    "installed_base": [{
                        "equipment_type": item.get('equipment', item.get('equipment_type', 'Not available')),
                        "manufacturer": item.get('oem', item.get('manufacturer', 'N/A')),
                        "year_of_startup": item.get('start_year', item.get('year', 'N/A')),
                        "status": item.get('status', 'Active')
                    }],
                    "final_products": item.get('products', 'Not available'),
                    "tons_per_year": str(item.get('capacity', 'Not available'))
                })
        
        return profile


# Singleton instance
profile_generator = ProfileGeneratorService()
