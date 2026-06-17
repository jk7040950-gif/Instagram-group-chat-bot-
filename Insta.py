import time
import json
import os
import getpass
import random
import re
from instagrapi import Client

# ================= CONFIGURATION ================= #

cl = Client()

SESSION_FILE = "session.json"
DATA_FILE = "bot_data.json"

# Admin Username (Master Control)
ADMIN_USERNAME = "do_remon9616" 

# Timers & Intervals (in seconds)
FOLLOWER_CHECK_INTERVAL = 600 
TWENTY_FOUR_HOURS = 86400  

# Automated Responses
KEYWORDS = {
    "help": "🤖 Bot Commands: rules, owner, bot, /test, /active.\n(Admin controls: lock GC name, change welcome texts, create groups).",
    "rules": "📜 *Group Rules:*\n1. No spamming (5+ identical messages = Auto Alert) 🚫\n2. No abusive language or fights.\n3. Respect the Admins! 🙏",
    "owner": "👑 *Group Owner:* @do_remon9616. The absolute boss! 😎",
    "bot": "I am the automated moderator for this group. 🤖 Monitoring active members!"
}

GREETINGS = ["hi", "hello", "yo", "wassup", "hey"]

# In-Memory Trackers for Rate Limiting
SPAM_TRACKER = {}
COOLDOWN_TRACKER = {} 

# ================= DATA MANAGEMENT ================= #

def load_data():
    """Loads database from JSON, creates default structure if not found."""
    default_structure = {
        "users": {}, 
        "followed_back": [], 
        "processed_messages": {},
        "config": {
            "welcome_message": "Hey @{}! Welcome 👋",
            "welcome_back_message": "Welcome back @{}! ✨ Glad to see you again."
        },
        "permanent_gc_names": {},
        "activity": {} 
    }
    
    if not os.path.exists(DATA_FILE):
        return default_structure
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Ensure all keys exist to prevent KeyErrors
            for key in default_structure:
                if key not in data:
                    data[key] = default_structure[key]
            return data
    except Exception as e:
        print(f"[ERROR] Failed to load data file: {e}")
        return default_structure

def save_data(data):
    """Saves current state to the JSON database."""
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"[ERROR] Failed to save data: {e}")

# ================= AUTHENTICATION ================= #

def login():
    """Handles Instagram Login via Session File or Fresh Credentials."""
    if os.path.exists(SESSION_FILE):
        try:
            print("[INFO] Attempting login using session file...")
            cl.load_settings(SESSION_FILE)
            cl.get_timeline_feed() 
            print("[SUCCESS] Session loaded successfully.")
            return
        except Exception as e:
            print(f"[WARNING] Existing session expired or invalid: {e}")

    print("[INFO] Initializing fresh login process...")
    username = input("Enter Username: ")
    password = getpass.getpass("Enter Password: ")

    try:
        cl.login(username, password)
        cl.dump_settings(SESSION_FILE)
        print("[SUCCESS] Fresh login successful. Token saved.")
    except Exception as e:
        print(f"[CRITICAL] Login failed: {e}")
        exit(1)

# ================= COMMUNICATION ================= #

def send_message(thread_id, text):
    """Sends a direct message to a specific thread with fast typing simulation."""
    try:
        # Fast typing delay (1 to 2 seconds)
        typing_duration = random.randint(1, 2)
        print(f"[INFO] Simulating typing... ({typing_duration}s)")
        time.sleep(typing_duration)
        
        cl.direct_send(text, thread_ids=[thread_id])
        print(f"[OUTBOUND] Sent to thread [{thread_id}]: '{text}'")
        
    except Exception as e:
        print(f"[ERROR] Failed to send message: {e}")

# ================= AUTOMATION MODULES ================= #

def check_and_follow_back(data):
    """Checks recent followers and auto-follows them back."""
    try:
        print("[TASK] Running follower check cycle...")
        followers = cl.user_followers(cl.user_id, amount=5)
        
        for follower_id, follower_info in followers.items():
            follower_id_str = str(follower_id)
            
            if follower_id_str not in data["followed_back"]:
                print(f"[ALERT] New follower detected: @{follower_info.username}. Initiating follow-back...")
                
                time.sleep(random.randint(2, 4)) # Fast follow back
                cl.user_follow(follower_id)
                print(f"[SUCCESS] Followed back @{follower_info.username}.")
                
                data["followed_back"].append(follower_id_str)
                save_data(data)
                time.sleep(1)
                
    except Exception as e:
        print(f"[ERROR] Follow-back routine failed: {e}")

# ================= CORE EVENT HANDLER ================= #

