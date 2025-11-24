from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import json
from typing import List, Dict
import time
from threading import Thread, Lock
from concurrent.futures import ThreadPoolExecutor
import os
import gzip

app = Flask(__name__)
CORS(app)

# Add response compression for large JSON payloads
@app.after_request
def compress_response(response):
    """Compress responses if they're large enough"""
    accept_encoding = request.headers.get('Accept-Encoding', '')
    
    if 'gzip' not in accept_encoding.lower():
        return response
    
    if response.status_code < 200 or response.status_code >= 300:
        return response
    
    # Only compress if response is larger than 1KB
    if len(response.data) < 1000:
        return response
    
    # Compress the response
    gzip_buffer = gzip.compress(response.data)
    response.data = gzip_buffer
    response.headers['Content-Encoding'] = 'gzip'
    response.headers['Content-Length'] = len(response.data)
    
    return response

# Cache for events data
events_cache = {
    'data': [],
    'last_updated': 0,
    'lock': Lock(),
    'is_updating': False,
    'initialized': False
}

CACHE_DURATION = 300
background_thread = None
init_lock = Lock()

gamma_api_url = "https://gamma-api.polymarket.com"
clob_api_url = "https://clob.polymarket.com"

def fetch_all_trending_events() -> List[Dict]:
    """Fetches all trending events maintaining volume order"""
    base_url = f"{gamma_api_url}/events"
    all_events = []
    limit = 100
    
    print(f"[PID {os.getpid()}] 🔄 Fetching events from Polymarket...", flush=True)
    start_time = time.time()
    
    def fetch_batch(offset):
        """Fetch a single batch of events"""
        params = {
            "active": True,
            "closed": False,
            "limit": limit,
            "offset": offset,
            "order": "volume",
            "ascending": False
        }
        
        try:
            response = requests.get(base_url, params=params, timeout=15)
            response.raise_for_status()
            events = response.json()
            return events if events else []
        except Exception as e:
            print(f"[PID {os.getpid()}] ❌ Error fetching at offset {offset}: {e}", flush=True)
            return []
    
    # Fetch in parallel but maintain order - reduced workers for stability
    offsets = list(range(0, 5000, limit))
    
    with ThreadPoolExecutor(max_workers=5) as executor:  # Reduced from 10 to 5
        # Submit all tasks and store futures with their offset
        future_to_offset = {executor.submit(fetch_batch, offset): offset for offset in offsets}
        
        # Collect results in a dictionary keyed by offset
        results = {}
        for future in future_to_offset:
            offset = future_to_offset[future]
            batch_events = future.result()
            if batch_events:
                results[offset] = batch_events
    
    # CRITICAL: Reconstruct events in correct order by offset
    for offset in sorted(results.keys()):
        all_events.extend(results[offset])
        
        # Stop when we hit a small batch (no more events)
        if len(results[offset]) < limit:
            break
    
    # Format events
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
            'markets': [
                {
                    **market,
                    'image': market.get('image') or market.get('icon') or event.get('image') or event.get('icon'),
                }
                for market in markets
            ]
        }
        
        formatted_events.append(formatted_event)
    
    elapsed = time.time() - start_time
    print(f"[PID {os.getpid()}] ✅ Fetched {len(formatted_events)} events in {elapsed:.1f}s", flush=True)
    return formatted_events

def update_events_cache():
    """Update cache without blocking reads"""
    with events_cache['lock']:
        if events_cache['is_updating']:
            print(f"[PID {os.getpid()}] ⏭️  Already updating, skipping", flush=True)
            return
        events_cache['is_updating'] = True
    
    try:
        new_data = fetch_all_trending_events()
        
        with events_cache['lock']:
            events_cache['data'] = new_data
            events_cache['last_updated'] = time.time()
            events_cache['is_updating'] = False
            events_cache['initialized'] = True
            
        print(f"[PID {os.getpid()}] ✅ Cache updated: {len(new_data)} events", flush=True)
        
    except Exception as e:
        print(f"[PID {os.getpid()}] ❌ Error updating cache: {e}", flush=True)
        import traceback
        traceback.print_exc()
        with events_cache['lock']:
            events_cache['is_updating'] = False

def background_updater():
    """Background thread for cache updates"""
    print(f"[PID {os.getpid()}] 🔄 Background updater started", flush=True)
    while True:
        time.sleep(CACHE_DURATION)
        print(f"[PID {os.getpid()}] 🔄 Background refresh triggered", flush=True)
        update_events_cache()

