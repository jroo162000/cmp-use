from flask import Flask, request, jsonify
import subprocess, webbrowser

app = Flask(__name__)

@app.route('/open_browser', methods=['POST'])
def open_browser():
    # Opens a website using the default browser.
    webbrowser.open('http://www.google.com')
    return jsonify({'status': 'Browser opened'})

@app.route('/run_code', methods=['POST'])
def run_code():
    # Receives code as JSON and executes it (use with caution).
    code = request.json.get('code')
    try:
        exec(code, globals())
        return jsonify({'status': 'Code executed'})
    except Exception as e:
        return jsonify({'status': 'Error executing code', 'error': str(e)}), 400

@app.route('/simulate_keystroke', methods=['POST'])
def simulate_keystroke():
    # Uses xdotool (make sure it's installed) to simulate a keystroke.
    key = request.json.get('key')
    try:
        subprocess.run(['xdotool', 'key', key])
        return jsonify({'status': f'Keystroke "{key}" simulated'})
    except Exception as e:
        return jsonify({'status': 'Error simulating keystroke', 'error': str(e)}), 400

if __name__ == '__main__':
    # Listen on all interfaces on port 5000.
    app.run(host='0.0.0.0', port=5000)
