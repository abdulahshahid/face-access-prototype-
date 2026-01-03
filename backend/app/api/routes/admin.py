import io
import csv
import logging
from typing import List, Optional
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query, status, Request
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session

from db.session import get_db
from models.attendee import Attendee
from core.deps import get_current_admin
from core.security import generate_invite_code, verify_access_token
from core.qdrant_ops import qdrant_service
from schemas import AttendeeResponse, BatchUploadResponse

router = APIRouter()
logger = logging.getLogger(__name__)

# ==============================================================================
# AUTH HELPER
# ==============================================================================

def check_auth_and_redirect(request: Request):
    """Check if user is authenticated, return (is_authenticated, redirect_response_or_none)"""
    auth_header = request.headers.get("Authorization")
    token = None
    
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
    
    # Also check cookies
    if not token:
        token = request.cookies.get("access_token")
    
    if token:
        try:
            payload = verify_access_token(token)
            if payload:
                return True, None
        except Exception as e:
            logger.warning(f"Token verification failed: {e}")
    
    # Not authenticated - check if this is an API request or HTML request
    accept_header = request.headers.get("Accept", "")
    if "text/html" in accept_header or request.url.path.endswith("/portal"):
        return False, RedirectResponse(url="/api/admin/portal/login")
    else:
        return False, JSONResponse(
            status_code=401,
            content={"detail": "Not authenticated"}
        )

# ==============================================================================
# ROUTES
# ==============================================================================

@router.get("/")
async def admin_root(request: Request):
    """Redirect to portal"""
    return RedirectResponse(url="/api/admin/portal")

@router.get("/attendees", response_model=List[AttendeeResponse])
def get_attendees(
    request: Request,
    skip: int = 0, 
    limit: int = 100, 
    search: Optional[str] = None, 
    db: Session = Depends(get_db)
):
    """Get all attendees with pagination"""
    is_auth, redirect_response = check_auth_and_redirect(request)
    if not is_auth:
        return redirect_response
    
    query = db.query(Attendee)
    
    if search:
        search_fmt = f"%{search}%"
        query = query.filter(
            (Attendee.email.ilike(search_fmt)) | 
            (Attendee.name.ilike(search_fmt))
        )
    
    users = query.order_by(Attendee.created_at.desc()).offset(skip).limit(limit).all()
    return users

@router.delete("/attendees/{user_id}")
def delete_attendee(
    request: Request,
    user_id: int, 
    db: Session = Depends(get_db)
):
    """Hard Delete user from SQL and Vector DB"""
    is_auth, redirect_response = check_auth_and_redirect(request)
    if not is_auth:
        return redirect_response
    
    user = db.query(Attendee).filter(Attendee.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"User with ID {user_id} not found"
        )
    
    email_backup = user.email
    
    vector_deleted = False
    try:
        vector_deleted = qdrant_service.delete_user_vector(user_id)
        if not vector_deleted:
             logger.warning(f"⚠️ Vector deletion returned False for user {user_id}")
    except Exception as e:
        logger.error(f"❌ CRITICAL: Failed to delete vector for {user_id}: {e}")

    try:
        db.delete(user)
        db.commit()
        
        logger.info(f"🗑️ [Admin] Deleted user {user_id} ({email_backup})")
        
        return {
            "status": "success", 
            "message": f"User {email_backup} deleted successfully.", 
            "vector_cleaned": vector_deleted
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ DB Delete failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Internal Database Error during deletion."
        )

