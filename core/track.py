import soundfile as sf
import numpy as np

class Track:
    def __init__(self, file_path: str, title: str = "Unknown", artist: str = "Unknown", bpm: float = 120.0, drop_timestamp: float = 0.0):
        """
        Wraps an audio file to manage block reading and state.
        
        Args:
            file_path: The local filesystem path to the audio file.
        """
        self.file_path = file_path
        self.title = title
        self.artist = artist
        self.bpm = bpm
        self.drop_timestamp = drop_timestamp
        self.sf_file = sf.SoundFile(file_path)
        self.sample_rate = self.sf_file.samplerate
        self.channels = self.sf_file.channels
        self.frames_total = self.sf_file.frames
        
        if self.channels != 2:
            raise ValueError("Only stereo audio files are supported in Phase 1.")
            
        self.done = False

    def get_audio_block(self, blocksize: int, frames_to_read: int = None) -> np.ndarray:
        """
        Reads a block of audio. 
        If frames_to_read is provided, reads that many frames (useful for resampling/pitch shifting).
        Returns exactly frames_to_read or blocksize frames. If EOF is reached, pads with zeros.
        """
        if self.done:
            return np.zeros((blocksize if frames_to_read is None else frames_to_read, self.channels), dtype=np.float32)

        read_size = frames_to_read if frames_to_read is not None else blocksize
        data = self.sf_file.read(read_size, dtype='float32')

        if len(data) < read_size:
            self.done = True
            # Pad the remaining buffer with zeros
            pad_size = read_size - len(data)
            pad = np.zeros((pad_size, self.channels), dtype=np.float32)
            data = np.vstack((data, pad)) if len(data) > 0 else pad

        return data
        
    def get_position(self) -> float:
        """Returns the current playback position in seconds."""
        return self.sf_file.tell() / self.sample_rate
        
    def get_duration(self) -> float:
        """Returns the total duration in seconds."""
        return self.frames_total / self.sample_rate
        
    def set_position(self, seconds: float):
        """Seeks to a specific timestamp in the track."""
        frame_pos = int(seconds * self.sample_rate)
        # Ensure we don't seek past the end
        frame_pos = min(frame_pos, self.frames_total - 1)
        self.sf_file.seek(frame_pos)
        self.done = False

    def close(self):
        """Closes the underlying soundfile handle."""
        self.sf_file.close()
