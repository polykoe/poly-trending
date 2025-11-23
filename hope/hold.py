from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import json, time, os
from concurrent.futures import ThreadPoolExecutor, as_completed

class TwitterScraper:
    def __init__(self, cookies_path="cookies.json", headless=False):
        """Initialize persistent browser session."""
        self.cookies_path = cookies_path
        self.driver = None
        self.cookies_loaded = False
        self._init_driver(headless)
    
    def _init_driver(self, headless):
        """Create and configure the browser driver."""
        options = Options()
        if headless:
            options.add_argument("--headless")
        options.add_argument("--width=1280")
        options.add_argument("--height=800")
        
        service = Service()
        self.driver = webdriver.Firefox(service=service, options=options)
        print("✅ Browser initialized and ready")
    
    def _load_cookies(self):
        """Load cookies once per session."""
        if self.cookies_loaded:
            return
        
        if not os.path.exists(self.cookies_path):
            print(f"⚠️ {self.cookies_path} not found. Continuing without cookies.")
            return
        
        try:
            with open(self.cookies_path, "r") as f:
                cookies = json.load(f)
            
            # Need to be on Twitter domain to add cookies
            print("🍪 Loading cookies...")
            self.driver.get("https://twitter.com")
            time.sleep(3)
            
            for cookie in cookies:
                cookie.pop("sameSite", None)
                try:
                    self.driver.add_cookie(cookie)
                except Exception as e:
                    pass
            
            # Refresh to apply cookies
            self.driver.refresh()
            time.sleep(3)
            
            # Verify login by checking for profile/home elements
            page_text = self.driver.page_source.lower()
            if "log in" not in page_text and "sign in" not in page_text:
                self.cookies_loaded = True
                print("✅ Cookies loaded and verified - Logged in!")
            else:
                print("⚠️ Cookies loaded but login verification failed")
                print("💡 You may need to export fresh cookies from your browser")
                
        except Exception as e:
            print(f"⚠️ Failed to load cookies: {e}")
    
    def _scrape_single_tweet_with_new_driver(self, tweet_info, tweet_number, cookies):
        """Launch a new Firefox driver just for this tweet and scrape comments."""
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--width=1280")
        options.add_argument("--height=800")

        driver = webdriver.Firefox(options=options)
        driver.get("https://twitter.com")
        time.sleep(2)

        # Load cookies to stay logged in
        for c in cookies:
            c.pop("sameSite", None)
            try:
                driver.add_cookie(c)
            except:
                pass
        driver.refresh()
        time.sleep(3)

        tweet_url = tweet_info["url"]
        driver.get(tweet_url)
        time.sleep(6)

        comments = []
        seen = set()

        for _ in range(30):  # Adjust scroll count
            reply_articles = driver.find_elements(By.TAG_NAME, "article")
            for idx, r in enumerate(reply_articles):
                if idx == 0:  # skip main tweet
                    continue
                try:
                    txt = r.text.strip()
                    if not txt or len(txt) < 20:
                        continue
                    h = hash(txt[:200])
                    if h not in seen:
                        seen.add(h)
                        lines = txt.split("\n")
                        username = lines[0] if lines and lines[0].startswith("@") else "Unknown"
                        comments.append({"user": username, "full_text": txt})
                except:
                    continue

            driver.execute_script("window.scrollBy(0, 1000);")
            time.sleep(2)

        driver.quit()
        print(f"✅ {tweet_url} → {len(comments)} comments")
        return {
            "tweet_number": tweet_number,  # Added this field
            "tweet": tweet_info["tweet"],
            "url": tweet_url,
            "time": tweet_info["time"],
            "comments": comments
        }

    def get_latest_tweets_and_replies(self, username: str, num_tweets=2):
        """Scrape the latest N tweets and their replies in parallel using tabs."""
        if not self.driver:
            return {"error": "Browser not initialized"}
        
        # Load cookies on first run
        if not self.cookies_loaded:
            self._load_cookies()
        
        print(f"🌐 Navigating to @{username}...")
        self.driver.get(f"https://twitter.com/{username}")
        time.sleep(5)

        # --- Detect suspension or missing account ---
        page = self.driver.page_source.lower()
        if "account suspended" in page:
            return {"error": f"Account @{username} is suspended."}
        if "this account doesn't exist" in page or "page doesn't exist" in page:
            return {"error": f"Account @{username} does not exist."}

        # --- Check if redirected to login ---
        if "login" in self.driver.current_url:
            self.driver.save_screenshot("login_redirect.png")
            return {"error": "Cookies invalid or expired — redirected to login page."}

        # --- Wait for tweet articles ---
        try:
            WebDriverWait(self.driver, 60).until(
                EC.presence_of_element_located((By.TAG_NAME, "article"))
            )
        except:
            self.driver.save_screenshot("no_tweets.png")
            return {"error": "Could not find any tweets (timeout)"}

        # --- Scrape latest N tweets (skip retweets and pinned) ---
        articles = self.driver.find_elements(By.TAG_NAME, "article")
        tweets_data = []

        for article in articles:
            if len(tweets_data) >= num_tweets:
                break
                
            text = article.text.strip()
            if not text or "Pinned" in text or "Retweeted" in text or "reposted" in text.lower():
                continue
            
            try:
                time_el = article.find_element(By.TAG_NAME, "time")
                tweet_time = time_el.get_attribute("datetime")
                link_el = article.find_element(By.CSS_SELECTOR, "a[href*='/status/']")
                tweet_url = link_el.get_attribute("href")
                
                # Skip if URL doesn't belong to this user
                if f"/{username}/" not in tweet_url.lower():
                    continue
                
                divs = article.find_elements(By.CSS_SELECTOR, "div[lang]")
                tweet_text = divs[0].text.strip() if divs else text.split("\n")[0]
                
                if tweet_text:
                    tweets_data.append({
                        "tweet": tweet_text,
                        "url": tweet_url,
                        "time": tweet_time
                    })
            except Exception as e:
                continue

        if not tweets_data:
            self.driver.save_screenshot("empty_articles.png")
            return {"error": f"No visible tweets found for @{username}"}

        print(f"✅ Found {len(tweets_data)} tweets to scrape")
        
        # --- Run tweets in true parallel drivers ---
        # Grab cookies once (so we can reuse them for each new driver)
        cookies = []
        if os.path.exists(self.cookies_path):
            with open(self.cookies_path, "r") as f:
                cookies = json.load(f)

        results = []
        print(f"🚀 Launching {len(tweets_data)} tweets in parallel...")

        with ThreadPoolExecutor(max_workers=len(tweets_data)) as executor:
            futures = {
                executor.submit(self._scrape_single_tweet_with_new_driver, tweet_info, idx + 1, cookies): idx
                for idx, tweet_info in enumerate(tweets_data)
            }

            for future in as_completed(futures):
                results.append(future.result())

        # Sort results by tweet_number to maintain order
        results.sort(key=lambda x: x.get('tweet_number', 0))
        
        print(f"✅ Done scraping {len(results)} tweets in parallel!")
        print(f"\n✅ Successfully scraped {len(results)} tweets from @{username} in parallel!")
        
        return {
            "username": username,
            "total_tweets": len(results),
            "tweets": results
        }
    
    def close(self):
        """Close the browser when done."""
        if self.driver:
            self.driver.quit()
            print("🔴 Browser closed")
            self.driver = None
            self.cookies_loaded = False


