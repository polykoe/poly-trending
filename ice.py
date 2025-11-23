import requests
import json
from typing import List, Dict, Optional
from datetime import datetime


class PolymarketTrendingFetcher:
    """Fetch trending markets and events from Polymarket Gamma API"""
    
    BASE_URL = "https://gamma-api.polymarket.com"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
        })
    
    def get_trending_events(
        self, 
        limit: int = 20,
        sort_by: str = "volume",
        use_24hr_volume: bool = False
    ) -> List[Dict]:
        """
        Get trending EVENTS (like homepage) sorted by volume
        
        Args:
            limit: Number of events to return
            sort_by: Field to sort by (volume for total, volume24hr for 24hr)
            use_24hr_volume: If True, sort by 24hr volume instead of total
            
        Returns:
            List of event dictionaries
        """
        endpoint = f"{self.BASE_URL}/events"
        
        if use_24hr_volume:
            sort_by = "volume24hr"
        
        params = {
            'closed': 'false',
            'active': 'true',
            'limit': limit,
            'order': sort_by,
            'ascending': 'false'
        }
        
        try:
            response = self.session.get(endpoint, params=params)
            response.raise_for_status()
            events = response.json()
            
            # Filter and enrich data with safe handling
            trending = []
            for event in events:
                # Safely extract and convert volume data
                volume_total = self._safe_float(event.get('volume', 0))
                volume_24hr = self._safe_float(event.get('volume24hr', 0))
                liquidity = self._safe_float(event.get('liquidity', 0))
                
                event_data = {
                    'id': event.get('id'),
                    'title': event.get('title'),
                    'slug': event.get('slug'),
                    'url': f"https://polymarket.com/event/{event.get('slug')}" if event.get('slug') else None,
                    'volume_total': volume_total,
                    'volume_24hr': volume_24hr,
                    'liquidity': liquidity,
                    'description': event.get('description'),
                    'end_date': event.get('endDate'),
                    'category': event.get('category'),
                    'market_count': len(event.get('markets', [])),
                    'tags': [tag.get('label', '') for tag in event.get('tags', []) if tag.get('label')],
                }
                trending.append(event_data)
            
            return trending
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching events: {e}")
            return []
        except Exception as e:
            print(f"Unexpected error: {e}")
            return []
    
    def get_trending_markets(
        self, 
        limit: int = 20,
        sort_by: str = "volumeNum",
        min_volume: Optional[float] = None,
        use_24hr_volume: bool = False
    ) -> List[Dict]:
        """
        Get trending individual markets sorted by volume
        
        Args:
            limit: Number of markets to return
            sort_by: Field to sort by (volumeNum for total, volume24hr for 24hr)
            min_volume: Minimum volume threshold
            use_24hr_volume: If True, sort by 24hr volume instead of total
            
        Returns:
            List of market dictionaries
        """
        endpoint = f"{self.BASE_URL}/markets"
        
        if use_24hr_volume:
            sort_by = "volume24hr"
        
        params = {
            'closed': 'false',
            'active': 'true',
            'limit': limit,
            'order': sort_by,
            'ascending': 'false'
        }
        
        if min_volume:
            params['volume_num_min'] = min_volume
        
        try:
            response = self.session.get(endpoint, params=params)
            response.raise_for_status()
            markets = response.json()
            
            # Filter and enrich data with safe handling
            trending = []
            for market in markets:
                # Safely extract and convert volume data
                volume_total = self._safe_float(market.get('volumeNum') or market.get('volume', 0))
                volume_24hr = self._safe_float(market.get('volume24hr', 0))
                liquidity = self._safe_float(market.get('liquidityNum', 0))
                
                market_data = {
                    'id': market.get('id'),
                    'question': market.get('question'),
                    'slug': market.get('slug'),
                    'url': f"https://polymarket.com/event/{market.get('slug')}" if market.get('slug') else None,
                    'volume_total': volume_total,
                    'volume_24hr': volume_24hr,
                    'liquidity': liquidity,
                    'last_trade_price': market.get('lastTradePrice'),
                    'outcomes': market.get('outcomes'),
                    'outcome_prices': market.get('outcomePrices'),
                    'end_date': market.get('endDate'),
                    'category': market.get('category'),
                    'tags': [tag.get('label', '') for tag in market.get('tags', []) if tag.get('label')],
                }
                trending.append(market_data)
            
            return trending
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching markets: {e}")
            return []
        except Exception as e:
            print(f"Unexpected error: {e}")
            return []
    
    def _safe_float(self, value) -> float:
        """Safely convert value to float"""
        if value is None:
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except (ValueError, TypeError):
                return 0.0
        return 0.0
    
    def get_trending_by_tag(
        self, 
        tag_id: int,
        limit: int = 10
    ) -> List[Dict]:
        """
        Get trending events filtered by tag
        
        Args:
            tag_id: Tag ID to filter by
            limit: Number of events to return
            
        Returns:
            List of event dictionaries
        """
        endpoint = f"{self.BASE_URL}/events"
        
        params = {
            'tag_id': tag_id,
            'closed': 'false',
            'active': 'true',
            'limit': limit,
            'order': 'volume',
            'ascending': 'false'
        }
        
        try:
            response = self.session.get(endpoint, params=params)
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching events by tag: {e}")
            return []
    
    def search_markets(self, query: str, limit: int = 10) -> Dict:
        """
        Search for markets by keyword
        
        Args:
            query: Search query string
            limit: Results per type
            
        Returns:
            Dictionary with events, tags, and profiles
        """
        endpoint = f"{self.BASE_URL}/public-search"
        
        params = {
            'q': query,
            'limit_per_type': limit,
            'events_status': 'active'
        }
        
        try:
            response = self.session.get(endpoint, params=params)
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"Error searching markets: {e}")
            return {}
    
    def get_event_by_slug(self, slug: str) -> Optional[Dict]:
        """
        Get detailed event information by slug
        
        Args:
            slug: Event slug from URL
            
        Returns:
            Event dictionary or None
        """
        endpoint = f"{self.BASE_URL}/events/slug/{slug}"
        
        try:
            response = self.session.get(endpoint)
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching event by slug: {e}")
            return None
    
    def format_event_summary(self, event: Dict) -> str:
        """Format event data for display"""
        volume_total = event.get('volume_total', 0) or 0
        volume_24hr = event.get('volume_24hr', 0) or 0
        liquidity = event.get('liquidity', 0) or 0
        market_count = event.get('market_count', 0)
        
        summary = f"""
{'='*70}
{event.get('title', 'N/A')}
{'='*70}
URL: {event.get('url', 'N/A')}
Total Volume: ${volume_total:,.2f}
24hr Volume: ${volume_24hr:,.2f}
Liquidity: ${liquidity:,.2f}
Number of Markets: {market_count}
Category: {event.get('category', 'N/A')}
Tags: {', '.join(event.get('tags', [])) or 'None'}
End Date: {event.get('end_date', 'N/A')}
{'='*70}
"""
        return summary


