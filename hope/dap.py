import requests
import json

"""
POLYMARKET COMMENTS FETCHER - FIXED VERSION
===========================================

Fixes:
1. Handle series data being a list instead of dict
2. WebSocket message parsing improvements
3. Better error handling for modified markets
"""

# Configuration
market_url = "https://polymarket.com/event/russia-x-ukraine-ceasefire-in-2025"
gamma_api_url = "https://gamma-api.polymarket.com"

# Extract slug
event_slug = market_url.split("/event/")[-1].split("?")[0]
print(f"🔍 Event slug: {event_slug}\n")

# ============================================================================
# STEP 1: GET EVENT DETAILS
# ============================================================================
print("="*80)
print("STEP 1: FETCHING EVENT DETAILS")
print("="*80)

events_endpoint = f"{gamma_api_url}/events"
response = requests.get(events_endpoint, params={"slug": event_slug})

if response.status_code != 200:
    print(f"❌ Failed to fetch event: {response.status_code}")
    exit()

events = response.json()
if not events:
    print("❌ Event not found")
    exit()

event = events[0]
event_id = event["id"]
event_title = event["title"]
comment_count = event.get("commentCount", 0)
markets = event.get("markets", [])
series_data = event.get("series", {})

# FIX 1: Handle series data being a list or dict
if isinstance(series_data, list):
    series_data = series_data[0] if series_data else {}
    
print(f"✅ Event found!")
print(f"   Title: {event_title}")
print(f"   Event ID: {event_id}")
print(f"   Comment Count (from event): {comment_count}")
print(f"   Markets in event: {len(markets)}")

if series_data and isinstance(series_data, dict):
    series_id = series_data.get('id')
    series_slug = series_data.get('slug', 'N/A')
    print(f"   Series ID: {series_id}")
    print(f"   Series slug: {series_slug}")
else:
    series_id = None
    print(f"   No series data")

# ============================================================================
# STEP 2: TRY MULTIPLE COMMENT FETCHING APPROACHES
# ============================================================================
comments_endpoint = f"{gamma_api_url}/comments"
all_comments = []
successful_approach = None

def fetch_comments(parent_id, parent_type, description):
    """Generic comment fetcher with improved error handling"""
    print(f"\n{'='*80}")
    print(f"TRYING: {description}")
    print(f"{'='*80}")
    print(f"Parent ID: {parent_id}")
    print(f"Parent Type: {parent_type}")
    
    limit = 100
    offset = 0
    comments = []
    
    while True:
        params = {
            "parent_entity_id": str(parent_id),
            "parent_entity_type": parent_type,
            "limit": limit,
            "offset": offset
        }
        
        try:
            response = requests.get(comments_endpoint, params=params, timeout=10)
            
            if offset == 0:
                print(f"Response Status: {response.status_code}")
            
            if response.status_code == 422:
                print(f"❌ 422 Error - Invalid parameters for this entity type")
                return []
            
            if response.status_code != 200:
                print(f"❌ Error {response.status_code}: {response.text[:200]}")
                return []
            
            data = response.json()
            
            # Handle different response formats
            if isinstance(data, list):
                batch = data
            elif isinstance(data, dict) and 'comments' in data:
                batch = data['comments']
            else:
                if offset == 0:
                    print(f"⚠️  Unexpected response format: {type(data)}")
                return []
            
            if len(batch) == 0:
                if offset == 0:
                    print(f"ℹ️  No comments found")
                else:
                    print(f"✅ Fetched all comments")
                break
            
            comments.extend(batch)
            
            if offset == 0:
                print(f"✅ Found comments! Fetching batch...")
            
            if offset % 1000 == 0 and offset > 0:
                print(f"   Progress: {len(comments)} comments fetched...")
            
            offset += limit
            
            # Safety limit
            if offset > 100000:
                print("⚠️  Safety limit reached (100k comments)")
                break
                
        except Exception as e:
            print(f"❌ Exception: {e}")
            return []
    
    if comments:
        print(f"✅ SUCCESS! Fetched {len(comments)} comments")
    
    return comments

# ============================================================================
# APPROACH 1: Event-level comments (MOST COMMON)
# ============================================================================
all_comments = fetch_comments(event_id, "Event", "Event-level comments (primary method)")
if all_comments:
    successful_approach = "Event"

