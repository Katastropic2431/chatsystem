import os
import sys
import io
import uuid
import pytest

# Adjust the path to include the src directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from app import app, UPLOAD_FOLDER

@pytest.fixture
def client():
    # Set up the test client and ensure the upload folder exists
    app.config['TESTING'] = True
    client = app.test_client()

    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

    yield client

    # Clean up after tests
    for file in os.listdir(UPLOAD_FOLDER):
        file_path = os.path.join(UPLOAD_FOLDER, file)
        if os.path.isfile(file_path):
            os.unlink(file_path)

def test_upload_file_success(client):
    """Test file upload with valid file."""
    data = {
        'file': (io.BytesIO(b"test file content"), 'testfile.txt')
    }
    response = client.post('/api/upload', content_type='multipart/form-data', data=data)
    
    assert response.status_code == 200
    json_data = response.get_json()
    assert 'file_url' in json_data

    # Verify file was saved in the upload folder
    uploaded_filename = json_data['file_url'].split('/')[-1]
    uploaded_file_path = os.path.join(UPLOAD_FOLDER, uploaded_filename)
    assert os.path.exists(uploaded_file_path)

def test_upload_file_no_file(client):
    """Test file upload with no file part in the request."""
    response = client.post('/api/upload', content_type='multipart/form-data', data={})
    
    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data['error'] == 'No file part'

def test_upload_file_no_filename(client):
    """Test file upload with an empty filename."""
    data = {
        'file': (io.BytesIO(b"test file content"), '')
    }
    response = client.post('/api/upload', content_type='multipart/form-data', data=data)
    
    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data['error'] == 'No selected file'

def test_get_file_success(client):
    """Test downloading an uploaded file."""
    # First, upload a file
    file_content = b"test file content"
    filename = 'testfile.txt'
    data = {
        'file': (io.BytesIO(file_content), filename)
    }
    response = client.post('/api/upload', content_type='multipart/form-data', data=data)
    json_data = response.get_json()
    uploaded_filename = json_data['file_url'].split('/')[-1]

    # Now, try to retrieve the uploaded file
    get_response = client.get(f'/uploads/{uploaded_filename}')
    assert get_response.status_code == 200
    assert get_response.data == file_content

def test_get_file_not_found(client):
    """Test downloading a file that doesn't exist."""
    fake_filename = str(uuid.uuid4()) + "_nonexistent.txt"
    response = client.get(f'/uploads/{fake_filename}')
    assert response.status_code == 404
