# AUTOMIX 🎧

AUTOMIX is a professional-grade, fully automated DJ engine built entirely in Python. It features real-time DSP, cloud streaming capabilities, and machine-learning audio analysis to dynamically sequence and beatmatch tracks exactly like a club DJ.

## Core Features

### ☁️ Cloud Streaming & Caching
Instead of managing a local folder of MP3s, Automix acts as a hybrid cloud player:
- **Spotify Metadata Search:** Search for any song directly in the UI. Automix queries Spotify for the official track title and artist.
- **`yt-dlp` High-Fidelity Fetching:** Once you click "Get", the backend intelligently scrapes the highest quality audio block from YouTube and rigidly resamples it to 44.1kHz.
- **Smart Caching:** Songs are permanently cached in the local library using their unique Spotify ID to prevent duplicate downloads.

### 🧠 Deep DSP Analysis (`librosa`)
Because standard APIs no longer provide deep audio feature data, Automix analyzes the raw audio wave locally using machine learning techniques:
- **Onset Detection (BPM):** Calculates the precise tempo of the track.
- **Chroma Feature Extraction (Key):** Detects the dominant pitch class and maps it to the **Camelot Wheel**.
- **RMS Energy & Drop Detection:** Calculates the track's overall energy and mathematically identifies the exact timestamp of the "Drop" (the highest sustained energy peak).

### 🎛️ Smart Reorder Algorithm
Never manually sequence a playlist again. Automix analyzes your selected tracks and sorts them using professional DJ logic:
- **Harmonic Mixing:** Ensures adjacent tracks share compatible Camelot Keys (e.g., transitioning from `8A` to `9A` or `8B`).
- **Energy Flow:** Prevents jarring transitions from extremely high-energy EDM tracks down to slow acoustic songs.

### 🎚️ Advanced Automixing & Transitions
The real-time `numpy` audio engine executes flawless transitions automatically:
- **Automated Phrasing:** The engine plays a track until 60 seconds after its "Drop", then triggers the crossfade.
- **Drop Sync:** The incoming track is silently cued up in the background so that its own "Drop" hits flawlessly at the exact moment the crossfade finishes.
- **Vinyl Tempo Ramping (Dynamic Resampling):** During an 8-second crossfade window, the outgoing track's waveform is physically stretched or compressed in real-time to mathematically match the incoming track's BPM.
- **Bass-Swap & Filter Masking:** The crossover isolates frequencies below 250Hz. The bass is cleanly swapped at the 50% mark, while the outgoing track is washed out with a Low-Pass Filter sweep to prevent melodic key clashing.

---

## Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/aryancodesit/AUTOMIX.git
   cd AUTOMIX
   ```

2. **Install system dependencies:**
   Automix requires `ffmpeg` for extracting audio and `yt-dlp` processing.
   ```powershell
   # Windows (PowerShell)
   winget install ffmpeg
   ```

3. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Variables:**
   Create a `.env` file in the root directory and add your Spotify Developer credentials:
   ```env
   SPOTIFY_CLIENT_ID=your_client_id_here
   SPOTIFY_CLIENT_SECRET=your_client_secret_here
   ```

## Running the Engine

Start the FastAPI backend and real-time audio callback loop:
```bash
python -m uvicorn api.server:app --reload
```

Open your browser to `http://127.0.0.1:8000`. 
1. Search for songs using the top-left panel.
2. Click **Get** to download and analyze them.
3. Select your tracks in the library and click **Generate Automix**. 
4. Sit back and enjoy the mix.

---

## 🚀 Future Enhancements

The Automix architecture is designed to be highly extensible. Planned future updates include:

- **Native Desktop Application:** Migrating the HTML/FastAPI frontend to a premium native desktop app using **PyQt6** or **CustomTkinter** for a true, standalone DJ software experience complete with live waveform rendering.
- **Mix Exporting:** Adding a background recorder to capture the real-time `numpy` output buffer and render your entire 1-hour Automix session directly to a `.wav` or `.mp3` file to share with friends.
- **Live Beatgrid Sync:** Upgrading the `librosa` onset detection to calculate full track beatgrids, completely eliminating tempo drift during extremely long crossfades.
- **WebSocket Streaming:** Modifying the engine to stream the raw PCM audio bytes over WebSockets directly to the browser, transforming Automix from a local "Living Room Jukebox" into a globally accessible web app.

---
> **Note:** This project is fully operable but still actively under development. Feel free to fork, explore, and contribute! `#audiophile`

*Built for the ultimate automated listening experience.*
