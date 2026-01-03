// Check for Auth Token immediately
const adminToken = localStorage.getItem('admin_token');

if (!adminToken) {
    // If no token, kick them out to login page
    window.location.href = '/login.html';
}

const form = document.getElementById('uploadForm');
const fileInput = document.getElementById('csvFile');
const statusDiv = document.getElementById('status');
const resultsDiv = document.getElementById('results');
const codesList = document.getElementById('codesList');

// Logout Functionality
document.getElementById('logoutBtn')?.addEventListener('click', () => {
    localStorage.removeItem('admin_token');
    window.location.href = '/login.html';
});

form.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    if (!fileInput.files[0]) {
        showStatus('Please select a file', 'error');
        return;
    }

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);

    showStatus('🔐 Authenticating & Uploading...', 'processing');
    resultsDiv.hidden = true;
    codesList.innerHTML = '';

    try {
        // IMPORTANT: Point to the secured Admin Endpoint
        // Assuming your router prefix is /api/admin
        const response = await fetch('/api/admin/upload-csv', { 
            method: 'POST',
            headers: {
                // 🛑 THIS IS THE KEY FIX FOR PHASE 02
                'Authorization': `Bearer ${adminToken}`
            },
            body: formData
        });

        const data = await response.json();

        if (response.ok) {
            if (data.success_count === 0) {
                showStatus('⚠️ Upload successful, but all emails were duplicates.', 'warning');
            } else {
                showStatus(`✅ Success! Generated ${data.success_count} new invite links.`, 'success');
                // Use the data format from our new Pydantic schema
                // If the backend returns 'results', use that, otherwise refetch list
                if(data.results) displayLinks(data.results);
                else fetchLatestAttendees(); // Fallback: fetch list if upload doesn't return full objects
            }
            
            if (data.skipped_emails && data.skipped_emails.length > 0) {
                const errorMsg = document.createElement('div');
                errorMsg.className = 'error-list';
                errorMsg.innerHTML = '<br><strong>Skipped (Duplicates):</strong><br>' + data.skipped_emails.join(', ');
                statusDiv.appendChild(errorMsg);
            }
        } else {
            // Handle Auth Errors
            if (response.status === 401) {
                showStatus('❌ Session expired. Please login again.', 'error');
                setTimeout(() => { window.location.href = '/login.html'; }, 2000);
            } else {
                showStatus(data.detail || 'Upload failed', 'error');
            }
        }
    } catch (error) {
        showStatus('Network error: ' + error.message, 'error');
    }
});

function displayLinks(attendees) {
    resultsDiv.hidden = false;
    const baseUrl = window.location.origin;

    codesList.innerHTML = attendees.map(a => {
        const fullLink = `${baseUrl}/register?code=${a.invite_code}`;
        return `
        <div class="code-card">
            <div class="code-info">
                <div class="code-name">${a.name}</div>
                <div class="code-link">${a.email}</div>
            </div>
            <div style="display:flex; gap:10px; align-items:center;">
                 <input type="text" value="${fullLink}" readonly 
                        style="background: #222; border: 1px solid #444; color: #fff; padding: 5px; border-radius: 4px; width: 200px;">
                 <a href="${fullLink}" target="_blank" class="copy-btn" style="text-decoration:none;">Open 🔗</a>
            </div>
        </div>
        `;
    }).join('');
}

function showStatus(message, type) {
    statusDiv.className = `status ${type}`;
    statusDiv.innerHTML = message;
}

// Optional: Helper to fetch list if upload doesn't return full objects
async function fetchLatestAttendees() {
    const response = await fetch('/api/admin/attendees?limit=10', {
        headers: { 'Authorization': `Bearer ${adminToken}` }
    });
    if(response.ok) {
        const users = await response.json();
        displayLinks(users);
    }
}