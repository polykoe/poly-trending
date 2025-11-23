import requests
import json
import time

class Twitter135Checker:
    def __init__(self, rapidapi_key):
        """Initialize with RapidAPI key for Twitter135 API"""
        self.rapidapi_key = rapidapi_key
        self.headers = {
            "x-rapidapi-host": "twitter135.p.rapidapi.com",
            "x-rapidapi-key": rapidapi_key
        }
        self.base_url = "https://twitter135.p.rapidapi.com"
        print("✅ Twitter135 API initialized\n")
    
    def _make_request(self, endpoint, params=None):
        """Helper method to make API requests with error handling"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=15)
            
            if response.status_code == 200:
                return response.json(), None
            elif response.status_code == 403:
                return None, "Not subscribed. Go to: https://rapidapi.com/Glavier/api/twitter135"
            elif response.status_code == 429:
                return None, "Rate limit exceeded. Wait 1 hour or upgrade."
            elif response.status_code == 401:
                return None, "Invalid API key."
            else:
                return None, f"Error {response.status_code}: {response.text[:200]}"
        except requests.exceptions.Timeout:
            return None, "Request timeout"
        except Exception as e:
            return None, f"Exception: {str(e)}"
    
    def get_tweet_details(self, tweet_id):
        """Get tweet details"""
        print(f"📄 Fetching tweet details...")
        
        params = {
            "id": tweet_id,
            "rankingMode": "Relevance"
        }
        
        data, error = self._make_request("/v2/TweetDetail/", params)
        
        if error:
            print(f"   ❌ {error}")
            return None
        
        print(f"   ✅ Tweet fetched successfully")
        return data
    
    def get_tweet_likers(self, tweet_id, count=100):
        """Get users who liked a tweet"""
        params = {
            "id": tweet_id,
            "count": count
        }
        
        data, error = self._make_request("/v2/Favoriters/", params)
        
        if error:
            print(f"   ❌ {error}")
            return None
        
        return data
    
    def get_tweet_retweeters(self, tweet_id, count=100):
        """Get users who retweeted a tweet"""
        params = {
            "id": tweet_id,
            "count": count
        }
        
        data, error = self._make_request("/v2/Retweeters/", params)
        
        if error:
            print(f"   ❌ {error}")
            return None
        
        return data
    
    def extract_users_from_response(self, data):
        """Extract usernames from Twitter135 API response"""
        usernames = []
        
        try:
            # Navigate through the complex nested structure
            if 'data' in data:
                timeline_data = data['data']
                
                # Method 1: Direct user_results array
                if 'user_results' in timeline_data:
                    user_results = timeline_data['user_results']
                    
                    for user_item in user_results:
                        if 'result' in user_item:
                            result = user_item['result']
                            if 'legacy' in result and 'screen_name' in result['legacy']:
                                usernames.append(result['legacy']['screen_name'])
                
                # Method 2: Check all keys for timeline structures
                for key, value in timeline_data.items():
                    if isinstance(value, dict):
                        # Check for timeline structure
                        if 'timeline' in value:
                            timeline = value['timeline']
                            if 'instructions' in timeline:
                                instructions = timeline['instructions']
                                
                                for instruction in instructions:
                                    # TimelineAddEntries
                                    if instruction.get('type') == 'TimelineAddEntries':
                                        entries = instruction.get('entries', [])
                                        
                                        for entry in entries:
                                            content = entry.get('content', {})
                                            
                                            # Check itemContent
                                            if 'itemContent' in content:
                                                item = content['itemContent']
                                                if 'user_results' in item:
                                                    user_result = item['user_results'].get('result', {})
                                                    if 'legacy' in user_result:
                                                        screen_name = user_result['legacy'].get('screen_name')
                                                        if screen_name and screen_name not in usernames:
                                                            usernames.append(screen_name)
                                    
                                    # TimelineAddToModule (alternative structure)
                                    elif instruction.get('type') == 'TimelineAddToModule':
                                        module_items = instruction.get('moduleItems', [])
                                        for module_item in module_items:
                                            item = module_item.get('item', {}).get('itemContent', {})
                                            if 'user_results' in item:
                                                user_result = item['user_results'].get('result', {})
                                                if 'legacy' in user_result:
                                                    screen_name = user_result['legacy'].get('screen_name')
                                                    if screen_name and screen_name not in usernames:
                                                        usernames.append(screen_name)
        except Exception as e:
            print(f"   ⚠️  Error extracting users: {e}")
        
        return usernames
    
    def check_user_liked(self, tweet_id, username):
        """Check if a specific user liked a tweet"""
        print(f"❤️  Checking if @{username} liked the tweet...")
        
        likers_data = self.get_tweet_likers(tweet_id)
        
        if not likers_data:
            return False
        
        # Save response to file for debugging
        with open('likers_response.json', 'w') as f:
            json.dump(likers_data, f, indent=2)
        print(f"   💾 Response saved to likers_response.json for debugging")
        
        usernames = self.extract_users_from_response(likers_data)
        
        if usernames:
            print(f"   📊 Found {len(usernames)} likers")
            
            for screen_name in usernames:
                if screen_name.lower() == username.lower():
                    print(f"   ✅ @{username} LIKED this tweet!")
                    return True
            
            print(f"   ❌ @{username} not found in likers")
            print(f"   👥 First few likers: {', '.join(['@' + u for u in usernames[:5]])}")
        else:
            print(f"   ⚠️  Could not extract usernames from response")
        
        return False
    
    def check_user_retweeted(self, tweet_id, username):
        """Check if a specific user retweeted a tweet"""
        print(f"🔄 Checking if @{username} retweeted the tweet...")
        
        retweeters_data = self.get_tweet_retweeters(tweet_id)
        
        if not retweeters_data:
            return False
        
        # Save response to file for debugging
        with open('retweeters_response.json', 'w') as f:
            json.dump(retweeters_data, f, indent=2)
        print(f"   💾 Response saved to retweeters_response.json for debugging")
        
        usernames = self.extract_users_from_response(retweeters_data)
        
        if usernames:
            print(f"   📊 Found {len(usernames)} retweeters")
            
            for screen_name in usernames:
                if screen_name.lower() == username.lower():
                    print(f"   ✅ @{username} RETWEETED this tweet!")
                    return True
            
            print(f"   ❌ @{username} not found in retweeters")
            print(f"   👥 First few retweeters: {', '.join(['@' + u for u in usernames[:5]])}")
        else:
            print(f"   ⚠️  Could not extract usernames from response")
        
        return False
    
    def check_user_replied(self, tweet_id, username):
        """Check if user replied to a tweet"""
        print(f"💬 Checking if @{username} replied...")
        
        # Get tweet details which includes replies/conversation
        params = {
            "id": tweet_id,
            "rankingMode": "Relevance"
        }
        
        data, error = self._make_request("/v2/TweetDetail/", params)
        
        if not data:
            print(f"   ❌ Could not fetch tweet conversation")
            return False
        
        # Save response for debugging
        with open('replies_response.json', 'w') as f:
            json.dump(data, f, indent=2)
        print(f"   💾 Response saved to replies_response.json for debugging")
        
        try:
            reply_usernames = []
            found_user = False
            
            if 'data' in data:
                # Navigate to conversation thread
                conversation = data['data'].get('threaded_conversation_with_injections_v2', {})
                instructions = conversation.get('instructions', [])
                
                for instruction in instructions:
                    if instruction.get('type') == 'TimelineAddEntries':
                        entries = instruction.get('entries', [])
                        
                        for entry in entries:
                            entry_id = entry.get('entryId', '')
                            content = entry.get('content', {})
                            
                            # Skip the original tweet (conversationthread-xxxxx)
                            if 'conversationthread' in entry_id and content.get('entryType') == 'TimelineTimelineItem':
                                item_content = content.get('itemContent', {})
                                
                                if item_content.get('itemType') == 'TimelineTweet':
                                    tweet_results = item_content.get('tweet_results', {})
                                    result = tweet_results.get('result', {})
                                    
                                    # Check if it's a retweet wrapper
                                    if result.get('__typename') == 'Tweet':
                                        # Get user info
                                        core = result.get('core', {})
                                        user_results = core.get('user_results', {})
                                        user_result = user_results.get('result', {})
                                        legacy_user = user_result.get('legacy', {})
                                        screen_name = legacy_user.get('screen_name', '')
                                        
                                        # Get tweet info to check if it's a reply
                                        tweet_legacy = result.get('legacy', {})
                                        in_reply_to_id = tweet_legacy.get('in_reply_to_status_id_str')
                                        
                                        if screen_name:
                                            # Check if this tweet is a reply (has in_reply_to_status_id_str)
                                            if in_reply_to_id:
                                                reply_usernames.append(screen_name)
                                                
                                                if screen_name.lower() == username.lower():
                                                    print(f"   ✅ @{username} REPLIED to this tweet!")
                                                    found_user = True
                                                    return True
            
            if reply_usernames:
                print(f"   📊 Found {len(reply_usernames)} replies")
                print(f"   👥 Users who replied: {', '.join(['@' + u for u in reply_usernames[:10]])}")
            else:
                print(f"   ⚠️  No replies found in conversation")
            
            if not found_user:
                print(f"   ❌ @{username} did not reply to this tweet")
            
            return False
            
        except Exception as e:
            print(f"   ❌ Error checking replies: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def check_all_interactions(self, tweet_id, username):
        """Check all types of interactions"""
        print(f"\n{'='*70}")
        print(f"🐦 Twitter Interaction Checker - Twitter135 API")
        print(f"{'='*70}")
        print(f"Tweet ID: {tweet_id}")
        print(f"Username: @{username}")
        print(f"{'='*70}\n")
        
        # Get tweet details first
        tweet_data = self.get_tweet_details(tweet_id)
        print()
        
        # Check interactions
        results = {
            "liked": self.check_user_liked(tweet_id, username),
            "retweeted": self.check_user_retweeted(tweet_id, username),
            "replied": self.check_user_replied(tweet_id, username)
        }
        
        results["interacted"] = any(results.values())
        
        return results


# Usage
if __name__ == "__main__":
    print("🐦 Twitter Interaction Checker - Twitter135 API")
    print("="*70)
    print("Using RapidAPI's Twitter135 (500 requests/month free)")
    print("="*70 + "\n")
    
    # YOUR API KEY
    RAPIDAPI_KEY = "e0e87d011dmsh0c5a8c685f5eaacp1dcb65jsna68c96b0a0eb"
    
    # IMPORTANT: Subscribe first at https://rapidapi.com/Glavier/api/twitter135
    
    # Initialize checker
    checker = Twitter135Checker(RAPIDAPI_KEY)
    
    # YOUR PARAMETERS
    tweet_id = "1986731165391147431"
    username = "Fcrypto794"
    
    # Check interactions
    results = checker.check_all_interactions(tweet_id, username)
    
    # Display results
    print(f"\n{'='*70}")
    print(f"📊 FINAL RESULTS")
    print(f"{'='*70}")
    print(f"  ❤️  Liked:      {'✅ YES' if results['liked'] else '❌ NO'}")
    print(f"  🔄 Retweeted:  {'✅ YES' if results['retweeted'] else '❌ NO'}")
    print(f"  💬 Replied:    {'✅ YES' if results['replied'] else '❌ NO'}")
    print(f"  {'='*70}")
    print(f"  ✨ Interacted: {'✅ YES' if results['interacted'] else '❌ NO'}")
    print(f"{'='*70}\n")
    
    print("📝 Notes:")
    print("  • Check likers_response.json, retweeters_response.json, and replies_response.json")
    print("  • Free tier: 500 requests/month")
    print("  • Subscribe at: https://rapidapi.com/Glavier/api/twitter135")
    print("="*70)