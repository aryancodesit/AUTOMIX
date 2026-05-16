import librosa
import numpy as np
import logging

logger = logging.getLogger(__name__)

# Camelot Wheel Mapping based on pitch class (0=C, 1=C#, etc.) and mode
# Format: CAMELOT_KEYS[mode][pitch_class]
CAMELOT_KEYS = {
    0: ["5A", "12A", "7A", "2A", "9A", "4A", "11A", "6A", "1A", "8A", "3A", "10A"], # Minor
    1: ["8B", "3B", "10B", "5B", "12B", "7B", "2B", "9B", "4B", "11B", "6B", "1B"]  # Major
}

class LocalAnalyzer:
    """Uses Librosa to extract BPM, Key, and Energy locally from audio files."""
    
    @staticmethod
    def analyze(file_path: str) -> dict:
        logger.info(f"Starting deep DSP analysis for {file_path}...")
        try:
            # Load the audio (loads at 22050 by default which is fine for analysis)
            # Analyze first 120s to ensure we catch the drop
            y, sr = librosa.load(file_path, duration=120) 
            
            # 1. BPM / Tempo
            onset_env = librosa.onset.onset_strength(y=y, sr=sr)
            tempo, _ = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr)
            bpm = float(tempo[0]) if isinstance(tempo, np.ndarray) else float(tempo)
            
            # 2. Key / Camelot
            chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
            # Sum the chroma features over time
            chroma_sum = np.sum(chroma, axis=1)
            # The pitch class with the highest magnitude is our root note
            root_note = int(np.argmax(chroma_sum))
            
            # Simple Mode detection (Major vs Minor) based on 3rd interval
            # Major 3rd is +4 semitones, Minor 3rd is +3 semitones
            major_3rd = (root_note + 4) % 12
            minor_3rd = (root_note + 3) % 12
            
            major_score = chroma_sum[major_3rd]
            minor_score = chroma_sum[minor_3rd]
            
            mode = 1 if major_score > minor_score else 0
            camelot = CAMELOT_KEYS[mode][root_note]
            
            # 3. Energy (RMS) and Drop Detection
            rms = librosa.feature.rms(y=y)[0]
            
            # Find the drop (highest sustained energy peak)
            drop_frame = int(np.argmax(rms))
            drop_timestamp = round(float(librosa.frames_to_time(drop_frame, sr=sr)), 2)
            
            # Normalize energy
            mean_rms = float(np.mean(rms))
            energy = min(max(mean_rms * 3.0, 0.0), 1.0)
            
            logger.info(f"Analysis Complete: {bpm} BPM | Key: {camelot} | Drop: {drop_timestamp}s | Energy: {energy}")
            
            return {
                "bpm": round(bpm, 1),
                "key": root_note,
                "mode": mode,
                "camelot": camelot,
                "energy": round(energy, 2),
                "drop_timestamp": drop_timestamp
            }
        except Exception as e:
            logger.error(f"Error analyzing {file_path}: {e}")
            return {
                "bpm": 120.0,
                "key": -1,
                "mode": 1,
                "camelot": "Unknown",
                "energy": 0.5,
                "drop_timestamp": 15.0
            }
