const API_URL = '/api';
let stream = null;
const video = document.getElementById('video');
const startBtn = document.getElementById('startBtn');
const checkBtn = document.getElementById('checkBtn');
const resultDiv = document.getElementById('result');

startBtn.addEventListener('click', async () => {
    try {
        stream = await navigator.mediaDevices.getUserMedia({ 
            video: { facingMode: 'user', width: 640, height: 480 } 
        });
        video.srcObject = stream;
        video.classList.add('active');
        startBtn.style.display = 'none';
        checkBtn.style.display = 'inline-block';
    } catch (error) {
        alert('Error accessing camera: ' + error.message);
    }
});

checkBtn.addEventListener('click', async () => {
    checkBtn.disabled = true;
    checkBtn.textContent = 'Checking...';
    resultDiv.innerHTML = '';
    
    const canvas = document.getElementById('canvas');
    const ctx = canvas.getContext('2d');
    
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    ctx.drawImage(video, 0, 0);
    
    canvas.toBlob(async (blob) => {
        await checkAccess(blob);
    }, 'image/jpeg', 0.95);
});

async function checkAccess(blob) {
    try {
        const formData = new FormData();
        formData.append('photo', blob, 'photo.jpg');
        
        const response = await fetch(`${API_URL}/access-check`, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        displayResult(data);
    } catch (error) {
        resultDiv.innerHTML = `
            <div class="result no">
                ❌ ERROR
                <div class="info">${error.message}</div>
            </div>
        `;
    } finally {
        checkBtn.disabled = false;
        checkBtn.textContent = 'Check Access';
    }
}

function displayResult(data) {
    const isOk = data.status === 'OK';
    const icon = isOk ? '✅' : '❌';
    const className = isOk ? 'ok' : 'no';
    
    // Only show confidence for successful matches
    const confidenceHTML = isOk && data.confidence 
        ? `<div class="confidence">Confidence: ${data.confidence.toFixed(1)}%</div>`
        : '';
    
    resultDiv.innerHTML = `
        <div class="result ${className}">
            ${icon} ${data.status}
            ${confidenceHTML}
            <div class="info">${data.message}</div>
        </div>
    `;
    
    // Auto-clear result after 5 seconds
    setTimeout(() => {
        resultDiv.innerHTML = '';
    }, 5000);
}