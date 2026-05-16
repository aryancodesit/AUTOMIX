from fastapi import FastAPI, BackgroundTasks, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import asyncio
import logging
import os

from metadata.database import Database
from metadata.spotify_api import SpotifyMetadataFetcher
from metadata.smart_reorder import SmartReorder
from metadata.local_analyzer import LocalAnalyzer
from core.cloud_fetcher import CloudFetcher
from core.mixer import Mixer
from core.audio_engine import AudioEngine
from core.track import Track

logging.getLogger("spotipy").setLevel(logging.ERROR)
logger = logging.getLogger(__name__)

app = FastAPI()
db = Database()

try:
    spotify = SpotifyMetadataFetcher()
except ValueError as e:
    logger.warning(f"Spotify features disabled: {e}")
    spotify = None

reorder_engine = SmartReorder()
cloud_fetcher = CloudFetcher()

# Global State
mixer = Mixer()
audio_engine = AudioEngine(mixer)
audio_engine.start()

current_playlist = []
current_track_idx = 0
automix_active = False

@app.on_event("startup")
async def start_automix_loop():
    asyncio.create_task(automix_loop())

async def automix_loop():
    global current_track_idx, automix_active
    while True:
        await asyncio.sleep(0.5)
        if not automix_active or not mixer.deck_a or mixer.is_paused or mixer.is_crossfading:
            continue
            
        pos_A = mixer.deck_a.get_position()
        dur_A = mixer.deck_a.get_duration()
        drop_A = mixer.deck_a.drop_timestamp
        
        # We transition 60 seconds after Track A's drop, or 10 seconds before it ends
        target_time = min(drop_A + 60.0, dur_A - 10.0)
        
        if pos_A >= target_time and mixer.deck_b:
            logger.info("Automix: Time to transition!")
            
            # Prepare Track B to hit the drop exactly when crossfade ends
            crossfade_dur = 8.0
            drop_B = mixer.deck_b.drop_timestamp
            start_B = max(0.0, drop_B - crossfade_dur)
            mixer.deck_b.set_position(start_B)
            
            # Trigger Crossfade
            await do_crossfade()

