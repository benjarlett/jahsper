# Granular Looper Specification

## 🔹 1. Grain-Level Design
Granular playback consists of many small overlapping audio snippets ("grains") played back with control over:
- **Start position (sample offset)**
- **Length (grain duration)**
- **Envelope (fade in/out)**
- **Rate (playback speed)**
- **Pitch shift** (can be tied to rate or independent with phase vocoding/time-stretching)
- **Grain Overlap Strategy** Each grain has a configurable overlap (default 50%). If max grain count is exceeded, oldest grains are dropped or skipped to preserve real-time performance.

**Recommendations:**
- Use **numpy-based buffers** for memory-efficient grain slicing.
- Apply a simple envelope (e.g., Hann window) to each grain.
- Trigger grains via:
  - A grain scheduler (time-based, tempo-locked),
  - Each voice can be muted or paused. Grain scheduler is only active while the voice is unmuted and triggered..

---

## 🔹 2. Voice Model (Single Loop Playback)
A `Voice` handles:
- One audio buffer (loop)
- Grain playback scheduling
- Pitch shift and time stretch
- Volume, panning, filters (optional)
- Each loop may optionally be routed to a specific JACK output channel (e.g., for external mixing or FX). Default is stereo mix.
- Playback mode options: loop, one-shot, retrigger.

### Control Parameters:
- `loop_id`, `file_path`
- `bpm`, `beat_length_ms`
- `start_beat_offset`, `grain_rate_hz`
- `pitch_shift_semitones`
- `tempo_sync: bool`

---

## 🔹 3. Multi-Voice Engine (Song Engine)
Manages multiple `Voice` objects:
- Global tempo (from MIDI tap)
- Shared clock (quantized triggers)
- Per-loop offsets
- Mute/solo per voice
- Crossfade/sync control

```
[Song] --> [Voice1, Voice2, Voice3...]
         ↳ [LoopA] [LoopB] [LoopC]
         ↳ Sync offset, BPM, Key
```

---

## 🔹 4. Loop Metadata
Stored as JSON or embedded in filename.

```json
{
  "filename": "loop1.wav",
  "path": "/loops/dub/",
  "original_key": "C",
  "playback_key": "D",
  "beats": 16,
  "beats_per_bar": 4,
  "bars": 4,
  "stretch_mode": "granular",
  "tags": ["bass", "dub", "slow"]
}
```

---

## 🔹 5. Song Definition
```json
{
  "name": "DubIntro",
  "global_bpm": 72,
  "loops": [
    {"file": "loop1.wav", "channel": 0, "start_offset_beats": 0},
    {"file": "loop2.wav", "channel": 1, "start_offset_beats": 4}
  ]
}
```

---

## 🔹 6. Control Model
- Global MIDI Tap Tempo → Sets BPM
- Per-loop control:
  - Trigger/mute (MIDI CC/note)
  - Pitch shift (encoder or automation)
  - Offset (delayed loop start by X beats)
  - Each loop channel can be toggled by a velocity of above 80 assigned note/channel (configurable threshold). Softer velocities are counted as tap tempo. I will need to use a better keyboard as the current one only outputs a fixed 100 velocity.

---

## 🔹 7. LLM Prompt Template
Use to scaffold code with LLM tools:

> Write a Python class `Grain` that reads from a numpy buffer and plays overlapping grains with Hann envelopes. Then a `Voice` class that uses a `GrainScheduler` to control rate and pitch. Ensure it supports dynamic BPM input and audio playback with `sounddevice`.

---

## ✅ Summary
Benefits:
- Headless + MIDI/web control
- Efficient (numpy/sounddevice)
- Portable (Pi 3/5, Mac, embedded Linux)
- `metadata-driven`

## 🔹 8. Platform and Hardware Context

### Current Development Setup:
- **Target Runtime**: Raspberry Pi 3 Model B with Pisound HAT
- **Operating System**: Raspbian GNU/Linux 11 (Bullseye) with JACK1 and ALSA
- **Audio Interface**: Pisound (card 1)
- **MIDI Input**: USB MIDI Keyboard (during development)
- **Control Computer**: macOS (for development, SSH access, browser control)
- Real-time kernel (optional)
- JACK buffer tuning (essential)
- Consider Pi 5 or other SBCs

### Future Portability Goals:
- Should support moving to other hardware (e.g., Raspberry Pi 5, or embedded Linux platforms with ALSA/JACK).
- Code should be cleanly separated from platform-specific audio/MIDI drivers to allow reuse.

