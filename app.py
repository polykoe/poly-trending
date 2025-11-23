# from selenium import webdriver
# from selenium.webdriver.common.by import By
# from selenium.webdriver.common.keys import Keys
# from selenium.webdriver.firefox.options import Options
# from selenium.webdriver.firefox.service import Service
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC
# import json, time, os
# from concurrent.futures import ThreadPoolExecutor, as_completed
# from datetime import datetime
# from urllib.parse import quote

# class TwitterScraper:
#     def __init__(self, cookies_path="cookies.json", headless=False):
#         """Initialize persistent browser session."""
#         self.cookies_path = cookies_path
#         self.driver = None
#         self.cookies_loaded = False
#         self._init_driver(headless)
    
#     def _init_driver(self, headless):
#         """Create and configure the browser driver."""
#         options = Options()
#         if headless:
#             options.add_argument("--headless")
#         options.add_argument("--width=1280")
#         options.add_argument("--height=800")
        
#         service = Service()
#         self.driver = webdriver.Firefox(service=service, options=options)
#         print("✅ Browser initialized and ready")
    
#     def _load_cookies(self):
#         """Load cookies once per session."""
#         if self.cookies_loaded:
#             return
        
#         if not os.path.exists(self.cookies_path):
#             print(f"⚠️ {self.cookies_path} not found. Continuing without cookies.")
#             return
        
#         try:
#             with open(self.cookies_path, "r") as f:
#                 cookies = json.load(f)
            
#             print("🍪 Loading cookies...")
#             self.driver.get("https://twitter.com")
#             time.sleep(3)
            
#             for cookie in cookies:
#                 cookie.pop("sameSite", None)
#                 try:
#                     self.driver.add_cookie(cookie)
#                 except Exception as e:
#                     pass
            
#             self.driver.refresh()
#             time.sleep(3)
            
#             page_text = self.driver.page_source.lower()
#             if "log in" not in page_text and "sign in" not in page_text:
#                 self.cookies_loaded = True
#                 print("✅ Cookies loaded and verified - Logged in!")
#             else:
#                 print("⚠️ Cookies loaded but login verification failed")
                
#         except Exception as e:
#             print(f"⚠️ Failed to load cookies: {e}")
    
#     def _scrape_comments_with_new_driver(self, tweet_url, cookies):
#         """Launch a new Firefox driver to scrape comments from a tweet."""
#         options = Options()
#         options.add_argument("--headless")
#         options.add_argument("--width=1280")
#         options.add_argument("--height=800")

#         driver = webdriver.Firefox(options=options)
#         driver.get("https://twitter.com")
#         time.sleep(2)

#         # Load cookies
#         for c in cookies:
#             c.pop("sameSite", None)
#             try:
#                 driver.add_cookie(c)
#             except:
#                 pass
#         driver.refresh()
#         time.sleep(3)

#         driver.get(tweet_url)
#         time.sleep(6)

#         comments = []
#         seen = set()

#         for _ in range(30):
#             reply_articles = driver.find_elements(By.TAG_NAME, "article")
#             for idx, r in enumerate(reply_articles):
#                 if idx == 0:
#                     continue
#                 try:
#                     txt = r.text.strip()
#                     if not txt or len(txt) < 20:
#                         continue
#                     h = hash(txt[:200])
#                     if h not in seen:
#                         seen.add(h)
#                         lines = txt.split("\n")
#                         username = lines[0] if lines and lines[0].startswith("@") else "Unknown"
#                         comments.append({"user": username, "full_text": txt})
#                 except:
#                     continue

#             driver.execute_script("window.scrollBy(0, 1000);")
#             time.sleep(2)

#         driver.quit()
#         print(f"✅ Scraped {len(comments)} comments from: {tweet_url}")
#         return comments

#     def _global_search_with_new_driver(self, search_query, cookies, max_results=10, 
#                                        language="en", exclude_retweets=True, since_date=None):
#         """
#         Launch a new Firefox driver to perform global Twitter search with advanced filters.
        
