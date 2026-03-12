"""
Market Intelligence Service - Analyze market trends, competitors, and opportunities
Based on Axel Windbrake's intelligence_service.py with enhancements
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime
from app.core.config import settings

try:
    from openai import AzureOpenAI, OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logging.warning("OpenAI not available for market intelligence service")

logger = logging.getLogger(__name__)


class MarketIntelligenceService:
    """Service for generating market intelligence and competitive analysis"""
    
    def __init__(self):
        self.client = None
        if OPENAI_AVAILABLE:
            self._initialize_client()
    
    def _initialize_client(self):
        """Initialize OpenAI client"""
        try:
            if settings.use_azure_openai:
                self.client = AzureOpenAI(
                    api_key=settings.AZURE_OPENAI_API_KEY,
                    api_version=settings.AZURE_OPENAI_API_VERSION,
                    azure_endpoint=settings.AZURE_OPENAI_ENDPOINT
                )
                self.model = settings.AZURE_OPENAI_DEPLOYMENT
            elif settings.use_openai:
                self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
                self.model = "gpt-4"
            else:
                logger.warning("No OpenAI configuration found")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            self.client = None
    
    def generate_market_intelligence(self, customer_data: Dict, profile_data: Dict) -> Dict[str, str]:
        """
        Generate comprehensive market intelligence report
        
        Args:
            customer_data: Raw customer data from CRM
            profile_data: AI-generated profile
        
        Returns:
            {
                'financial_health': str,
                'recent_developments': str,
                'market_position': str,
                'strategic_outlook': str,
                'risk_assessment': str,
                'market_size': str,
                'competitors': List[str],
                'growth_trends': str,
                'sources': List[str]
            }
        """
        if not self.client:
            return self._generate_fallback_intelligence(customer_data, profile_data)
        
        try:
            prompt = self._create_intelligence_prompt(customer_data, profile_data)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a market intelligence analyst specializing in the metallurgical and industrial equipment sector. Provide detailed, actionable insights based on available data."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            content = response.choices[0].message.content
            return self._parse_intelligence_response(content)
            
        except Exception as e:
            logger.error(f"Market intelligence generation failed: {e}")
            return self._generate_fallback_intelligence(customer_data, profile_data)
    
    def analyze_competitors(self, company_name: str, industry: str, installed_base: List[Dict]) -> Dict:
        """
        Analyze competitive landscape
        
        Returns:
            {
                'main_competitors': List[str],
                'competitive_advantages': str,
                'threats': str,
                'opportunities': str,
                'market_share_estimate': str
            }
        """
        # Extract OEM/manufacturers from installed base as indicators
        oems = set()
        if installed_base:
            for equipment in installed_base:
                if 'manufacturer' in equipment:
                    oems.add(equipment['manufacturer'])
        
        return {
            'main_competitors': list(oems) if oems else ['Analysis pending'],
            'competitive_advantages': 'Based on installed base: diversified equipment portfolio',
            'threats': 'Technology obsolescence, market consolidation',
            'opportunities': 'Modernization projects, sustainability initiatives',
            'market_share_estimate': 'Requires external market data'
        }
    
    def get_tender_opportunities(self, company_name: str, region: str = None) -> List[Dict]:
        """
        Get recent tender and procurement opportunities
        
        Returns:
            [
                {
                    'tender_id': str,
                    'title': str,
                    'description': str,
                    'buyer': str,
                    'value_estimate': str,
                    'deadline': str,
                    'source_url': str
                },
                ...
            ]
        """
        # Mock implementation - would integrate with TED or national procurement APIs
        return []
    
    def analyze_regional_trends(self, region: str, country: str) -> Dict:
        """
        Analyze regional market trends
        
        Returns:
            {
                'market_growth_rate': str,
                'key_drivers': List[str],
                'regulatory_environment': str,
                'investment_trends': str,
                'regional_insights': str
            }
        """
        regional_data = {
            'market_growth_rate': 'Analysis pending',
            'key_drivers': ['Infrastructure development', 'Industrial modernization'],
            'regulatory_environment': f'Subject to {country} regulations',
            'investment_trends': 'Moderate growth expected',
            'regional_insights': f'{region} market showing stable demand'
        }
        
        return regional_data
    
    def _create_intelligence_prompt(self, customer_data: Dict, profile_data: Dict) -> str:
        """Create prompt for AI intelligence generation"""
        company_name = profile_data.get('basic_data', {}).get('name', 'Unknown')
        industry = profile_data.get('basic_data', {}).get('company_focus', 'Industrial')
        installed_base = customer_data.get('installed_base', [])

        equipment_counts = {}
        oem_counts = {}
        countries = set()
        startup_years = []
        for eq in installed_base:
            eq_type = str(eq.get('equipment_type', 'Unknown'))
            oem = str(eq.get('manufacturer', 'Unknown'))
            country = str(eq.get('country', '') or eq.get('country_internal', '')).strip()
            startup = eq.get('year_of_startup') or eq.get('start_year') or eq.get('start_year_internal')
            equipment_counts[eq_type] = equipment_counts.get(eq_type, 0) + 1
            oem_counts[oem] = oem_counts.get(oem, 0) + 1
            if country:
                countries.add(country)
            try:
                if startup is not None and str(startup).strip():
                    startup_years.append(int(float(startup)))
            except Exception:
                pass

        equipment_summary = (
            f"Equipment count: {len(installed_base)}\n"
            f"Top equipment types: {', '.join(f'{k} ({v})' for k, v in sorted(equipment_counts.items(), key=lambda kv: kv[1], reverse=True)[:6]) or 'Unknown'}\n"
            f"OEM mix: {', '.join(f'{k} ({v})' for k, v in sorted(oem_counts.items(), key=lambda kv: kv[1], reverse=True)[:6]) or 'Unknown'}\n"
            f"Countries: {', '.join(sorted(countries)) if countries else 'Unknown'}\n"
            f"Oldest startup year: {min(startup_years) if startup_years else 'Unknown'}\n"
            f"Newest startup year: {max(startup_years) if startup_years else 'Unknown'}"
        )

        prompt = f"""Analyze the following company and provide market intelligence for SMS group.

