import numpy as np
from scipy import signal

class CrossoverFilter:
    def __init__(self, sample_rate: int, split_freq: float = 250.0, order: int = 4):
        """
        Initializes a Butterworth crossover filter.
        
        Args:
            sample_rate: Audio sample rate in Hz.
            split_freq: The crossover frequency in Hz (default: 250Hz).
            order: Filter order (default 4 for 24dB/oct slope).
        """
        self.sample_rate = sample_rate
        self.split_freq = split_freq
        self.order = order
        
        nyquist = 0.5 * sample_rate
        norm_freq = split_freq / nyquist
        
        # Generate Second-Order Sections (SOS) for numerical stability
        self.lp_sos = signal.butter(order, norm_freq, btype='lowpass', output='sos')
        self.hp_sos = signal.butter(order, norm_freq, btype='highpass', output='sos')
        
        # State holds previous samples for continuous filtering across blocks
        # Shape matches (n_sections, channels, 2)
        self.z_lp = np.zeros((self.lp_sos.shape[0], 2, 2))
        self.z_hp = np.zeros((self.hp_sos.shape[0], 2, 2))
        
    def reset(self):
        """Resets the internal filter states, necessary when loading a new track."""
        self.z_lp = np.zeros((self.lp_sos.shape[0], 2, 2))
        self.z_hp = np.zeros((self.hp_sos.shape[0], 2, 2))

    def process(self, audio_chunk: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """
        Processes a stereo audio chunk through the crossover.
        
        Args:
            audio_chunk: A numpy array of shape (frames, 2).
            
        Returns:
            A tuple of (low_frequencies, high_frequencies) numpy arrays.
        """
        frames, channels = audio_chunk.shape
        if channels != 2:
            raise ValueError("CrossoverFilter expects a stereo input (2 channels).")

        low_out = np.zeros_like(audio_chunk)
        high_out = np.zeros_like(audio_chunk)
        
        # Process each channel independently with maintained state
        for c in range(channels):
            low_out[:, c], self.z_lp[:, c, :] = signal.sosfilt(
                self.lp_sos, audio_chunk[:, c], zi=self.z_lp[:, c, :]
            )
            high_out[:, c], self.z_hp[:, c, :] = signal.sosfilt(
                self.hp_sos, audio_chunk[:, c], zi=self.z_hp[:, c, :]
            )
            
        return low_out, high_out