def handle_thread(thread, data):
    """Processes incoming messages, triggers commands, and applies moderation."""
    global SPAM_TRACKER, COOLDOWN_TRACKER
    try:
        if not thread.messages:
            return

        msg = thread.messages[0]
        sender_id = str(msg.user_id)
        
        # Self-protection rule (Ignore bot's own messages)
        if sender_id == str(cl.user_id):
            return

        msg_text = (msg.text or "").strip()
        msg_text_lower = msg_text.lower()
        msg_id = str(msg.id)
        thread_id = str(thread.id)

        # Duplicate Check (Prevent processing same message twice)
        if data["processed_messages"].get(thread_id) == msg_id:
            return

        is_group = getattr(thread, "is_group", len(thread.users) > 1)

        # Retrieve sender username
        sender_username = "user"
        for u in thread.users:
            if str(u.pk) == sender_id:
                sender_username = u.username
                break

        # Log incoming message
        current_time = time.time()
        readable_time = time.strftime('%I:%M:%S %p', time.localtime(current_time))
        print(f"[{readable_time}] [INBOUND] @{sender_username}: '{msg_text}' | Thread: [{thread_id}]")

        # 📊 ACTIVITY TRACKING (Group Only)
        if is_group:
            if thread_id not in data["activity"]:
                data["activity"][thread_id] = {}
            if sender_id not in data["activity"][thread_id]:
                data["activity"][thread_id][sender_id] = {"username": sender_username, "count": 0}
            
            data["activity"][thread_id][sender_id]["count"] += 1
            data["activity"][thread_id][sender_id]["username"] = sender_username
            save_data(data)

        # 🔐 GC TITLE LOCKER
        if is_group and thread_id in data["permanent_gc_names"]:
            perm_title = data["permanent_gc_names"][thread_id]
            if thread.title != perm_title:
                print(f"[ALERT] Unauthorized title change detected. Reverting to '{perm_title}'.")
                cl.direct_thread_update_title(thread_id, perm_title)
                time.sleep(1)

        # FAST SEEN MARK
        cl.direct_send_seen(thread_id)

        # Log message as processed
        data["processed_messages"][thread_id] = msg_id
        save_data(data)

        # ============ ⏱️ COMMAND RATE LIMITER (30s) ============
        is_keyword_or_cmd = (
            msg_text_lower in KEYWORDS or 
            msg_text_lower in ["/test", "/active"] or 
            msg_text_lower.startswith(("/change ", "create group ", "set -p gc "))
        )
        
        if is_keyword_or_cmd and sender_username != ADMIN_USERNAME:
            last_cmd_time = COOLDOWN_TRACKER.get(sender_id, 0)
            if current_time - last_cmd_time < 30:
                print(f"[WARNING] Rate limit enforced for @{sender_username}.")
                send_message(thread_id, f"⚠️ @{sender_username}, cooldown active. Please wait 30 seconds between commands. ⏳")
                return
            else:
                COOLDOWN_TRACKER[sender_id] = current_time

        # ============ 🚯 ANTI-SPAM MODERATION ============
        if is_group and sender_username != ADMIN_USERNAME:
            if thread_id not in SPAM_TRACKER:
                SPAM_TRACKER[thread_id] = {}
            if sender_id not in SPAM_TRACKER[thread_id]:
                SPAM_TRACKER[thread_id][sender_id] = {"last_text": "", "count": 0}

            user_spam = SPAM_TRACKER[thread_id][sender_id]

            if user_spam["last_text"] == msg_text_lower:
                user_spam["count"] += 1
            else:
                user_spam["last_text"] = msg_text_lower
                user_spam["count"] = 1

            if user_spam["count"] >= 5:
                send_message(thread_id, f"🚫 *⚠️ SPAM ALERT!* 🚫\n\n@{sender_username} has been flagged for repetitive spamming.")
                user_spam["count"] = 0 
                return

        # ============ 👑 ADMIN CONTROL PANEL ============
        if sender_username == ADMIN_USERNAME:
            
            # Create group: create group "Name" @username
            if msg_text_lower.startswith('create group "'):
                match = re.search(r'"([^"]*)"\s*@?([\w\.]+)?', msg_text)
                if match:
                    new_gc_name = match.group(1)
                    target_username = match.group(2)
                    if not target_username:
                        send_message(thread_id, "⚠️ Syntax Error: Use `create group \"Name\" @username`")
                        return
                    try:
                        target_id = cl.user_id_from_username(target_username)
                        cl.direct_thread_create(user_ids=[int(sender_id), int(target_id)], title=new_gc_name)
                        send_message(thread_id, f"✅ Admin Action: Group '{new_gc_name}' created successfully with @{target_username}.")
                        return
                    except Exception as create_err:
                        send_message(thread_id, f"❌ Group creation failed: {create_err}")
                        return

            # Update Welcome Message: /change welcome "Text @{}"
            if msg_text_lower.startswith("/change welcome "):
                match = re.search(r'"([^"]*)"', msg_text)
                if match:
                    data["config"]["welcome_message"] = match.group(1)
                    save_data(data)
                    send_message(thread_id, "✅ Admin Action: Welcome message updated.")
                    return

            # Update Welcome Back Message: /change welcomeback "Text @{}"
            if msg_text_lower.startswith("/change welcomeback "):
                match = re.search(r'"([^"]*)"', msg_text)
                if match:
                    data["config"]["welcome_back_message"] = match.group(1)
                    save_data(data)
                    send_message(thread_id, "✅ Admin Action: Welcome back message updated.")
                    return

            # Set Permanent GC Name: set -p gc name "Title"
            if msg_text_lower.startswith('set -p gc name "'):
                match = re.search(r'"([^"]*)"', msg_text)
                if match and is_group:
                    perm_title = match.group(1)
                    data["permanent_gc_names"][thread_id] = perm_title
                    save_data(data)
                    cl.direct_thread_update_title(thread_id, perm_title)
                    send_message(thread_id, f"🔒 Admin Action: Thread title locked to '{perm_title}'.")
                    return

        # ============ 📊 DYNAMIC ACTIVITY REPORT ============
        if msg_text_lower == "/active" and is_group:
            group_activity = data["activity"].get(thread_id, {})
            if not group_activity:
                send_message(thread_id, "📊 No activity data recorded for this group yet.")
                return
            
            sorted_users = sorted(group_activity.values(), key=lambda x: x['count'], reverse=True)
            active_list = [f"🔥 @{u['username']} ({u['count']} msgs)" for u in sorted_users if u['count'] >= 5]
            silent_list = [f"💤 @{u['username']} ({u['count']} msgs)" for u in sorted_users if u['count'] < 5]
            
            response = "📊 *GROUP ACTIVITY REPORT* 📊\n\n"
            response += "🌟 *Most Active Members:*\n" + ("\n".join(active_list) if active_list else "— None —")
            response += "\n\n😴 *Inactive Members:*\n" + ("\n".join(silent_list) if silent_list else "— None —")
            
            send_message(thread_id, response)
            return

        # ============ SYSTEM DIAGNOSTICS ============
        if msg_text_lower == "/test":
            send_message(thread_id, "🧪 *System Diagnostic:* Server is operating normally. ✅")
            return

        # ============ WELCOME PROTOCOL ============
        if sender_id not in data["users"]:
            print(f"[INFO] New user detected: @{sender_username}.")
            data["users"][sender_id] = {"last_seen": current_time}
            save_data(data)

            welcome_template = data["config"].get("welcome_message", "Welcome @{}! 🙏")
            formatted_msg = welcome_template.format(sender_username) if "{}" in welcome_template else f"{welcome_template} @{sender_username}"
            send_message(thread_id, formatted_msg)
            return 
        else:
            user_info = data["users"][sender_id]
            last_seen_time = user_info.get("last_seen", 0) 

            # Welcome back if returning after 24 hours
            if current_time - last_seen_time > TWENTY_FOUR_HOURS:
                print(f"[INFO] Returning user detected: @{sender_username}.")
                wb_template = data["config"].get("welcome_back_message", "Welcome back @{}! ✨")
                formatted_msg = wb_template.format(sender_username) if "{}" in wb_template else f"{wb_template} @{sender_username}"
                send_message(thread_id, formatted_msg)
            
            data["users"][sender_id]["last_seen"] = current_time
            save_data(data)

        # ============ DM GREETINGS ============
        if not is_group and any(g == msg_text_lower or g in msg_text_lower.split() for g in GREETINGS):
            send_message(thread_id, f"Hello @{sender_username}! 😊 Type 'help' to see available commands.")
            return

        # ============ KEYWORD RESPONDER ============
        for key, reply in KEYWORDS.items():
            if key in msg_text_lower:
                send_message(thread_id, reply)
                return

    except Exception as e:
        print(f"[ERROR] Exception in thread handler: {e}")