def ensure_initialized():
    """Initialize worker on first request"""
    global background_thread
    
    if events_cache.get('initialized', False) and background_thread and background_thread.is_alive():
        return
    
    with init_lock:
        if events_cache.get('initialized', False) and background_thread and background_thread.is_alive():
            return
        
        print(f"\n{'='*60}", flush=True)
        print(f"🚀 INITIALIZING WORKER (PID: {os.getpid()})", flush=True)
        print(f"{'='*60}", flush=True)
        
        update_events_cache()
        
        background_thread = Thread(target=background_updater, daemon=True, name=f"updater-{os.getpid()}")
        background_thread.start()
        
        print(f"✅ Worker {os.getpid()} ready with {len(events_cache['data'])} events", flush=True)
        print(f"{'='*60}\n", flush=True)

@app.before_request
def before_request():
    """Initialize on first request"""
    ensure_initialized()

def get_cached_events() -> List[Dict]:
    """Get events from cache"""
    current_time = time.time()
    
    should_update = False
    with events_cache['lock']:
        if (current_time - events_cache['last_updated'] > CACHE_DURATION and 
            not events_cache['is_updating']):
            should_update = True
    
    if should_update:
        thread = Thread(target=update_events_cache, daemon=True)
        thread.start()
    
    with events_cache['lock']:
        return events_cache['data'].copy()

@app.route('/api/events', methods=['GET'])
def get_events():
    if not events_cache.get('initialized', False):
        return jsonify({
            'success': True,
            'data': [],
            'count': 0,
            'message': 'Loading events, please try again in a moment...',
            'initializing': True
        })
    
    events = get_cached_events()
    return jsonify({
        'success': True,
        'data': events,
        'count': len(events),
        'last_update': events_cache['last_updated'],
        'timestamp': time.time()
    })

