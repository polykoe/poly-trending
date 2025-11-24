# ============================================
# backend.py - Flask Backend for Events Only
# FIXED: Now returns ALL markets, not just 5
# ============================================

from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import json
import threading
import time
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# Global variables
cached_events = []
last_update = 0
UPDATE_INTERVAL = 300

# Configuration
gamma_api_url = "https://gamma-api.polymarket.com"
clob_api_url = "https://clob.polymarket.com"


def get_all_trending_events():
    """Get ALL trending EVENTS by fetching multiple pages"""
    try:
        all_events = []
        offset = 0
        limit = 100
        
        print("Starting to fetch all events...")
        
        while True:
            url = "https://gamma-api.polymarket.com/events"
            params = {
                "active": True,
                "closed": False,
                "limit": limit,
                "offset": offset,
                "order": "volume",
                "ascending": False
            }
            
            try:
                response = requests.get(url, params=params, timeout=15)
                response.raise_for_status()
                batch = response.json()
                
                if not batch or len(batch) == 0:
                    break
                
                print(f"Fetched {len(batch)} events at offset {offset}")
                all_events.extend(batch)
                
                if len(batch) < limit:
                    break
                
                offset += limit
                
                if offset >= 10000:
                    break
                
                time.sleep(0.1)
                
            except Exception as e:
                print(f"Error fetching batch at offset {offset}: {e}")
                break
        
        formatted_events = []
        
        for i, event in enumerate(all_events, 1):
            tags_list = event.get('tags', [])
            markets = event.get('markets', [])
            
            volume = event.get('volume', 0)
            if isinstance(volume, str):
                try:
                    volume = float(volume)
                except (ValueError, TypeError):
                    volume = 0
            
            volume_24hr = event.get('volume24hr', 0)
            if isinstance(volume_24hr, str):
                try:
                    volume_24hr = float(volume_24hr)
                except (ValueError, TypeError):
                    volume_24hr = 0
            
            liquidity = event.get('liquidity', 0)
            if isinstance(liquidity, str):
                try:
                    liquidity = float(liquidity)
                except (ValueError, TypeError):
                    liquidity = 0
            
            formatted_event = {
                'rank': i,
                'id': event.get('id'),
                'title': event.get('title'),
                'slug': event.get('slug'),
                'link': f"https://polymarket.com/event/{event.get('slug')}",
                'image': event.get('image') or event.get('icon') or 'https://via.placeholder.com/150',
                'tags': [
                    {
                        'id': tag.get('id'),
                        'label': tag.get('label'),
                        'slug': tag.get('slug')
                    }
                    for tag in tags_list
                ],
                'tag_labels': [tag.get('label') for tag in tags_list],
                'volume': volume,
                'volume_24hr': volume_24hr,
                'liquidity': liquidity,
                'description': event.get('description', ''),
                'end_date': event.get('endDate'),
                'market_count': len(markets),
                'category': event.get('category'),
                # ✅ FIXED: Return ALL markets, not just first 5
                # Also ensure each market includes its image/icon
                'markets': [
                    {
                        **market,
                        'image': market.get('image') or market.get('icon') or event.get('image') or event.get('icon'),
                    }
                    for market in markets
                ]  # Returns all markets now with images!
            }
            
            formatted_events.append(formatted_event)
        
        print(f"✓ Total events fetched and formatted: {len(formatted_events)}")
        return formatted_events
    
    except Exception as e:
        print(f"Error fetching events: {e}")
        return []


def update_events_background():
    global cached_events, last_update
    
    while True:
        try:
            print("\n" + "="*60)
            print("Fetching latest events data...")
            events = get_all_trending_events()
            
            if events:
                cached_events = events
                last_update = time.time()
                print(f"✓ Updated {len(events)} events at {time.ctime()}")
                print("="*60 + "\n")
            else:
                print("⚠ No events fetched, keeping cached data")
        
        except Exception as e:
            print(f"Error in background update: {e}")
        
        time.sleep(UPDATE_INTERVAL)


