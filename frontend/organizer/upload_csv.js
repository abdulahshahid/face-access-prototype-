// 1. FIXED: Use relative path. Nginx handles the routing automatically.
// This works on localhost, 89.117.49.7, or any domain.
const API_URL = '/api';

const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const uploadBtn = document.getElementById('uploadBtn');
const messageDiv = document.getElementById('message');
const loadingDiv = document.getElementById('loading');
const resultsDiv = document.getElementById('results');
const resultsList = document.getElementById('resultsList');

// Drag and drop handlers
['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    uploadArea.addEventListener(eventName, preventDefaults, false);
});

function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
}

uploadArea.addEventListener('dragover', () => uploadArea.classList.add('dragover'));
uploadArea.addEventListener('dragleave', () => uploadArea.classList.remove('dragover'));
uploadArea.addEventListener('drop', handleDrop);
uploadArea.addEventListener('click', () => fileInput.click());

fileInput.addEventListener('change', handleFiles);

function handleDrop(e) {
    uploadArea.classList.remove('dragover');
    const dt = e.dataTransfer;
    const files = dt.files;
    handleFiles({ target: { files: files } });
}

function handleFiles(e) {
    const file = e.target.files[0];
    if (file) {
        if (file.type !== 'text/csv' && !file.name.endsWith('.csv')) {
            showMessage('❌ Please upload a valid CSV file.', 'error');
            return;
        }
        uploadArea.innerHTML = `<p>📄 ${file.name}</p><p style="font-size:12px;color:#666;">Click to change</p>`;
        uploadBtn.style.display = 'block';
        uploadBtn.onclick = () => uploadCSV(file);
    }
}

async function uploadCSV(file) {
    loadingDiv.classList.add('show');
    uploadBtn.disabled = true;
    messageDiv.innerHTML = '';
    resultsDiv.classList.remove('show');

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch(`${API_URL}/upload-csv`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        console.log("Server Response:", data); // Debugging line

        if (response.ok) {
            showMessage(`✅ Successfully processed attendees!`, 'success');
            
            // 2. FIXED: Handle different response structures safely
            if (data.results && Array.isArray(data.results)) {
                displayResults(data.results);
            } else if (data.invite_codes && Array.isArray(data.invite_codes)) {
                displayResults(data.invite_codes);
            } else {
                console.warn("Unexpected data structure:", data);
                showMessage("✅ Upload successful, but no list returned to display.", "success");
            }
        } else {
            throw new Error(data.detail || 'Upload failed');
        }
    } catch (error) {
        console.error("Upload Error:", error);
        showMessage(`❌ Error: ${error.message}`, 'error');
    } finally {
        loadingDiv.classList.remove('show');
        uploadBtn.disabled = false;
    }
}

function displayResults(items) {
    resultsList.innerHTML = '';
    
    // Safety check before looping
    if (!items || !Array.isArray(items)) {
        console.error("displayResults received invalid data:", items);
        return;
    }

    items.forEach(item => {
        const div = document.createElement('div');
        div.className = 'result-item';
        div.innerHTML = `
            <div>
                <strong>${item.name || 'Unknown'}</strong><br>
                <small>${item.email || 'No Email'}</small>
            </div>
            <span class="invite-code">${item.invite_code || item.code || 'N/A'}</span>
        `;
        resultsList.appendChild(div);
    });
    resultsDiv.classList.add('show');
}

function showMessage(text, type) {
    messageDiv.innerHTML = `<div class="${type}">${text}</div>`;
}