---

## 🔹 9. Web Interface

### UI Features:
- Tap tempo button
- Live BPM display
- Volume control slider
- Loop/channel playback status
- Toggle/mute/start/stop per channel
- Settings form to adjust:
  - Loop assignments
  - Stretch mode
  - Playback key
  - Grain length and rate

### Backend Requirements:
- Flask or FastAPI server with REST + Server-Sent Events (SSE)
- Expose endpoints for:
  - `/tap` → Receives tap input
  - `/bpm_stream` → Sends live BPM updates
  - `/play`, `/stop`, `/volume`, `/set_port`, `/set_output_device`
  - `/loop_config`, `/save_song`, `/load_song`

---

## 🔹 10. MIDI Mapping

### Tempo Input:
- MIDI Note On triggers from a defined **channel** and **note number**
- This tempo tap input replaces manual web tap in performance mode
- Configurable per user preference

```json
{
  "tempo_source": {
    "type": "midi_note",
    "channel": 10,
    "note": 37
  }
}
```

### Double Tap Detection:
- Double tap = two taps within 125ms (configurable)
- Used to start/stop loops per channel
- Mimics a "MIDI switch pedal" behavior
- Optionally distinguish by note velocity

---

## 🔹 11. Configuration and Settings

All runtime options should be editable via:
- Web UI settings page
- JSON file (`settings.json`)
- Live reload without restart

```json
{
  "default_port": "USB MIDI keyboard:USB MIDI keyboard MIDI 1 24:0",
  "default_output_device": 5,
  "tempo_input": {
    "mode": "midi_note",
    "channel": 10,
    "note": 37
  },
  "grain_defaults": {
    "length_ms": 80,
    "rate_hz": 25,
    "overlap": 0.5
  }
}
```
---

---

## 🔹 12. Advanced Considerations

### 1. Grain Scheduling Strategy
- Grains can fire at fixed intervals (e.g., every X ms).
- Optionally sync grain interval to beat subdivisions using a "grain sync" toggle.
- Jitter/randomization can be applied via a slider.
- Pitch-shifted grains will become shorter when played faster (higher pitch).

### 2. Clock & Sync Design
- A global clock is derived from a dedicated MIDI note tap (e.g., a pad on the first MIDI channel).
- Loops can be quantized to start on beats or bars (user-selectable).
- Loops can be resynced mid-play using another MIDI pad.

### 3. Latency Consideration
- MIDI tap input latency should be minimal.
- Buffer sizes and JACK configuration should aim for low latency (details TBD).
- Grains can use "pre-roll" — buffering slightly before playback begins to improve timing.

### 4. Granular Engine Modes
Supported playback modes:
- **Classic**: evenly spaced grains with fixed pitch.
- **Pitch-shifted**: grains play faster/slower and transpose.
- **Random scatter**: grains jitter slightly for texture.
- **Envelope-modulated**: grains change volume or pitch dynamically (e.g., using LFO).

### 5. Audio File Constraints
- Accepts WAV, FLAC, MP3.
- Optionally cache files in the target format for performance.
- Project-wide setting for sample rate and bit depth (e.g., 16bit/48kHz or 8bit/24kHz).
- Max file duration: 64 bars.
- File metadata (tempo, key, bars) must be entered via web UI.
- File upload via web UI is desirable but optional.

### 6. Web UI Notes
- Per-loop controls: Volume, Key, Play/Stop, Sync Mode.
- Global BPM indicator.
- Loop browser or file selector.
- Global volume.
- Granular engine controls:
  - Grain length, rate, pitch glissando, envelope shape.
  - Max grain density before grains are skipped or stolen.
- Settings page:
  - CPU frequency, temperature, performance monitoring.
  - Default settings editor.

### 7. Performance Targets
- Target: 4 voices under 80% CPU usage on Pi 3B.
- Include CPU usage indicator if feasible.
- Auto-throttle grain density when CPU load exceeds 80%.

### 8. Logging & Debugging
- Logging levels: off, info, warning, error (user selectable).
- Global beat counter display.
- Loop start feedback (e.g., "Loop 1 started at beat 17").
- Visual debugging: VU meters, loop playback state.

### 9. Modular Code Goals
- A clean separation between core audio engine, web UI, and MIDI input.
- Main engine logic in an `Engine` class or module.

