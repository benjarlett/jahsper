from flask import Flask, render_template, jsonify, request
import threading
import time
import sys
import logging
import json # Import json module

# Configure logging for Flask app
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Global references to the actual engine and midi_handler
# These will be set by main.py
engine = None
midi_handler = None
mido = None # Will be set by main.py
get_audio_output_devices = None # Will be set by main.py

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/status')
def status():
    # Ensure engine is not None before accessing its attributes
    current_bpm = engine.global_clock.bpm if engine else 0
    current_cpu_usage = engine.cpu_usage if engine else 0.0
    voices_status = []
    if engine and engine.voices:
        voices_status = [{'id': i, 'status': 'playing'} for i in range(len(engine.voices))] # Placeholder
    latest_midi = midi_handler.latest_midi_message if midi_handler else None

    return jsonify({
        'bpm': current_bpm,
        'voices': voices_status,
        'cpu_usage': current_cpu_usage,
        'latest_midi': latest_midi
    })

@app.route('/tap')
def tap():
    logging.info("Web /tap endpoint hit.")
    if midi_handler:
        # Simulate a MIDI note_on event for tap tempo
        midi_handler.midi_callback({'type': 'note_on', 'note': 41, 'velocity': 100, 'time': 0})
        return jsonify({'message': 'Tap received', 'bpm': engine.global_clock.bpm})
    return jsonify({'error': 'MIDI handler not initialized'}), 500

@app.route('/set_bpm', methods=['POST'])
def set_bpm():
    data = request.get_json()
    new_bpm = data.get('bpm')
    logging.info(f"Web /set_bpm endpoint hit with data: {data}")
    if new_bpm and engine:
        engine.global_clock.bpm = float(new_bpm)
        return jsonify({'message': f'BPM set to {new_bpm}', 'bpm': engine.global_clock.bpm})
    return jsonify({'error': 'Invalid BPM or engine not initialized'}), 400

@app.route('/midi_ports')
def midi_ports():
    try:
        if mido:
            ports = mido.get_input_names()
            return jsonify({'ports': ports})
        return jsonify({'error': 'Mido not initialized'}), 500
    except Exception as e:
        logging.error(f"Error getting MIDI ports: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/set_midi_port', methods=['POST'])
def set_midi_port():
    data = request.get_json()
    port_name = data.get('port_name')
    logging.info(f"Web /set_midi_port endpoint hit with port_name: {port_name}")
    if port_name and midi_handler:
        midi_handler.close_midi_port()
        midi_handler.open_midi_port(port_name)
        return jsonify({'message': f'MIDI port set to {port_name}'})
    return jsonify({'error': 'Invalid port name or MIDI handler not initialized'}), 400

@app.route('/audio_output_devices')
def audio_output_devices():
    try:
        if get_audio_output_devices:
            devices = get_audio_output_devices()
            return jsonify({'devices': devices})
        return jsonify({'error': 'Audio output device function not initialized'}), 500
    except Exception as e:
        logging.error(f"Error getting audio output devices: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/set_audio_output_device', methods=['POST'])
def set_audio_output_device():
    data = request.get_json()
    device_id = data.get('device_id')
    logging.info(f"Web /set_audio_output_device endpoint hit with device_id: {device_id}")
    if device_id is not None:
        try:
            sd.default.device = int(device_id)
            logging.info(f"Audio output device set to ID: {device_id}")
            return jsonify({'message': f'Audio output device set to ID: {device_id}'})
        except Exception as e:
            logging.error(f"Error setting audio output device: {e}")
            return jsonify({'error': str(e)}), 500
    return jsonify({'error': 'Invalid device ID'}), 400

# SSE endpoint for live BPM and CPU updates
@app.route('/status_stream')
def status_stream():
    def generate():
        while True:
            # Ensure engine is not None before accessing its attributes
            current_bpm = engine.global_clock.bpm if engine else 0
            current_cpu_usage = engine.cpu_usage if engine else 0.0
            latest_midi = midi_handler.latest_midi_message if midi_handler else None
            
            # Serialize latest_midi to JSON string
            latest_midi_json = json.dumps(latest_midi)

            yield f"data: {{\"bpm\": {current_bpm}, \"cpu_usage\": {current_cpu_usage}, \"latest_midi\": {latest_midi_json}}}\n\n"
            time.sleep(0.1) # Send updates every 100ms for smoother MIDI display
    return app.response_class(generate(), mimetype='text/event-stream')

# This part will not be executed when imported by main.py
if __name__ == '__main__':
    # This is for standalone testing of the web app (without audio engine)
    # In a real scenario, main.py will set the engine and midi_handler
    class DummyGlobalClock:
        def __init__(self):
            self.bpm = 120

    class DummyEngine:
        def __init__(self):
            self.global_clock = DummyGlobalClock()
            self.voices = []
            self.cpu_usage = 0.0

    class DummyMidiHandler:
        def __init__(self):
            self.engine = None # Will be set later
            self.latest_midi_message = None
        def midi_callback(self, message):
            logging.info(f"Dummy MIDI callback received: {message}")
            self.latest_midi_message = message
            if message.get('note') == 41:
                # Simulate BPM change for dummy engine
                self.engine.global_clock.bpm += 1
        def open_midi_port(self, port_name=None):
            logging.info(f"Dummy MIDI port opened: {port_name or 'default'}")
        def close_midi_port(self):
            logging.info("Dummy MIDI port closed.")

    engine = DummyEngine()
    midi_handler = DummyMidiHandler()
    midi_handler.engine = engine # Link dummy midi_handler to dummy engine
    app.run(host='0.0.0.0', port=5000, debug=True)