#         Args:
#             search_query: Base search term (e.g., "Sam Altman jail")
#             cookies: Session cookies
#             max_results: Maximum number of tweets to return
#             language: Language filter (e.g., "en")
#             exclude_retweets: If True, excludes retweets
#             since_date: Date string in format "YYYY-MM-DD" (e.g., "2025-10-30")
#         """
#         options = Options()
#         options.add_argument("--headless")
#         options.add_argument("--width=1280")
#         options.add_argument("--height=800")

#         driver = webdriver.Firefox(options=options)
#         driver.get("https://twitter.com")
#         time.sleep(2)

#         # Load cookies
#         for c in cookies:
#             c.pop("sameSite", None)
#             try:
#                 driver.add_cookie(c)
#             except:
#                 pass
#         driver.refresh()
#         time.sleep(3)

#         # Build advanced search query
#         query_parts = [search_query]
        
#         if language:
#             query_parts.append(f"lang:{language}")
        
#         if exclude_retweets:
#             query_parts.append("-is:retweet")
        
#         if since_date:
#             query_parts.append(f"since:{since_date}")
        
#         full_query = " ".join(query_parts)
#         encoded_query = quote(full_query)
        
#         # Navigate to search
#         print(f"🔍 Performing global search: '{full_query}'")
#         search_url = f"https://twitter.com/search?q={encoded_query}&src=typed_query&f=live"
#         driver.get(search_url)
#         time.sleep(5)

#         found_tweets = []
#         seen_urls = set()

#         # Scroll and collect tweets
#         for _ in range(15):
#             articles = driver.find_elements(By.TAG_NAME, "article")
            
#             for article in articles:
#                 if len(found_tweets) >= max_results:
#                     break
                    
#                 try:
#                     text = article.text.strip()
#                     if not text or len(text) < 20:
#                         continue
                    
#                     # Get tweet URL
#                     link_el = article.find_element(By.CSS_SELECTOR, "a[href*='/status/']")
#                     tweet_url = link_el.get_attribute("href")
                    
#                     if tweet_url in seen_urls:
#                         continue
#                     seen_urls.add(tweet_url)
                    
#                     # Get username
#                     lines = text.split("\n")
#                     username = lines[0] if lines and lines[0].startswith("@") else "Unknown"
                    
#                     # Get tweet time
#                     try:
#                         time_el = article.find_element(By.TAG_NAME, "time")
#                         tweet_time = time_el.get_attribute("datetime")
#                     except:
#                         tweet_time = "Unknown"
                    
#                     # Get tweet text
#                     divs = article.find_elements(By.CSS_SELECTOR, "div[lang]")
#                     tweet_text = divs[0].text.strip() if divs else text.split("\n")[1] if len(lines) > 1 else text
                    
#                     found_tweets.append({
#                         "username": username,
#                         "tweet": tweet_text,
#                         "url": tweet_url,
#                         "time": tweet_time
#                     })
                    
#                 except Exception as e:
#                     continue
            
#             if len(found_tweets) >= max_results:
#                 break
                
#             driver.execute_script("window.scrollBy(0, 1000);")
#             time.sleep(2)

#         driver.quit()
#         print(f"✅ Global search found {len(found_tweets)} tweets")
#         return found_tweets

#     def search_and_scrape_concurrent(self, username: str, search_sentence: str, 
#                                     max_global_results=10, global_search_params=None):
#         """
#         Search for a sentence on user's account, scrape its comments,
#         AND simultaneously perform global search for the same sentence.
        
#         Args:
#             username: Twitter username to search
#             search_sentence: Sentence to search for
#             max_global_results: Max tweets in global search
#             global_search_params: Dict with optional keys:
#                 - 'query': Custom global search query (default: search_sentence)
#                 - 'language': Language filter (default: "en")
#                 - 'exclude_retweets': Exclude retweets (default: True)
#                 - 'since_date': Date filter "YYYY-MM-DD" (default: None)
#         """
#         if not self.driver:
#             return {"error": "Browser not initialized"}
        
