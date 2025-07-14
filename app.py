from flask import Flask, jsonify, request
import subprocess
import webbrowser

app = Flask(__name__)


@app.route('/open_browser', methods=['POST'])
def open_browser():
    # Opens a website using the default browser.
    webbrowser.open('http://www.google.com')
    return jsonify({'status': 'Browser opened'})


# Disabled remote code execution endpoint for security.
@app.route('/run_code', methods=['POST'])
def run_code():
    """Endpoint removed to prevent arbitrary code execution."""
    return (
        jsonify({
            'status': 'Execution disabled',
            'error': 'Remote code execution is not allowed.'
        }),
        403,
    )


@app.route('/simulate_keystroke', methods=['POST'])
def simulate_keystroke():
    # Uses xdotool (make sure it's installed) to simulate a keystroke.
    key = request.json.get('key')
    try:
        subprocess.run(['xdotool', 'key', key])
        return jsonify({'status': f'Keystroke "{key}" simulated'})
    except Exception as e:
        return jsonify({
            'status': 'Error simulating keystroke',
            'error': str(e),
        }), 400


if __name__ == '__main__':
    # Listen on all interfaces on port 5000.
    app.run(host='0.0.0.0', port=5000)
