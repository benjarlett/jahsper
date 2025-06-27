import sounddevice as sd
import mido
import time
import threading
import psutil
import logging

from src.engine import Voice, Engine
import web.app as web_app # Import the web app module

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Global engine instance
engine = None
midi_handler = None

def audio_callback(outdata, frames, time, status):
    if status:
        logging.warning(status)
    chunk = engine.get_audio_chunk(frames)
    outdata[:] = chunk.reshape(outdata.shape)

class MidiInputHandler:
    def __init__(self, engine):
        self.engine = engine
        self.last_tap_time = 0
        self.tap_times = []
        self.midi_port = None

    def open_midi_port(self, port_name=None):
        try:
            if self.midi_port:
                self.midi_port.close()

            input_names = mido.get_input_names()
            
            if port_name:
                # Try to open the specified port
                if port_name in input_names:
                    self.midi_port = mido.open_input(port_name)
                else:
                    logging.warning(f"Specified MIDI port '{port_name}' not found. Opening default.")
                    if input_names:
                        self.midi_port = mido.open_input(input_names[0])
                    else:
                        logging.warning("No MIDI input ports found.")
                        return
            else:
                # Try to open "USB MIDI keyboard" by default
                default_port_name = "USB MIDI keyboard"
                if default_port_name in input_names:
                    self.midi_port = mido.open_input(default_port_name)
                elif input_names:
                    self.midi_port = mido.open_input(input_names[0])
                else:
                    logging.warning("No MIDI input ports found.")
                    return

            logging.info(f"Opened MIDI port: {self.midi_port.name}")
            self.midi_port.callback = self.midi_callback
        except Exception as e:
            logging.error(f"Error opening MIDI port: {e}")
            logging.info("Available MIDI input ports:", mido.get_input_names())

    def midi_callback(self, message):
        # This method can now receive either a mido.Message object or a dict from the web app
        if isinstance(message, mido.Message):
            msg_type = message.type
            msg_note = message.note
        elif isinstance(message, dict):
            msg_type = message.get('type')
            msg_note = message.get('note')
        else:
            logging.warning(f"Unknown message type received by MIDI handler: {type(message)}")
            return

        if msg_type == 'note_on':
            # Tap tempo (e.g., C3 - MIDI note 48)
            if msg_note == 48:
                current_time = time.time()
                if self.last_tap_time != 0:
                    self.tap_times.append(current_time - self.last_tap_time)
                    if len(self.tap_times) > 4:  # Keep last 4 taps for average
                        self.tap_times.pop(0)
                    
                    if len(self.tap_times) >= 2:
                        avg_interval = sum(self.tap_times) / len(self.tap_times)
                        new_bpm = 60 / avg_interval
                        self.engine.global_clock.bpm = new_bpm
                        logging.info(f"New BPM: {new_bpm:.2f}")
                self.last_tap_time = current_time
            
            # Loop control (e.g., C4 - MIDI note 60 for voice 0, C#4 - MIDI note 61 for voice 1)
            elif 60 <= msg_note < 60 + len(self.engine.voices):
                voice_index = msg_note - 60
                # For now, just print. Later, we'll implement mute/unmute or trigger.
                logging.info(f"MIDI Note On: {msg_note} for Voice {voice_index}")

    def close_midi_port(self):
        if self.midi_port:
            self.midi_port.close()
            logging.info("MIDI port closed.")

def get_cpu_usage():
    return psutil.cpu_percent(interval=None) # Non-blocking call

def run_flask_app():
    web_app.app.run(host='0.0.0.0', port=5000, debug=False) # debug=False for production

if __name__ == "__main__":
    samplerate = 44100  # Assuming a default samplerate
    bpm = 120  # Initial BPM

    engine = Engine(samplerate, bpm)

    # Add voices to the engine
    voice1 = Voice("loops/Better With Brushes.wav")
    engine.add_voice(voice1)

    midi_handler = MidiInputHandler(engine)
    midi_handler.open_midi_port() # Opens the first available MIDI input port, or default

    # Set the global engine and midi_handler in the web_app module
    web_app.engine = engine
    web_app.midi_handler = midi_handler
    web_app.mido = mido # Pass mido module to web_app

    # Start Flask app in a separate thread
    flask_thread = threading.Thread(target=run_flask_app)
    flask_thread.daemon = True # Daemonize thread so it exits when main thread exits
    flask_thread.start()

    with sd.OutputStream(channels=1, callback=audio_callback, samplerate=samplerate):
        logging.info("Playing audio. Press Ctrl+C to stop.")
        try:
            while True:
                # Update Flask engine's CPU usage from the main engine's global clock
                # BPM is directly linked via web_app.engine.global_clock.bpm
                web_app.engine.cpu_usage = get_cpu_usage()
                time.sleep(0.1) # Keep main thread alive and allow Flask thread to run
        except KeyboardInterrupt:
            logging.info("\nPlayback stopped.")
        finally:
            midi_handler.close_midi_port()