#         # Load cookies on first run
#         if not self.cookies_loaded:
#             self._load_cookies()
        
#         print(f"\n🔍 Searching for '{search_sentence}' on @{username}'s account...")
        
#         # Navigate to user's profile with search
#         search_url = f"https://twitter.com/search?q={quote(search_sentence)}%20from%3A{username}&src=typed_query&f=live"
#         self.driver.get(search_url)
#         time.sleep(5)

#         # Check for errors
#         page = self.driver.page_source.lower()
#         if "account suspended" in page:
#             return {"error": f"Account @{username} is suspended."}
#         if "login" in self.driver.current_url:
#             return {"error": "Cookies invalid or expired — redirected to login page."}

#         # Find the tweet with the sentence
#         try:
#             WebDriverWait(self.driver, 15).until(
#                 EC.presence_of_element_located((By.TAG_NAME, "article"))
#             )
#         except:
#             return {"error": f"Could not find any tweets with '{search_sentence}' from @{username}"}

#         articles = self.driver.find_elements(By.TAG_NAME, "article")
#         target_tweet = None

#         for article in articles:
#             try:
#                 text = article.text.strip()
#                 if search_sentence.lower() in text.lower():
#                     link_el = article.find_element(By.CSS_SELECTOR, "a[href*='/status/']")
#                     tweet_url = link_el.get_attribute("href")
                    
#                     # Verify it's from the target user
#                     if f"/{username}/" in tweet_url.lower():
#                         time_el = article.find_element(By.TAG_NAME, "time")
#                         tweet_time = time_el.get_attribute("datetime")
                        
#                         divs = article.find_elements(By.CSS_SELECTOR, "div[lang]")
#                         tweet_text = divs[0].text.strip() if divs else text.split("\n")[0]
                        
#                         target_tweet = {
#                             "tweet": tweet_text,
#                             "url": tweet_url,
#                             "time": tweet_time
#                         }
#                         print(f"✅ Found target tweet: {tweet_url}")
#                         break
#             except:
#                 continue

#         if not target_tweet:
#             return {"error": f"Could not find tweet with '{search_sentence}' from @{username}"}

#         # Load cookies for parallel tasks
#         cookies = []
#         if os.path.exists(self.cookies_path):
#             with open(self.cookies_path, "r") as f:
#                 cookies = json.load(f)

#         # Set default global search parameters
#         if global_search_params is None:
#             global_search_params = {}
        
#         global_query = global_search_params.get('query', search_sentence)
#         language = global_search_params.get('language', 'en')
#         exclude_retweets = global_search_params.get('exclude_retweets', True)
#         since_date = global_search_params.get('since_date', None)

#         # Run both tasks concurrently
#         print(f"\n🚀 Starting concurrent tasks:")
#         print(f"   1. Scraping comments from @{username}'s tweet")
#         print(f"   2. Performing global search with filters")

#         with ThreadPoolExecutor(max_workers=2) as executor:
#             # Submit both tasks
#             future_comments = executor.submit(
#                 self._scrape_comments_with_new_driver, 
#                 target_tweet["url"], 
#                 cookies
#             )
#             future_global = executor.submit(
#                 self._global_search_with_new_driver, 
#                 global_query, 
#                 cookies,
#                 max_global_results,
#                 language,
#                 exclude_retweets,
#                 since_date
#             )

#             # Wait for both to complete
#             comments = future_comments.result()
#             global_tweets = future_global.result()

#         print(f"\n✅ Concurrent tasks completed!")
        
#         result = {
#             "search_query": search_sentence,
#             "user_account": {
#                 "username": username,
#                 "found_tweet": {
#                     "tweet": target_tweet["tweet"],
#                     "url": target_tweet["url"],
#                     "time": target_tweet["time"],
#                     "comments_count": len(comments),
#                     "comments": comments
#                 }
#             },
#             "global_search": {
#                 "query_used": f"{global_query} lang:{language} {'-is:retweet' if exclude_retweets else ''} {f'since:{since_date}' if since_date else ''}".strip(),
#                 "total_found": len(global_tweets),
#                 "tweets": global_tweets
#             }
#         }
        
