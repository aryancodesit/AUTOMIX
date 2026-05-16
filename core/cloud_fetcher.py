import os
import yt_dlp
import logging

logger = logging.getLogger(__name__)

class CloudFetcher:
    def __init__(self, cache_dir: str = "automix_cache"):
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)
        
    def get_track_path(self, spotify_id: str) -> str:
        """Returns the local path if the track is cached, else None."""
        expected_path = os.path.join(self.cache_dir, f"{spotify_id}.mp3")
        if os.path.exists(expected_path):
            return expected_path
        return None

    def fetch_audio(self, spotify_id: str, query: str) -> str:
        """
        Uses yt-dlp to search YouTube for the query and download the audio.
        Returns the absolute path to the downloaded cache file.
        """
        # First check cache to completely avoid duplicate downloads!
        cached_path = self.get_track_path(spotify_id)
        if cached_path:
            logger.info(f"Track {spotify_id} found in cache. Skipping download.")
            return cached_path
            
        output_template = os.path.join(self.cache_dir, f"{spotify_id}.%(ext)s")
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_template,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'postprocessor_args': [
                '-ar', '44100'
            ],
            'quiet': True,
            'no_warnings': True,
            'default_search': 'ytsearch1:', # Only return top 1 search result
        }

        logger.info(f"Downloading from cloud: {query}...")
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # "ytsearch1: Song Name Artist"
                ydl.extract_info(query, download=True)
                
            final_path = os.path.join(self.cache_dir, f"{spotify_id}.mp3")
            if os.path.exists(final_path):
                logger.info(f"Download complete: {final_path}")
                return final_path
            else:
                logger.error("Download failed to produce mp3 file. Is ffmpeg installed?")
                return None
        except Exception as e:
            logger.error(f"Cloud fetch error: {e}")
            return None
