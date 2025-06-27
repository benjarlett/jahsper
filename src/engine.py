import numpy as np
import sounddevice as sd
import soundfile as sf

class Grain:
    """A single audio grain."""
    def __init__(self, buffer, start_pos, length, envelope):
        self.buffer = buffer
        self.start_pos = start_pos
        self.length = length
        self.envelope = envelope
        self.current_pos = 0

    def get_chunk(self, size):
        """Get the next chunk of audio data from the grain."""
        remaining = self.length - self.current_pos
        if remaining == 0:
            return None
        
        chunk_size = min(size, remaining)
        chunk = self.buffer[self.start_pos + self.current_pos : self.start_pos + self.current_pos + chunk_size]
        
        # Apply envelope
        chunk *= self.envelope[self.current_pos : self.current_pos + chunk_size]
        
        self.current_pos += chunk_size
        return chunk

class Voice:
    """A single voice that plays a loop using granular synthesis."""
    def __init__(self, audio_file, grain_length_ms=80, grain_rate_hz=25):
        self.audio_data, self.samplerate = self.load_audio(audio_file)
        self.grain_length = int(self.samplerate * (grain_length_ms / 1000))
        self.grain_rate_hz = grain_rate_hz
        self.hann_window = np.hanning(self.grain_length)
        self.active_grains = []
        self.grain_scheduler = GrainScheduler(self.samplerate, self.grain_rate_hz, self.spawn_grain)
        self.position = 0

    def load_audio(self, audio_file):
        """Loads an audio file."""
        data, samplerate = sf.read(audio_file)
        return data, samplerate

    def spawn_grain():
        """Spawns a new grain."""
        start_pos = self.position
        grain = Grain(self.audio_data, start_pos, self.grain_length, self.hann_window)
        self.active_grains.append(grain)
        
        # Advance position for the next grain
        self.position += int(self.grain_length * 0.5) # 50% overlap
        if self.position + self.grain_length >= len(self.audio_data):
            self.position = 0 # Loop back to the beginning

    def get_audio_chunk(self, chunk_size):
        """Generates the next chunk of audio data."""
        self.grain_scheduler.tick()
        
        output_buffer = np.zeros(chunk_size, dtype=np.int16)
        
        for grain in self.active_grains[:]:
            chunk = grain.get_chunk(chunk_size)
            if chunk is not None:
                output_buffer[:len(chunk)] += chunk.astype(np.int16)
            else:
                self.active_grains.remove(grain)
                
        return output_buffer

class GlobalClock:
    """Manages the global tempo and beat."""
    def __init__(self, samplerate, bpm):
        self.samplerate = samplerate
        self.bpm = bpm
        self.samples_per_beat = (self.samplerate * 60) / self.bpm
        self.current_sample = 0
        self.current_beat = 0

    def tick(self, frames):
        self.current_sample += frames
        self.current_beat = self.current_sample / self.samples_per_beat

class GrainScheduler:
    """Schedules the creation of new grains based on tempo."""
    def __init__(self, samplerate, grain_rate_hz, spawn_callback):
        self.samplerate = samplerate
        self.grain_rate_hz = grain_rate_hz
        self.spawn_callback = spawn_callback
        self.samples_per_grain_interval = self.samplerate / self.grain_rate_hz
        self.samples_until_next_grain = self.samples_per_grain_interval

    def tick(self):
        """Should be called for every audio sample."""
        self.samples_until_next_grain -= 1
        if self.samples_until_next_grain <= 0:
            self.spawn_callback()
            self.samples_until_next_grain = self.samples_per_grain_interval

class Engine:
    """Manages multiple Voice objects and the global clock."""
    def __init__(self, samplerate, bpm):
        self.samplerate = samplerate
        self.global_clock = GlobalClock(samplerate, bpm)
        self.voices = []

    def add_voice(self, voice):
        self.voices.append(voice)

    def get_audio_chunk(self, frames):
        self.global_clock.tick(frames)
        output_buffer = np.zeros(frames, dtype=np.int16)
        for voice in self.voices:
            output_buffer += voice.get_audio_chunk(frames)
        return output_buffer