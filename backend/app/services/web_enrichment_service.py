"""
Web Enrichment Service - Fetch and enrich customer data from external sources
All external data includes source URL for provenance tracking
"""
import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import time
from urllib.parse import urljoin, quote_plus
import logging

logger = logging.getLogger(__name__)


class WebEnrichmentService:
    """Service for enriching customer data with external web sources"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.cache = {}
        self.cache_ttl = timedelta(hours=24)
    
    def get_company_overview(self, company_name: str) -> Dict[str, any]:
        """
        Get company overview from multiple sources
        
        Returns:
            {
                'description': str,
                'source_url': str,
                'headquarters': str,
                'founded': str,
                'industry': str,
                'employee_count': str,
                'last_updated': datetime
            }
        """
        cache_key = f"overview_{company_name}"
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if datetime.now() - timestamp < self.cache_ttl:
                return cached_data
        
        overview = {
            'description': None,
            'source_url': None,
            'headquarters': None,
            'founded': None,
            'industry': None,
            'employee_count': None,
            'last_updated': datetime.now()
        }
        
        try:
            # Try Wikipedia first (free, reliable for large companies)
            wiki_data = self._get_wikipedia_data(company_name)
            if wiki_data:
                overview.update(wiki_data)
        except Exception as e:
            logger.warning(f"Wikipedia lookup failed for {company_name}: {e}")
        
        # Cache the result
        self.cache[cache_key] = (overview, datetime.now())
        return overview
    
    def get_recent_news(self, company_name: str, limit: int = 10) -> List[Dict[str, str]]:
        """
        Get recent news mentions for a company
        
        Returns:
            [
                {
                    'title': str,
                    'description': str,
                    'url': str,
                    'published_date': str,
                    'source': str
                },
                ...
            ]
        """
        cache_key = f"news_{company_name}_{limit}"
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if datetime.now() - timestamp < timedelta(hours=1):  # News cache: 1 hour
                return cached_data
        
        news_items = []
        
        try:
            # Use Google News RSS (free, no API key needed)
            news_items = self._get_google_news(company_name, limit)
        except Exception as e:
            logger.warning(f"News lookup failed for {company_name}: {e}")
        
        # Cache the result
        self.cache[cache_key] = (news_items, datetime.now())
        return news_items
    
    def get_ownership_info(self, company_name: str) -> Dict[str, any]:
        """
        Get ownership and corporate structure information
        
        Returns:
            {
                'parent_company': str,
                'source_url': str,
                'ownership_type': str,  # 'Public', 'Private', 'Subsidiary'
                'stock_ticker': str,
                'shareholders': List[Dict],
                'last_updated': datetime
            }
        """
        ownership = {
            'parent_company': None,
            'source_url': None,
            'ownership_type': 'Unknown',
            'stock_ticker': None,
            'shareholders': [],
            'last_updated': datetime.now()
        }
        
        try:
            # Try to get from Wikipedia infobox
            wiki_data = self._get_wikipedia_data(company_name)
            if wiki_data and wiki_data.get('parent_company'):
                ownership['parent_company'] = wiki_data['parent_company']
                ownership['source_url'] = wiki_data['source_url']
        except Exception as e:
            logger.warning(f"Ownership lookup failed for {company_name}: {e}")
        
        return ownership
    
    def get_related_projects(self, company_name: str) -> List[Dict[str, str]]:
        """
        Get related projects and case studies
        
        Returns:
            [
                {
                    'project_name': str,
                    'description': str,
                    'source_url': str,
                    'date': str,
                    'type': str  # 'Case Study', 'Press Release', 'Project', etc.
                },
                ...
            ]
        """
        projects = []
        
        try:
            # Search for project-related news and press releases
            search_query = f'"{company_name}" (project OR contract OR deal OR partnership)'
            projects = self._search_web_for_projects(search_query)
        except Exception as e:
            logger.warning(f"Project lookup failed for {company_name}: {e}")
        
        return projects
    
    # Private helper methods
    
    def _get_wikipedia_data(self, company_name: str) -> Optional[Dict]:
        """Extract company data from Wikipedia"""
        try:
            # Wikipedia API for search
            search_url = f"https://en.wikipedia.org/w/api.php"
            search_params = {
                'action': 'opensearch',
                'search': company_name,
                'limit': 1,
                'format': 'json'
            }
            
            response = self.session.get(search_url, params=search_params, timeout=5)
            if response.status_code != 200:
                return None
            
            search_results = response.json()
            if not search_results[1]:  # No results
                return None
            
            page_title = search_results[1][0]
            page_url = search_results[3][0]
            
            # Get page content
            content_params = {
                'action': 'parse',
                'page': page_title,
                'format': 'json',
                'prop': 'text'
            }
            
            content_response = self.session.get(search_url, params=content_params, timeout=5)
            if content_response.status_code != 200:
                return None
            
            page_data = content_response.json()
            html_content = page_data.get('parse', {}).get('text', {}).get('*', '')
            
            if not html_content:
                return None
            
            # Parse the infobox
            soup = BeautifulSoup(html_content, 'html.parser')
            infobox = soup.find('table', {'class': 'infobox'})
            
            result = {
                'source_url': page_url,
                'description': None,
                'headquarters': None,
                'founded': None,
                'industry': None,
                'employee_count': None,
                'parent_company': None
            }
            
            if infobox:
                # Extract first paragraph as description
                first_para = soup.find('p', recursive=False)
                if first_para:
                    result['description'] = first_para.get_text().strip()
                
                # Parse infobox rows
                for row in infobox.find_all('tr'):
                    header = row.find('th')
                    data = row.find('td')
                    
                    if not header or not data:
                        continue
                    
                    header_text = header.get_text().strip().lower()
                    data_text = data.get_text().strip()
                    
                    if 'headquarter' in header_text:
                        result['headquarters'] = data_text
                    elif 'founded' in header_text:
                        result['founded'] = data_text
                    elif 'industry' in header_text or 'industries' in header_text:
                        result['industry'] = data_text
                    elif 'employee' in header_text:
                        result['employee_count'] = data_text
                    elif 'parent' in header_text:
                        result['parent_company'] = data_text
            
            return result
            
        except Exception as e:
            logger.error(f"Wikipedia extraction error for {company_name}: {e}")
            return None
    
    def _get_google_news(self, company_name: str, limit: int = 10) -> List[Dict]:
        """Get news from Google News RSS"""
        news_items = []
        
        try:
            # Google News RSS feed
            query = quote_plus(company_name)
            rss_url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
            
            response = self.session.get(rss_url, timeout=10)
            if response.status_code != 200:
                return news_items
            
            soup = BeautifulSoup(response.content, 'xml')
            items = soup.find_all('item', limit=limit)
            
            for item in items:
                title = item.find('title')
                link = item.find('link')
                pub_date = item.find('pubDate')
                description = item.find('description')
                source = item.find('source')
                
                desc_text = ''
                if description and description.text:
                    try:
                        soup_desc = BeautifulSoup(description.text, 'html.parser')
                        desc_text = soup_desc.get_text(separator=' ', strip=True)
                    except:
                        desc_text = description.text
                
                news_items.append({
                    'title': title.text if title else 'No title',
                    'description': desc_text,
                    'url': link.text if link else '',
                    'published_date': pub_date.text if pub_date else '',
                    'source': source.text if source else 'Google News'
                })
            
        except Exception as e:
            logger.error(f"Google News fetch error for {company_name}: {e}")
        
        return news_items
    
    def get_country_intelligence(self, country: str) -> dict:
        """
        Fetch country-level intelligence relevant to the steel industry.

        Returns a dict with:
            steel_news          – list of news items about steel in the country
            economic_developments – list of economic/macro news items
            tariffs_trade       – list of tariff/trade news items
            automotive_trends   – list of automotive industry news items
            other_macro         – list of other macro/sector news items
            summary_text        – short AI-friendly summary string
        """
        if not country or country.lower() == "all":
            country = "global"

        cache_key = f"country_intel_{country}"
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if datetime.now() - timestamp < timedelta(hours=3):
                return cached_data

        def _fetch(query: str, limit: int = 5) -> List[Dict]:
            try:
                return self._get_google_news(query, limit)
            except Exception as e:
                logger.warning(f"Country intel news fetch failed for '{query}': {e}")
                return []

        base = country if country.lower() != "global" else ""
        prefix = f"{base} " if base else ""

        steel_news          = _fetch(f"{prefix}steel industry market", 6)
        economic_news       = _fetch(f"{prefix}economy GDP industrial output", 4)
        tariffs_trade_news  = _fetch(f"{prefix}steel tariffs trade policy", 4)
        automotive_news     = _fetch(f"{prefix}automotive steel demand", 4)
        other_macro_news    = _fetch(f"{prefix}infrastructure investment manufacturing", 4)

        result = {
            "country": country,
            "steel_news": steel_news,
            "economic_developments": economic_news,
            "tariffs_trade": tariffs_trade_news,
            "automotive_trends": automotive_news,
            "other_macro": other_macro_news,
            "retrieved_at": datetime.now().isoformat(),
        }

        self.cache[cache_key] = (result, datetime.now())
        return result

    def get_dashboard_news(self, company: str, country: str, region: str, limit: int = 15) -> List[Dict]:
        """Fetch and aggregate news for dashboard based on active filters"""
        from email.utils import parsedate_to_datetime
        
        queries = []
        if company and company.lower() not in ("all", "unknown", "none"):
            queries.append(f'"{company}" AND (steel OR market OR corporate OR business)')
        if country and country.lower() not in ("all", "unknown", "none"):
            queries.append(f'"{country}" AND (steel OR economy OR manufacturing)')
        if region and region.lower() not in ("all", "unknown", "none", "global"):
            queries.append(f'"{region}" AND steel industry')
            
        if not queries:
            queries.append("global steel industry market")
            
        all_news = []
        seen_urls = set()
        
        for q in queries:
            try:
                # Append 12 month time constraint
                rss_query = f"{q} when:12m"
                items = self._get_google_news(rss_query, limit=limit)
                for item in items:
                    url = item.get('url')
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        pub_str = item.get('published_date', '')
                        try:
                            # Parse standard RFC 2822 dates from RSS
                            dt = parsedate_to_datetime(pub_str)
                            # Remove timezone info so we can sort properly
                            item['dt'] = dt.replace(tzinfo=None)
                        except Exception:
                            item['dt'] = datetime.min
                        all_news.append(item)
            except Exception as e:
                logger.warning(f"Dashboard news fetch failed for '{q}': {e}")
                
        # Sort by datetime descending
        all_news.sort(key=lambda x: x.get('dt', datetime.min), reverse=True)
        return all_news[:limit]

    def _search_web_for_projects(self, search_query: str, limit: int = 5) -> List[Dict]:
        """Search web for project-related information"""
        # Mock implementation - in production, would use a search API
        # For now, return empty list and rely on CRM data
        return []
    
    def clear_cache(self):
        """Clear the cache"""
        self.cache.clear()


# Singleton instance
web_enrichment_service = WebEnrichmentService()