# ============================================
# API Endpoints
# ============================================

@app.route('/api/events', methods=['GET'])
def get_events():
    return jsonify({
        'success': True,
        'data': cached_events,
        'count': len(cached_events),
        'last_update': last_update,
        'timestamp': time.time()
    })


@app.route('/api/events/featured', methods=['GET'])
def get_featured_event():
    if cached_events:
        return jsonify({
            'success': True,
            'data': cached_events[0],
            'timestamp': time.time()
        })
    else:
        return jsonify({
            'success': False,
            'error': 'No events available',
            'timestamp': time.time()
        }), 404


@app.route('/api/events/remaining', methods=['GET'])
def get_remaining_events():
    if len(cached_events) > 1:
        return jsonify({
            'success': True,
            'data': cached_events[1:],
            'count': len(cached_events) - 1,
            'timestamp': time.time()
        })
    else:
        return jsonify({
            'success': False,
            'error': 'Not enough events available',
            'timestamp': time.time()
        }), 404


@app.route('/api/markets/paginated', methods=['GET'])
def get_paginated_markets():
    try:
        offset = int(request.args.get('offset', 0))
        limit = int(request.args.get('limit', 100))
        
        if offset < 0:
            offset = 0
        if limit < 1 or limit > 500:
            limit = 100
        
        start_idx = offset
        end_idx = offset + limit
        
        paginated_events = cached_events[start_idx:end_idx]
        has_more = end_idx < len(cached_events)
        
        return jsonify({
            'success': True,
            'data': paginated_events,
            'count': len(paginated_events),
            'offset': offset,
            'limit': limit,
            'total': len(cached_events),
            'has_more': has_more,
            'timestamp': time.time()
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': time.time()
        }), 500


