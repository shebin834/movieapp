import os
import re
import asyncio

# --- Python 3.14 Event Loop Fix (Ithu nirbandhamayi mukalil thanne venam) ---
try:
    loop = asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
# -------------------------------------------------------------------------

from aiohttp import web
from pyrogram import Client, filters, idle
import motor.motor_asyncio

# ==========================================
# Bhagam 1: Configuration (Cloud & Local Setup)
# ==========================================
API_ID = int(os.environ.get("API_ID", 32557254))
API_HASH = os.environ.get("API_HASH", "448bb61d4711ef33afff691ac1bb0931")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8651739298:AAGhkzfT9EDiR16Zy1yg4cJWyqWoR9AKV3I")
PORT = int(os.environ.get("PORT", 8080))

# ==========================================
# Bhagam 2: Multi-Database Manager
# ==========================================
class AsyncDatabaseManager:
    def __init__(self):
        self.uris = [
            os.environ.get("DB_URI_1", "mongodb+srv://kallankunnanshebin_db_user:7EjwaJf1FaMswq3J@cluster1.t8j1kyz.mongodb.net/?retryWrites=true&w=majority"),
            os.environ.get("DB_URI_2", "mongodb+srv://kallankunnanshebin_db_user:w91sXki0wzXw1GqM@cluster0.cfmo2un.mongodb.net/?retryWrites=true&w=majority"),
            os.environ.get("DB_URI_3", "mongodb+srv://kallankunnanshebin_db_user:zUCiR3LalM3D7aKf@cluster0.gavp9rl.mongodb.net/?retryWrites=true&w=majority")
        ]
        self.current_idx = 0
        self.client = motor.motor_asyncio.AsyncIOMotorClient(self.uris[self.current_idx])
        self.db = self.client['VibePlusDB']
        self.collection = self.db['movies']

    async def insert_movie(self, movie_data):
        duplicate = await self.collection.find_one({"title": movie_data['title']})
        if duplicate:
            return None 

        count = await self.collection.count_documents({})
        if count >= 5000:
            if self.current_idx < len(self.uris) - 1:
                self.current_idx += 1
                self.client = motor.motor_asyncio.AsyncIOMotorClient(self.uris[self.current_idx])
                self.db = self.client['VibePlusDB']
                self.collection = self.db['movies']
                
        await self.collection.insert_one(movie_data)
        return True

    async def get_total_count(self):
        return await self.collection.count_documents({})

    async def delete_all_movies(self):
        for uri in self.uris:
            try:
                temp_client = motor.motor_asyncio.AsyncIOMotorClient(uri)
                temp_db = temp_client['VibePlusDB']
                await temp_db['movies'].delete_many({})
            except Exception as e:
                print(f"Error clearing DB: {e}")
        
        self.current_idx = 0
        self.client = motor.motor_asyncio.AsyncIOMotorClient(self.uris[self.current_idx])
        self.db = self.client['VibePlusDB']
        self.collection = self.db['movies']

db_manager = AsyncDatabaseManager()

