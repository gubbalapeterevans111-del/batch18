import os
import shutil
import cv2
import numpy as np
from tqdm import tqdm
import concurrent.futures

from downloader import download_folder
from camera import capture_target_face
from face_engine import FaceRecogniser

def main():
    print("Welcome to the Wedding Photo Search System")
    
    # 1. Setup Face Recogniser
    # Use CPU by default. Change to ['CUDAExecutionProvider'] if GPU is available.
    recogniser = FaceRecogniser() 
    
    # 2. Get Target Face
    print("\n--- Step 1: Capture Target Face ---")
    use_camera = input("Do you want to capture from webcam? (y/n) [y]: ").lower() != 'n'
    
    target_embedding = None
    target_img = None
    
    if use_camera:
        target_img = capture_target_face()
    else:
        path = input("Enter path to target image file: ").strip()
        if os.path.exists(path):
            target_img = cv2.imread(path)
        else:
            print("File not found.")
            return

    if target_img is None:
        print("No target image provided. Exiting.")
        return

    # DEBUG: Save the captured image to check quality
    cv2.imwrite("debug_target.jpg", target_img)
    print("DEBUG: Saved captured face to 'debug_target.jpg'. Please check this file if detection fails.")

    # Extract embedding
    res = recogniser.get_embedding(target_img)
    if res is None:
        print("No face detected in the target image! Please try again with a clearer photo.")
        return
    
    target_embedding, _, _ = res
    print("Target face successfully encoded.")

    # 3. Download Photos
    print("\n--- Step 2: Download Photos ---")
    gdrive_link = input("Enter Google Drive Link: ").strip()
    
    download_dir = "downloaded_photos"
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)
        
    print(f"Downloading to {download_dir}...")
    # NOTE: user might provide a link. gdown handles it.
    download_folder(gdrive_link, download_dir)

    # 4. Search
    print("\n--- Step 3: Searching ---")
    matches_dir = "matched_photos"
    if not os.path.exists(matches_dir):
        os.makedirs(matches_dir)

    # Walk through downloaded files
    image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}
    files_to_scan = []
    
    for root, dirs, files in os.walk(download_dir):
        for file in files:
            if os.path.splitext(file)[1].lower() in image_extensions:
                files_to_scan.append(os.path.join(root, file))
    
    print(f"Found {len(files_to_scan)} images. Scanning...")
    
    match_count = 0
    threshold = 0.45 # Tunable
    
    def check_file(file_path):
        try:
            faces = recogniser.get_all_faces(file_path)
            for face in faces:
                sim = recogniser.compute_similarity(target_embedding, face.embedding)
                if sim > threshold:
                    return True, file_path
            return False, file_path
        except Exception as e:
            return False, file_path

    # Process in parallel using ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
        futures = {executor.submit(check_file, p): p for p in files_to_scan}
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(files_to_scan)):
            is_match, file_path = future.result()
            
            if is_match:
                match_count += 1
                filename = os.path.basename(file_path)
                shutil.copy(file_path, os.path.join(matches_dir, filename))

    print(f"\nSearch complete. Found {match_count} matches.")
    print(f"Relevant photos are saved in: {os.path.abspath(matches_dir)}")
    
    # Show matches folder (Windows specific explorer launch)
    os.startfile(os.path.abspath(matches_dir))

if __name__ == "__main__":
    main()
