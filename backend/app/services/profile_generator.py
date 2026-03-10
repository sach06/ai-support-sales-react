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
        return f"""You are an expert industrial strategy consultant, metallurgist, and financial analyst working for SMS group, a global engineering and plant construction company for the steel industry.
Your task is to generate a highly detailed, 10 to 15 pages long, executive-level Customer Analysis Report based on the provided data sources.
Maintain a formal, executive consulting tone comparable to BCG, McKinsey, or Goldman Sachs industry deep-dive reports.

METHODOLOGY & CONSTRAINTS:
1. Base your analysis on steel industry expertise, metallurgical process knowledge, market intelligence, and financial analysis.
2. If exact data is unavailable, clearly state assumptions and use conservative industry benchmarks based on your expert knowledge.
3. Do not hallucinate proprietary datasets; instead, infer logically and label as industry-based estimation.
4. Always analyze from the perspective of SMS group's equipment portfolio, decarbonization strategy, and competitive positioning vs competitors (Danieli, Primetals, Fives).
5. Output MUST be in the exact JSON schema provided below. Format long text areas with '\n\n' for paragraph breaks.

DATA SOURCES:
{context}

Generate a JSON object with the following structure. Pay extraordinary attention to the length and depth constraints for the text fields:
{{
    "basic_data": {{
        "name": "Company name",
        "hq_address": "Headquarters address",
        "owner": "Owner/Parent company",
        "management": "Key management personnel",
        "ceo": "CEO Name",
        "fte": "Number of employees",
        "financials": "High-level financial status",
        "company_focus": "Company strategic positioning in steel (e.g., stainless steel, flat products)",
        "ownership_history": "Brief ownership history"
    }},
    "locations": [
        {{
            "address": "Location address",
            "city": "City",
            "country": "Country",
            "final_products": "Products manufactured",
            "tons_per_year": "Production capacity",
            "installed_base": [
                {{
                    "equipment_type": "Type of equipment",
                    "manufacturer": "OEM",
                    "year_of_startup": "Year",
                    "status": "Operational/Idle"
                }}
            ]
        }}
    ],
    "priority_analysis": {{
        "priority_score": "Score (0-100)",
        "priority_rank": "Rank",
        "company_explainer": "PRIORITY RANKING ANALYSIS: Detailed 5-paragraph deep dive. Analyze operations, country footprint, site relevance, financial strength, and strategic fit for SMS group. Conclude what this ranking means for resource allocation.",
        "key_opportunity_drivers": "KEY OPPORTUNITY DRIVERS (5-7 paragraphs): Elaborate on large installed base and modernization needs, alignment with green steel / SMS decarbonization portfolio, and historical relationship upselling potential.",
        "engagement_recommendation": "ENGAGEMENT RECOMMENDATION (5-7 paragraphs): Elaborate on urgency, site prioritization (e.g. key meltshops or rolling mills), and specific pilot solutions to introduce."
    }},
    "history": {{
        "latest_projects": "PROJECT HISTORY & SALES RELATIONSHIP: Describe relationship maturity, trust level, realized/ongoing projects and what they indicate strategically. State if CRM data is unavailable and implications.",
        "total_won_value_eur": "Total won value",
        "win_rate_pct": "Win rate",
        "sms_relationship": "Key SMS contact"
    }},
    "market_intelligence": {{
        "financial_health": "COMPANY FINANCIAL ANALYSIS (5-7 paragraphs): Chartered-accountant-level deep dive. Analyze revenue trends, EBITDA, margins, debt, capex. Interpret financial health in terms of investment capacity for modernization and green steel.",
        "market_position": "MARKET CONTEXT: End-customer industries, demand drivers, and competitive positioning in the steel market."
    }},
    "country_intelligence": {{
        "steel_market_summary": "COUNTRY-LEVEL INTELLIGENCE: Steel market structure of the operations country",
        "economic_context": "Economic context",
        "trade_tariff_context": "Trade & tariffs",
        "automotive_sector": "Automotive demand",
        "investment_drivers": "Investment drivers and risks"
    }},
    "metallurgical_insights": {{
        "process_efficiency": "METALLURGICAL INSIGHTS: Process efficiency and age profile based on installed base",
        "carbon_footprint_strategy": "Carbon footprint and green steel readiness",
        "modernization_potential": "Modernization potential using SMS technologies",
        "technical_bottlenecks": "Technical bottlenecks and digitalization opportunities"
    }},
    "sales_strategy": {{
        "value_proposition": "STRATEGIC SALES PITCH (10-15 paragraphs): Recommended SMS portfolio. Value proposition linked to KPIs (energy, yield, CO2, quality). Competitive landscape vs. Danieli, Primetals, Fives. Suggested next steps with concrete actions."
    }}
}}

CRITICAL INSTRUCTIONS:
- You must write extensively. The entire report should total 10-15 pages of text when combined.
- Use '\n\n' for paragraph spacing in long strings to ensure frontend readability.
- Deliver executive, BCG/McKinsey-level prose. No marketing fluff, no emojis."""
    
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
