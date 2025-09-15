#!/usr/bin/env python3
"""
Debug AI processing for the test post.
"""

import sys
import os

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.crud import get_db_connection, botsettings_get
from config import get_bot_runner_settings
from ai.openai_service import decide_and_summarize_for_post

def debug_ai_processing():
    """Debug the AI processing for the test post."""
    
    # Get AI prompts (same as the bot uses)
    conn = get_db_connection()
    if not conn:
        print("❌ Cannot connect to database")
        return
    
    try:
        # Get prompts exactly like the bot does
        default_system, default_user, _, _ = get_bot_runner_settings()
        system_prompt = botsettings_get(conn, 'bot_system', default_system)
        user_prompt = botsettings_get(conn, 'bot_user', default_user)
        
        print("🤖 AI DEBUG - Testing Your Post")
        print("=" * 60)
        print(f"📝 SYSTEM PROMPT:")
        print(f'"{system_prompt}"')
        print()
        print(f"👤 USER PROMPT:")
        print(f'"{user_prompt}"')
        print()
        
        # Create the exact post dict that would be sent to AI
        test_post = {
            'content': "hey, looking for Google ads marketing services",
            'author': 'Anonymous',
            'url': 'https://www.facebook.com/groups/spauskcia/posts/123456'
        }
        
        print(f"📄 TEST POST:")
        print(f"Content: \"{test_post['content']}\"")
        print(f"Author: {test_post['author']}")
        print(f"URL: {test_post['url']}")
        print()
        
        print("🔄 Calling AI...")
        
        # Call AI exactly like the bot does
        is_relevant, summary = decide_and_summarize_for_post(
            test_post, 
            system_prompt,
            user_prompt
        )
        
        print("=" * 60)
        print("🤖 AI RESPONSE:")
        print(f"✅ Relevant: {is_relevant}")
        print(f"📝 Summary: \"{summary}\"")
        print("=" * 60)
        
        if is_relevant:
            print("🎉 SUCCESS! AI correctly identified this as relevant!")
            print("🔔 This should trigger a Telegram notification!")
        else:
            print("❌ FAILURE! AI incorrectly marked this as NOT relevant!")
            print("🚫 This explains why no Telegram notification was sent!")
            print()
            print("🔍 POSSIBLE ISSUES:")
            print("1. AI prompt is too restrictive")
            print("2. AI model is malfunctioning") 
            print("3. Prompt formatting is wrong")
            print("4. JSON parsing is broken")
        
    except Exception as e:
        print(f"❌ Error during AI debug: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    debug_ai_processing() 