@app.route('/api/events/featured', methods=['GET'])
def get_featured_event():
    if not events_cache.get('initialized', False):
        return jsonify({
            'success': True,
            'data': None,
            'message': 'Loading events...',
            'initializing': True
        })
    
    events = get_cached_events()
    if events:
        return jsonify({
            'success': True,
            'data': events[0],
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
    """Get remaining events with pagination - NEVER return all events at once"""
    if not events_cache.get('initialized', False):
        return jsonify({
            'success': True,
            'data': [],
            'message': 'Loading events...',
            'initializing': True
        })
    
    # Force pagination with reasonable defaults
    limit = int(request.args.get('limit', 100))  # Default 100
    offset = int(request.args.get('offset', 1))  # Start at index 1 (skip featured)
    
    if limit > 200:
        limit = 200  # Hard cap at 200
    if offset < 1:
        offset = 1
    
    events = get_cached_events()
    
    if len(events) <= offset:
        return jsonify({
            'success': True,
            'data': [],
            'count': 0,
            'has_more': False,
            'timestamp': time.time()
        })
    
    # Get slice of events
    end_idx = offset + limit
    remaining = events[offset:end_idx]
    has_more = end_idx < len(events)
    
    # Strip heavy fields (markets array)
    stripped = [
        {
            'rank': e['rank'],
            'id': e['id'],
            'title': e['title'],
            'slug': e['slug'],
            'link': e['link'],
            'image': e['image'],
            'tags': e.get('tags', []),
            'tag_labels': e.get('tag_labels', []),
            'volume': e['volume'],
            'volume_24hr': e.get('volume_24hr', 0),
            'liquidity': e['liquidity'],
            'market_count': e.get('market_count', 0),
            'category': e.get('category'),
            'description': e.get('description', '')[:200] if e.get('description') else ''
        }
        for e in remaining
    ]
    
    return jsonify({
        'success': True,
        'data': stripped,
        'count': len(stripped),
        'offset': offset,
        'limit': limit,
        'total_available': len(events) - 1,  # Exclude featured
        'has_more': has_more,
        'timestamp': time.time()
    })

@app.route('/api/markets/paginated', methods=['GET'])
def get_paginated_markets():
    """Paginated markets endpoint - strips markets array by default for performance"""
    try:
        offset = int(request.args.get('offset', 0))
        limit = int(request.args.get('limit', 100))
        include_markets = request.args.get('include_markets', 'false').lower() == 'true'
        
        if offset < 0:
            offset = 0
        if limit < 1 or limit > 200:  # Reduced max from 500 to 200
            limit = 100
        
        if not events_cache.get('initialized', False):
            return jsonify({
                'success': True,
                'data': [],
                'message': 'Loading events...',
                'initializing': True
            })
        
        events = get_cached_events()
        
        start_idx = offset
        end_idx = offset + limit
        
        paginated_events = events[start_idx:end_idx]
        has_more = end_idx < len(events)
        
        # Strip markets array by default for performance
        if not include_markets:
            paginated_events = [
                {
                    'rank': e['rank'],
                    'id': e['id'],
                    'title': e['title'],
                    'slug': e['slug'],
                    'link': e['link'],
                    'image': e['image'],
                    'tags': e.get('tags', []),
                    'tag_labels': e.get('tag_labels', []),
                    'volume': e['volume'],
                    'volume_24hr': e.get('volume_24hr', 0),
                    'liquidity': e['liquidity'],
                    'market_count': e.get('market_count', 0),
                    'category': e.get('category'),
                    'description': e.get('description', '')[:200] if e.get('description') else ''
                }
                for e in paginated_events
            ]
        
        return jsonify({
            'success': True,
            'data': paginated_events,
            'count': len(paginated_events),
            'offset': offset,
            'limit': limit,
            'total': len(events),
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
        events_endpoint = f"{gamma_api_url}/events/slug/{slug}"
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
            
            clob_url = f"{clob_api_url}/prices-history"
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
        events = get_cached_events()
        market_from_cache = next((event for event in events if event.get('slug') == slug), None)
        
        if market_from_cache:
            return jsonify({
                'success': True,
                'data': market_from_cache,
                'source': 'cache',
                'timestamp': time.time()
            })
        
        gamma_response = requests.get(
            f"{gamma_api_url}/events",
            params={'slug': slug},
            timeout=10
        )
        
        if gamma_response.status_code != 200:
            return jsonify({
                'success': False,
                'error': 'Market not found',
                'timestamp': time.time()
            }), 404
        
        events_data = gamma_response.json()
        
        if not events_data or len(events_data) == 0:
            return jsonify({
                'success': False,
                'error': 'Market not found',
                'timestamp': time.time()
            }), 404
        
        event = events_data[0]
        
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
            'markets': markets
        }
        
        return jsonify({
            'success': True,
            'data': formatted_event,
            'source': 'api',
            'timestamp': time.time()
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': time.time()
        }), 500

@app.route('/api/market/<slug>/related', methods=['GET'])
def get_related_markets(slug):
    """Get related markets based on tags"""
    try:
        events = get_cached_events()
        market = next((event for event in events if event.get('slug') == slug), None)
        
        if not market:
            return jsonify({
                'success': False,
                'error': 'Market not found',
                'timestamp': time.time()
            }), 404
        
        market_tags = set(market.get('tag_labels', []))
        
        if not market_tags:
            return jsonify({
                'success': True,
                'data': [],
                'count': 0,
                'timestamp': time.time()
            })
        
        related_markets = []
        
        for event in events:
            if event.get('slug') == slug:
                continue
            
            event_tags = set(event.get('tag_labels', []))
            common_tags = market_tags.intersection(event_tags)
            
            if common_tags:
                event_copy = event.copy()
                event_copy['match_score'] = len(common_tags)
                event_copy['matching_tags'] = list(common_tags)
                related_markets.append(event_copy)
        
        related_markets.sort(
            key=lambda x: (x.get('match_score', 0), x.get('volume', 0)),
            reverse=True
        )
        
        related_markets = related_markets[:10]
        
        return jsonify({
            'success': True,
            'data': related_markets,
            'count': len(related_markets),
            'timestamp': time.time()
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': time.time()
        }), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    with events_cache['lock']:
        cache_age = time.time() - events_cache['last_updated']
        is_updating = events_cache['is_updating']
        initialized = events_cache.get('initialized', False)
        cache_size = len(events_cache['data'])
    
    is_alive = background_thread is not None and background_thread.is_alive()
    
    return jsonify({
        'success': True,
        'status': 'healthy' if initialized else 'initializing',
        'initialized': initialized,
        'cache_size': cache_size,
        'cache_age_seconds': cache_age,
        'is_updating': is_updating,
        'background_thread_alive': is_alive,
        'worker_pid': os.getpid()
    })

@app.route('/api/refresh', methods=['POST'])
def force_refresh():
    thread = Thread(target=update_events_cache, daemon=True)
    thread.start()
    
    return jsonify({'success': True, 'message': 'Cache refresh initiated'})

# Debug endpoint to verify order
@app.route('/api/debug/top-events', methods=['GET'])
def debug_top_events():
    """Show top 10 events with volumes to verify ordering"""
    events = get_cached_events()
    top_10 = events[:10]
    
    return jsonify({
        'success': True,
        'top_10': [
            {
                'rank': e['rank'],
                'title': e['title'],
                'volume': e['volume'],
                'volume_24hr': e.get('volume_24hr', 0)
            }
            for e in top_10
        ]
    })

if __name__ == '__main__':
    ensure_initialized()
    app.run(debug=True, host='0.0.0.0', port=8100)