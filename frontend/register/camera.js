const API_URL = '/api';

const verifyBtn = document.getElementById('verifyBtn');
const inviteInput = document.getElementById('inviteCode');
const video = document.getElementById('video');
const videoContainer = document.getElementById('video-container');
const overlay = document.getElementById('overlay');
const instruction = document.getElementById('livenessInstruction');
const captureCanvas = document.getElementById('captureCanvas');

// New DOM Elements
const step1 = document.getElementById('step1');
const step2 = document.getElementById('step2');
const stepPreview = document.getElementById('step-preview');
const step3 = document.getElementById('step3');
const previewImg = document.getElementById('previewImg');
const retakeBtn = document.getElementById('retakeBtn');
const confirmBtn = document.getElementById('confirmBtn');

let inviteCode = '';
let modelsLoaded = false;
let isBlinking = false;
let livenessConfirmed = false;
let blinkInterval = null; // Store interval to clear it later
let capturedBlob = null;  // Store the blob for upload
let brightnessCheckInterval = null; // Store brightness check interval

// --- Check URL for Invite Code on Load ---
document.addEventListener('DOMContentLoaded', () => {
    const params = new URLSearchParams(window.location.search);
    const codeFromUrl = params.get('code');

    if (codeFromUrl) {
        inviteInput.value = codeFromUrl;
        verifyBtn.click();
    }
});

verifyBtn.addEventListener('click', () => {
    inviteCode = inviteInput.value.trim();
    if (inviteCode.length < 5) {
        document.getElementById('msg1').innerHTML = '<div class="error">Invalid code format</div>';
        return;
    }
    step1.classList.add('hidden');
    step2.classList.remove('hidden');

    startLivenessCheck();
});

// --- NEW: Retake and Confirm Logic ---
retakeBtn.addEventListener('click', () => {
    stepPreview.classList.add('hidden');
    step2.classList.remove('hidden');
    
    // Reset State
    livenessConfirmed = false;
    isBlinking = false;
    capturedBlob = null;
    
    instruction.innerText = "Please look into the camera and blink to capture photo 📸";
    instruction.classList.remove('warning', 'error');
    
    video.play();
    startBrightnessMonitoring(); // Restart brightness monitoring
    detectBlink(); // Restart detection loop
});

confirmBtn.addEventListener('click', () => {
    if (capturedBlob) {
        registerUser(capturedBlob);
    }
});
// -------------------------------------

async function startLivenessCheck() {
    try {
        instruction.innerText = "Loading AI Models...";

        await faceapi.nets.tinyFaceDetector.loadFromUri('/libs');
        await faceapi.nets.faceLandmark68TinyNet.loadFromUri('/libs');

        modelsLoaded = true;

        const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' } });
        video.srcObject = stream;
        videoContainer.style.display = 'block';

        video.onloadedmetadata = () => {
            video.play();
            startBrightnessMonitoring(); // Start monitoring brightness
            detectBlink();
        };

    } catch (err) {
        document.getElementById('msg2').innerHTML = `<div class="error">Error: ${err.message}</div>`;
        console.error(err);
    }
}

async function detectBlink() {
    if (livenessConfirmed) return;
    if (blinkInterval) clearInterval(blinkInterval); // Ensure no duplicate loops

    const displaySize = { width: video.videoWidth, height: video.videoHeight };
    faceapi.matchDimensions(overlay, displaySize);

    blinkInterval = setInterval(async () => {
        if (livenessConfirmed) return;

        const detections = await faceapi.detectAllFaces(video, new faceapi.TinyFaceDetectorOptions()).withFaceLandmarks(true);
        const ctx = overlay.getContext('2d');
        ctx.clearRect(0, 0, overlay.width, overlay.height);

        if (detections.length > 0) {
            const brightness = checkBrightness(video, captureCanvas);
            
            // Only allow blink detection if lighting is adequate
            if (brightness < 50) {
                // Too dark - brightness monitor will show warning
                return;
            }
            
            const landmarks = detections[0].landmarks;
            const leftEye = landmarks.getLeftEye();
            const rightEye = landmarks.getRightEye();

            const avgEAR = (getEAR(leftEye) + getEAR(rightEye)) / 2;

            if (avgEAR < 0.25) { // Blink Threshold
                if (!isBlinking) {
                    isBlinking = true;
                    instruction.innerText = "Blink Detected! Capturing...";
                    instruction.classList.remove('warning', 'error');
                    instruction.style.color = "#28a745";
                    livenessConfirmed = true;
                    clearInterval(blinkInterval); // Stop detecting
                    clearInterval(brightnessCheckInterval); // Stop brightness check
                    
                    // Show Preview instead of registering immediately
                    setTimeout(() => captureAndPreview(), 500);
                }
            } else {
                isBlinking = false;
            }
            faceapi.draw.drawFaceLandmarks(overlay, detections);
        }
    }, 100);
}

