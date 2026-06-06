import re
import os
import telebot
from pymongo import MongoClient
from flask import Flask
from threading import Thread

# 1. API Token
TOKEN = "8651739298:AAGhkzfT9EDiR16Zy1yg4cJWyqWoR9AKV3I"
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# 2. Database Manager (3 Clusters Load Balancing)
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
        # 5000 ഫയലുകൾക്ക് ശേഷം അടുത്ത ക്ലസ്റ്ററിലേക്ക് മാറുന്നു
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
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Vibe+ Indexing Bot Active! 🚀\nചാനലിലെ ഫയലുകൾ തനിയെ ഇൻഡക്സ് ചെയ്യപ്പെടുന്നു.")

@bot.channel_post_handler(content_types=['video', 'document'])
def auto_indexing(message):
    file_info = message.video or message.document
    if not file_info: return
    
    original_name = file_info.file_name or "Unknown Movie"
    
    # പേര് ക്ലീൻ ചെയ്യൽ
    clean_name = re.sub(r'(@\w+)|(_FOX_)|(www\.\S+)|(t\.me\S+)', '', original_name, flags=re.IGNORECASE)
    clean_name = " ".join(clean_name.replace('_', ' ').replace('[', '').replace(']', '').split())

    # ഡാറ്റാബേസിൽ സേവ് ചെയ്യൽ
    db_manager.insert_movie({"title": clean_name, "file_id": file_info.file_id})
    
    # സ്റ്റോറേജ് സ്റ്റാറ്റസ് എടുക്കുന്നു
    used, avail = db_manager.get_db_stats()
    
    # സ്റ്റാറ്റസ് മെസ്സേജ് ബോക്സ്
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
        print(f"Error: {e}")

# 5. Start Services
if __name__ == "__main__":
    Thread(target=run_web_server).start()
    print("Bot & Web Server Started Successfully! 🚀")
    bot.infinity_polling()