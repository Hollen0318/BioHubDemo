# main.py
import os
import threading
import time
import serial
import serial.tools.list_ports
from datetime import datetime
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

DEVICE_INFO = {
    "programmed": "2024-08-15",
    "storage": "512MB",
    "battery": "88%",
    "user": "Default_User",
    "id": "LUMOS-V3",
    "mfg": "Lumos Tech",
    "sn": "SER-X99"
}

class LumosCore:
    def __init__(self):
        self.ser = None
        self.running = False
        self.recording = False
        self.buffer = []
        self.thread = None

    def list_available_ports(self):
        return [port.device for port in serial.tools.list_ports.comports()]

    def parse_arduino_data(self, line):
        try:
            # Expected: 00-00-04.094,0,0,0,1,0,0,0,0,0,1,167,[0],1000;
            clean = line.strip().rstrip(';')
            parts = clean.split(',')
            if len(parts) < 14:
                return None

            return {
                "boot_time": parts[0],
                "readings": [int(x) for x in parts[1:12]],
                "led_idx": int(parts[12].strip('[]')),
                "intensity": int(parts[13]),
                "raw": line
            }
        except:
            return None

    def _read_worker(self):
        while self.running:
            if self.ser and self.ser.is_open:
                try:
                    if self.ser.in_waiting > 0:
                        line = self.ser.readline().decode('utf-8', errors='replace').strip()
                        parsed = self.parse_arduino_data(line)
                        if parsed:
                            socketio.emit('data_update', parsed)
                            if self.recording:
                                self.buffer.append(line)
                except Exception as e:
                    print(f"Serial Read Error: {e}")
            time.sleep(0.005)

    def connect(self, port):
        try:
            self.ser = serial.Serial(port, 115200, timeout=1)
            self.running = True
            self.thread = threading.Thread(target=self._read_worker, daemon=True)
            self.thread.start()
            return True
        except Exception as e:
            print(f"Connect error: {e}")
            return False

    def stop_and_save(self):
        self.recording = False
        if not self.buffer:
            return None
        folder = "Lumos_Records"
        os.makedirs(folder, exist_ok=True)
        fname = f"Recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        path = os.path.join(folder, fname)
        with open(path, 'w') as f:
            for line in self.buffer:
                f.write(line + "\n")
        self.buffer = []
        return path

lumos = LumosCore()

@app.route('/')
def home():
    return render_template('index.html', info=DEVICE_INFO)

@app.route('/get_ports')
def get_ports():
    return jsonify({"ports": lumos.list_available_ports()})

@app.route('/connect', methods=['POST'])
def connect():
    port = request.json.get('port')
    if lumos.connect(port):
        return jsonify({"status": "connected"})
    return jsonify({"status": "failed"})

@app.route('/record', methods=['POST'])
def record():
    action = request.json.get('action')
    if action == "start":
        lumos.buffer = []
        lumos.recording = True
        return jsonify({"msg": "Recording started"})
    else:
        path = lumos.stop_and_save()
        return jsonify({"msg": "Saved", "path": path})

if __name__ == '__main__':
    socketio.run(app, debug=True, port=5001)