function getEAR(eye) {
    const A = dist(eye[1], eye[5]);
    const B = dist(eye[2], eye[4]);
    const C = dist(eye[0], eye[3]);
    return (A + B) / (2.0 * C);
}

function dist(p1, p2) {
    return Math.sqrt(Math.pow(p1.x - p2.x, 2) + Math.pow(p1.y - p2.y, 2));
}

// Brightness Detection Function
function checkBrightness(video, canvas) {
    const ctx = canvas.getContext('2d');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    
    const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
    const data = imageData.data;
    let brightnessSum = 0;
    
    // Sample every 10th pixel for performance
    for (let i = 0; i < data.length; i += 40) {
        const r = data[i];
        const g = data[i + 1];
        const b = data[i + 2];
        // Calculate perceived brightness (weighted for human perception)
        brightnessSum += (0.299 * r + 0.587 * g + 0.114 * b);
    }
    
    const avgBrightness = brightnessSum / (data.length / 40);
    return avgBrightness;
}

function startBrightnessMonitoring() {
    if (brightnessCheckInterval) clearInterval(brightnessCheckInterval);
    
    brightnessCheckInterval = setInterval(() => {
        if (livenessConfirmed) {
            clearInterval(brightnessCheckInterval);
            return;
        }
        
        const brightness = checkBrightness(video, captureCanvas);
        
        // Brightness thresholds
        const TOO_DARK = 50;  // Adjust based on testing
        const GOOD_LIGHT = 80; // Minimum acceptable brightness
        
        if (brightness < TOO_DARK) {
            instruction.innerHTML = "⚠️ Too Dark! Please move to a brighter area";
            instruction.classList.remove('error');
            instruction.classList.add('warning');
        } else if (brightness < GOOD_LIGHT) {
            instruction.innerHTML = "💡 Lighting could be better. Move to brighter area for best results";
            instruction.classList.remove('error');
            instruction.classList.add('warning');
        } else {
            instruction.innerHTML = "Please look into the camera and blink to capture photo 📸";
            instruction.classList.remove('warning', 'error');
        }
    }, 500); // Check every 500ms
}

// Replaced captureAndRegister with captureAndPreview
async function captureAndPreview() {
    captureCanvas.width = video.videoWidth;
    captureCanvas.height = video.videoHeight;
    captureCanvas.getContext('2d').drawImage(video, 0, 0);
    
    // Convert to blob and show preview
    captureCanvas.toBlob(blob => {
        capturedBlob = blob;
        const previewUrl = URL.createObjectURL(blob);
        previewImg.src = previewUrl;
        
        // Pause video to save resources
        video.pause();
        
        // Switch UI
        step2.classList.add('hidden');
        stepPreview.classList.remove('hidden');
    }, 'image/jpeg', 0.95);
}

async function registerUser(blob) {
    const formData = new FormData();
    formData.append('photo', blob, 'face.jpg');
    formData.append('invite_code', inviteCode);

    // Disable button to prevent double clicks
    confirmBtn.disabled = true;
    confirmBtn.innerText = "Processing...";

    try {
        const response = await fetch(`${API_URL}/register`, { method: 'POST', body: formData });
        const data = await response.json();

        if (response.ok) {
            stepPreview.classList.add('hidden');
            step3.classList.remove('hidden');
            if (video.srcObject) video.srcObject.getTracks().forEach(track => track.stop());
        } else {
            throw new Error(data.detail || 'Registration failed');
        }
    } catch (error) {
        alert(`Registration Error: ${error.message}`);
        confirmBtn.disabled = false;
        confirmBtn.innerText = "Register";
    }
}