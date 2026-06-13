import re
import requests
from flask import Flask, jsonify
from flask_cors import CORS
from pymongo import MongoClient

app = Flask(__name__)
CORS(app)

# -------------------------------------------------------------
# UptimeRobot-ന് വേണ്ടിയുള്ള ഹോം പേജ് (ഇത് എറർ 404 മാറ്റാൻ സഹായിക്കും)
# -------------------------------------------------------------
@app.route('/')
def ping():
    return "Bot is Running! 🟢 UptimeRobot is happy! Server is awake."

# -------------------------------------------------------------
# 1. ഒന്നാമത്തെ ഡാറ്റാബേസിന്റെ URL (പഴയത്)
# -------------------------------------------------------------
MONGO_URI_1 = "mongodb+srv://shebin:eOFYZRp6YiCzjtN6@cluster0.hunvcay.mongodb.net/myDatabase?retryWrites=true&w=majority"

# -------------------------------------------------------------
# 2. രണ്ടാമത്തെ ഡാറ്റാബേസിന്റെ URL (VPS-ലേത്)
# -------------------------------------------------------------
# (ഇവിടെ നമ്മൾ കൃത്യമായി 127.0.0.1 എന്ന് കൊടുത്തിട്ടുണ്ട്)
MONGO_URI_2 = "mongodb://Shebin:Shebin%408156@127.0.0.1:27017/admin?authSource=admin"

try:
    # ഒന്നാമത്തെ കണക്ഷൻ
    client1 = MongoClient(MONGO_URI_1)
    db1 = client1['Cluster0'] 
    collection_files = db1['MalluTeaters_files'] 
    
    # രണ്ടാമത്തെ കണക്ഷൻ (VPS)
    client2 = MongoClient(MONGO_URI_2)
    # ഡാറ്റാബേസിന്റെ പേര് Cluster0 അല്ലെങ്കിൽ അത് മാറ്റികൊടുക്കുക
    db2 = client2['Cluster0'] 
    collection_updates = db2['movie_updates'] 
    
    print("Both Databases Connected Successfully! 🔥")
except Exception as e:
    print("MongoDB Connection Error:", e)

TMDB_API_KEY = "bde51ff58b49153b4d8b808558d860de"

# പഴയ ഫയലുകളുടെ പേര് വൃത്തിയാക്കാൻ
def clean_filename(filename):
    name = re.sub(r'MASHOBUC|Flow|A K A', '', filename, flags=re.IGNORECASE)
    name = re.sub(r'(1080p|720p|480p|2160p|10bit|WEBRip|HDRip|x265|x264|HEVC|6CH|\.mkv|\.mp4|\.avi)', '', name, flags=re.IGNORECASE)
    name = re.sub(r'[\.\-\_]', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def fetch_tmdb_data(title):
    url = f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={title}"
    try:
        response = requests.get(url).json()
        if response.get('results'):
            for res in response['results']:
                if res.get('media_type') in ['movie', 'tv']:
                    return res
    except Exception as e:
        print("TMDB Fetch Error:", e)
    return None

@app.route('/api/movies', methods=['GET'])
def get_movies():
    print("Flutter app is requesting movies from BOTH databases...")
    movies_list = []
    
    # 1. MalluTeaters_files എന്ന കളക്ഷനിൽ നിന്നുള്ള ഡാറ്റ (ഏറ്റവും പുതിയ 5 എണ്ണം)
    files_data = list(collection_files.find().sort('_id', -1).limit(5))
    for file in files_data:
        file_name = file.get('file_name', '')
        file_id = file.get('_id', '')
        
        clean_title = clean_filename(file_name)
        tmdb_data = fetch_tmdb_data(clean_title)
        
        if tmdb_data:
            movies_list.append({
                "id": tmdb_data.get('id'),
                "title": tmdb_data.get('title') or tmdb_data.get('name'),
                "poster_path": tmdb_data.get('poster_path'),
                "backdrop_path": tmdb_data.get('backdrop_path'),
                "overview": tmdb_data.get('overview', 'No storyline available.'),
                "release_date": tmdb_data.get('release_date') or tmdb_data.get('first_air_date', 'N/A'),
                "vote_average": tmdb_data.get('vote_average', 0.0),
                "media_type": tmdb_data.get('media_type', 'movie'),
                "file_id": file_id 
            })

    # 2. movie_updates എന്ന കളക്ഷനിൽ നിന്നുള്ള ഡാറ്റ (ഏറ്റവും പുതിയ 5 എണ്ണം)
    updates_data = list(collection_updates.find().sort('_id', -1).limit(5))
    for update in updates_data:
        raw_title = update.get('_id', '')
        clean_title = re.sub(r'\d{4}', '', raw_title).strip()
        
        file_id = ""
        files_array = update.get('files', [])
        if len(files_array) > 0:
            first_file = files_array[0]
            if type(first_file) == dict:
                file_id = first_file.get('file_id', '') or str(first_file)
            else:
                file_id = str(first_file)
        
        tmdb_data = fetch_tmdb_data(clean_title)
        
        if tmdb_data:
            movies_list.append({
                "id": tmdb_data.get('id'),
                "title": tmdb_data.get('title') or tmdb_data.get('name'),
                "poster_path": tmdb_data.get('poster_path'),
                "backdrop_path": tmdb_data.get('backdrop_path'),
                "overview": tmdb_data.get('overview', 'No storyline available.'),
                "release_date": tmdb_data.get('release_date') or tmdb_data.get('first_air_date', 'N/A'),
                "vote_average": tmdb_data.get('vote_average', 0.0),
                "media_type": tmdb_data.get('media_type', 'movie'),
                "file_id": file_id 
            })
            
    return jsonify({"trending": movies_list})

if __name__ == '__main__':
    app.run(debug=True, port=5001, host='0.0.0.0')