@router.post("/upload-csv", response_model=BatchUploadResponse)
async def upload_csv(
    request: Request,
    file: UploadFile = File(...), 
    db: Session = Depends(get_db)
):
    """Bulk import users via CSV"""
    is_auth, redirect_response = check_auth_and_redirect(request)
    if not is_auth:
        return redirect_response
    
    if not file.filename.lower().endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Invalid file format. Please upload a .csv file."
        )

    try:
        content = await file.read()
        decoded_content = content.decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(decoded_content))
    except Exception as e:
        logger.error(f"CSV Reading Error: {e}")
        raise HTTPException(status_code=400, detail="Could not read or decode CSV file.")
    
    headers = [h.lower().strip() for h in csv_reader.fieldnames or []]
    if 'email' not in headers:
         raise HTTPException(
             status_code=400, 
             detail=f"CSV is missing required 'email' column. Found: {headers}"
         )

    new_attendees = []
    skipped_emails = []
    
    for row in csv_reader:
        clean_row = {k.lower().strip(): v.strip() for k, v in row.items() if k}
        
        email = clean_row.get('email')
        name = clean_row.get('name', 'Unknown')

        if not email:
            continue

        existing = db.query(Attendee).filter(Attendee.email == email).first()
        if existing:
            skipped_emails.append(email)
            continue

        invite_code = generate_invite_code()
        attendee = Attendee(
            name=name,
            email=email,
            invite_code=invite_code,
            status="pending"
        )
        db.add(attendee)
        new_attendees.append(attendee)

    try:
        db.commit()
        logger.info(f"✅ [Admin] Batch Import: {len(new_attendees)} created, {len(skipped_emails)} skipped")
        
        return {
            "total_processed": len(new_attendees) + len(skipped_emails), 
            "success_count": len(new_attendees),
            "skipped_emails": skipped_emails
        }
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Batch Upload Commit Failed: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Database error while saving users."
        )

# ==============================================================================
# ADMIN PORTAL PAGES
# ==============================================================================

BASE_DIR = Path(__file__).parent.parent.parent
ADMIN_PORTAL_DIR = BASE_DIR / "admin-portal"
print(f"Admin Portal Directory: {ADMIN_PORTAL_DIR} {BASE_DIR}")
ADMIN_PORTAL_DIR.mkdir(exist_ok=True)

