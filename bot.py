import re
import os
import telebot
from pymongo import MongoClient
from flask import Flask
from threading import Thread

# 1. API Token & Flask Setup
TOKEN = "8651739298:AAGhkzfT9EDiR16Zy1yg4cJWyqWoR9AKV3I"
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# 2. Database Manager (3 Clusters & Duplicate Check)
class DatabaseManager:
    def __init__(self):
        self.uris = [
            "mongodb+srv://kallankunnanshebin_db_user:7EjwaJf1FaMswq3J@cluster1.t8j1kyz.mongodb.net/?retryWrites=true&w=majority",
            "mongodb+srv://kallankunnanshebin_db_user:w91sXki0wzXw1GqM@cluster0.cfmo2un.mongodb.net/?retryWrites=true&w=majority",
            "mongodb+srv://kallankunnanshebin_db_user:zUCiR3LalM3D7aKf@cluster0.gavp9rl.mongodb.net/?retryWrites=true&w=majority"
        ]
        self.current_idx = 0
        self.client = MongoClient(self.uris[self.current_idx])
        self.db = self.client['VibePlusDB']
        self.collection = self.db['movies']

    def insert_movie(self, movie_data):
        # ഡ്യൂപ്ലിക്കേറ്റ് ഫയൽ ആണോ എന്ന് ചെക്ക് ചെയ്യുന്നു
        duplicate = self.collection.find_one({"title": movie_data['title']})
        if duplicate:
            return None # ഓൾറെഡി ഉണ്ടെങ്കിൽ സേവ് ചെയ്യില്ല

        # 5000 ഫയലുകൾക്ക് ശേഷം അടുത്ത ഡാറ്റാബേസിലേക്ക് മാറുന്നു
        if self.collection.count_documents({}) >= 5000:
            if self.current_idx < len(self.uris) - 1:
                self.current_idx += 1
                self.client = MongoClient(self.uris[self.current_idx])
                self.db = self.client['VibePlusDB']
                self.collection = self.db['movies']
                
        return self.collection.insert_one(movie_data)

    def get_db_stats(self):
        try:
            stats = self.db.command("dbStats")
            used = stats['dataSize'] / (1024 * 1024)
            limit = 512 # MongoDB Free Tier Limit (MB)
            return used, limit - used
        except:
            return 0.0, 512.0

db_manager = DatabaseManager()

# 3. Web Server (Render 24/7 Keep Alive)
@app.route('/')
def home():
    return "Vibe+ Bot Indexing Engine is running 24/7!"

def run_web_server():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

# 4. Bot Handlers

# ബോട്ടിനെ ചാനലിൽ ആഡ് ചെയ്യുമ്പോൾ അഡ്മിന് PM അയക്കാൻ
@bot.my_chat_member_handler()
def handle_bot_added(message):
    if message.new_chat_member.status in ['administrator', 'member']:
        try:
            bot.send_message(message.from_user.id, f"✅ Bot successfully connected in channel: {message.chat.title}")
        except Exception as e:
            print("PM Error (Admin needs to start the bot in private first):", e)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Vibe+ Indexing Bot Active! 🚀\nചാനലിലെ ഫയലുകൾ തനിയെ ഇൻഡക്സ് ചെയ്യപ്പെടുന്നു.")

# ചാനലിൽ പുതിയ ഫയലുകൾ വരുമ്പോൾ
@bot.channel_post_handler(content_types=['video', 'document'])
def auto_indexing(message):
    file_info = message.video or message.document
    if not file_info: return
    
    original_name = file_info.file_name or "Unknown Movie"
    
    # പേര് ക്ലീൻ ചെയ്യൽ
    clean_name = re.sub(r'(@\w+)|(_FOX_)|(www\.\S+)|(t\.me\S+)', '', original_name, flags=re.IGNORECASE)
    clean_name = " ".join(clean_name.replace('_', ' ').replace('[', '').replace(']', '').split())

    # ഡാറ്റാബേസിൽ സേവ് ചെയ്യാൻ ശ്രമിക്കുന്നു
    result = db_manager.insert_movie({"title": clean_name, "file_id": file_info.file_id})
    
    # ഡ്യൂപ്ലിക്കേറ്റ് ആണെങ്കിൽ ചാനലിൽ നിന്ന് തനിയെ ഡിലീറ്റ് ചെയ്യും
    if result is None:
        try:
            bot.delete_message(message.chat.id, message.message_id)
        except Exception as e:
            print("Delete Error (Bot needs Delete Messages permission):", e)
        return
    
    # പുതിയ ഫയൽ ആണെങ്കിൽ സ്റ്റോറേജ് ഡീറ്റെയിൽസ് എടുക്കുന്നു
    used, avail = db_manager.get_db_stats()
    
    # സ്റ്റാറ്റസ് മെസ്സേജ് ചാനലിലേക്ക് അയക്കുന്നു
    status_msg = f"""
╔═════ FORWARD STATUS ═════╗
║ 🟢 SUCCESSFULLY INDEXED
║ 📁 FILE: {clean_name[:20]}...
║ 📊 TOTAL IN DB: {db_manager.collection.count_documents({})}
║ 💾 USED: {used:.2f} MB
║ 🟢 AVAIL: {avail:.2f} MB
║ 🌐 STATUS: COMPLETED
╚═════════════════════════╝
    """
    try:
        bot.send_message(message.chat.id, status_msg)
    except Exception as e:
        print(f"Status Message Error:", e)

# 5. Start Services
if __name__ == "__main__":
    Thread(target=run_web_server).start()
    print("Bot & Web Server Started Successfully! 🚀")
    bot.infinity_polling()