# ================= MAIN EXECUTION LOOP (SMART ADAPTIVE POLLING) ================= #

def run():
    """Initializes the daemon process with Smart Adaptive Polling."""
    login()
    print("\n=======================================================")
    print("🚀 INSTAGRAM MODERATOR BOT INITIALIZED")
    print("🧠 Mode: ADAPTIVE SMART SCAN | Features: Anti-Spam, Analytics")
    print("=======================================================\n")
    
    data = load_data()
    last_follower_check = 0 

    # Default sleep time
    current_sleep_time = 15 

    while True:
        try:
            threads = cl.direct_threads(selected_filter="unread")

            if threads:
                # Naya message mila! Speed badha do (Fast Mode Active)
                current_sleep_time = 2  
                print(f"[ACTIVE] Message detected! Switching to FAST MODE ({current_sleep_time}s delay).")
                
                for thread in threads:
                    handle_thread(thread, data)
                    time.sleep(0.5) 
            else:
                # Group shant hai. Speed slow kar do (Save API requests)
                # Dheere-dheere sleep time badhayega maximum 20 seconds tak
                if current_sleep_time < 20:
                    current_sleep_time += 2 
                print(f"[STANDBY] No new messages. Sleeping for {current_sleep_time}s...")

            # Follower Check routine
            current_time = time.time()
            if current_time - last_follower_check > FOLLOWER_CHECK_INTERVAL:
                check_and_follow_back(data)
                last_follower_check = current_time

            # Bot so jayega (Adaptive time ke hisaab se)
            time.sleep(current_sleep_time)

        except KeyboardInterrupt:
            print("\n[SHUTDOWN] Bot terminated by user.")
            break
        except Exception as e:
            print(f"[CRITICAL] Unexpected loop error: {e}. Retrying in 15s...")
            time.sleep(15)

if __name__ == "__main__":
    run()
  