Company: {company_name}
Industry: {industry}
{equipment_summary}

Provide a structured analysis covering the sections below. Avoid generic phrases such as 'well positioned' or 'analysis pending'. Tie each conclusion to specific evidence and explain what it means for SMS group commercially.

1. FINANCIAL HEALTH
Assess financial stability, recent performance trends, debt levels, capex headroom, and investment capacity for modernization or decarbonization.

2. RECENT DEVELOPMENTS  
Highlight significant recent news, projects, expansions, outages, strategic changes, or policy shifts from the past 12-24 months.

3. MARKET POSITION
Analyze competitive position, product-market focus, OEM landscape, and strategic advantages in the steel value chain.

4. STRATEGIC OUTLOOK
Evaluate growth prospects, expansion plans, technology adoption, decarbonization agenda, and likely procurement triggers.

5. RISK ASSESSMENT
Identify business risks including market, operational, technical, energy, and trade-policy risks, then explain the SMS implication.

Provide actionable insights for a sales team in the metallurgical equipment sector. Use steel-process language where relevant (BF/BOF, EAF, caster, hot strip, finishing, energy intensity, yield, maintenance shutdowns)."""

        return prompt
    
    def _parse_intelligence_response(self, content: str) -> Dict[str, str]:
        """Parse AI response into structured format"""
        intel = {
            'financial_health': '',
            'recent_developments': '',
            'market_position': '',
            'strategic_outlook': '',
            'risk_assessment': '',
            'market_size': 'Analysis pending',
            'competitors': [],
            'growth_trends': '',
            'sources': ['AI-generated analysis']
        }
        
        # Simple parsing - split by numbered sections
        sections = content.split('\n\n')
        current_section = None
        
        for section in sections:
            section_lower = section.lower()
            if 'financial health' in section_lower:
                current_section = 'financial_health'
                intel[current_section] = section
            elif 'recent development' in section_lower:
                current_section = 'recent_developments'
                intel[current_section] = section
            elif 'market position' in section_lower:
                current_section = 'market_position'
                intel[current_section] = section
            elif 'strategic outlook' in section_lower:
                current_section = 'strategic_outlook'
                intel[current_section] = section
            elif 'risk assessment' in section_lower:
                current_section = 'risk_assessment'
                intel[current_section] = section
            elif current_section:
                intel[current_section] += '\n\n' + section
        
        return intel
    
    def _generate_fallback_intelligence(self, customer_data: Dict, profile_data: Dict) -> Dict[str, str]:
        """Generate basic intelligence when AI is unavailable"""
        company_name = profile_data.get('basic_data', {}).get('name', 'Unknown Company')
        basic = profile_data.get('basic_data', {})
        installed_base = customer_data.get('installed_base', []) or []
        focus = basic.get('company_focus', 'steel production and downstream processing')
        country = basic.get('hq_address', 'Unknown location')

        equipment_counts = {}
        oem_counts = {}
        ages = []
        for eq in installed_base:
            eq_type = str(eq.get('equipment_type') or eq.get('equipment') or 'Unknown')
            oem = str(eq.get('manufacturer') or eq.get('oem') or 'Unknown')
            year = eq.get('year_of_startup') or eq.get('start_year') or eq.get('start_year_internal')
            equipment_counts[eq_type] = equipment_counts.get(eq_type, 0) + 1
            oem_counts[oem] = oem_counts.get(oem, 0) + 1
            try:
                if year is not None and str(year).strip():
                    ages.append(max(0, datetime.now().year - int(float(year))))
            except Exception:
                pass

        top_equipment = ', '.join(f"{k} ({v})" for k, v in sorted(equipment_counts.items(), key=lambda kv: kv[1], reverse=True)[:4]) or 'no verified equipment classes in the current dataset'
        top_competitors = [oem for oem, _ in sorted(oem_counts.items(), key=lambda kv: kv[1], reverse=True) if oem and oem.lower() not in ('unknown', 'sms group', 'sms')][:4]
        avg_age = round(sum(ages) / len(ages), 1) if ages else None

        financial_health = (
            f"Public, audited financial evidence is limited in the current data package. Working hypothesis: {company_name} appears to have a meaningful operating footprint in {focus}, which usually implies recurring maintenance and periodic capex requirements. "
            f"For SMS, the key issue is not absolute size alone but whether the customer can fund furnace, caster, or rolling-mill modernization within a multi-year investment cycle. "
            f"Before committing to a major capital pursuit, validate EBITDA resilience, leverage, and announced capex priorities against annual reports, filings, or management commentary."
        )

        recent_developments = (
            f"The current dataset does not contain a fully curated recent-events file for {company_name}. However, the installed-base evidence suggests operational relevance around {top_equipment}. "
            f"That means the most material developments to watch are expansion projects, shutdown extensions, decarbonization announcements, power-cost exposure, and OEM change-outs. "
            f"These developments should be monitored through company releases, trade press, and, where available, internal SMS account intelligence."
        )

        market_position = (
            f"{company_name} should be assessed as a process-specific steel customer rather than through generic corporate positioning. The current footprint indicates relevance in {focus}, with verified equipment concentrated in {top_equipment}. "
            f"For SMS, market position matters insofar as it influences investment cadence, product-quality requirements, and appetite for modernization versus life-extension spending. "
            f"The existing OEM mix ({', '.join(top_competitors) if top_competitors else 'limited non-SMS OEM visibility'}) is also important because it shapes switching friction and competitive displacement difficulty."
        )

        strategic_outlook = (
            f"The most plausible strategic path is a combination of productivity, energy-efficiency, and decarbonization upgrades rather than greenfield expansion. "
            f"If the average visible asset age is {avg_age} years, that points to a meaningful probability of phased modernization, especially where yield losses, maintenance intensity, or energy consumption have become commercially material. "
            f"SMS should frame the opportunity around targeted bottleneck removal, digitalization, lifecycle extension where appropriate, and decarbonization-ready equipment packages instead of broad corporate messaging."
        )

        risk_assessment = (
            f"Main risks include weak public financial transparency, uncertain capex timing, incumbent OEM lock-in, and potential mismatch between operational pain points and the current SMS entry point. "
            f"Where installed assets are old, the opportunity is higher but so is execution complexity because outages, brownfield interfaces, and budget approvals become critical. "
            f"A disciplined pursuit should therefore validate asset condition, production bottlenecks, decision-makers, and decarbonization mandates before escalating to full-scope proposals."
        )

        return {
            'financial_health': financial_health,
            'recent_developments': recent_developments,
            'market_position': market_position,
            'strategic_outlook': strategic_outlook,
            'risk_assessment': risk_assessment,
            'market_size': 'Steel market sizing should be derived from the customer product mix, regional steel demand, and disclosed capacity footprint rather than a generic company-level estimate.',
            'competitors': top_competitors,
            'growth_trends': 'Growth should be evaluated through replacement cycles, downstream product demand, energy-price exposure, and decarbonization investment pressure rather than headline volume assumptions.',
            'sources': ['CRM/BCG installed base', 'Derived fallback heuristics']
        }


# Singleton instance
market_intelligence_service = MarketIntelligenceService()