@router.get("/portal/upload", response_class=HTMLResponse)
async def upload_page(request: Request):
    """Serve the CSV upload page"""
    is_auth, redirect_response = check_auth_and_redirect(request)
    if not is_auth and redirect_response:
        return redirect_response
    
    # Return the upload page HTML with INLINE JavaScript
    return HTMLResponse("""
    <!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="icon" type="image/svg+xml" href="public/favicon.svg">
    <link rel="alternate icon" href="/favicon.ico">
    <title>Organizer Portal - Upload CSV</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0a0a0f;
            color: #ffffff;
            min-height: 100vh;
            overflow-x: hidden;
        }
        
        /* Animated gradient background */
        .bg-gradient {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: radial-gradient(circle at 20% 50%, rgba(120, 119, 198, 0.15) 0%, transparent 50%),
                        radial-gradient(circle at 80% 80%, rgba(99, 102, 241, 0.15) 0%, transparent 50%),
                        radial-gradient(circle at 40% 20%, rgba(168, 85, 247, 0.1) 0%, transparent 40%);
            z-index: 0;
        }
        
        .container {
            position: relative;
            z-index: 1;
            max-width: 900px;
            margin: 0 auto;
            padding: 60px 24px;
        }
        
        /* Back button */
        .back-link {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            color: rgba(255, 255, 255, 0.6);
            text-decoration: none;
            font-size: 14px;
            margin-bottom: 32px;
            transition: color 0.3s;
        }
        
        .back-link:hover {
            color: rgba(255, 255, 255, 0.9);
        }
        
        /* Card */
        .card {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 20px;
            padding: 48px 40px;
            backdrop-filter: blur(10px);
        }
        
        h1 {
            font-size: 36px;
            font-weight: 700;
            margin-bottom: 12px;
            letter-spacing: -0.02em;
        }
        
        .description {
            font-size: 16px;
            color: rgba(255, 255, 255, 0.6);
            margin-bottom: 40px;
            line-height: 1.6;
        }
        
        /* Upload Area */
        .upload-area {
            border: 2px dashed rgba(99, 102, 241, 0.3);
            background: rgba(99, 102, 241, 0.05);
            padding: 60px 40px;
            text-align: center;
            border-radius: 16px;
            transition: all 0.3s;
            cursor: pointer;
        }
        
        .upload-area:hover {
            border-color: rgba(99, 102, 241, 0.5);
            background: rgba(99, 102, 241, 0.08);
        }
        
        .upload-icon {
            width: 64px;
            height: 64px;
            background: linear-gradient(135deg, rgba(99, 102, 241, 0.2) 0%, rgba(168, 85, 247, 0.2) 100%);
            border: 1px solid rgba(99, 102, 241, 0.3);
            border-radius: 16px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 28px;
            margin-bottom: 20px;
        }
        
        .upload-text {
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 8px;
        }
        
        .upload-hint {
            font-size: 14px;
            color: rgba(255, 255, 255, 0.5);
        }
        
        input[type="file"] {
            display: none;
        }
        
        .file-selected {
            margin-top: 20px;
            padding: 12px 20px;
            background: rgba(34, 197, 94, 0.1);
            border: 1px solid rgba(34, 197, 94, 0.3);
            border-radius: 10px;
            color: rgba(34, 197, 94, 1);
            font-size: 14px;
            display: none;
        }
        
        .btn {
            background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
            color: white;
            border: none;
            padding: 14px 32px;
            border-radius: 12px;
            cursor: pointer;
            font-size: 16px;
            font-weight: 600;
            margin-top: 24px;
            transition: all 0.3s;
            width: 100%;
            max-width: 300px;
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 30px rgba(99, 102, 241, 0.3);
        }
        
        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }
        
        /* Status Messages */
        .status {
            margin-top: 24px;
            padding: 16px 20px;
            border-radius: 12px;
            display: none;
            font-size: 14px;
            line-height: 1.6;
        }
        
        .status.success {
            background: rgba(34, 197, 94, 0.1);
            border: 1px solid rgba(34, 197, 94, 0.3);
            color: rgba(34, 197, 94, 1);
            display: block;
        }
        
        .status.error {
            background: rgba(239, 68, 68, 0.1);
            border: 1px solid rgba(239, 68, 68, 0.3);
            color: rgba(239, 68, 68, 1);
            display: block;
        }
        
        .status.warning {
            background: rgba(245, 158, 11, 0.1);
            border: 1px solid rgba(245, 158, 11, 0.3);
            color: rgba(245, 158, 11, 1);
            display: block;
        }
        
        .status.processing {
            background: rgba(99, 102, 241, 0.1);
            border: 1px solid rgba(99, 102, 241, 0.3);
            color: rgba(99, 102, 241, 1);
            display: flex;
            align-items: center;
            gap: 12px;
        }
        
        .spinner {
            width: 16px;
            height: 16px;
            border: 2px solid rgba(99, 102, 241, 0.3);
            border-top-color: rgba(99, 102, 241, 1);
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        /* Results Section */
        #results {
            margin-top: 40px;
            padding-top: 40px;
            border-top: 1px solid rgba(255, 255, 255, 0.08);
        }
        
        #results h3 {
            font-size: 24px;
            font-weight: 600;
            margin-bottom: 24px;
            letter-spacing: -0.01em;
        }
        
        .code-card {
            background: white;
            padding: 15px;
            margin: 10px 0;
            border-radius: 8px;
            border: 1px solid #ddd;
        }
        
        .attendee-info {
            margin-bottom: 8px;
        }
        
        .attendee-info strong {
            font-size: 1.1em;
            color: #333;
        }
        
        .attendee-info small {
            color: #666;
        }
        
        .code-actions {
            display: flex;
            gap: 10px;
        }
        
        .code-actions input[type="text"] {
            flex-grow: 1;
            padding: 8px;
            border: 1px solid #ccc;
            border-radius: 4px;
            background: #f9f9f9;
            color: #333;
        }
        
        .code-actions a {
            background: #007bff;
            color: white;
            padding: 8px 15px;
            text-decoration: none;
            border-radius: 4px;
            align-self: center;
        }
        
        .code-actions a:hover {
            background: #0056b3;
        }
        
        .error-list {
            margin-top: 10px;
            padding: 10px;
            background: rgba(239, 68, 68, 0.1);
            border-radius: 8px;
            color: #ef4444;
        }
        
        /* Responsive */
        @media (max-width: 768px) {
            .container {
                padding: 40px 20px;
            }
            
            .card {
                padding: 32px 24px;
            }
            
            .upload-area {
                padding: 40px 24px;
            }
            
            h1 {
                font-size: 28px;
            }
            
            .code-actions {
                flex-direction: column;
            }
            
            .code-actions a {
                width: 100%;
                text-align: center;
            }
        }
    </style>
</head>
<body>
    <div class="bg-gradient"></div>
    
    <div class="container">
        <a href="/api/admin/portal" class="back-link">
            ← Back to Admin Portal
        </a>
        
        <div class="card">
            <h1>📋 Bulk Upload CSV</h1>
            <p class="description">Upload your attendee list (CSV format) to generate secure invite links for each person.</p>
            
            <form id="uploadForm">
                <div class="upload-area" onclick="document.getElementById('csvFile').click()">
                    <div class="upload-icon">📄</div>
                    <div class="upload-text">Click to upload CSV file</div>
                    <div class="upload-hint">or drag and drop your file here</div>
                    <div class="file-selected" id="fileSelected"></div>
                </div>
                <input type="file" id="csvFile" accept=".csv" required>
                <center>
                    <button type="submit" class="btn">Generate Invite Links</button>
                </center>
            </form>
            
            <div id="status"></div>
            
            <div id="results" hidden>
                <h3>Generated Invite Links</h3>
                <div id="codesList"></div>
            </div>
        </div>
    </div>
    
    <script>
        // Show selected file name
        document.getElementById('csvFile').addEventListener('change', function(e) {
            const fileName = e.target.files[0]?.name;
            const fileSelected = document.getElementById('fileSelected');
            if (fileName) {
                fileSelected.textContent = `Selected: ${fileName}`;
                fileSelected.style.display = 'block';
            }
        });
        
        // Prevent default drag behaviors
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            document.querySelector('.upload-area').addEventListener(eventName, preventDefaults, false);
        });
        
        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }
        
        // Handle drop
        document.querySelector('.upload-area').addEventListener('drop', function(e) {
            const dt = e.dataTransfer;
            const files = dt.files;
            document.getElementById('csvFile').files = files;
            
            const fileName = files[0]?.name;
            const fileSelected = document.getElementById('fileSelected');
            if (fileName) {
                fileSelected.textContent = `Selected: ${fileName}`;
                fileSelected.style.display = 'block';
            }
        });
        
        // YOUR EXACT JAVASCRIPT LOGIC - with ONLY the endpoint changed
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
                // ONLY CHANGE: Updated endpoint from /api/upload-csv to /api/admin/upload-csv
                const response = await fetch('/api/admin/upload-csv', {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json();
                console.log('API Response:', data); // Debug log to see actual structure

                if (response.ok) {
                    // Warn if 0 new people (duplicates), otherwise Success
                    // Check both total_processed and success_count
                    const processedCount = data.total_processed || data.success_count || 0;
                    
                    if (processedCount === 0) {
                        showStatus('⚠️ Upload successful, but no NEW attendees were added (all duplicates).', 'warning');
                    } else {
                        showStatus(`✅ Success! Generated ${processedCount} new invite links.`, 'success');
                        
                        // Check if we have results to display
                        if (data.results && Array.isArray(data.results) && data.results.length > 0) {
                            displayLinks(data.results);
                        } else if (data.success_count > 0) {
                            // If API doesn't return results but we know success_count > 0
                            // Fetch the recently created attendees
                            fetchRecentAttendees();
                        }
                    }
                    
                    // Show errors if any - check both errors and skipped_emails
                    if (data.errors && data.errors.length > 0) {
                        const errorMsg = document.createElement('div');
                        errorMsg.className = 'error-list';
                        errorMsg.innerHTML = '<br><strong>Skipped Rows:</strong><br>' + data.errors.join('<br>');
                        statusDiv.appendChild(errorMsg);
                    }
                    
                    // Also check for skipped_emails
                    if (data.skipped_emails && data.skipped_emails.length > 0) {
                        const skippedMsg = document.createElement('div');
                        skippedMsg.className = 'error-list';
                        skippedMsg.innerHTML = '<br><strong>Skipped Duplicates:</strong><br>' + data.skipped_emails.join('<br>');
                        statusDiv.appendChild(skippedMsg);
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
                <div class="code-card">
                    <div class="attendee-info">
                        <strong>${a.name}</strong><br>
                        <small>${a.email}</small>
                    </div>
                    <div class="code-actions">
                        <input type="text" value="${fullLink}" readonly onclick="this.select()">
                        <a href="${fullLink}" target="_blank">
                            Open 🔗
                        </a>
                    </div>
                </div>
                `;
            }).join('');
        }

        // Helper function to fetch recently created attendees if API doesn't return them
        async function fetchRecentAttendees() {
            try {
                const response = await fetch('/api/admin/attendees/recent');
                if (response.ok) {
                    const data = await response.json();
                    if (data.attendees && Array.isArray(data.attendees) && data.attendees.length > 0) {
                        displayLinks(data.attendees);
                    }
                }
            } catch (error) {
                console.log('Could not fetch recent attendees:', error);
            }
        }

        function showStatus(message, type) {
            statusDiv.className = `status ${type}`;
            statusDiv.innerHTML = type === 'processing' ? 
                `<div class="spinner"></div>${message}` : 
                message;
        }
    </script>
</body>
</html>
    """)

