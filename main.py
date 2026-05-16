import asyncio
import logging
import sys
import os
from core.track import Track
from core.mixer import Mixer
from core.audio_engine import AudioEngine

# Configure standardized logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("AutomixApp")

async def main():
    logger.info("Initializing Automix Engine Phase 1")
    
    # 1. Setup Audio Environment
    sample_rate = 44100
    mixer = Mixer(sample_rate=sample_rate)
    engine = AudioEngine(mixer, sample_rate=sample_rate, block_size=2048)
    
    # Require two tracks as CLI arguments for the test
    if len(sys.argv) < 3:
        logger.error("Usage: python main.py <track1_path> <track2_path>")
        sys.exit(1)
        
    track1_path = sys.argv[1]
    track2_path = sys.argv[2]
    
    if not os.path.exists(track1_path) or not os.path.exists(track2_path):
        logger.error("Provided track paths do not exist. Please check your file paths.")
        sys.exit(1)
        
    # 2. Load Tracks
    logger.info(f"Loading Deck A: {track1_path}")
    track1 = Track(track1_path)
    mixer.load_track_a(track1)
    
    logger.info(f"Loading Deck B: {track2_path}")
    track2 = Track(track2_path)
    mixer.load_track_b(track2)
    
    # 3. Start PortAudio Stream
    engine.start()
    
    try:
        # Let Track 1 play undisturbed for 5 seconds
        logger.info("Playing Track 1 for 5 seconds before initiating crossfade...")
        await asyncio.sleep(5.0)
        
        # Trigger the 8-second Bass Swap Crossfade natively
        logger.info("Triggering 8-second Bass Swap Crossfade...")
        mixer.start_crossfade(duration_sec=8.0, bass_swap=True)
        
        # Wait for the crossfade to complete, and let Track 2 play for a bit
        await asyncio.sleep(15.0)
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
    finally:
        engine.stop()
        if mixer.deck_a:
            mixer.deck_a.close()
        if mixer.deck_b:
            mixer.deck_b.close()
        logger.info("Shutdown complete.")

if __name__ == "__main__":
    try:
        # Run the asyncio event loop
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
