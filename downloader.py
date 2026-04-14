import os
import gdown
import zipfile
import shutil
import re
from urllib.parse import urlparse, parse_qs
import warnings

# Suppress annoying XML warning from gdown/bs4
try:
    from bs4 import XMLParsedAsHTMLWarning
    warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
except ImportError:
    pass

def extract_gdrive_id(url):
    """
    Extracts the Google Drive file/folder ID from a URL.
    """
    # Pattern for /file/d/ID/view
    match = re.search(r'/file/d/([a-zA-Z0-9_-]+)', url)
    if match:
        return match.group(1)
    
    # Pattern for /folders/ID
    match = re.search(r'/folders/([a-zA-Z0-9_-]+)', url)
    if match:
        return match.group(1)
        
    # Pattern for ?id=ID
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    if 'id' in qs:
        return qs['id'][0]
        
    return None

def download_folder(url, output_dir="downloads"):
    """
    Downloads a folder or file from a Google Drive URL.
    Handles extraction if the downloaded file is a zip/archive.
    Includes caching based on the Drive ID.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    file_id = extract_gdrive_id(url)
    if not file_id:
        file_id = "unknown_link"
        
    target_dir = os.path.join(output_dir, file_id)
    
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)

    print(f"Downloading from {target_dir}...")
    
    # helper to clean url if no id found. 
    # WARNING: stripping params is bad if the link works by params (e.g. ?id=...).
    # We will prefer using the full url for download_folder, hoping gdown handles it.
    # clean_url = url.split('?')[0] if '?' in url else url

    # Clear gdown cookies to prevent "Cannot retrieve public link" due to stale/bad cookies
    # This mimics "Incognito" mode behavior
    try:
        home = os.path.expanduser("~")
        cookie_path = os.path.join(home, ".cache", "gdown", "cookies.txt")
        if os.path.exists(cookie_path):
            print(f"Clearing cached gdown cookies at {cookie_path}...")
            os.remove(cookie_path)
    except Exception as e:
        print(f"Warning: Could not clear gdown cookies: {e}")

    # Context manager to prevent gdown from nuking the folder on error
    class NoCleanup:
        def __enter__(self):
            self.original_rmtree = shutil.rmtree
            shutil.rmtree = self._fake_rmtree
        def __exit__(self, exc_type, exc_val, exc_tb):
            shutil.rmtree = self.original_rmtree
        def _fake_rmtree(self, *args, **kwargs):
            # print("Prevented gdown from deleting folder.")
            pass

    folder_success = False

    print(f"Attempting to download as a FOLDER (ID: {file_id})...")
    
    # Try downloading as folder
    try:
        with NoCleanup():
            # Get list of files first without downloading sequentially
            files_to_download = gdown.download_folder(url, output=target_dir, quiet=True, skip_download=True)
            
            if files_to_download:
                import concurrent.futures
                
                print(f"Folder structure retrieved. {len(files_to_download)} files to download concurrently.")
                
                def download_single_file(f):
                    try:
                        # gdown returns GoogleDriveFileToDownload(id, path, local_path)
                        # but just in case, it might just return paths if skip_download works differently
                        # Wait, let's verify gdown source we read: if skip_download, it appends GoogleDriveFileToDownload.
                        if hasattr(f, 'id') and f.id:
                            if os.path.exists(f.local_path) and os.path.getsize(f.local_path) > 0:
                                pass # Already downloaded
                            else:
                                gdown.download(id=f.id, output=f.local_path, quiet=True)
                        elif isinstance(f, str):
                            pass # Normally skip_download returns NamedTuple, but if it's string, we shouldn't get here unless resume=True
                    except Exception as e:
                        print(f"Error downloading {f.local_path}: {e}")
                
                # Highly parallelized downloading based on user request "very fast"
                with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
                    list(executor.map(download_single_file, files_to_download))
                
                print(f"Folder parallel download successful. {len(files_to_download)} files processed.")
                folder_success = True
                return target_dir
            else:
                print("gdown.download_folder returned empty/None. Possibly not a recognized folder link or empty folder.")
    except Exception as e:
        print(f"Folder download attempt failed: {e}")
        print("Falling back to single file/ID download...")

    if folder_success:
        return target_dir

    # 2. Download as a file (zip or single image)
    print("Attempting to download as a single FILE or ZIP (fallback)...")
    output_path = None
    try:
        if file_id:
            print(f"Using Query ID: {file_id}")
            output_path = gdown.download(id=file_id, quiet=False, fuzzy=True)
        else:
            print("No ID detected, using URL directly...")
            # Use full URL here too
            output_path = gdown.download(url=url, quiet=False, fuzzy=True)
    except Exception as e:
        print(f"File download error: {e}")
        
    # Check if we have files in target_dir (maybe folder download partially worked or file download worked)
    if os.path.exists(target_dir) and len(os.listdir(target_dir)) > 0:
         # Check if we just downloaded a file that needs moving
         pass
    else:
         if not output_path:
             print("Download completely failed.")
             return None

    if output_path:
        # Move to target_dir
        filename = os.path.basename(output_path)
        dest_path = os.path.join(target_dir, filename)
        
        # If gdown downloaded to current dir/temp, move it
        # We need to handle the case where it downloads to a temp name
        try:
            if os.path.abspath(output_path) != os.path.abspath(dest_path):
                 if os.path.exists(dest_path):
                     try:
                        os.remove(dest_path)
                     except: 
                        pass
                 shutil.move(output_path, dest_path)
                 output_path = dest_path
        except Exception as move_error:
            print(f"Warning: Could not move file: {move_error}")

        # Check if zip
        if zipfile.is_zipfile(output_path):
            print("Detected zip file. Extracting...")
            try:
                with zipfile.ZipFile(output_path, 'r') as zip_ref:
                    zip_ref.extractall(target_dir)
                print("Extraction complete.")
            except Exception as e:
                print(f"Error extracting zip: {e}")
            
            # os.remove(output_path) 
        
        return target_dir
    
    # Final check
    if os.path.exists(target_dir) and len(os.listdir(target_dir)) > 0:
        return target_dir

    return None