### 10. Dev/Prod Modes
- **Dev mode**:
  - Verbose logging
  - Test loops available
  - Hot-reload UI

- **Prod mode**:
  - Auto-start with `boot.sh`
  - Watchdog for process recovery
  - Optimized for CPU use
---

## 🔹 13. Storage Model and Metadata

### Hybrid Storage Strategy
This project uses a **hybrid approach** combining JSON files and future database support:

- ✅ **Current Approach (JSON)**:
  - Transparent, human-readable files
  - Easy to version control
  - Each loop and song has a standalone `.json` file
  - Recommended for prototyping, small- to medium-scale use

- 🧠 **Future Option (Database)**:
  - SQLite or similar embedded database
  - Useful for organizing large loop libraries, search/filtering, or multiple users
  - Code should abstract storage layer to support both file and DB backends

### Folder Layout Example
```
/loops/
  loop1.wav
  loop1.json
/songs/
  dub_intro.json
/config/
  settings.json
```

---

## 🔹 14. Example Loop Metadata File

```json
{
  "filename": "loop1.wav",
  "path": "loops/dub/",
  "original_key": "C",
  "playback_key": "D",
  "bpm": 72,
  "beats_per_bar": 4,
  "bars": 4,
  "loop_mode": "loop",
  "output_channel": "main",
  "grain_settings": {
    "length_ms": 85,
    "rate_hz": 30,
    "glissando": 0,
    "envelope": "hann"
  },
  "tags": ["dub", "bassline", "slow"]
}
```

---

## 🔹 15. Dependencies in Use (subject to change)

These are the currently installed or expected packages on the development system:

- Python 3.9
- `mido==1.2.9` — MIDI I/O
- `python-rtmidi==1.4.7` — Backend for mido
- `sounddevice==0.5.2` — Real-time audio playback
- `numpy` — Array manipulation and audio buffers
- `Flask` or `FastAPI` — Web UI server (TBD or switchable)
- `JACK1` and `ALSA` — Audio backend on Raspberry Pi

Dependencies may evolve, especially if:
- WebSocket replaces SSE
- SQLite is introduced
- GUI styling libraries or waveform visualization is added

---

## 🔹 16. License

License: TBD (likely MIT or GPLv3 depending on contribution and future distribution plans).
---

## 🔹 17. Development Plan & Technical Considerations

### Development Phases
This project will be developed incrementally for clarity and testability:

1. **Phase 1** – Single voice, granular playback from static file
2. **Phase 2** – Add tempo-based grain scheduling (tap tempo → BPM)
3. **Phase 3** – Multi-voice architecture with offset support
4. **Phase 4** – MIDI input mapping (tempo + loop control)
5. **Phase 5** – Web UI for live status + control
6. **Phase 6** – Performance tuning, debugging tools, visual UI/UX polish

---

### State Management Across Control Surfaces
- The **core engine** should maintain authoritative playback state.
- Web UI and MIDI inputs send **events**, not direct state changes.
- Use a **message/event bus** or **reactive observer pattern** to keep UI and engine in sync.
- Prevent feedback loops (e.g., MIDI updates UI, which loops back).

---

### Grain Density & Audio Quality
- Default density: ~25 Hz (40 ms interval)
- Provide per-loop **min/max grain density limits**
- Sound quality depends on **grain overlap, source texture**, and pitch/stretch amount
- Visualize grain count per voice if possible

```json
"grain_settings": {
  "rate_hz": 25,
  "length_ms": 80,
  "min_density_hz": 15,
  "max_density_hz": 40
}
```

---

### Latency Budget
- Target **<30ms** total latency from MIDI trigger to grain output
- Account for JACK buffer size (64–128 samples)
- Grain scheduler should **pre-roll** and align to callback boundaries

---

### Performance & Audio Backend Notes
- `sounddevice`: simple and effective for early dev
- `aubio`: consider for future audio analysis (onset, BPM detection)
- `numba` or C extension: explore for grain render loop if CPU-limited
- `pyaudio`: optional alternative for direct ALSA if needed

---

## 🔹 18. Gemini Feedback Integration

### Strengths Confirmed
- Clear modular design (Grain, Voice, Engine)
- Robust platform awareness and performance targets
- Numpy for buffers and hybrid JSON/database model
- Strong attention to real-time audio challenges

### Enhancements Integrated

#### Envelope Variety (Future Feature)
Offer configurable window functions (`hann`, `hamming`, `blackman`) via `envelope_shape` in grain settings.

