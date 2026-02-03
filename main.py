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
    "programmed": "Feb 2, 2026",
    "storage": "512MB",
    "battery": "88%",
    "user": "BioHub Demo",
    "id": "P17F",
    "mfg": "Watson Research Lab",
    "sn": "SZL-6791"
}

# -------------------------
# NEW: Placeholder predictors
# -------------------------
def lactatePrediction(recorded_lines):
    """
    Placeholder lactate prediction.
    Takes raw Arduino lines (strings), parses them, and returns a placeholder result.

    Later: replace with feature extraction + .joblib model inference.
    """
    parsed_points = []
    for line in recorded_lines:
        p = lumos.parse_arduino_data(line)
        if p:
            parsed_points.append(p)

    if not parsed_points:
        return {"value": None, "units": "mmol/L", "note": "No valid data captured."}

    # Placeholder: simple aggregate from readings
    # (This is just a stand-in; replace with real pipeline/model.)
    # We'll compute a stable-ish scalar from mean of all PD readings.
    total = 0
    count = 0
    for p in parsed_points:
        for v in p["readings"]:
            total += v
            count += 1

    mean_val = total / max(count, 1)

    # Map mean_val to a fake lactate mmol/L range (e.g., 0.8–12.0) deterministically
    # purely as placeholder.
    lactate = 0.8 + (min(mean_val, 25500) / 25500.0) * (12.0 - 0.8)

    return {
        "value": round(lactate, 2),
        "units": "mmol/L",
        # "note": "Placeholder estimate (replace with ML model)."
        "note": "Reference only."
    }

def skinTonePrediction(recorded_lines):
    """
    Placeholder skin tone prediction.
    Takes raw Arduino lines (strings), parses them, and returns a placeholder classification.

    Later: replace with calibration/features + .joblib model inference.
    """
    parsed_points = []
    for line in recorded_lines:
        p = lumos.parse_arduino_data(line)
        if p:
            parsed_points.append(p)

    if not parsed_points:
        return {"value": None, "scale": "Fitzpatrick", "note": "No valid data captured."}

    # Placeholder: use average of a subset of readings to produce a mock Fitzpatrick type
    # (Again: purely placeholder.)
    total = 0
    count = 0
    for p in parsed_points:
        # bias toward visible-ish PD indices as a simplistic placeholder
        subset = p["readings"][:6]
        total += sum(subset)
        count += len(subset)

    mean_val = total / max(count, 1)

    # Convert to a type 1-6 placeholder
    # Lower mean -> lighter, higher mean -> darker (just a placeholder mapping)
    t = int(1 + (min(mean_val, 25500) / 25500.0) * 5)
    t = max(1, min(6, t))

    return {
        "value": f"Type {t}",
        "scale": "Fitzpatrick",
        # "note": "Placeholder classification (replace with ML model)."
        "note": "Reference only."
    }

class LumosCore:
    def __init__(self):
        self.ser = None
        self.running = False
        self.recording = False
        self.buffer = []
        self.thread = None

        # NEW: prediction capture (separate from manual recording to keep behavior unchanged)
        self.pred_recording = False
        self.pred_buffer = []

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

                            # NEW: prediction capture (does not affect existing recording)
                            if self.pred_recording:
                                self.pred_buffer.append(line)
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

    # NEW: save prediction capture to its own folder
    def _save_prediction_capture(self, prefix="Prediction"):
        if not self.pred_buffer:
            return None, []

        folder = "Lumos_Predictions"
        os.makedirs(folder, exist_ok=True)
        fname = f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        path = os.path.join(folder, fname)
        lines_copy = list(self.pred_buffer)

        with open(path, 'w') as f:
            for line in lines_copy:
                f.write(line + "\n")

        self.pred_buffer = []
        return path, lines_copy

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

# -----------------------------------------
# NEW: Prediction progress streaming helpers
# -----------------------------------------
LACTATE_WORKFLOW = [
    "Start Predicting Lactate",
    "Removing Motion Artifacts",
    "Intensity Calibration",
    "Incident Light Measurement",
    "Ambient Light Cancellation",
    "Absorbance Feature Extraction",
    "Skin Tone Calibration",
    "Data Normalization",
    "Passing into Machine Learning Model",
    "Complete"
]

SKINTONE_WORKFLOW = [
    "Start Predicting Skin Tone",
    "Removing Motion Artifacts",
    "Intensity Calibration",
    "Incident Light Measurement",
    "Ambient Light Cancellation",
    "Reflectance Feature Extraction",
    "Data Normalization",
    "Passing into Machine Learning Model",
    "Complete"
]

def _emit_progress(kind, step_index, total_steps, label):
    pct = int((step_index / max(total_steps - 1, 1)) * 100)
    socketio.emit('prediction_progress', {
        "kind": kind,
        "step_index": step_index,
        "total_steps": total_steps,
        "label": label,
        "percent": pct
    })

def _run_prediction(kind):
    """
    Background thread:
    - capture 1 minute of data into pred_buffer
    - simulate workflow steps with progress updates
    - run placeholder predictor using captured lines
    - emit final result
    """
    # Make sure device is connected
    if not (lumos.ser and lumos.ser.is_open):
        socketio.emit('prediction_result', {
            "kind": kind,
            "ok": False,
            "error": "Device not connected."
        })
        return

    workflow = LACTATE_WORKFLOW if kind == "lactate" else SKINTONE_WORKFLOW
    total_steps = len(workflow)

    # Step 0
    _emit_progress(kind, 0, total_steps, workflow[0])

    # Capture 1 minute
    lumos.pred_buffer = []
    lumos.pred_recording = True

    # While capturing, keep the UI alive with a smooth progress ramp for the first part
    capture_seconds = 60
    for s in range(capture_seconds):
        # We keep this as "Start..." while capturing, but update percent subtly
        socketio.emit('prediction_capture_tick', {
            "kind": kind,
            "seconds_elapsed": s + 1,
            "seconds_total": capture_seconds
        })
        time.sleep(1)

    lumos.pred_recording = False
    path, recorded_lines = lumos._save_prediction_capture(prefix=("Lactate" if kind == "lactate" else "SkinTone"))

    if not recorded_lines:
        socketio.emit('prediction_result', {
            "kind": kind,
            "ok": False,
            "error": "No data captured during the 1-minute window."
        })
        return

    # Simulate the rest of the pipeline steps (fast, but visible)
    # Start from step 1 through the last
    for i in range(1, total_steps):
        _emit_progress(kind, i, total_steps, workflow[i])
        time.sleep(0.6 if i < total_steps - 1 else 0.2)

    # Produce result
    if kind == "lactate":
        pred = lactatePrediction(recorded_lines)
    else:
        pred = skinTonePrediction(recorded_lines)

    socketio.emit('prediction_result', {
        "kind": kind,
        "ok": True,
        "file_path": path,
        "prediction": pred
    })

# -----------------------------------------
# NEW: Routes to start predictions
# -----------------------------------------
@app.route('/predict_lactate', methods=['POST'])
def predict_lactate():
    threading.Thread(target=_run_prediction, args=("lactate",), daemon=True).start()
    return jsonify({"status": "started"})

@app.route('/predict_skin_tone', methods=['POST'])
def predict_skin_tone():
    threading.Thread(target=_run_prediction, args=("skin",), daemon=True).start()
    return jsonify({"status": "started"})

if __name__ == '__main__':
    socketio.run(app, debug=True, port=5001)