@app.route('/api/market/<slug>/chart', methods=['GET'])
def get_market_chart(slug):
    """Get chart data with ALL outcomes and their probabilities"""
    try:
        events_endpoint = f"https://gamma-api.polymarket.com/events/slug/{slug}"
        response = requests.get(events_endpoint, timeout=10)
        
        if response.status_code != 200:
            return jsonify({'success': False, 'error': 'Event not found'}), 404
        
        event = response.json()
        markets = event.get('markets', [])
        
        if not markets:
            return jsonify({'success': False, 'error': 'No markets found'}), 404
        
        market = markets[0]
        
        outcomes = market.get('outcomes', [])
        outcome_prices_raw = market.get('outcomePrices', [])
        
        outcome_prices = []
        if isinstance(outcome_prices_raw, str):
            try:
                outcome_prices = json.loads(outcome_prices_raw)
            except json.JSONDecodeError:
                outcome_prices = []
        elif isinstance(outcome_prices_raw, list):
            outcome_prices = outcome_prices_raw
        
        clob_token_ids_raw = market.get('clobTokenIds')
        clob_token_ids = []
        
        if isinstance(clob_token_ids_raw, str):
            try:
                clob_token_ids = json.loads(clob_token_ids_raw)
            except json.JSONDecodeError:
                pass
        elif isinstance(clob_token_ids_raw, list):
            clob_token_ids = clob_token_ids_raw
        
        if not clob_token_ids:
            return jsonify({
                'success': False,
                'error': 'No token IDs found'
            }), 404
        
        timeframe = request.args.get('timeframe', 'ALL')
        interval_map = {
            '1H': '1h',
            '6H': '6h',
            '1D': '1d',
            '1W': '7d',
            '1M': '30d',
            'ALL': 'max'
        }
        interval = interval_map.get(timeframe, 'max')
        
        all_outcomes_data = []
        
        for idx, token_id in enumerate(clob_token_ids):
            outcome_name = outcomes[idx] if idx < len(outcomes) else f"Outcome {idx+1}"
            
            clob_url = "https://clob.polymarket.com/prices-history"
            params = {'market': token_id, 'interval': interval, 'fidelity': 100}
            
            try:
                chart_response = requests.get(clob_url, params=params, timeout=10)
                
                if chart_response.status_code == 200:
                    chart_data = chart_response.json()
                    history = chart_data.get('history', [])
                    
                    all_outcomes_data.append({
                        'outcome': outcome_name,
                        'tokenId': token_id,
                        'history': history,
                        'currentPrice': outcome_prices[idx] if idx < len(outcome_prices) else None
                    })
                    
            except Exception as e:
                print(f"Error fetching chart for {outcome_name}: {e}")
        
        return jsonify({
            'success': True,
            'outcomes': all_outcomes_data,
            'market': {
                'title': market.get('question'),
                'outcomes': outcomes,
                'outcomePrices': outcome_prices
            }
        })
    
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/market/<slug>', methods=['GET'])
def get_market_by_slug(slug):
    """Get detailed information about a specific market by slug"""
    try:
        # First check if it's in our cached events
        market_from_cache = next((event for event in cached_events if event.get('slug') == slug), None)
        
        if market_from_cache:
            print(f"✅ Found '{slug}' in cache with {len(market_from_cache.get('markets', []))} markets")
            return jsonify({
                'success': True,
                'data': market_from_cache,
                'source': 'cache',
                'timestamp': time.time()
            })
        
        # If not in cache, fetch from Polymarket API
        print(f"\n{'='*60}")
        print(f"Fetching market details for slug: {slug}")
        print('='*60)
        
        # Fetch from Polymarket Gamma API
        gamma_response = requests.get(
            f"{gamma_api_url}/events",
            params={'slug': slug},
            timeout=10
        )
        
        if gamma_response.status_code != 200:
            print(f"❌ Event not found: {gamma_response.status_code}")
            return jsonify({
                'success': False,
                'error': 'Market not found',
                'timestamp': time.time()
            }), 404
        
        events_data = gamma_response.json()
        
        # The API returns an array, get the first item
        if not events_data or len(events_data) == 0:
            return jsonify({
                'success': False,
                'error': 'Market not found',
                'timestamp': time.time()
            }), 404
        
        event = events_data[0]
        
        # Format the event data
        tags_list = event.get('tags', [])
        markets = event.get('markets', [])
        
        volume = event.get('volume', 0)
        if isinstance(volume, str):
            try:
                volume = float(volume)
            except (ValueError, TypeError):
                volume = 0
        
        volume_24hr = event.get('volume24hr', 0)
        if isinstance(volume_24hr, str):
            try:
                volume_24hr = float(volume_24hr)
            except (ValueError, TypeError):
                volume_24hr = 0
        
        liquidity = event.get('liquidity', 0)
        if isinstance(liquidity, str):
            try:
                liquidity = float(liquidity)
            except (ValueError, TypeError):
                liquidity = 0
        
        formatted_event = {
            'id': event.get('id'),
            'title': event.get('title'),
            'slug': event.get('slug'),
            'link': f"https://polymarket.com/event/{event.get('slug')}",
            'image': event.get('image') or event.get('icon') or 'https://via.placeholder.com/150',
            'tags': [
                {
                    'id': tag.get('id'),
                    'label': tag.get('label'),
                    'slug': tag.get('slug')
                }
                for tag in tags_list
            ],
            'tag_labels': [tag.get('label') for tag in tags_list],
            'volume': volume,
            'volume_24hr': volume_24hr,
            'liquidity': liquidity,
            'description': event.get('description', ''),
            'end_date': event.get('endDate'),
            'market_count': len(markets),
            'category': event.get('category'),
            'markets': markets  # ✅ Include ALL markets
        }
        
        print(f"✅ Successfully fetched market: {formatted_event['title']}")
        print(f"   - Volume: ${volume:,.2f}")
        print(f"   - Liquidity: ${liquidity:,.2f}")
        print(f"   - Markets: {len(markets)}")
        print('='*60 + '\n')
        
        return jsonify({
            'success': True,
            'data': formatted_event,
            'source': 'api',
            'timestamp': time.time()
        })
    
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error fetching market: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch market data from Polymarket',
            'timestamp': time.time()
        }), 500
    
    except Exception as e:
        print(f"❌ Error fetching market: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': time.time()
        }), 500


