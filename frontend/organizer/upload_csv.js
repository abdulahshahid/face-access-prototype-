const API_URL = window.location.origin.includes('localhost') 
    ? 'http://localhost:8000/api' 
    : '/api';

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

        if (response.ok) {
            showMessage(`✅ Successfully processed ${data.total_processed} attendees!`, 'success');
            displayResults(data.results);
        } else {
            throw new Error(data.detail || 'Upload failed');
        }
    } catch (error) {
        showMessage(`❌ Error: ${error.message}`, 'error');
    } finally {
        loadingDiv.classList.remove('show');
        uploadBtn.disabled = false;
    }
}

function displayResults(results) {
    resultsList.innerHTML = '';
    results.forEach(item => {
        const div = document.createElement('div');
        div.className = 'result-item';
        div.innerHTML = `
            <div>
                <strong>${item.name}</strong><br>
                <small>${item.email}</small>
            </div>
            <span class="invite-code">${item.invite_code}</span>
        `;
        resultsList.appendChild(div);
    });
    resultsDiv.classList.add('show');
}

function showMessage(text, type) {
    messageDiv.innerHTML = `<div class="${type}">${text}</div>`;
}