# ==========================================
# Bhagam 3: Telegram Bot (Indexer Logic)
# ==========================================
bot = Client("Fox_Stream_Bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

@bot.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    welcome_text = (
        "Halo! Vibe+ Indexing Bot active aanu 🚀\n\n"
        "Enne ningalude backup channel-il admin aakkuka. "
        "Puthiya files varumbol njan athu thaniye clean cheythu database-il save cheytholam."
    )
    await message.reply_text(welcome_text)

@bot.on_message(filters.command("deleteall") & filters.private)
async def delete_all_command(client, message):
    await message.reply_text("Database empty aakkan thudangunnu... Dayavayi kurachu samayam wait cheyyuka.")
    await db_manager.delete_all_movies()
    await message.reply_text("Database motham empty aayi! Ippo paka clean aanu. Ini puthiya files dhairyamayi forward cheyyam. 🚀")

@bot.on_message(filters.channel & (filters.document | filters.video))
async def auto_indexing(client, message):
    file_info = message.video or message.document
    if not file_info: return
    
    original_name = getattr(file_info, "file_name", "Unknown Movie")
    file_size = getattr(file_info, "file_size", 0) 
    
    junk_pattern = r'(?i)(\[YDF\]|\[MCU\]|@\w+|www\.\S+|t\.me\S+|\bMM\b|\bfox\b|\bKC\b|@)'
    clean_name = re.sub(junk_pattern, ' ', original_name)
    clean_name = clean_name.replace('_', ' ').replace('-', ' ').replace('[', '').replace(']', '')
    clean_name = re.sub(r'(?i)\.(mkv|mp4|avi|webm)$', '', clean_name)
    clean_name = " ".join(clean_name.split())

    result = await db_manager.insert_movie({
        "title": clean_name, 
        "file_id": file_info.file_id,
        "file_size": file_size
    })
    
    if result is None:
        try:
            await message.delete()
        except Exception as e:
            pass
        return
    
    total_db = await db_manager.get_total_count()
    size_mb = round(file_size / (1024 * 1024), 2)
    
    status_msg = f"""
╔═════ FORWARD STATUS ═════╗
║ 🟢 SUCCESSFULLY INDEXED
║ 📁 FILE: {clean_name[:20]}...
║ 💾 SIZE: {size_mb} MB
║ 🔑 FILE ID: `{file_info.file_id}`
║ 🔗 TEST LINK: http://localhost:8080/watch/{file_info.file_id}
║ 📊 TOTAL IN DB: {total_db}
║ 🌐 STATUS: COMPLETED
╚═════════════════════════╝
    """
    try:
        await message.reply_text(status_msg)
    except Exception as e:
        pass

# ==========================================
# Bhagam 4: Web Server (Streaming Logic)
# ==========================================

# --- Puthiya Ping Route (UptimeRobot-nu vendi) ---
async def ping(request):
    return web.Response(text="Bot is Running! 🟢 UptimeRobot is happy! Server is awake.")

async def handle_stream(request):
    file_id = request.match_info.get('file_id')
    movie_data = await db_manager.collection.find_one({"file_id": file_id})
    
    if not movie_data:
        return web.Response(text="Movie not found in database!", status=404)
        
    file_size = movie_data.get("file_size", 0)
    range_header = request.headers.get('Range', '')
    
    offset = 0
    limit = file_size - 1
    
    if range_header:
        range_match = re.match(r'bytes=(\d+)-(\d*)', range_header)
        if range_match:
            offset = int(range_match.group(1))
            if range_match.group(2):
                limit = int(range_match.group(2))
                
    chunk_size = limit - offset + 1
    
    response = web.StreamResponse(
        status=206 if range_header else 200,
        headers={
            'Content-Type': 'video/mp4',
            'Accept-Ranges': 'bytes',
            'Content-Range': f'bytes {offset}-{limit}/{file_size}',
            'Content-Length': str(chunk_size),
        }
    )
    
    await response.prepare(request)
    
    chunk_size_tg = 1024 * 1024 
    aligned_offset = offset - (offset % chunk_size_tg)
    skip_bytes = offset - aligned_offset
    bytes_sent = 0
    
    try:
        async for chunk in bot.stream_media(file_id, offset=aligned_offset):
            if skip_bytes > 0:
                chunk = chunk[skip_bytes:]
                skip_bytes = 0
                
            if bytes_sent + len(chunk) > chunk_size:
                chunk = chunk[:chunk_size - bytes_sent]
                
            await response.write(chunk)
            bytes_sent += len(chunk)
            
            if bytes_sent >= chunk_size:
                break
    except Exception as e:
        pass
        
    return response

async def start_web_server():
    app = web.Application()
    
    # നമ്മൾ ഉണ്ടാക്കിയ പിംഗ് റൂട്ട് ഇവിടെ ചേർത്തു!
    app.router.add_get('/', ping) 
    app.router.add_get('/watch/{file_id}', handle_stream)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    print(f"✅ Web Server Started on Port {PORT}")

# ==========================================
# Bhagam 5: System Start Cheyyunnu!
# ==========================================
async def main():
    print("Starting Fox Stream System with Database Wipe Option...")
    await start_web_server()
    await bot.start()
    print("✅ System is Fully Online!")
    await idle()
    await bot.stop()

if __name__ == "__main__":
    loop.run_until_complete(main())
