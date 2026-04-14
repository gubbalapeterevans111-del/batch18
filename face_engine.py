import cv2
import numpy as np
import insightface
from insightface.app import FaceAnalysis

class FaceRecogniser:
    def __init__(self, provider=['CPUExecutionProvider']):
        """
        Initialize the FaceAnalysis app.
        provider: list of providers for onnxruntime (e.g., ['CUDAExecutionProvider', 'CPUExecutionProvider'] if GPU available)
        """
        print("Initializing FaceAnalysis...")
        # Use 'buffalo_s' which is a much lighter and faster model for CPU
        self.app = FaceAnalysis(name='buffalo_s', providers=provider)
        # Reduce det_size for extremely fast detection (may miss tiny background faces, but speeds up ~8x)
        self.app.prepare(ctx_id=0, det_size=(320, 320))
        print("FaceAnalysis initialized with extremely lightweight model (320x320).")

    def get_embedding(self, image_input):
        """
        Detects faces in the image and returns the embedding of the largest face found.
        image_input: can be a filepath (str) or a numpy array (image).
        Returns: embedding (numpy array) or None if no face found.
        """
        if isinstance(image_input, str):
            img = cv2.imread(image_input)
            if img is None:
                print(f"Could not read image: {image_input}")
                return None
        else:
            img = image_input

        faces = self.app.get(img)
        print(f"DEBUG: Found {len(faces)} faces in the image.")
        
        if not faces:
            return None
        
        # If multiple faces, we assume the target (e.g. from webcam) is the main/largest one.
        # sort by bounding box area (width * height) descending
        faces.sort(key=lambda x: (x.bbox[2]-x.bbox[0]) * (x.bbox[3]-x.bbox[1]), reverse=True)
        
        return faces[0].embedding, faces[0].bbox, img

    def get_all_faces(self, image_path):
        """
        Returns all faces found in an image path.
        Returns: list of face objects (with embeddings).
        """
        img = cv2.imread(image_path)
        if img is None:
            return []
        
        return self.app.get(img)

    def compute_similarity(self, embed1, embed2):
        """
        Computes cosine similarity between two embeddings.
        """
        if embed1 is None or embed2 is None:
            return 0.0
            
        return np.dot(embed1, embed2) / (np.linalg.norm(embed1) * np.linalg.norm(embed2))

    def is_match(self, embed1, embed2, threshold=0.5):
        """
        Checks if two embeddings belong to the same person based on a threshold.
        Default threshold 0.5 is common for arcface/insightface but may need tuning.
        """
        sim = self.compute_similarity(embed1, embed2)
        return sim > threshold, sim
