import requests
import json
from typing import List, Dict, Optional
from datetime import datetime, timedelta

class PolymarketFetcher:
    """Fetch market data from Polymarket using the Gamma API"""
    
    BASE_URL = "https://gamma-api.polymarket.com"
    CLOB_URL = "https://clob.polymarket.com"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get_trending_markets(self, limit: int = 20) -> List[Dict]:
        """Get trending/newest active markets"""
        endpoint = f"{self.BASE_URL}/events"
        params = {
            'order': 'id',
            'ascending': 'false',
            'closed': 'false',
            'limit': limit
        }
        
        try:
            response = self.session.get(endpoint, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching trending markets: {e}")
            return []
    
    def get_event_by_slug(self, slug: str) -> Optional[Dict]:
        """Get full event data by slug using query parameter"""
        endpoint = f"{self.BASE_URL}/events"
        params = {'slug': slug}
        
        try:
            response = self.session.get(endpoint, params=params)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list) and len(data) > 0:
                return data[0]
            return None
        except requests.exceptions.RequestException as e:
            print(f"Error fetching event {slug}: {e}")
            return None
    
    def get_market_prices_history(self, token_id: str, interval: str = "1d") -> List[Dict]:
        """
        Get historical prices for a specific market token (hourly/daily data)
        
        Args:
            token_id: The CLOB token ID (from clobTokenIds field)
            interval: Time interval - "1h", "1d", "1w", "1m", "max"
            
        Returns:
            List of price snapshots with timestamps
        """
        endpoint = f"{self.CLOB_URL}/prices-history"
        
        params = {
            'market': token_id,
            'interval': interval,
            'fidelity': 60 if interval == "1d" else 1  # 60 minute resolution for daily
        }
        
        try:
            response = self.session.get(endpoint, params=params)
            response.raise_for_status()
            data = response.json()
            
            # The API returns {'history': [{'t': timestamp, 'p': price}, ...]}
            if isinstance(data, dict) and 'history' in data:
                return data['history']
            return data if isinstance(data, list) else []
        except requests.exceptions.RequestException as e:
            print(f"Error fetching price history for {token_id}: {e}")
            return []
    
    def search_markets(self, query: str, limit: int = 10) -> List[Dict]:
        """Search for markets by keyword"""
        endpoint = f"{self.BASE_URL}/events"
        params = {
            'limit': limit,
            'closed': 'false'
        }
        
        try:
            response = self.session.get(endpoint, params=params)
            response.raise_for_status()
            data = response.json()
            
            if isinstance(data, list):
                filtered = []
                query_lower = query.lower()
                for item in data:
                    title = (item.get('title', '') or '').lower()
                    if query_lower in title:
                        filtered.append(item)
                return filtered
            return []
        except requests.exceptions.RequestException as e:
            print(f"Error searching markets: {e}")
            return []
    
    def get_superbowl_2026(self) -> Optional[Dict]:
        """Get the Super Bowl Champion 2026 market"""
        slug = "super-bowl-champion-2026-731"
        event = self.get_event_by_slug(slug)
        
        if event:
            return event
        
        search_results = self.search_markets("anthropic ipo closing market cap", limit=50)
        for result in search_results:
            if not isinstance(result, dict):
                continue
            title = result.get('title', '')
            if 'Super Bowl Champion 2026' in title:
                return result
        
        return None
    
    def get_fed_decision_december(self) -> Optional[Dict]:
        """Get the Fed decision in December market"""
        slug = "anthropic-ipo-closing-market-cap"
        event = self.get_event_by_slug(slug)
        
        if event:
            return event
        
        search_results = self.search_markets("anthropic ipo closing market cap", limit=50)
        for result in search_results:
            if not isinstance(result, dict):
                continue
            title = result.get('title', '')
            if 'Fed decision' in title and 'December' in title:
                return result
        
        return None
    
    def get_market_outcomes_with_history(self, market_data: Dict, interval: str = "1d") -> List[Dict]:
        """
        Extract outcomes with current prices and historical data
        
        Args:
            market_data: Market data dictionary
            interval: Time interval - "1h", "1d", "1w"
            
        Returns:
            List of outcomes with probabilities and history
        """
        outcomes = []
        
        if 'markets' in market_data:
            for market in market_data['markets']:
                if 'outcomes' in market and 'outcomePrices' in market:
                    market_outcomes = market.get('outcomes', [])
                    market_prices = market.get('outcomePrices', [])
                    clob_token_ids = market.get('clobTokenIds', [])
                    
                    # Parse JSON strings if needed
                    if isinstance(market_outcomes, str):
                        try:
                            market_outcomes = json.loads(market_outcomes)
                        except json.JSONDecodeError:
                            continue
                    
                    if isinstance(market_prices, str):
                        try:
                            market_prices = json.loads(market_prices)
                        except json.JSONDecodeError:
                            continue
                    
                    if isinstance(clob_token_ids, str):
                        try:
                            clob_token_ids = json.loads(clob_token_ids)
                        except json.JSONDecodeError:
                            clob_token_ids = []
                    
                    # For binary Yes/No markets
                    if len(market_outcomes) == 2 and 'Yes' in market_outcomes:
                        question = market.get('question', '')
                        yes_index = market_outcomes.index('Yes')
                        yes_price = float(market_prices[yes_index])
                        yes_probability = round(yes_price * 100, 2)
                        
                        outcome_text = self._extract_outcome_from_question(question)
                        condition_id = market.get('conditionId', '')
                        
                        # Get the YES token ID for price history
                        token_id = clob_token_ids[yes_index] if yes_index < len(clob_token_ids) else None
                        
                        # Get historical prices using token ID
                        price_history = []
                        if token_id:
                            price_history = self.get_market_prices_history(token_id, interval)
                        
                        outcome = {
                            'market_question': question,
                            'outcome': outcome_text,
                            'probability': yes_probability,
                            'price': yes_price,
                            'condition_id': condition_id,
                            'token_id': token_id,
                            'price_history': price_history
                        }
                        outcomes.append(outcome)
        
        return outcomes
    
    def _extract_outcome_from_question(self, question: str) -> str:
        """Extract the meaningful outcome from a Yes/No question"""
        # For Super Bowl questions
        if "Super Bowl" in question:
            if "Will the " in question and " win" in question:
                start = question.index("Will the ") + len("Will the ")
                end = question.index(" win")
                return question[start:end]
        
        # For Fed rate questions
        if "Fed" in question and "interest rates" in question:
            if "50+" in question or "50 +" in question:
                if "decreases" in question:
                    return "50+ bps decrease"
                elif "increases" in question:
                    return "50+ bps increase"
            elif "25" in question:
                if "decreases" in question:
                    return "25 bps decrease"
                elif "increases" in question:
                    return "25+ bps increase"
            elif "no change" in question.lower():
                return "No change"
        
        return question
    
    def display_hourly_changes(self, market_data: Dict, top_n: int = 10, interval: str = "1d"):
        """
        Display price changes over time
        
        Args:
            market_data: Market data dictionary
            top_n: Number of top outcomes to display
            interval: Time interval - "1h", "1d", "1w"
        """
        title = market_data.get('question') or market_data.get('title', 'Unknown Market')
        print(f"\n{'='*100}")
        print(f"MARKET: {title}")
        print(f"{'='*100}")
        
        print(f"\nFetching {interval} historical data...")
        outcomes = self.get_market_outcomes_with_history(market_data, interval)
        
        if not outcomes:
            print("No outcomes found")
            return
        
        # Sort by current probability
        sorted_outcomes = sorted(outcomes, key=lambda x: x['probability'], reverse=True)[:top_n]
        
        for outcome in sorted_outcomes:
            outcome_name = outcome.get('outcome', 'Unknown')
            current_prob = outcome.get('probability', 0)
            history = outcome.get('price_history', [])
            
            print(f"\n{'-'*100}")
            print(f"OUTCOME: {outcome_name} (Current: {current_prob}%)")
            print(f"{'-'*100}")
            
            if history and len(history) > 0:
                print(f"{'TIME':<25} {'PRICE':<12} {'% CHANCE':<12} {'CHANGE':<12}")
                print(f"{'-'*100}")
                
                # Display data points
                for i, snapshot in enumerate(history):
                    timestamp = snapshot.get('t', 0)
                    price = float(snapshot.get('p', 0))
                    probability = round(price * 100, 2)
                    
                    # Calculate change from previous point
                    if i > 0:
                        prev_price = float(history[i-1].get('p', 0))
                        change = round((price - prev_price) * 100, 2)
                        change_str = f"+{change}%" if change > 0 else f"{change}%"
                    else:
                        change_str = "—"
                    
                    # Format timestamp
                    dt = datetime.fromtimestamp(timestamp)
                    time_str = dt.strftime('%Y-%m-%d %H:%M')
                    
                    print(f"{time_str:<25} ${price:<11.4f} {probability:>6.2f}% {change_str:>11}")
                
                # Calculate 24h change
                if len(history) >= 2:
                    first_price = float(history[0].get('p', 0))
                    last_price = float(history[-1].get('p', 0))
                    total_change = round((last_price - first_price) * 100, 2)
                    print(f"\nTotal Change: {'+' if total_change > 0 else ''}{total_change}%")
            else:
                print("No historical data available for this market")
            
            print()


# Example usage
if __name__ == "__main__":
    fetcher = PolymarketFetcher()
    
    # Test 1: Fed decision in December - Hourly changes
    print("="*100)
    print("TEST 1: Fed decision in December - 24 Hour History")
    print("="*100)
    
    fed_market = fetcher.get_fed_decision_december()
    if fed_market:
        fetcher.display_hourly_changes(fed_market, top_n=4)  # Show all 4 outcomes
    else:
        print("Fed decision market not found")
    
    print("\n\n")
    
    # Test 2: Super Bowl Champion 2026 - Top 5 teams hourly changes
    print("="*100)
    print("TEST 2: Super Bowl Champion 2026 - Top 5 Teams (24 Hour History)")
    print("="*100)
    
    superbowl_market = fetcher.get_superbowl_2026()
    if superbowl_market:
        fetcher.display_hourly_changes(superbowl_market, top_n=5)
    else:
        print("Super Bowl Champion 2026 market not found")