# ============================================
# Usage Example
# ============================================
if __name__ == "__main__":
    # Create scraper instance (NOT headless for debugging)
    scraper = TwitterScraper(headless=False)
    
    try:
        # Scrape last 2 tweets from polymarket IN PARALLEL
        print("\n" + "="*50)
        result = scraper.get_latest_tweets_and_replies("polymarket", num_tweets=2)
        
        # Print summary
        print("\n" + "="*60)
        print(f"📊 FINAL SUMMARY")
        print("="*60)
        print(f"Username: {result.get('username')}")
        print(f"Total Tweets Scraped: {result.get('total_tweets', 0)}")
        
        if 'tweets' in result:
            for tweet_data in result['tweets']:
                print(f"\n--- Tweet #{tweet_data['tweet_number']} ---")
                print(f"Tweet: {tweet_data['tweet'][:100]}...")
                print(f"URL: {tweet_data['url']}")
                print(f"Time: {tweet_data['time']}")
                print(f"Comments: {len(tweet_data['comments'])}")
        elif 'error' in result:
            print(f"\n❌ Error: {result['error']}")
        
        # Save to file
        with open("polymarket_last_2_tweets_parallel.json", "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print("\n💾 Full results saved to polymarket_last_2_tweets_parallel.json")
        
    finally:
        # Close browser when completely done
        scraper.close()