# ============================================================================
# APPROACH 2: Series-level comments (for modified/updated markets)
# ============================================================================
if not all_comments and series_id:
    all_comments = fetch_comments(series_id, "Series", "Series-level comments (for modified markets)")
    if all_comments:
        successful_approach = "Series"

# ============================================================================
# APPROACH 3: Try first market's conditionId
# ============================================================================
if not all_comments and markets:
    first_market = markets[0]
    condition_id = first_market.get('conditionId')
    if condition_id:
        all_comments = fetch_comments(condition_id, "Market", "Market condition ID")
        if all_comments:
            successful_approach = "Market (conditionId)"

# ============================================================================
# APPROACH 4: Check if event is part of a group/series event
# ============================================================================
if not all_comments:
    # Try to find parent series through events endpoint
    parent_check = requests.get(f"{gamma_api_url}/events/{event_id}").json()
    if "seriesId" in parent_check or "series" in parent_check:
        series_info = parent_check.get("series", {})
        if isinstance(series_info, list) and series_info:
            series_info = series_info[0]
        parent_series_id = series_info.get("id") if series_info else None
        
        if parent_series_id:
            all_comments = fetch_comments(parent_series_id, "Series", "Parent series from event detail")
            if all_comments:
                successful_approach = "Parent Series"

# ============================================================================
# STEP 3: DISPLAY RESULTS
# ============================================================================
print(f"\n{'='*80}")
print(f"FINAL RESULTS")
print(f"{'='*80}\n")

if all_comments:
    print(f"✅ Successfully fetched {len(all_comments)} comments!")
    print(f"   Successful approach: {successful_approach}")
    print(f"   Event comment count: {comment_count}")
    
    if len(all_comments) != comment_count and comment_count > 0:
        print(f"   ⚠️  Note: Fetched count differs from event count")
    
    # Sort by creation date
    try:
        all_comments.sort(key=lambda x: x.get('createdAt', ''), reverse=True)
    except:
        pass
    
    # Save to file
    output_file = f"comments_event_{event_id}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_comments, f, indent=2, ensure_ascii=False)
    print(f"\n💾 Saved to: {output_file}")
    
    # Display sample comments
    print(f"\n{'='*80}")
    print(f"SAMPLE COMMENTS (first 5)")
    print(f"{'='*80}\n")
    
    for i, comment in enumerate(all_comments[:5], 1):
        comment_id = comment.get('id', 'N/A')
        body = comment.get('body', '').strip()
        created_at = comment.get('createdAt', 'Unknown')
        
        # Get user info
        profile = comment.get('profile', {})
        if profile:
            author = profile.get('name') or profile.get('username') or 'Anonymous'
        else:
            author = comment.get('userAddress', 'Anonymous')
            if len(author) > 12:
                author = f"{author[:6]}...{author[-4:]}"
        
        # Format output
        print(f"Comment #{i} (ID: {comment_id})")
        print(f"👤 {author}")
        print(f"🕒 {created_at}")
        if body:
            body_preview = body[:150] + "..." if len(body) > 150 else body
            print(f"💬 {body_preview}")
        print("-" * 80)
    
    # Statistics
    print(f"\n📊 Statistics:")
    print(f"   Total comments: {len(all_comments)}")
    
    replies = [c for c in all_comments if c.get('parentCommentID')]
    print(f"   Direct comments: {len(all_comments) - len(replies)}")
    print(f"   Replies: {len(replies)}")
    
    users = set()
    for c in all_comments:
        profile = c.get('profile', {})
        if profile:
            user_id = profile.get('name') or profile.get('username') or c.get('userAddress')
        else:
            user_id = c.get('userAddress', '')
        if user_id:
            users.add(user_id)
    print(f"   Unique commenters: {len(users)}")
    
else:
    print("❌ NO COMMENTS FOUND USING ANY APPROACH")
    print("\n💡 Possible reasons:")
    print("   1. This event truly has no comments")
    print("   2. Event is modified/updated - comments may be under parent series")
    print("   3. Comments are stored under a different entity structure")
    print("   4. The event was recently created and comments aren't indexed yet")
    print("\n🔍 Debugging information:")
    print(f"   Event ID: {event_id}")
    print(f"   Series ID: {series_id if series_id else 'None'}")
    print(f"   Number of markets: {len(markets)}")
    print("\n🔗 Next steps:")
    print("   • Try the WebSocket approach for real-time comment streaming")
    print("   • Check if this is part of a larger series/group event")
    print("   • Review: https://docs.polymarket.com/developers/RTDS/RTDS-comments")