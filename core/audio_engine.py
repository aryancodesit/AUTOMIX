import sounddevice as sd
import numpy as np
import logging
from core.mixer import Mixer

logger = logging.getLogger(__name__)

class AudioEngine:
    def __init__(self, mixer: Mixer, sample_rate: int = 44100, block_size: int = 2048):
        """
        Manages the non-blocking sounddevice callback thread.
        """
        self.mixer = mixer
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.stream = None
        
    def _audio_callback(self, outdata: np.ndarray, frames: int, time, status: sd.CallbackFlags):
        """
        High-priority C-level callback invoked natively by PortAudio via sounddevice.
        """
        if status:
            logger.warning(f"Audio Callback Status: {status}")
            
        try:
            # Request the next block from the mixer
            audio_block = self.mixer.get_audio_block(frames)
            outdata[:] = audio_block
        except Exception as e:
            # If any exception occurs in the audio thread, fail safely with silence
            logger.error(f"Error in audio callback: {e}")
            outdata[:] = 0.0

    def start(self):
        """Starts the audio output stream."""
        logger.info("Starting Audio Engine Stream...")
        self.stream = sd.OutputStream(
            samplerate=self.sample_rate,
            channels=2,
            callback=self._audio_callback,
            blocksize=self.block_size,
            dtype='float32'
        )
        self.stream.start()

    def stop(self):
        """Stops the audio output stream."""
        if self.stream:
            logger.info("Stopping Audio Engine Stream...")
            self.stream.stop()
            self.stream.close()
