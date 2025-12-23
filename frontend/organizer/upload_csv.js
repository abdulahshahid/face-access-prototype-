const form = document.getElementById('uploadForm');
const fileInput = document.getElementById('csvFile');
const statusDiv = document.getElementById('status');
const resultsDiv = document.getElementById('results');
const codesList = document.getElementById('codesList');

form.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    if (!fileInput.files[0]) {
        showStatus('Please select a file', 'error');
        return;
    }

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);

    showStatus('Uploading...', 'processing');
    resultsDiv.hidden = true;
    codesList.innerHTML = '';

    try {
        const response = await fetch('/api/upload-csv', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (response.ok) {
            // Warn if 0 new people (duplicates), otherwise Success
            if (data.total_processed === 0) {
                showStatus('⚠️ Upload successful, but no NEW attendees were added (all duplicates).', 'warning');
            } else {
                showStatus(`✅ Success! Generated ${data.total_processed} new invite links.`, 'success');
                displayLinks(data.results);
            }
            
            // Show errors if any
            if (data.errors && data.errors.length > 0) {
                const errorMsg = document.createElement('div');
                errorMsg.className = 'error-list';
                errorMsg.innerHTML = '<br><strong>Skipped Rows:</strong><br>' + data.errors.join('<br>');
                statusDiv.appendChild(errorMsg);
            }
        } else {
            showStatus(data.detail || 'Upload failed', 'error');
        }
    } catch (error) {
        showStatus('Network error: ' + error.message, 'error');
    }
});

function displayLinks(attendees) {
    resultsDiv.hidden = false;
    
    // 1. Get the current website address (e.g. http://89.117.49.7)
    const baseUrl = window.location.origin;

    // 2. Render each invite as a clickable link
    codesList.innerHTML = attendees.map(a => {
        const fullLink = `${baseUrl}/register?code=${a.invite_code}`;
        return `
        <div class="code-card" style="background: white; padding: 15px; margin: 10px 0; border-radius: 8px; border: 1px solid #ddd;">
            <div class="attendee-info" style="margin-bottom: 8px;">
                <strong style="font-size: 1.1em;">${a.name}</strong><br>
                <small style="color: #666;">${a.email}</small>
            </div>
            <div class="code-actions" style="display: flex; gap: 10px;">
                <input type="text" value="${fullLink}" readonly onclick="this.select()" 
                       style="flex-grow: 1; padding: 8px; border: 1px solid #ccc; border-radius: 4px; background: #f9f9f9;">
                
                <a href="${fullLink}" target="_blank" 
                   style="background: #007bff; color: white; padding: 8px 15px; text-decoration: none; border-radius: 4px; align-self: center;">
                   Open 🔗
                </a>
            </div>
        </div>
        `;
    }).join('');
}

function showStatus(message, type) {
    statusDiv.className = `status ${type}`;
    statusDiv.innerHTML = message;
}