def main():
    """Example usage"""
    fetcher = PolymarketTrendingFetcher()
    
    # Get top 10 trending EVENTS (like homepage)
    print("🔥 TOP TRENDING EVENTS (by total volume - EXACTLY like homepage)\n")
    trending_events = fetcher.get_trending_events(limit=10)
    
    for i, event in enumerate(trending_events, 1):
        vol_total = event.get('volume_total', 0)
        vol_24hr = event.get('volume_24hr', 0)
        market_count = event.get('market_count', 0)
        
        print(f"{i}. {event.get('title', 'N/A')}")
        print(f"   Total Volume: ${vol_total:,.2f}")
        print(f"   24hr Volume: ${vol_24hr:,.2f}")
        print(f"   Markets: {market_count}")
        print(f"   URL: {event.get('url', 'N/A')}")
        print()
    
    # Get events trending in last 24 hours
    print("\n🔥 HOT EVENTS IN LAST 24 HOURS (by 24hr volume)\n")
    hot_24hr = fetcher.get_trending_events(limit=5, use_24hr_volume=True)
    
    for i, event in enumerate(hot_24hr, 1):
        vol_24hr = event.get('volume_24hr', 0)
        
        print(f"{i}. {event.get('title', 'N/A')}")
        print(f"   24hr Volume: ${vol_24hr:,.2f}")
        print(f"   URL: {event.get('url', 'N/A')}")
        print()
    
    # Get trending individual markets
    print("\n📊 TOP TRENDING INDIVIDUAL MARKETS\n")
    trending_markets = fetcher.get_trending_markets(limit=5)
    
    for i, market in enumerate(trending_markets, 1):
        vol_total = market.get('volume_total', 0)
        
        print(f"{i}. {market.get('question', 'N/A')}")
        print(f"   Total Volume: ${vol_total:,.2f}")
        print(f"   URL: {market.get('url', 'N/A')}")
        print()
    
    # Search for specific topic
    print("\n🔍 SEARCH: 'election'\n")
    search_results = fetcher.search_markets('election', limit=5)
    
    if search_results.get('events'):
        for event in search_results['events'][:3]:
            print(f"- {event.get('title', 'N/A')}")
    
    # Get specific event details
    print("\n📊 DETAILED EVENT INFO (Top Trending)\n")
    if trending_events and len(trending_events) > 0:
        print(fetcher.format_event_summary(trending_events[0]))


if __name__ == "__main__":
    main()