import threading
import time
from flask import Flask, render_template
from flask_socketio import SocketIO

app = Flask(__name__)
# Explicitly setting async_mode to threading for simple debugging
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

@app.route('/')
def index():
    return render_template('index.html', info={"mfg": "Test", "sn": "123", "battery": "100%"})

def background_test():
    """Sends dummy data every second to see if the web UI reacts."""
    count = 0
    while True:
        time.sleep(1)
        count += 1
        test_data = {
            "boot_time": f"00-00-{count:02d}.000",
            "readings": [1000 * (i+1) for i in range(11)],
            "led_idx": count % 17,
            "intensity": 2048,
            "sys_time": "TEST-MODE"
        }
        print(f"Emitting test data: {count}")
        socketio.emit('data_update', test_data)

if __name__ == '__main__':
    # Start the dummy data thread
    threading.Thread(target=background_test, daemon=True).start()
    socketio.run(app, debug=False, port=5001)