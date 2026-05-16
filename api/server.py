from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import logging
import os

from metadata.database import Database
from metadata.spotify_api import SpotifyMetadataFetcher
from metadata.smart_reorder import SmartReorder
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

# Global Audio Engine State
mixer = Mixer()
audio_engine = AudioEngine(mixer)
audio_engine.start()

# Mount static directory for UI
os.makedirs("static", exist_ok=True)
os.makedirs("static/css", exist_ok=True)
os.makedirs("static/js", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

class ScanRequest(BaseModel):
    directory: str

class AutomixRequest(BaseModel):
    track_ids: list[int]

class SeekRequest(BaseModel):
    position_sec: float

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    with open("static/index.html", "r") as f:
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

@app.get("/api/tracks")
async def get_tracks():
    return db.get_all_tracks()

@app.post("/api/automix")
async def trigger_automix(req: AutomixRequest):
    track_ids = req.track_ids
    if not track_ids:
        return {"error": "No tracks provided"}
        
    all_tracks = db.get_all_tracks()
    selected_tracks = [t for t in all_tracks if t['id'] in track_ids]
    
    # Smart Reorder
    ordered = reorder_engine.sort_playlist(selected_tracks)
    
    # Load first track immediately
    if ordered:
        t = Track(ordered[0]['file_path'], ordered[0]['title'], ordered[0]['artist'])
        mixer.load_track_a(t)
        
        # Preload second track
        if len(ordered) > 1:
            t2 = Track(ordered[1]['file_path'], ordered[1]['title'], ordered[1]['artist'])
            mixer.load_track_b(t2)
            
    return {"message": "Automix started", "playlist": ordered}

@app.post("/api/crossfade")
async def do_crossfade():
    mixer.start_crossfade(duration_sec=8.0, bass_swap=True)
    return {"message": "Crossfade triggered!"}

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
    if mixer.deck_a: mixer.deck_a.close(); mixer.deck_a = None
    if mixer.deck_b: mixer.deck_b.close(); mixer.deck_b = None
    mixer.is_paused = False
    return {"message": "Playback stopped"}
