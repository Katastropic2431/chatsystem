# app.py
from flask import Flask, request, jsonify, send_from_directory
import os
import uuid

app = Flask(__name__)

UPLOAD_FOLDER = '/tmp/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        print('No file part')
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        print('No selected file')
        return jsonify({"error": "No selected file"}), 400

    # Generate a unique filename
    unique_filename = str(uuid.uuid4()) + "_" + file.filename
    file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
    file.save(file_path)

    file_url = f"http://{request.host}/uploads/{unique_filename}"
    print(f"File uploaded: {file_url}")
    return jsonify({"file_url": file_url}), 200

@app.route('/uploads/<filename>', methods=['GET'])
def get_file(filename):
    print(f"Get file: {filename}")
    return send_from_directory(UPLOAD_FOLDER, filename)

if __name__ == '__main__':
    app.run(port=5000)