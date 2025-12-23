const API_URL = '/api';

const verifyBtn = document.getElementById('verifyBtn');
const inviteInput = document.getElementById('inviteCode');
const video = document.getElementById('video');
const videoContainer = document.getElementById('video-container');
const overlay = document.getElementById('overlay');
const instruction = document.getElementById('livenessInstruction');
const captureCanvas = document.getElementById('captureCanvas');

let inviteCode = '';
let modelsLoaded = false;
let isBlinking = false;
let livenessConfirmed = false;

// --- NEW: Check URL for Invite Code on Load ---
document.addEventListener('DOMContentLoaded', () => {
    const params = new URLSearchParams(window.location.search);
    const codeFromUrl = params.get('code');
    
    if (codeFromUrl) {
        // Pre-fill and auto-start
        inviteInput.value = codeFromUrl;
        verifyBtn.click();
    }
});
// ----------------------------------------------

verifyBtn.addEventListener('click', () => {
    inviteCode = inviteInput.value.trim();
    if (inviteCode.length < 5) {
        document.getElementById('msg1').innerHTML = '<div class="error">Invalid code format</div>';
        return;
    }
    document.getElementById('step1').classList.add('hidden');
    document.getElementById('step2').classList.remove('hidden');
    
    startLivenessCheck();
});

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
            detectBlink();
        };

    } catch (err) {
        document.getElementById('msg2').innerHTML = `<div class="error">Error: ${err.message}</div>`;
        console.error(err);
    }
}

async function detectBlink() {
    if (livenessConfirmed) return;

    instruction.innerText = "Please BLINK to capture photo 📸";

    const displaySize = { width: video.videoWidth, height: video.videoHeight };
    faceapi.matchDimensions(overlay, displaySize);

    setInterval(async () => {
        if (livenessConfirmed) return;

        const detections = await faceapi.detectAllFaces(video, new faceapi.TinyFaceDetectorOptions()).withFaceLandmarks(true);
        const ctx = overlay.getContext('2d');
        ctx.clearRect(0, 0, overlay.width, overlay.height);

        if (detections.length > 0) {
            const landmarks = detections[0].landmarks;
            const leftEye = landmarks.getLeftEye();
            const rightEye = landmarks.getRightEye();

            // Calculate EAR
            const avgEAR = (getEAR(leftEye) + getEAR(rightEye)) / 2;

            if (avgEAR < 0.25) { // Blink Threshold
                if (!isBlinking) {
                    isBlinking = true;
                    instruction.innerText = "Blink Detected! Capturing...";
                    instruction.style.color = "#28a745";
                    livenessConfirmed = true;
                    setTimeout(() => captureAndRegister(), 500);
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

async function captureAndRegister() {
    captureCanvas.width = video.videoWidth;
    captureCanvas.height = video.videoHeight;
    captureCanvas.getContext('2d').drawImage(video, 0, 0);
    captureCanvas.toBlob(blob => registerUser(blob), 'image/jpeg', 0.95);
}

async function registerUser(blob) {
    const formData = new FormData();
    formData.append('photo', blob, 'face.jpg');
    formData.append('invite_code', inviteCode);
    
    instruction.innerText = "Processing Registration...";

    try {
        const response = await fetch(`${API_URL}/register`, { method: 'POST', body: formData });
        const data = await response.json();
        
        if (response.ok) {
            document.getElementById('step2').classList.add('hidden');
            document.getElementById('step3').classList.remove('hidden');
            if (video.srcObject) video.srcObject.getTracks().forEach(track => track.stop());
        } else {
            throw new Error(data.detail || 'Registration failed');
        }
    } catch (error) {
        instruction.innerText = "Error. Please reload.";
        document.getElementById('msg2').innerHTML = `<div class="error">${error.message}</div>`;
        livenessConfirmed = false;
    }
}
