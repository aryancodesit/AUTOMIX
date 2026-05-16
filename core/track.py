import soundfile as sf
import numpy as np

class Track:
    def __init__(self, file_path: str, title: str = "Unknown", artist: str = "Unknown"):
        """
        Wraps an audio file to manage block reading and state.
        
        Args:
            file_path: The local filesystem path to the audio file.
        """
        self.file_path = file_path
        self.title = title
        self.artist = artist
        self.sf_file = sf.SoundFile(file_path)
        self.sample_rate = self.sf_file.samplerate
        self.channels = self.sf_file.channels
        self.frames_total = self.sf_file.frames
        
        if self.channels != 2:
            raise ValueError("Only stereo audio files are supported in Phase 1.")
            
        self.done = False

    def read_frames(self, num_frames: int) -> np.ndarray:
        """
        Reads `num_frames` from the file. If EOF is reached, pads the rest with zeros.
        """
        if self.done:
            return np.zeros((num_frames, self.channels), dtype=np.float32)
            
        data = self.sf_file.read(num_frames, dtype='float32')
        frames_read = data.shape[0]
        
        if frames_read < num_frames:
            self.done = True
            # Pad with zeros if we reached EOF
            padded = np.zeros((num_frames, self.channels), dtype=np.float32)
            padded[:frames_read, :] = data
            return padded
            
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
