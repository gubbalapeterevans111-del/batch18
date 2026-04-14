import cv2
import time

def capture_target_face():
    """
    Opens the webcam and allows the user to capture a face.
    Press 's' or 'SPACE' to save the current frame.
    Press 'q' or 'ESC' to quit without saving.
    Returns: captured frame (numpy array) or None
    """
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Cannot open camera")
        return None

    print("Press 'SPACE' to capture your face. Press 'ESC' to cancel.")
    
    captured_frame = None

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Can't receive frame (stream end?). Exiting ...")
            break

        # Display the resulting frame
        cv2.imshow('Capture Target Face - Press SPACE', frame)
        
        key = cv2.waitKey(1)
        if key % 256 == 32: # SPACE
            # Capture
            captured_frame = frame
            print("Image captured!")
            break
        elif key % 256 == 27: # ESC
            print("Capture cancelled.")
            break

    cap.release()
    cv2.destroyAllWindows()
    return captured_frame
