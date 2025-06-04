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
    """Execute Python code sent in the request body."""
    data = request.get_json(silent=True) or {}
    code = data.get('code')
    if code is None:
        return jsonify({'status': 'No code provided'}), 400

    try:
        exec(code, globals())
        return jsonify({'status': 'Code executed'})
    except Exception as e:
        return jsonify({'status': 'Error executing code', 'error': str(e)}), 400

@app.route('/simulate_keystroke', methods=['POST'])
def simulate_keystroke():
    """Simulate a keystroke using xdotool."""
    data = request.get_json(silent=True) or {}
    key = data.get('key')
    if not key:
        return jsonify({'status': 'No key provided'}), 400

    try:
        subprocess.run(['xdotool', 'key', key], check=True)
        return jsonify({'status': f'Keystroke "{key}" simulated'})
    except Exception as e:
        return jsonify({'status': 'Error simulating keystroke', 'error': str(e)}), 400

if __name__ == '__main__':
    # Listen on all interfaces on port 5000.
    app.run(host='0.0.0.0', port=5000)