@app.route('/api/market/<slug>/related', methods=['GET'])
def get_related_markets(slug):
    """Get related markets based on tags"""
    try:
        # First get the main market
        market = next((event for event in cached_events if event.get('slug') == slug), None)
        
        if not market:
            return jsonify({
                'success': False,
                'error': 'Market not found',
                'timestamp': time.time()
            }), 404
        
        # Get tags from the market
        market_tags = set(market.get('tag_labels', []))
        
        if not market_tags:
            return jsonify({
                'success': True,
                'data': [],
                'count': 0,
                'timestamp': time.time()
            })
        
        # Find related markets with similar tags
        related_markets = []
        
        for event in cached_events:
            if event.get('slug') == slug:
                continue  # Skip the current market
            
            event_tags = set(event.get('tag_labels', []))
            
            # Calculate tag overlap
            common_tags = market_tags.intersection(event_tags)
            
            if common_tags:
                event_copy = event.copy()
                event_copy['match_score'] = len(common_tags)
                event_copy['matching_tags'] = list(common_tags)
                related_markets.append(event_copy)
        
        # Sort by match score and volume
        related_markets.sort(
            key=lambda x: (x.get('match_score', 0), x.get('volume', 0)),
            reverse=True
        )
        
        # Return top 10 related markets
        related_markets = related_markets[:10]
        
        return jsonify({
            'success': True,
            'data': related_markets,
            'count': len(related_markets),
            'timestamp': time.time()
        })
    
    except Exception as e:
        print(f"Error fetching related markets: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': time.time()
        }), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'events_count': len(cached_events),
        'last_update': last_update,
        'last_update_time': time.ctime(last_update) if last_update else 'Never',
        'timestamp': time.time()
    })


@app.route('/api/refresh', methods=['POST'])
def force_refresh():
    global cached_events, last_update
    
    try:
        events = get_all_trending_events()
        
        if events:
            cached_events = events
            last_update = time.time()
            
            return jsonify({
                'success': True,
                'message': 'Events refreshed successfully',
                'count': len(events),
                'timestamp': time.time()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to fetch events',
                'timestamp': time.time()
            }), 500
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': time.time()
        }), 500


# ============================================
# INITIALIZATION
# ============================================
def initialize_app():
    """Initialize app - runs in both dev and production"""
    print("\n" + "="*60)
    print("🚀 MEGA FAST GRADING - COMMENT-FIRST LOGIC")
    print("="*60)
    print(f"Config: {MAX_WORKERS} workers | {COMMENTS_PER_CHUNK} comments/chunk")
    print(f"Filter: Liquidity > ${MIN_LIQUIDITY}")
    print("Logic: Comment picks market+position → shares boost")
    print("="*60 + "\n")
    
    load_cache()
    load_graded_comments()
    
    # Only fetch top event and start background tasks in development
    if os.environ.get('FLASK_ENV') == 'development':
        slug = get_top_event()
        if slug:
            update_event(slug)
        threading.Thread(target=background_updater, daemon=True).start()

# Load caches on import
load_cache()
load_graded_comments()

# Start background updater on first request (not on import)
@app.before_request
def start_background_tasks():
    if not hasattr(app, 'background_started'):
        app.background_started = True
        threading.Thread(target=background_updater, daemon=True).start()

# Development server
if __name__ == '__main__':
    initialize_app()
    port = int(os.environ.get('PORT', 8400))  # ✅ USE PORT ENV VAR
    app.run(debug=False, host='0.0.0.0', port=port, threaded=True)
