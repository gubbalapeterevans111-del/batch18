const webcam = document.getElementById('webcam');
const canvas = document.getElementById('canvas');
const capturePreview = document.getElementById('capture-preview');
const startCamBtn = document.getElementById('start-cam-btn');
const captureBtn = document.getElementById('capture-btn');
const retakeBtn = document.getElementById('retake-btn');
const findBtn = document.getElementById('find-btn');
const gdriveInput = document.getElementById('gdrive-link');
const errorMsg = document.getElementById('error-msg');
const progressSection = document.getElementById('progress-section');
const statusText = document.getElementById('status-text');
const progressBar = document.getElementById('progress-bar');
const resultsGrid = document.getElementById('results-section');
const downloadSection = document.getElementById('download-section');
const downloadBtn = document.getElementById('download-btn');

let stream = null;
let capturedImage = null;
let sessionId = null;

// 1. Webcam Logic
async function initCamera() {
    // Check if secure context
    if (!window.isSecureContext) {
        showError("Camera requires a Secure Context. Please use http://127.0.0.1:5000");
        return;
    }

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        showError("Browser requires HTTPS for camera. Please use localhost.");
        return;
    }

    try {
        stream = await navigator.mediaDevices.getUserMedia({ video: true });
        webcam.srcObject = stream;
        // Explicitly play to avoid black screen on some browsers
        await webcam.play();

        startCamBtn.style.display = 'none';
        captureBtn.disabled = false;
        errorMsg.style.display = 'none';
        console.log("Camera started successfully");
    } catch (err) {
        if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
            showError("Permission denied. Click the lock icon in the URL bar to allow camera access.");
        } else if (err.name === 'NotFoundError') {
            showError("No camera found. Please connect a webcam.");
        } else {
            showError(`Camera error: ${err.name} - ${err.message}`);
        }
        console.error(err);
    }
}

// Event Listeners
startCamBtn.addEventListener('click', initCamera);

// Spacebar Listener
document.addEventListener('keydown', (event) => {
    if (event.code === 'Space') {
        if (!captureBtn.disabled && captureBtn.offsetParent !== null) {
            event.preventDefault();
            captureBtn.click();
        } else if (startCamBtn.offsetParent !== null && startCamBtn.style.display !== 'none') {
            event.preventDefault();
            initCamera();
        }
    }
});

captureBtn.addEventListener('click', () => {
    // Draw frame to canvas
    canvas.width = webcam.videoWidth;
    canvas.height = webcam.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(webcam, 0, 0);

    // Convert to base64
    capturedImage = canvas.toDataURL('image/jpeg');

    // Show preview
    capturePreview.src = capturedImage;
    capturePreview.style.display = 'block';

    // Transform stream tracks
    if (stream) {
        stream.getTracks().forEach(track => track.stop());
    }

    // Hide webcam video
    webcam.style.display = 'none';

    // Toggle buttons
    captureBtn.style.display = 'none';
    retakeBtn.style.display = 'inline-block';

    checkReady();
});

retakeBtn.addEventListener('click', () => {
    capturePreview.style.display = 'none';
    webcam.style.display = 'block';
    capturedImage = null;

    captureBtn.style.display = 'inline-block';
    retakeBtn.style.display = 'none';

    // Restart the camera so they can retake
    initCamera();

    checkReady();
});

gdriveInput.addEventListener('input', checkReady);

function checkReady() {
    if (capturedImage && gdriveInput.value.trim().length > 0) {
        findBtn.disabled = false;
    } else {
        findBtn.disabled = true;
    }
}

function showError(msg) {
    errorMsg.textContent = msg;
    errorMsg.style.display = 'block';
}

// 2. API Logic
findBtn.addEventListener('click', async () => {
    const link = gdriveInput.value.trim();
    if (!link || !capturedImage) return;

    // UI Reset
    findBtn.disabled = true;
    errorMsg.style.display = 'none';
    progressSection.style.display = 'block';
    downloadSection.style.display = 'none';
    resultsGrid.innerHTML = '';

    try {
        const response = await fetch('/api/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ link: link, image: capturedImage })
        });

        // Handle HTML error pages (Flask default)
        const contentType = response.headers.get("content-type");
        if (contentType && contentType.indexOf("application/json") === -1) {
            const text = await response.text();
            console.error("Server returned non-JSON:", text);
            throw new Error(`Server Error (${response.status}). Check terminal for details.`);
        }

        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.error || 'Server error');
        }

        const data = await response.json();
        console.log("Search started:", data);
        sessionId = data.session_id;

        // Start polling
        pollStatus();

    } catch (err) {
        console.error(err);
        showError(err.message);
        findBtn.disabled = false;
    }
});

async function pollStatus() {
    if (!sessionId) return;
    const interval = setInterval(async () => {
        try {
            const res = await fetch('/api/status?session_id=' + sessionId);
            const data = await res.json();

            // Update UI
            statusText.textContent = data.message;
            if (data.progress) {
                progressBar.style.width = data.progress + '%';
            }

            // Update Matches
            if (data.matches) {
                updateGallery(data.matches);
            }

            if (data.status === 'complete') {
                clearInterval(interval);
                findBtn.disabled = false;
                progressBar.style.width = '100%';
                if (!data.matches || data.matches.length === 0) {
                    showError("Search finished but no matches were found.");
                }
                if (data.download_url) {
                    downloadBtn.href = data.download_url;
                    downloadSection.style.display = 'block';
                }
            } else if (data.status === 'error') {
                clearInterval(interval);
                findBtn.disabled = false;
                showError(data.error);
            }

        } catch (err) {
            console.error("Poll error:", err);
        }
    }, 1000);
}

function updateGallery(matches) {
    // Determine existing
    const currentCount = resultsGrid.children.length;
    if (matches.length > currentCount) {
        // Add new ones
        for (let i = currentCount; i < matches.length; i++) {
            const imgParams = matches[i];
            const img = document.createElement('img');
            img.src = imgParams;
            img.loading = 'lazy';

            // Fade in
            img.style.opacity = 0;
            resultsGrid.appendChild(img);

            setTimeout(() => {
                img.style.opacity = 1;
            }, 50);
        }
    }
}
