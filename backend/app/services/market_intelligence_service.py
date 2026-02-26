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
        
        equipment_summary = f"Equipment count: {len(installed_base)}"
        if installed_base:
            types = [eq.get('equipment_type', 'Unknown') for eq in installed_base[:5]]
            equipment_summary += f", Types: {', '.join(types)}"
        
        prompt = f"""Analyze the following company and provide market intelligence:

Company: {company_name}
Industry: {industry}
{equipment_summary}

Provide a structured analysis covering:

1. FINANCIAL HEALTH
Assess financial stability, recent performance trends, debt levels, and investment capacity.

2. RECENT DEVELOPMENTS  
Highlight any significant recent news, projects, expansions, or strategic changes from the past 12-24 months.

3. MARKET POSITION
Analyze their competitive position, market share indicators, and strategic advantages.

4. STRATEGIC OUTLOOK
Evaluate future growth prospects, expansion plans, technology adoption, and sustainability initiatives.

5. RISK ASSESSMENT
Identify key business risks including market risks, operational risks, and external factors.

Provide actionable insights for a sales team in the metallurgical equipment sector."""

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
        
        return {
            'financial_health': f'{company_name} operates in the industrial sector. Detailed financial analysis requires external data sources.',
            'recent_developments': 'Recent developments tracking requires integration with news APIs and press release monitoring.',
            'market_position': f'{company_name} is an established player in their market segment. Detailed competitive analysis pending.',
            'strategic_outlook': 'Strategic outlook analysis requires current market data and industry trends.',
            'risk_assessment': 'Standard industry risks apply: market volatility, technological change, regulatory compliance.',
            'market_size': 'Market size analysis pending',
            'competitors': [],
            'growth_trends': 'Growth trend analysis requires historical market data',
            'sources': ['CRM data']
        }


# Singleton instance
market_intelligence_service = MarketIntelligenceService()