@router.get("/portal", response_class=HTMLResponse)
async def admin_portal(request: Request):
    """Serve the main admin portal page"""
    is_auth, redirect_response = check_auth_and_redirect(request)
    if not is_auth and redirect_response:
        return redirect_response
    
    portal_page = ADMIN_PORTAL_DIR / "index.html"
    if portal_page.exists():
        return FileResponse(portal_page)
    
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Admin Portal - Face Access Control</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #0a0a0f 0%, #1a1a2e 100%);
                color: white;
                min-height: 100vh;
                padding: 20px;
            }
            .container { max-width: 1200px; margin: 0 auto; }
            .header { 
                display: flex; 
                justify-content: space-between; 
                align-items: center;
                margin-bottom: 40px;
                padding: 20px;
                background: rgba(255,255,255,0.05);
                border-radius: 15px;
            }
            h1 { color: #6366f1; font-size: 2rem; }
            .logout-btn {
                background: rgba(255,255,255,0.1);
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 8px;
                cursor: pointer;
                transition: all 0.3s;
            }
            .logout-btn:hover { background: rgba(255,255,255,0.2); }
            .grid { 
                display: grid; 
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }
            .card { 
                background: rgba(255,255,255,0.05);
                backdrop-filter: blur(10px);
                padding: 30px;
                border-radius: 15px;
                border: 1px solid rgba(255,255,255,0.1);
                transition: all 0.3s;
            }
            .card:hover { 
                transform: translateY(-5px);
                border-color: #6366f1;
                box-shadow: 0 10px 30px rgba(99, 102, 241, 0.2);
            }
            .card h3 { color: #a855f7; margin-bottom: 15px; }
            .btn { 
                background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
                color: white;
                padding: 12px 24px;
                border: none;
                border-radius: 8px;
                cursor: pointer;
                font-size: 16px;
                transition: all 0.3s;
                text-decoration: none;
                display: inline-block;
                margin-top: 15px;
            }
            .btn:hover { 
                transform: scale(1.05);
                box-shadow: 0 5px 15px rgba(99, 102, 241, 0.4);
            }
            .link-list { list-style: none; margin-top: 15px; }
            .link-list li { margin: 10px 0; }
            .link-list a { 
                color: #a855f7; 
                text-decoration: none;
                transition: color 0.3s;
            }
            .link-list a:hover { color: #6366f1; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔐 Admin Portal</h1>
                <button class="logout-btn" onclick="logout()">Logout</button>
            </div>
            
            <div class="grid">
                <div class="card">
                    <h3>👥 Manage Attendees</h3>
                    <p>View, search, and manage all registered attendees in the system.</p>
                    <button class="btn" onclick="window.location.href='/api/admin/attendees'">View Attendees</button>
                </div>
                
                <div class="card">
                    <h3>📤 Bulk Upload</h3>
                    <p>Upload CSV files to add multiple attendees at once.</p>
                    <button class="btn" onclick="window.location.href='/api/admin/portal/upload'">Upload CSV</button>
                </div>
                
                <div class="card">
                    <h3>📊 Quick Links</h3>
                    <ul class="link-list">
                        <li><a href="/api/admin/attendees">→ List All Attendees</a></li>
                        <li><a href="/docs">→ API Documentation</a></li>
                        <li><a href="/api/admin/portal">→ Portal Home</a></li>
                    </ul>
                </div>
            </div>
        </div>
        
        <script>
            function logout() {
                localStorage.removeItem('access_token');
                document.cookie = 'access_token=; Max-Age=0; path=/';
                window.location.href = '/api/admin/portal/login';
            }
            
            function showUploadForm() {
                alert('CSV upload form will be implemented. For now, use the API endpoint: POST /api/admin/upload-csv');
            }
        </script>
    </body>
    </html>
    """)



@router.get("/portal/login", response_class=HTMLResponse)
async def admin_portal_login():
    """Serve the admin portal login page"""
    login_page = ADMIN_PORTAL_DIR / "login.html"
    if login_page.exists():
        return FileResponse(login_page)
    
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Admin Login</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #0a0a0f 0%, #1a1a2e 100%);
                color: white;
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .login-box { 
                max-width: 450px;
                width: 100%;
                background: rgba(255,255,255,0.05);
                backdrop-filter: blur(10px);
                padding: 50px;
                border-radius: 20px;
                border: 1px solid rgba(255,255,255,0.1);
                box-shadow: 0 20px 60px rgba(0,0,0,0.5);
            }
            h2 { 
                color: #6366f1; 
                margin-bottom: 10px;
                font-size: 2rem;
            }
            .subtitle {
                color: rgba(255,255,255,0.6);
                margin-bottom: 30px;
                font-size: 14px;
            }
            .form-group { margin-bottom: 20px; }
            label {
                display: block;
                margin-bottom: 8px;
                color: rgba(255,255,255,0.8);
                font-size: 14px;
            }
            input { 
                width: 100%;
                padding: 14px;
                background: rgba(255,255,255,0.1);
                border: 1px solid rgba(255,255,255,0.2);
                color: white;
                border-radius: 8px;
                font-size: 16px;
                transition: all 0.3s;
            }
            input:focus {
                outline: none;
                border-color: #6366f1;
                background: rgba(255,255,255,0.15);
            }
            input::placeholder { color: rgba(255,255,255,0.4); }
            button { 
                width: 100%;
                padding: 14px;
                background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
                color: white;
                border: none;
                border-radius: 8px;
                cursor: pointer;
                font-size: 16px;
                font-weight: 600;
                margin-top: 20px;
                transition: all 0.3s;
            }
            button:hover { 
                transform: translateY(-2px);
                box-shadow: 0 10px 30px rgba(99, 102, 241, 0.4);
            }
            button:disabled {
                opacity: 0.5;
                cursor: not-allowed;
                transform: none;
            }
            .error {
                background: rgba(239, 68, 68, 0.2);
                border: 1px solid rgba(239, 68, 68, 0.5);
                color: #fca5a5;
                padding: 12px;
                border-radius: 8px;
                margin-bottom: 20px;
                display: none;
            }
            .success {
                background: rgba(34, 197, 94, 0.2);
                border: 1px solid rgba(34, 197, 94, 0.5);
                color: #86efac;
                padding: 12px;
                border-radius: 8px;
                margin-bottom: 20px;
                display: none;
            }
            .note {
                margin-top: 20px;
                font-size: 12px;
                color: rgba(255,255,255,0.4);
                text-align: center;
            }
            .debug {
                margin-top: 20px;
                padding: 10px;
                background: rgba(255,255,255,0.05);
                border-radius: 8px;
                font-size: 11px;
                color: rgba(255,255,255,0.5);
                font-family: monospace;
            }
        </style>
    </head>
    <body>
        <div class="login-box">
            <h2>🔐 Admin Login</h2>
            <p class="subtitle">Enter your credentials to access the portal</p>
            
            <div id="error" class="error"></div>
            <div id="success" class="success"></div>
            
            <form id="loginForm">
                <div class="form-group">
                    <label for="email">Email Address</label>
                    <input type="email" id="email" placeholder="admin@example.com" required autocomplete="email">
                </div>
                
                <div class="form-group">
                    <label for="password">Password</label>
                    <input type="password" id="password" placeholder="••••••••" required autocomplete="current-password">
                </div>
                
                <button type="submit" id="loginBtn">Login</button>
            </form>
            
            <p class="note">
                Use credentials from .env file (ADMIN_EMAIL and ADMIN_PASSWORD)
            </p>
            
            <div id="debug" class="debug"></div>
        </div>
        
        <script>
            const debugLog = (msg) => {
                console.log(msg);
                const debugDiv = document.getElementById('debug');
                debugDiv.innerHTML += msg + '<br>';
            };
            
            debugLog('Page loaded');
            
            // Get form element
            const loginForm = document.getElementById('loginForm');
            
            if (!loginForm) {
                debugLog('ERROR: Form not found!');
            } else {
                debugLog('Form found, attaching listener');
                
                loginForm.addEventListener('submit', async function(e) {
                    e.preventDefault();
                    debugLog('Form submitted!');
                    
                    const email = document.getElementById('email').value;
                    const password = document.getElementById('password').value;
                    const loginBtn = document.getElementById('loginBtn');
                    const errorDiv = document.getElementById('error');
                    const successDiv = document.getElementById('success');
                    
                    debugLog('Email: ' + email);
                    debugLog('Password length: ' + password.length);
                    
                    loginBtn.disabled = true;
                    loginBtn.textContent = 'Logging in...';
                    errorDiv.style.display = 'none';
                    successDiv.style.display = 'none';
                    
                    try {
                        debugLog('Sending request to /api/auth/login');
                        
                        const response = await fetch('/api/auth/login', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'Accept': 'application/json'
                            },
                            body: JSON.stringify({email: email, password: password})
                        });
                        
                        debugLog('Response status: ' + response.status);
                        
                        const data = await response.json();
                        debugLog('Response data: ' + JSON.stringify(data));
                        
                        if (response.ok && data.access_token) {
                            debugLog('Login successful! Token received');
                            
                            // Store token in localStorage
                            localStorage.setItem('access_token', data.access_token);
                            debugLog('Token stored in localStorage');
                            
                            // Store token in cookie
                            const maxAge = 86400; // 24 hours
                            document.cookie = `access_token=${data.access_token}; path=/; max-age=${maxAge}; SameSite=Lax`;
                            debugLog('Token stored in cookie');
                            
                            // Show success message
                            successDiv.textContent = '✓ Login successful! Redirecting...';
                            successDiv.style.display = 'block';
                            
                            // Wait a moment then redirect
                            setTimeout(() => {
                                debugLog('Redirecting to portal...');
                                window.location.href = '/api/admin/portal';
                            }, 1000);
                        } else {
                            throw new Error(data.detail || 'Login failed');
                        }
                    } catch (error) {
                        debugLog('ERROR: ' + error.message);
                        console.error('Login error:', error);
                        errorDiv.textContent = '✗ ' + (error.message || 'Login failed. Check credentials.');
                        errorDiv.style.display = 'block';
                        loginBtn.disabled = false;
                        loginBtn.textContent = 'Login';
                    }
                });
                
                debugLog('Event listener attached successfully');
            }
            
            // Check if already logged in
            window.addEventListener('DOMContentLoaded', () => {
                const token = localStorage.getItem('access_token');
                if (token) {
                    debugLog('Token found in storage, redirecting...');
                    window.location.href = '/api/admin/portal';
                } else {
                    debugLog('No token found, showing login form');
                }
            });
        </script>
    </body>
    </html>
    """)

@router.get("/{filename:path}")
async def admin_portal_static(filename: str):
    """Serve static files for admin portal"""
    if ".." in filename or filename.startswith("/"):
        raise HTTPException(status_code=403, detail="Access denied")
    
    file_path = ADMIN_PORTAL_DIR / filename
    
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    
    raise HTTPException(status_code=404, detail="File not found")