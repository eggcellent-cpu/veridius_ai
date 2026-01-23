from flask import Flask, jsonify, request, send_from_directory
import os
import json

# ------------------------
# Paths
# ------------------------
# Base directory of this script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Frontend folder
FRONTEND_DIR = os.path.join(BASE_DIR, '..', 'frontend')

# Path to recipients.json in project root /out folder
RECIPIENTS_FILE = os.path.join(BASE_DIR, '..', 'out', 'recipients.json')

# Ensure the /out folder exists
os.makedirs(os.path.dirname(RECIPIENTS_FILE), exist_ok=True)

print("Recipients.json path:", os.path.abspath(RECIPIENTS_FILE))

# ------------------------
# Initialize Flask
# ------------------------
app = Flask(__name__, static_folder=FRONTEND_DIR)

# ------------------------
# Routes for email_list.html
# ------------------------
@app.route('/')
def index():
    """Serve the email_list.html page"""
    return send_from_directory(app.static_folder, 'email_list.html')


@app.route('/get_recipients', methods=['GET'])
def get_recipients():
    """Return current recipients as JSON"""
    if not os.path.exists(RECIPIENTS_FILE):
        return jsonify({"emails": []})
    with open(RECIPIENTS_FILE, 'r') as f:
        data = json.load(f)
    return jsonify(data)


@app.route('/save_recipients', methods=['POST'])
def save_recipients():
    """Save recipients to JSON file"""
    try:
        data = request.get_json()
        emails = data.get('emails', [])

        # Basic email validation
        invalid = [e for e in emails if not e or '@' not in e]
        if invalid:
            return jsonify({"status": "error", "msg": f"Invalid emails: {invalid}"}), 400

        # Save to JSON
        with open(RECIPIENTS_FILE, 'w') as f:
            json.dump({"emails": emails}, f, indent=2)

        print("Saved recipients:", emails)
        return jsonify({"status": "success", "msg": "Recipients saved successfully."})
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)}), 500

# ------------------------
# Serve frontend static files
# ------------------------
@app.route('/<path:path>')
def serve_static(path):
    """Serve any frontend files (CSS, JS, HTML)"""
    return send_from_directory(app.static_folder, path)

# ------------------------
# Serve /data and /out files outside frontend
# ------------------------
@app.route('/data/<path:filename>')
def serve_data(filename):
    """Serve JSON or other files from /data folder"""
    data_dir = os.path.join(BASE_DIR, '..', 'data')
    return send_from_directory(data_dir, filename)

@app.route('/out/<path:filename>')
def serve_out(filename):
    """Serve JSON or other files from /out folder"""
    out_dir = os.path.join(BASE_DIR, '..', 'out')
    return send_from_directory(out_dir, filename)

# ------------------------
# Run the server
# ------------------------
if __name__ == '__main__':
    print("Starting Flask server...")
    app.run(debug=True)