#         return result
    
#     def close(self):
#         """Close the browser when done."""
#         if self.driver:
#             self.driver.quit()
#             print("🔴 Browser closed")
#             self.driver = None
#             self.cookies_loaded = False


# # ============================================
# # Usage Example
# # ============================================
# if __name__ == "__main__":
#     # Create scraper instance
#     scraper = TwitterScraper(headless=True)
    
#     try:
#         # Search for a specific sentence and scrape concurrently
#         search_sentence = "When will Sam Altman be in jail by"
#         username = "polymarket"
        
#         # Configure global search with advanced filters
#         global_params = {
#             'query': 'Sam Altman jail',  # Custom query for global search
#             'language': 'en',
#             'exclude_retweets': True,
#             'since_date': '2025-10-30'  # Format: YYYY-MM-DD
#         }
        
#         print("\n" + "="*70)
#         print(f"🔍 SEARCHING: '{search_sentence}' on @{username}")
#         print(f"   + Scraping comments from user's tweet")
#         print(f"   + Global search: {global_params['query']} lang:{global_params['language']} -is:retweet since:{global_params['since_date']}")
#         print("="*70)
        
#         result = scraper.search_and_scrape_concurrent(
#             username=username,
#             search_sentence=search_sentence,
#             max_global_results=10,
#             global_search_params=global_params
#         )
        
#         # Print summary
#         print("\n" + "="*70)
#         print(f"📊 RESULTS SUMMARY")
#         print("="*70)
        
#         if 'error' in result:
#             print(f"\n❌ Error: {result['error']}")
#         else:
#             print(f"\n🎯 User Account Search (@{result['user_account']['username']}):")
#             print(f"   Tweet: {result['user_account']['found_tweet']['tweet'][:100]}...")
#             print(f"   URL: {result['user_account']['found_tweet']['url']}")
#             print(f"   Comments: {result['user_account']['found_tweet']['comments_count']}")
            
#             print(f"\n🌍 Global Search Results:")
#             print(f"   Query: {result['global_search']['query_used']}")
#             print(f"   Total tweets found: {result['global_search']['total_found']}")
#             for idx, tweet in enumerate(result['global_search']['tweets'][:5], 1):
#                 print(f"   {idx}. @{tweet['username']}: {tweet['tweet'][:60]}...")
        
#         # Save to file
#         filename = f"{username}_search_concurrent.json"
#         with open(filename, "w", encoding="utf-8") as f:
#             json.dump(result, f, indent=2, ensure_ascii=False)
#         print(f"\n💾 Full results saved to {filename}")
        
#     finally:
#         scraper.close()
import requests
import json

# Keep your event link
market_url = "https://polymarket.com/event/new-york-city-mayoral-election-staten-island-winner"

# Extract slug
event_slug = market_url.split("/event/")[-1]
print(f"Event slug: {event_slug}")

# Step 1: Get event details
gamma_api_url = "https://gamma-api.polymarket.com"
events_endpoint = f"{gamma_api_url}/events"

params = {"slug": event_slug}
print("\n🔍 Fetching event details...")
response = requests.get(events_endpoint, params=params)

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

print(f"✅ Event found!")
print(f"   Title: {event_title}")
print(f"   Event ID: {event_id}")
print(f"   Total Comments: {comment_count}")

# Step 2: Fetch all comments from Gamma API with correct parameters
print(f"\n📥 Fetching all {comment_count} comments...")

comments_endpoint = f"{gamma_api_url}/comments"

# Use the correct parameter names from the error message
limit = 100
offset = 0
all_comments = []

