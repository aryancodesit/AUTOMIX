import numpy as np
import logging
from typing import Optional
from core.track import Track
from core.filters import CrossoverFilter

logger = logging.getLogger(__name__)

class Mixer:
    def __init__(self, sample_rate: int = 44100):
        """
        The Master Mixer responsible for tracking Decks A/B, computing crossfades,
        and applying DSP techniques like Bass Swapping.
        """
        self.sample_rate = sample_rate
        self.deck_a: Optional[Track] = None
        self.deck_b: Optional[Track] = None
        
        # Crossfade states
        self.is_crossfading = False
        self.crossfade_duration = 0.0
        self.crossfade_progress = 0.0
        self.bass_swap = False
        self.is_paused = False
        
        self.master_volume = 1.0
        
        # Each deck gets its own crossover filter to maintain independent DSP state
        self.crossover_a = CrossoverFilter(sample_rate)
        self.crossover_b = CrossoverFilter(sample_rate)

    def load_track_a(self, track: Track):
        """Loads a track into Deck A."""
        self.deck_a = track
        self.crossover_a.reset()

    def load_track_b(self, track: Track):
        """Loads a track into Deck B."""
        self.deck_b = track
        self.crossover_b.reset()

    def toggle_pause(self) -> bool:
        """Toggles playback state and returns the new is_paused state."""
        self.is_paused = not self.is_paused
        return self.is_paused
        
    def seek(self, position_sec: float):
        """Seeks the active deck A to a new position."""
        if self.deck_a:
            self.deck_a.set_position(position_sec)

    def start_crossfade(self, duration_sec: float = 8.0, bass_swap: bool = True):
        """Initiates a crossfade from Deck A to Deck B."""
        if not self.deck_a or not self.deck_b:
            logger.warning("Both Deck A and Deck B must be loaded to trigger a crossfade.")
            return
            
        self.is_crossfading = True
        self.crossfade_duration = duration_sec
        self.crossfade_progress = 0.0
        self.bass_swap = bass_swap
        logger.info(f"Started crossfade: {duration_sec}s, bass_swap={bass_swap}")

    def _apply_crossfade(self, frames: int, out_buffer: np.ndarray):
        """Processes the crossfade logic for a block of audio."""
        if not self.deck_a or not self.deck_b:
            self.is_crossfading = False
            return
            
        # Compute curve progress range for this block
        start_progress = self.crossfade_progress
        end_progress = min(1.0, start_progress + (frames / self.sample_rate) / self.crossfade_duration)
        
        # Linearly interpolate weights for every frame in the buffer
        progress_array = np.linspace(start_progress, end_progress, frames, endpoint=False)
        self.crossfade_progress = end_progress
        
        # Retrieve raw audio blocks
        audio_a = self.deck_a.read_frames(frames)
        audio_b = self.deck_b.read_frames(frames)
        
        if self.bass_swap:
            # 1. Split audio into Lows (<250Hz) and Highs (>250Hz)
            lows_a, highs_a = self.crossover_a.process(audio_a)
            lows_b, highs_b = self.crossover_b.process(audio_b)
            
            # 2. Bass Swap Logic: 
            # Outgoing Track A loses its bass linearly during the FIRST half of the fade.
            # Incoming Track B gains its bass linearly during the SECOND half of the fade.
            bass_weight_a = np.where(progress_array < 0.5, 1.0 - (progress_array * 2), 0.0)
            bass_weight_b = np.where(progress_array >= 0.5, (progress_array - 0.5) * 2, 0.0)
            
            # Highs/Mids crossfade linearly over the entire duration
            highs_weight_a = 1.0 - progress_array
            highs_weight_b = progress_array
            
            # 3. Apply weights (broadcasting across stereo channels)
            bass_a_mixed = lows_a * bass_weight_a[:, np.newaxis]
            highs_a_mixed = highs_a * highs_weight_a[:, np.newaxis]
            
            bass_b_mixed = lows_b * bass_weight_b[:, np.newaxis]
            highs_b_mixed = highs_b * highs_weight_b[:, np.newaxis]
            
            # 4. Recombine frequencies
            mixed_a = bass_a_mixed + highs_a_mixed
            mixed_b = bass_b_mixed + highs_b_mixed
            
            out_buffer[:] = mixed_a + mixed_b
            
        else:
            # Standard linear volume crossfade
            weight_a = 1.0 - progress_array
            weight_b = progress_array
            
            out_buffer[:] = (audio_a * weight_a[:, np.newaxis]) + (audio_b * weight_b[:, np.newaxis])
            
        # Check completion condition
        if self.crossfade_progress >= 1.0:
            self.is_crossfading = False
            
            # Perform Deck Swap: B becomes A
            self.deck_a.close()
            self.deck_a = self.deck_b
            self.deck_b = None
            
            self.crossover_a = self.crossover_b
            self.crossover_b = CrossoverFilter(self.sample_rate)
            logger.info("Crossfade complete. Deck B is now Deck A.")

    def get_audio_block(self, frames: int) -> np.ndarray:
        """Called by the AudioEngine callback to fetch the next audio block."""
        out_buffer = np.zeros((frames, 2), dtype=np.float32)
        
        if self.is_paused:
            return out_buffer
            
        if self.is_crossfading:
            self._apply_crossfade(frames, out_buffer)
        elif self.deck_a:
            out_buffer = self.deck_a.read_frames(frames)
            
        return out_buffer * self.master_volume
