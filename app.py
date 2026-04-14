import os
import threading
import time
import base64
import cv2
import numpy as np
import shutil
import concurrent.futures
import uuid
import zipfile
from flask import Flask, render_template, request, jsonify, send_from_directory, send_file
from flask_cors import CORS

from downloader import download_folder
from face_engine import FaceRecogniser

app = Flask(__name__)
CORS(app)

# Global States Dictionary keyed by session_id
states = {}

DOWNLOAD_BASE_DIR = "downloaded_photos"
MATCHES_BASE_DIR = "matched_photos"

os.makedirs(DOWNLOAD_BASE_DIR, exist_ok=True)
os.makedirs(MATCHES_BASE_DIR, exist_ok=True)

# Re-use your engine
recogniser = None

def init_engine():
    global recogniser
    if recogniser is None:
        recogniser = FaceRecogniser()

def get_initial_state():
    return {
        "status": "idle",
        "message": "Ready to start",
        "progress": 0,
        "matches": [],
        "error": None,
        "download_url": None
    }

def cleanup_old_sessions():
    """Optional: Remove old directories to save space if needed. Hard to do safely without time tracking, 
    but we can just clean the specific session's download dir after extraction."""
    pass

@app.route('/api/search', methods=['POST'])
def start_search():
    try:
        data = request.json
        if not data:
             return jsonify({"error": "Invalid JSON body"}), 400
             
        link = data.get('link')
        image = data.get('image')
        
        if not link or not image:
            return jsonify({"error": "Missing link or image"}), 400
        
        session_id = str(uuid.uuid4())
        states[session_id] = get_initial_state()
        
        # Start background thread
        thread = threading.Thread(target=process_search_task, args=(link, image, session_id))
        thread.start()
        
        return jsonify({"message": "Started", "session_id": session_id})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

def process_search_task(gdrive_link, target_img_data, session_id):
    try:
        init_engine()
        state = states[session_id]
        
        # Isolated directories for this session
        session_matches_dir = os.path.join(MATCHES_BASE_DIR, session_id)
        os.makedirs(session_matches_dir, exist_ok=True)
        
        # 1. Decode Target Image
        state["status"] = "processing_target"
        state["message"] = "Processing target face..."
        
        if ',' in target_img_data:
            target_img_data = target_img_data.split(',')[1]
        
        img_bytes = base64.b64decode(target_img_data)
        nparr = np.frombuffer(img_bytes, np.uint8)
        target_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if target_img is None:
            raise Exception("Failed to decode image")

        res = recogniser.get_embedding(target_img)
        if res is None:
            raise Exception("No face detected in the captured photo. Please try again.")
        
        target_embedding, _, _ = res
        
        # 2. Download
        state["status"] = "downloading"
        state["message"] = "Downloading photos from Google Drive..."
        
        try:
           # download_folder already handles caching based on the drive URL ID internally!
           download_path = download_folder(gdrive_link, DOWNLOAD_BASE_DIR)
        except Exception as e:
           raise Exception(f"Download failed: {str(e)}")

        if not download_path:
             raise Exception("Download returned no path. Check the link.")

        # 3. Search
        state["status"] = "scanning"
        state["message"] = "Scanning photos..."
        
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}
        files_to_scan = []
        for root, dirs, files in os.walk(download_path):
            for file in files:
                if os.path.splitext(file)[1].lower() in image_extensions:
                    files_to_scan.append(os.path.join(root, file))
        
        total_files = len(files_to_scan)
        if total_files == 0:
            state["message"] = "No images found in the downloaded folder."
            state["status"] = "complete"
            return

        threshold = 0.45
        matches = []
        completed = 0
        
        def check_file(file_path):
            try:
                faces = recogniser.get_all_faces(file_path)
                for face in faces:
                    sim = recogniser.compute_similarity(target_embedding, face.embedding)
                    if sim > threshold:
                        return True, file_path
                return False, file_path
            except Exception as e:
                print(f"Error scanning {file_path}: {e}")
                return False, file_path

        state["message"] = f"Scanning {total_files} photos..."
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
            futures = [executor.submit(check_file, p) for p in files_to_scan]
            for i, future in enumerate(concurrent.futures.as_completed(futures)):
                is_match, file_path = future.result()
                completed += 1
                state["progress"] = int((completed / total_files) * 100)
                state["message"] = f"Scanning {completed}/{total_files}..."
                
                if is_match:
                    filename = os.path.basename(file_path)
                    unique_name = f"{completed}_{filename}"
                    dest_path = os.path.join(session_matches_dir, unique_name)
                    shutil.copy(file_path, dest_path)
                    # Expose match via routing that uses session_id
                    matches.append(f"/matches/{session_id}/{unique_name}")
                    state["matches"] = matches

        # Create zip file if there are matches
        if matches:
            state["message"] = "Zipping matched photos..."
            zip_filename = f"{session_matches_dir}.zip"
            with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(session_matches_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        zipf.write(file_path, arcname=file)
            state["download_url"] = f"/api/download/{session_id}"

        # We DO NOT clean up the download directory anymore, so future
        # users typing the same Google Drive link can scan the cached images instantly.

        state["progress"] = 100
        state["status"] = "complete"
        state["message"] = f"Finished! Found {len(matches)} photos."

    except Exception as e:
        print(f"Error in task: {e}")
        states[session_id]["status"] = "error"
        states[session_id]["error"] = str(e)
        states[session_id]["message"] = "Error occurred."

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def get_status():
    session_id = request.args.get('session_id')
    if not session_id or session_id not in states:
        return jsonify({"error": "Invalid or missing session_id"}), 400
    return jsonify(states[session_id])

@app.route('/matches/<session_id>/<path:filename>')
def serve_match(session_id, filename):
    # Serve from the session-specific folder
    session_matches_dir = os.path.join(MATCHES_BASE_DIR, session_id)
    return send_from_directory(session_matches_dir, filename)

@app.route('/api/download/<session_id>')
def download_zip(session_id):
    zip_path = os.path.join(MATCHES_BASE_DIR, f"{session_id}.zip")
    if os.path.exists(zip_path):
        return send_file(zip_path, as_attachment=True, download_name="matched_photos.zip")
    else:
        return "Zip file not found", 404

if __name__ == '__main__':
    # Ensure directories exist
    os.makedirs("templates", exist_ok=True)
    os.makedirs("static", exist_ok=True)
    
    print("Starting Flask server...")
    print("👉 Please click this link: http://127.0.0.1:5000")
    init_engine() # Pre-load model
    app.run(debug=True, use_reloader=False, host='127.0.0.1', port=5000)