while True:
    params = {
        "parent_entity_id": event_id,  # Correct parameter name (with underscores)
        "parent_entity_type": "Event",  # Correct parameter name
        "limit": limit,
        "offset": offset
    }
    
    print(f"\n🔄 Fetching comments {offset} to {offset + limit}...")
    
    try:
        response = requests.get(comments_endpoint, params=params)
        
        if response.status_code != 200:
            print(f"   ❌ Status {response.status_code}: {response.text[:500]}")
            break
        
        data = response.json()
        
        # Handle different response formats
        if isinstance(data, list):
            batch = data
        elif isinstance(data, dict) and 'comments' in data:
            batch = data['comments']
        else:
            print(f"   ⚠️  Unexpected response format: {type(data)}")
            if isinstance(data, dict):
                print(f"   Keys: {list(data.keys())}")
            break
        
        if len(batch) == 0:
            print(f"   ✅ No more comments (reached end)")
            break
        
        all_comments.extend(batch)
        print(f"   ✅ Fetched {len(batch)} comments (total: {len(all_comments)}/{comment_count})")
        
        offset += limit
        
        # Stop if we've fetched all comments
        if len(all_comments) >= comment_count:
            break
        
        # Safety limit
        if offset > 10000:  # Prevent infinite loops
            print("   ⚠️  Safety limit reached")
            break
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        break

# Display comments if found
if all_comments:
    print(f"\n{'='*80}")
    print(f"✅ Successfully fetched {len(all_comments)} comments!")
    print(f"{'='*80}\n")
    
    # Sort by creation date (most recent first)
    try:
        all_comments.sort(key=lambda x: x.get('createdAt', ''), reverse=True)
    except:
        pass
    
    # Display comments
    for i, comment in enumerate(all_comments, 1):
        comment_id = comment.get('id', 'N/A')
        body = comment.get('body', '').strip()
        created_at = comment.get('createdAt', 'Unknown time')
        
        # Try to get user info
        profile = comment.get('profile', {})
        if profile:
            author = profile.get('name') or profile.get('username') or 'Anonymous'
            profile_img = profile.get('profileImage', '')
        else:
            author = comment.get('userAddress', 'Anonymous')
            if len(author) > 12:
                author = f"{author[:6]}...{author[-4:]}"  # Shorten address
            profile_img = ''
        
        # Get reply info if applicable
        parent_comment_id = comment.get('parentCommentID')
        reply_address = comment.get('replyAddress', '')
        
        # Check for reactions
        reactions = comment.get('reactions', [])
        reaction_summary = ""
        if reactions:
            reaction_counts = {}
            for reaction in reactions:
                r_type = reaction.get('reactionType', '👍')
                reaction_counts[r_type] = reaction_counts.get(r_type, 0) + 1
            reaction_summary = " | " + " ".join([f"{k}:{v}" for k, v in reaction_counts.items()])
        
        # Format output
        reply_marker = "   ↳ " if parent_comment_id else ""
        
        print(f"{reply_marker}Comment #{i} (ID: {comment_id})")
        print(f"{reply_marker}👤 {author}")
        print(f"{reply_marker}🕒 {created_at}{reaction_summary}")
        if body:
            # Split long comments into multiple lines
            if len(body) > 100:
                words = body.split()
                lines = []
                current_line = reply_marker + "💬 "
                for word in words:
                    if len(current_line) + len(word) + 1 > 100:
                        lines.append(current_line)
                        current_line = reply_marker + "   " + word
                    else:
                        current_line += " " + word if current_line.endswith(" ") or current_line.endswith("💬 ") else word
                if current_line.strip():
                    lines.append(current_line)
                print("\n".join(lines))
            else:
                print(f"{reply_marker}💬 {body}")
        print("-" * 80)
    
    # Save to file
    output_file = f"comments_event_{event_id}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_comments, f, indent=2, ensure_ascii=False)
    print(f"\n💾 All {len(all_comments)} comments saved to: {output_file}")
    
    # Statistics
    print(f"\n📊 Statistics:")
    print(f"   Total comments: {len(all_comments)}")
    
    # Count replies
    replies = [c for c in all_comments if c.get('parentCommentID')]
    print(f"   Direct comments: {len(all_comments) - len(replies)}")
    print(f"   Replies: {len(replies)}")
    
    # Count unique users
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
    print("\n❌ No comments fetched")
    print("💡 The API might have changed or requires authentication")