#### Grain Processing Optimization
- Start with simple pitch-based resampling.
- Postpone phase vocoding until later; may require `numba` or C for performance.
- Consider grain "stealing" (reuse low-impact grains) instead of only oldest-first drop.

#### Optional Filters
- If implemented, use simple low-pass/high-pass IIR filters.
- Avoid complex filters in early versions to preserve CPU.

#### Clock Precision and Scheduling
- Use sample-frame-accurate clock for internal timing.
- Avoid blocking ops inside sounddevice callback.
- Pre-roll grains and align to high-resolution internal time.

#### Memory & GC Management
- Implement grain pooling to avoid real-time allocation spikes.
- Reuse numpy buffers where possible.

#### Error Handling
- Catch and log errors from audio/MIDI/file handling.
- Always fail gracefully (e.g., skip loop, log issue, continue playback).

#### Live Config Reload
- Detect `settings.json` changes at runtime.
- Apply settings in a thread-safe way (e.g., enqueue config update events).

#### Grain Parameter UX
- Visualize overlap %, grain density, and scheduling rate.
- Offer presets or suggest matching `grain_rate` to `grain_length`.

#### Extensible Granular Modes
- Use a Strategy pattern: define separate `GrainScheduler` or `GrainStrategy` classes.
- Keeps the core `Voice` class clean and easy to extend.

#### JACK Config Guidance
- Start with moderate buffer sizes (e.g., 256–512 samples).
- Adjust for lowest stable latency on your system.

#### Web UI Consideration
- Flask: simpler, good for MVP.
- FastAPI: async support for scaling (e.g., live updates + control).
- SSE for status; REST for control.

#### Advanced MIDI Mapping
- Support velocity-sensitive tap (later feature).
- All timing thresholds (e.g., double tap detection) must be configurable.

#### Loop Metadata Enhancements
- Add `stretch_mode`: options might include `granular`, `resample`, or `none`.
- Preserve `original_bpm` and `beat_length_ms` in metadata.

#### Performance Watchdog
- Monitor CPU/memory usage.
- Auto-reduce grain density when under load.

### Implementation Notes
- Plan Phase 1 with 2 voices max, measure CPU usage.
- Upgrade to Pi 5 or real-time kernel if dropouts persist under expected load.


## 🔹 19. Mobile App Expansion Path (Future)

This section outlines a potential future port of the browser-based control interface to a dedicated iOS app. The iPhone becomes a **performance-focused remote control** for the Pi-based engine.

### ❓ Why
- More responsive control during live use
- Portable monitoring while walking the venue
- Enables performance without needing a browser or desktop device

### 🧰 Architecture Compatibility
The current system already uses:
- **HTTP REST endpoints** (`/tap`, `/play`, `/stop`, etc.)
- **Server-Sent Events (SSE)** for live updates (`/bpm_stream`, `/vu_stream`)

This is ideal for mobile interaction and can be used by:
- **React Native** (`fetch()`, EventSource)
- **Swift / SwiftUI** (using `URLSession`, Combine)
- **Progressive Web App (PWA)** (quick deployment)

### 📱 Potential App Features
- Tap tempo
- Play/stop toggle
- Volume + output control
- MIDI port selection
- Live BPM/VU display
- System status readout

### 🔗 Communication Mapping

| Action        | Method | Endpoint             | Payload                 |
|---------------|--------|----------------------|--------------------------|
| Tap Tempo     | POST   | `/tap`               | –                        |
| Play/Stop     | POST   | `/play`, `/stop`     | –                        |
| Volume        | POST   | `/volume`            | `{ volume: Float }`      |
| Output Select | POST   | `/set_output_device` | `{ device_index: Int }`  |
| MIDI Port     | POST   | `/set_port`          | `{ port: String }`       |
| Status Fetch  | GET    | `/system_status`     | –                        |
| BPM/VU Meter  | SSE    | `/bpm_stream`, `/vu_stream` | –                |

### 🚀 Development Path
1. Scaffold React Native app (preferred: Expo)
2. Reuse `main.js` logic for endpoint calls
3. Test live connection to Pi
4. Iterate UI for touch UX
5. Explore Swift/SwiftUI version if deeper iOS features (Bluetooth MIDI) are desired

### 🌐 Enhancements
- Bonjour/ZeroConf for Pi discovery (`patchbox.local`)
- Optional auth system if used beyond local network
- Optimize for big touch targets, dark mode