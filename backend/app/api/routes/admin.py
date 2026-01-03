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
                    <button class="btn" onclick="showUploadForm()">Upload CSV</button>
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