# Mount static directory for UI
os.makedirs("static", exist_ok=True)
os.makedirs("static/css", exist_ok=True)
os.makedirs("static/js", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

class ScanRequest(BaseModel):
    directory: str

class SearchRequest(BaseModel):
    query: str

class DownloadRequest(BaseModel):
    spotify_id: str
    title: str
    artist: str
    duration_ms: int

class AutomixRequest(BaseModel):
    track_ids: list[int]

class SeekRequest(BaseModel):
    position_sec: float

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.post("/api/scan_directory")
async def scan_directory(req: ScanRequest):
    directory = req.directory
    if not os.path.isdir(directory):
        return {"error": "Invalid directory"}
        
    added = 0
    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(('.mp3', '.wav', '.flac')):
                file_path = os.path.join(root, file)
                
                # Check DB
                cursor = db.conn.cursor()
                cursor.execute("SELECT id FROM Tracks WHERE file_path = ?", (file_path,))
                if cursor.fetchone():
                    continue
                    
                title, artist, duration_ms = spotify.extract_id3(file_path) if spotify else ("Unknown", "Unknown", 0)
                track_id = db.add_track(file_path, title, artist, duration_ms)
                
                if spotify:
                    features = spotify.fetch_features(title, artist)
                    if features:
                        db.add_audio_features(
                            track_id, 
                            features['bpm'], 
                            features['key'], 
                            features['mode'], 
                            features['camelot'], 
                            features['energy']
                        )
                added += 1
                
    return {"message": f"Scanned and added {added} new tracks.", "added": added}

@app.post("/api/search")
async def search_spotify(req: SearchRequest):
    if not spotify:
        return {"error": "Spotify not configured."}
    results = spotify.search_tracks(req.query, limit=10)
    return {"results": results}

@app.post("/api/download")
async def download_track(req: DownloadRequest):
    if not spotify:
        return {"error": "Spotify not configured."}
        
    # Check if already in DB
    cursor = db.conn.cursor()
    cursor.execute("SELECT id FROM Tracks WHERE title = ? AND artist = ?", (req.title, req.artist))
    existing = cursor.fetchone()
    if existing:
        return {"message": "Track already in library", "track_id": existing['id']}

    # 1. Fetch Audio via yt-dlp
    search_query = f"{req.title} {req.artist} official audio"
    local_path = cloud_fetcher.fetch_audio(req.spotify_id, search_query)
    
    if not local_path:
        return {"error": "Failed to download audio track."}
        
    # 2. Add to DB
    track_id = db.add_track(local_path, req.title, req.artist, req.duration_ms)
    
    # 3. Add Audio Features using Librosa Local Analysis
    features = LocalAnalyzer.analyze(local_path)
    if features:
        db.add_audio_features(
            track_id, 
            features['bpm'], 
            features['key'], 
            features['mode'], 
            features['camelot'], 
            features['energy'],
            features['drop_timestamp']
        )
        
    return {"message": "Track downloaded and analyzed successfully", "track_id": track_id}

@app.get("/api/tracks")
async def get_tracks():
    return db.get_all_tracks()

@app.post("/api/automix")
async def trigger_automix(req: AutomixRequest):
    global current_playlist, current_track_idx, automix_active
    track_ids = req.track_ids
    if not track_ids:
        return {"error": "No tracks provided"}
        
    all_tracks = db.get_all_tracks()
    selected_tracks = [t for t in all_tracks if t['id'] in track_ids]
    
    # Smart Reorder
    ordered = reorder_engine.sort_playlist(selected_tracks)
    
    current_playlist = ordered
    current_track_idx = 0
    automix_active = True
    
    # Load first track immediately
    if current_playlist:
        t0 = current_playlist[0]
        t = Track(t0['file_path'], t0['title'], t0['artist'], t0.get('bpm', 120.0), t0.get('drop_timestamp', 0.0))
        # Start A exactly at its drop for immediate impact!
        t.set_position(t0.get('drop_timestamp', 0.0))
        mixer.load_track_a(t)
        
        # Preload second track
        if len(current_playlist) > 1:
            t1 = current_playlist[1]
            t2 = Track(t1['file_path'], t1['title'], t1['artist'], t1.get('bpm', 120.0), t1.get('drop_timestamp', 0.0))
            mixer.load_track_b(t2)
            
    return {"message": "Automix started", "playlist": current_playlist}

@app.post("/api/crossfade")
async def do_crossfade():
    global current_track_idx
    mixer.start_crossfade(duration_sec=8.0, bass_swap=True)
    if current_playlist and current_track_idx < len(current_playlist) - 1:
        current_track_idx += 1
        # Preload the next NEXT track if available into B
        if current_track_idx < len(current_playlist) - 1:
            t_next = current_playlist[current_track_idx + 1]
            t2 = Track(t_next['file_path'], t_next['title'], t_next['artist'], t_next.get('bpm', 120.0), t_next.get('drop_timestamp', 0.0))
            mixer.load_track_b(t2)
    return {"message": "Crossfade triggered!"}

@app.post("/api/next")
async def skip_next():
    global current_track_idx
    if current_playlist and current_track_idx < len(current_playlist) - 1:
        current_track_idx += 1
        mixer.is_crossfading = False
        t_curr = current_playlist[current_track_idx]
        t = Track(t_curr['file_path'], t_curr['title'], t_curr['artist'], t_curr.get('bpm', 120.0), t_curr.get('drop_timestamp', 0.0))
        mixer.load_track_a(t)
        if current_track_idx < len(current_playlist) - 1:
            t_next = current_playlist[current_track_idx + 1]
            t2 = Track(t_next['file_path'], t_next['title'], t_next['artist'], t_next.get('bpm', 120.0), t_next.get('drop_timestamp', 0.0))
            mixer.load_track_b(t2)
        return {"message": "Skipped to next"}
    return {"error": "End of queue"}

@app.post("/api/prev")
async def skip_prev():
    global current_track_idx
    if current_playlist and current_track_idx > 0:
        current_track_idx -= 1
        mixer.is_crossfading = False
        t_curr = current_playlist[current_track_idx]
        t = Track(t_curr['file_path'], t_curr['title'], t_curr['artist'], t_curr.get('bpm', 120.0), t_curr.get('drop_timestamp', 0.0))
        mixer.load_track_a(t)
        t_next = current_playlist[current_track_idx + 1]
        t2 = Track(t_next['file_path'], t_next['title'], t_next['artist'], t_next.get('bpm', 120.0), t_next.get('drop_timestamp', 0.0))
        mixer.load_track_b(t2)
        return {"message": "Skipped to prev"}
    return {"error": "Start of queue"}

@app.post("/api/pause")
async def toggle_pause():
    is_paused = mixer.toggle_pause()
    return {"is_paused": is_paused}

@app.post("/api/seek")
async def seek_track(req: SeekRequest):
    mixer.seek(req.position_sec)
    return {"message": "Seeked"}

@app.get("/api/state")
async def get_state():
    state = {
        "is_playing": mixer.deck_a is not None and not mixer.is_paused,
        "is_paused": mixer.is_paused,
        "position": mixer.deck_a.get_position() if mixer.deck_a else 0,
        "duration": mixer.deck_a.get_duration() if mixer.deck_a else 0,
        "title": getattr(mixer.deck_a, 'title', 'Unknown') if mixer.deck_a else "",
        "artist": getattr(mixer.deck_a, 'artist', 'Unknown') if mixer.deck_a else ""
    }
    return state

@app.post("/api/stop")
async def stop_playback():
    global automix_active
    automix_active = False
    if mixer.deck_a: mixer.deck_a.close(); mixer.deck_a = None
    if mixer.deck_b: mixer.deck_b.close(); mixer.deck_b = None
    mixer.is_paused = False
    return {"message": "Playback stopped"}
