const API_URL = '/api';

const verifyBtn = document.getElementById('verifyBtn');
const captureBtn = document.getElementById('captureBtn');
const inviteInput = document.getElementById('inviteCode');
const video = document.getElementById('video');
let inviteCode = '';

// Step 1: Verify Code
verifyBtn.addEventListener('click', () => {
    inviteCode = inviteInput.value.trim();
    if (inviteCode.length < 5) {
        document.getElementById('msg1').innerHTML = '<div class="error">Invalid code format</div>';
        return;
    }
    document.getElementById('step1').classList.remove('active');
    document.getElementById('step2').classList.add('active');
    startCamera();
});

async function startCamera() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' } });
        video.srcObject = stream;
        video.style.display = 'block';
    } catch (err) {
        document.getElementById('msg2').innerHTML = `<div class="error">Camera error: ${err.message}</div>`;
    }
}

// Step 2: Capture and Register
captureBtn.addEventListener('click', () => {
    captureBtn.disabled = true;
    captureBtn.textContent = 'Processing...';
    
    const canvas = document.getElementById('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0);
    
    canvas.toBlob(blob => registerUser(blob), 'image/jpeg', 0.95);
});

async function registerUser(blob) {
    const formData = new FormData();
    formData.append('photo', blob, 'face.jpg');
    
    // --- FIX: Append code to BODY, not URL ---
    formData.append('invite_code', inviteCode);
    
    try {
        // --- FIX: No query params here ---
        const response = await fetch(`${API_URL}/register`, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok) {
            document.getElementById('step2').classList.remove('active');
            document.getElementById('step3').classList.add('active');
            stopCamera();
        } else {
            throw new Error(data.detail || 'Registration failed');
        }
    } catch (error) {
        document.getElementById('msg2').innerHTML = `<div class="error">${error.message}</div>`;
        captureBtn.disabled = false;
        captureBtn.textContent = 'Try Again';
    }
}

function stopCamera() {
    if (video.srcObject) {
        video.srcObject.getTracks().forEach(track => track.stop());
    }
}
