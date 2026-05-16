import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import os
from dotenv import load_dotenv
import logging
from mutagen.easyid3 import EasyID3
import mutagen

logger = logging.getLogger(__name__)

# Standard pitch class to Camelot Wheel mapping
# (key, mode) -> Camelot String
# Mode 1 = Major, 0 = Minor
CAMELOT_MAP = {
    (0, 1): "8B", (0, 0): "5A",   # C
    (1, 1): "3B", (1, 0): "12A",  # C#/Db
    (2, 1): "10B", (2, 0): "7A",  # D
    (3, 1): "5B", (3, 0): "2A",   # D#/Eb
    (4, 1): "12B", (4, 0): "9A",  # E
    (5, 1): "7B", (5, 0): "4A",   # F
    (6, 1): "2B", (6, 0): "11A",  # F#/Gb
    (7, 1): "9B", (7, 0): "6A",   # G
    (8, 1): "4B", (8, 0): "1A",   # G#/Ab
    (9, 1): "11B", (9, 0): "8A",  # A
    (10, 1): "6B", (10, 0): "3A", # A#/Bb
    (11, 1): "1B", (11, 0): "10A" # B
}

class SpotifyMetadataFetcher:
    def __init__(self):
        load_dotenv()
        client_id = os.getenv("SPOTIFY_CLIENT_ID")
        client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        
        if not client_id or not client_secret:
            raise ValueError("Missing Spotify API credentials in .env")
            
        self.sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
            client_id=client_id,
            client_secret=client_secret
        ))

    def extract_id3(self, file_path: str) -> tuple[str, str, int]:
        """Extracts Title, Artist, and Duration (ms) from local MP3 file."""
        duration_ms = 0
        try:
            audio = EasyID3(file_path)
            title = audio.get('title', ['Unknown Title'])[0]
            artist = audio.get('artist', ['Unknown Artist'])[0]
            # Mutagen provides duration via File
            audio_info = mutagen.File(file_path)
            if audio_info and audio_info.info:
                duration_ms = int(audio_info.info.length * 1000)
            return title, artist, duration_ms
        except mutagen.id3.ID3NoHeaderError:
            # Fallback to filename parsing
            basename = os.path.basename(file_path)
            name_without_ext = os.path.splitext(basename)[0]
            
            # Try to get duration even if no ID3 tags
            try:
                audio_info = mutagen.File(file_path)
                if audio_info and audio_info.info:
                    duration_ms = int(audio_info.info.length * 1000)
            except:
                pass
                
            # Simple heuristic: "Artist - Title"
            if " - " in name_without_ext:
                artist, title = name_without_ext.split(" - ", 1)
                return title.strip(), artist.strip(), duration_ms
            return name_without_ext, "Unknown", duration_ms
        except Exception as e:
            logger.error(f"Error parsing ID3 for {file_path}: {e}")
            return "Unknown", "Unknown", 0

    def search_tracks(self, query: str, limit: int = 10) -> list[dict]:
        """Searches Spotify for tracks based on a query."""
        results = self.sp.search(q=query, type="track", limit=limit)
        tracks = results.get("tracks", {}).get("items", [])
        
        parsed_tracks = []
        for t in tracks:
            parsed_tracks.append({
                "spotify_id": t["id"],
                "title": t["name"],
                "artist": t["artists"][0]["name"] if t["artists"] else "Unknown",
                "duration_ms": t["duration_ms"],
                "preview_url": t.get("preview_url")
            })
        return parsed_tracks

    def fetch_features_by_id(self, track_id: str) -> dict:
        """Fetches Audio Features directly by Spotify ID."""
        try:
            features_list = self.sp.audio_features([track_id])
            if not features_list or not features_list[0]:
                raise ValueError("No features returned")
                
            feat = features_list[0]
            key = feat.get("key", -1)
            mode = feat.get("mode", 1)
            camelot = CAMELOT_MAP.get((key, mode), "Unknown")
            
            return {
                "bpm": feat.get("tempo", 120.0),
                "key": key,
                "mode": mode,
                "camelot": camelot,
                "energy": feat.get("energy", 0.5)
            }
        except Exception as e:
            logger.warning(f"Spotify Audio Features API unavailable (likely deprecated 403 error). Using fallback features. Error: {e}")
            return {
                "bpm": 120.0,
                "key": -1,
                "mode": 1,
                "camelot": "Unknown",
                "energy": 0.5
            }

    def fetch_features(self, title: str, artist: str) -> dict:
        """Searches Spotify and retrieves Audio Features."""
        query = f"track:{title} artist:{artist}"
        if artist == "Unknown":
            query = f"track:{title}"
            
        # 1. Search for the track
        results = self.sp.search(q=query, type="track", limit=1)
        tracks = results.get("tracks", {}).get("items", [])
        
        if not tracks:
            logger.warning(f"Track not found on Spotify: {title} by {artist}")
            return None
            
        track_id = tracks[0]["id"]
        
        # 2. Fetch Audio Features for the track ID
        features_list = self.sp.audio_features([track_id])
        
        if not features_list or not features_list[0]:
            return None
            
        feat = features_list[0]
        
        # Calculate Camelot notation from Spotify's Key & Mode
        key = feat.get("key", -1)
        mode = feat.get("mode", 1)
        camelot = CAMELOT_MAP.get((key, mode), "Unknown")
        
        return {
            "bpm": feat.get("tempo", 120.0),
            "key": key,
            "mode": mode,
            "camelot": camelot,
            "energy": feat.get("energy", 0.5)
        }
