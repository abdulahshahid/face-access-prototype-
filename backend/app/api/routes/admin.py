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
    
    # Try to get token from Authorization header
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
    
    # Try to get token from cookies
    if not token:
        token = request.cookies.get("access_token")
    
    # Validate token
    if token:
        try:
            payload = verify_access_token(token)
            if payload and payload.get("is_admin"):
                logger.info(f"✓ Authenticated admin: {payload.get('sub')}")
                return True, None  # Authenticated, no redirect needed
        except Exception as e:
            logger.warning(f"Token verification failed: {e}")
    
    # Not authenticated - determine response type
    accept_header = request.headers.get("Accept", "")
    is_html_request = "text/html" in accept_header or request.url.path.endswith("/portal")
    
    if is_html_request:
        # HTML request - redirect to login
        logger.info(f"↺ Redirecting to login: {request.url.path}")
        return False, RedirectResponse(url="/api/admin/portal/login", status_code=302)
    else:
        # API request - return 401
        logger.warning(f"✗ Unauthorized API request: {request.url.path}")
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

@router.post("/upload-csv")
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
    results = []  # For returning detailed results
    
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
        
        # Store for results
        results.append({
            "name": name,
            "email": email,
            "invite_code": invite_code
        })

    try:
        db.commit()
        logger.info(f"✅ [Admin] Batch Import: {len(new_attendees)} created, {len(skipped_emails)} skipped")
        
        return {
            "status": "success",
            "total_processed": len(new_attendees) + len(skipped_emails),
            "success_count": len(new_attendees),
            "skipped_count": len(skipped_emails),
            "skipped_emails": skipped_emails,
            "results": results  # Include detailed results
        }
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Batch Upload Commit Failed: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Database error while saving users."
        )

# ==============================================================================
# LOGIN PAGE
# ==============================================================================

@router.get("/portal/login", response_class=HTMLResponse)
async def admin_login_page():
    """Serve the admin login page"""
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Admin Login - Face Access Control</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { 
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: #0a0a0f;
                color: white;
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }
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
                pointer-events: none;
            }
            .login-container {
                width: 100%;
                max-width: 400px;
                background: rgba(255,255,255,0.03);
                backdrop-filter: blur(10px);
                border-radius: 24px;
                padding: 40px;
                border: 1px solid rgba(255,255,255,0.08);
                position: relative;
                z-index: 1;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            }
            .logo {
                text-align: center;
                margin-bottom: 40px;
            }
            .logo h1 {
                font-size: 28px;
                background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-bottom: 8px;
            }
            .logo p {
                color: rgba(255,255,255,0.6);
                font-size: 14px;
            }
            .form-group {
                margin-bottom: 25px;
            }
            .form-group label {
                display: block;
                margin-bottom: 8px;
                font-size: 14px;
                font-weight: 500;
                color: rgba(255,255,255,0.8);
            }
            .form-group input {
                width: 100%;
                padding: 14px 18px;
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 12px;
                color: white;
                font-size: 15px;
                transition: all 0.3s;
            }
            .form-group input:focus {
                outline: none;
                border-color: rgba(99, 102, 241, 0.5);
                background: rgba(99, 102, 241, 0.05);
            }
            .form-group input::placeholder {
                color: rgba(255,255,255,0.4);
            }
            .btn {
                width: 100%;
                padding: 16px;
                background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
                color: white;
                border: none;
                border-radius: 12px;
                font-size: 16px;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.3s;
                margin-top: 10px;
            }
            .btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 10px 30px rgba(99, 102, 241, 0.4);
            }
            .btn:disabled {
                opacity: 0.5;
                cursor: not-allowed;
                transform: none;
            }
            .error-message {
                background: rgba(239, 68, 68, 0.1);
                border: 1px solid rgba(239, 68, 68, 0.3);
                color: rgba(239, 68, 68, 1);
                padding: 12px 16px;
                border-radius: 8px;
                margin-top: 20px;
                font-size: 14px;
                display: none;
            }
            .success-message {
                background: rgba(34, 197, 94, 0.1);
                border: 1px solid rgba(34, 197, 94, 0.3);
                color: rgba(34, 197, 94, 1);
                padding: 12px 16px;
                border-radius: 8px;
                margin-top: 20px;
                font-size: 14px;
                display: none;
            }
            .spinner {
                width: 20px;
                height: 20px;
                border: 2px solid rgba(255,255,255,0.3);
                border-top-color: white;
                border-radius: 50%;
                animation: spin 0.8s linear infinite;
                display: inline-block;
                vertical-align: middle;
                margin-right: 10px;
            }
            @keyframes spin { to { transform: rotate(360deg); } }
            .login-info {
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid rgba(255,255,255,0.08);
                text-align: center;
                font-size: 13px;
                color: rgba(255,255,255,0.5);
            }
            .login-info a {
                color: #6366f1;
                text-decoration: none;
            }
            .login-info a:hover {
                text-decoration: underline;
            }
        </style>
    </head>
    <body>
        <div class="bg-gradient"></div>
        
        <div class="login-container">
            <div class="logo">
                <h1>🔐 Admin Portal</h1>
                <p>Face Access Control System</p>
            </div>
            
            <form id="loginForm">
                <div class="form-group">
                    <label for="username">Admin Username</label>
                    <input type="text" id="username" placeholder="Enter admin username" required>
                </div>
                
                <div class="form-group">
                    <label for="password">Admin Password</label>
                    <input type="password" id="password" placeholder="Enter admin password" required>
                </div>
                
                <button type="submit" class="btn" id="loginBtn">
                    <span id="btnText">Sign In</span>
                    <div class="spinner" id="spinner" style="display: none;"></div>
                </button>
                
                <div class="error-message" id="errorMessage"></div>
                <div class="success-message" id="successMessage"></div>
            </form>
            
            <div class="login-info">
                <p>Contact system administrator for credentials</p>
            </div>
        </div>
        
        <script>
            const loginForm = document.getElementById('loginForm');
            const loginBtn = document.getElementById('loginBtn');
            const btnText = document.getElementById('btnText');
            const spinner = document.getElementById('spinner');
            const errorMessage = document.getElementById('errorMessage');
            const successMessage = document.getElementById('successMessage');
            
            loginForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                
                const username = document.getElementById('username').value;
                const password = document.getElementById('password').value;
                
                // Show loading state
                loginBtn.disabled = true;
                btnText.style.display = 'none';
                spinner.style.display = 'inline-block';
                errorMessage.style.display = 'none';
                successMessage.style.display = 'none';
                
                try {
                    const response = await fetch('/api/auth/login', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            username: username,
                            password: password
                        })
                    });
                    
                    const data = await response.json();
                    
                    if (response.ok && data.access_token) {
                        // Store token
                        localStorage.setItem('access_token', data.access_token);
                        
                        // Set cookie for server-side auth
                        document.cookie = `access_token=${data.access_token}; path=/; max-age=86400`; // 1 day
                        
                        // Show success message
                        successMessage.textContent = 'Login successful! Redirecting...';
                        successMessage.style.display = 'block';
                        
                        // Redirect to admin portal
                        setTimeout(() => {
                            window.location.href = '/api/admin/portal';
                        }, 1000);
                    } else {
                        throw new Error(data.detail || 'Login failed');
                    }
                } catch (error) {
                    errorMessage.textContent = error.message;
                    errorMessage.style.display = 'block';
                } finally {
                    // Reset button state
                    loginBtn.disabled = false;
                    btnText.style.display = 'inline';
                    spinner.style.display = 'none';
                }
            });
            
            // Check if already logged in
            if (localStorage.getItem('access_token')) {
                window.location.href = '/api/admin/portal';
            }
            
            // Focus on username field
            document.getElementById('username').focus();
        </script>
    </body>
    </html>
    """)
# ==============================================================================
# ADMIN PORTAL PAGES
# ==============================================================================

BASE_DIR = Path(__file__).parent.parent.parent
ADMIN_PORTAL_DIR = BASE_DIR / "admin-portal"
ADMIN_PORTAL_DIR.mkdir(exist_ok=True)

@router.get("/portal", response_class=HTMLResponse)
async def admin_portal(request: Request):
    """Serve the main admin portal page with integrated bulk upload"""
    is_auth, redirect_response = check_auth_and_redirect(request)
    if not is_auth and redirect_response:
        return redirect_response
    
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Admin Portal - Face Access Control</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { 
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: #0a0a0f;
                color: white;
                min-height: 100vh;
                padding: 20px;
            }
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
                pointer-events: none;
            }
            .container { max-width: 1400px; margin: 0 auto; position: relative; z-index: 1; }
            .header { 
                display: flex; 
                justify-content: space-between; 
                align-items: center;
                margin-bottom: 40px;
                padding: 20px 30px;
                background: rgba(255,255,255,0.03);
                backdrop-filter: blur(10px);
                border-radius: 20px;
                border: 1px solid rgba(255,255,255,0.08);
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
                font-size: 14px;
                font-weight: 500;
            }
            .logout-btn:hover { background: rgba(255,255,255,0.2); }
            
            /* Tabs */
            .tabs {
                display: flex;
                gap: 10px;
                margin-bottom: 30px;
                border-bottom: 1px solid rgba(255,255,255,0.08);
                padding-bottom: 0;
            }
            .tab {
                padding: 15px 25px;
                background: transparent;
                border: none;
                color: rgba(255,255,255,0.6);
                cursor: pointer;
                font-size: 15px;
                font-weight: 500;
                border-bottom: 3px solid transparent;
                transition: all 0.3s;
            }
            .tab:hover { color: rgba(255,255,255,0.9); }
            .tab.active {
                color: #6366f1;
                border-bottom-color: #6366f1;
            }
            
            /* Tab Content */
            .tab-content { display: none; }
            .tab-content.active { display: block; }
            
            /* Upload Section */
            .upload-card {
                background: rgba(255,255,255,0.03);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 20px;
                padding: 40px;
                backdrop-filter: blur(10px);
                max-width: 800px;
                margin: 0 auto;
            }
            .upload-icon {
                width: 80px;
                height: 80px;
                background: linear-gradient(135deg, rgba(99, 102, 241, 0.2) 0%, rgba(168, 85, 247, 0.2) 100%);
                border: 1px solid rgba(99, 102, 241, 0.3);
                border-radius: 20px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 40px;
                margin: 0 auto 25px;
            }
            .upload-area {
                border: 2px dashed rgba(99, 102, 241, 0.3);
                background: rgba(99, 102, 241, 0.05);
                padding: 60px 40px;
                text-align: center;
                border-radius: 16px;
                transition: all 0.3s;
                cursor: pointer;
                margin: 30px 0;
            }
            .upload-area:hover, .upload-area.dragover {
                border-color: rgba(99, 102, 241, 0.5);
                background: rgba(99, 102, 241, 0.1);
            }
            .upload-area h3 { margin: 15px 0 10px; font-size: 20px; }
            .upload-area p { color: rgba(255,255,255,0.6); margin: 5px 0; }
            .file-selected {
                margin-top: 20px;
                padding: 15px;
                background: rgba(34, 197, 94, 0.1);
                border: 1px solid rgba(34, 197, 94, 0.3);
                border-radius: 12px;
                color: rgba(34, 197, 94, 1);
                display: none;
            }
            .btn {
                background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
                color: white;
                padding: 14px 28px;
                border: none;
                border-radius: 12px;
                cursor: pointer;
                font-size: 16px;
                font-weight: 600;
                transition: all 0.3s;
            }
            .btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 10px 30px rgba(99, 102, 241, 0.4);
            }
            .btn:disabled {
                opacity: 0.5;
                cursor: not-allowed;
                transform: none;
            }
            
            /* Status Messages */
            .status {
                margin-top: 30px;
                padding: 20px;
                border-radius: 12px;
                display: none;
                font-size: 15px;
            }
            .status.success {
                background: rgba(34, 197, 94, 0.1);
                border: 1px solid rgba(34, 197, 94, 0.3);
                color: rgba(34, 197, 94, 1);
            }
            .status.error {
                background: rgba(239, 68, 68, 0.1);
                border: 1px solid rgba(239, 68, 68, 0.3);
                color: rgba(239, 68, 68, 1);
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
                width: 18px;
                height: 18px;
                border: 2px solid rgba(99, 102, 241, 0.3);
                border-top-color: rgba(99, 102, 241, 1);
                border-radius: 50%;
                animation: spin 0.8s linear infinite;
            }
            @keyframes spin { to { transform: rotate(360deg); } }
            
            /* Results */
            .results-section {
                margin-top: 40px;
                display: none;
            }
            .results-section.show { display: block; }
            .results-summary {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }
            .result-stat {
                background: rgba(255,255,255,0.03);
                padding: 25px;
                border-radius: 12px;
                border: 1px solid rgba(255,255,255,0.08);
                text-align: center;
            }
            .result-stat .number {
                font-size: 36px;
                font-weight: 700;
                margin-bottom: 8px;
            }
            .result-stat.success .number { color: #22c55e; }
            .result-stat.skipped .number { color: #f59e0b; }
            .result-stat .label {
                font-size: 14px;
                color: rgba(255,255,255,0.6);
            }
            .invite-list {
                background: rgba(255,255,255,0.03);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 12px;
                padding: 25px;
                max-height: 400px;
                overflow-y: auto;
            }
            .invite-item {
                padding: 15px;
                background: rgba(255,255,255,0.02);
                border: 1px solid rgba(255,255,255,0.05);
                border-radius: 8px;
                margin-bottom: 10px;
            }
            .invite-item:hover {
                background: rgba(255,255,255,0.05);
            }
            .invite-name {
                font-weight: 600;
                margin-bottom: 5px;
                font-size: 16px;
            }
            .invite-email {
                font-size: 13px;
                color: rgba(255,255,255,0.5);
                margin-bottom: 8px;
            }
            .invite-link {
                display: flex;
                gap: 10px;
                align-items: center;
            }
            .invite-link input {
                flex: 1;
                padding: 8px 12px;
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 6px;
                color: rgba(99, 102, 241, 0.9);
                font-size: 13px;
            }
            .copy-btn {
                background: rgba(99, 102, 241, 0.15);
                border: 1px solid rgba(99, 102, 241, 0.3);
                color: rgba(99, 102, 241, 1);
                padding: 8px 16px;
                border-radius: 6px;
                cursor: pointer;
                font-size: 13px;
                font-weight: 500;
                transition: all 0.3s;
            }
            .copy-btn:hover {
                background: rgba(99, 102, 241, 0.25);
            }
            
            /* Attendees Table */
            .search-bar {
                margin-bottom: 25px;
                display: flex;
                gap: 10px;
            }
            .search-bar input {
                flex: 1;
                padding: 14px 18px;
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.1);
                color: white;
                border-radius: 10px;
                font-size: 15px;
            }
            .search-bar input::placeholder { color: rgba(255,255,255,0.4); }
            .table-container {
                background: rgba(255,255,255,0.03);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 16px;
                overflow: hidden;
            }
            table {
                width: 100%;
                border-collapse: collapse;
            }
            th, td {
                padding: 16px 20px;
                text-align: left;
                border-bottom: 1px solid rgba(255,255,255,0.05);
            }
            th {
                background: rgba(255,255,255,0.03);
                color: #a855f7;
                font-weight: 600;
                font-size: 13px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            td { font-size: 14px; }
            .status-badge {
                padding: 5px 12px;
                border-radius: 20px;
                font-size: 12px;
                font-weight: 600;
            }
            .status-active { background: rgba(34, 197, 94, 0.2); color: #86efac; }
            .status-pending { background: rgba(251, 191, 36, 0.2); color: #fde047; }
            .delete-btn {
                background: rgba(239, 68, 68, 0.15);
                color: #fca5a5;
                padding: 7px 14px;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                font-size: 13px;
                transition: all 0.3s;
            }
            .delete-btn:hover { background: rgba(239, 68, 68, 0.3); }
            .loading { text-align: center; padding: 60px; color: rgba(255,255,255,0.5); }
            
            .csv-template {
                background: rgba(255,255,255,0.02);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 12px;
                padding: 20px;
                margin: 25px 0;
            }
            .csv-template h4 {
                margin-bottom: 15px;
                font-size: 16px;
            }
            .code-block {
                background: rgba(0,0,0,0.3);
                padding: 15px;
                border-radius: 8px;
                font-family: 'Courier New', monospace;
                font-size: 13px;
                color: #22c55e;
                margin-bottom: 15px;
                overflow-x: auto;
            }
            
            @media (max-width: 768px) {
                .header { flex-direction: column; gap: 15px; }
                .tabs { overflow-x: auto; }
                .results-summary { grid-template-columns: 1fr; }
            }
        </style>
    </head>
    <body>
        <div class="bg-gradient"></div>
        
        <div class="container">
            <div class="header">
                <h1>🔐 Admin Portal</h1>
                <button class="logout-btn" onclick="logout()">Logout</button>
            </div>
            
            <div class="tabs">
                <button class="tab active" onclick="switchTab('attendees')">👥 Attendees</button>
                <button class="tab" onclick="switchTab('upload')">📤 Bulk Upload</button>
            </div>
            
            <!-- Attendees Tab -->
            <div id="attendeesTab" class="tab-content active">
                <div class="search-bar">
                    <input type="text" id="searchInput" placeholder="Search by name or email..." onkeyup="searchAttendees()">
                    <button class="btn" onclick="loadAttendees()">Refresh</button>
                </div>

                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>Name</th>
                                <th>Email</th>
                                <th>Status</th>
                                <th>Invite Code</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody id="attendeesTableBody">
                            <tr><td colspan="6" class="loading">Loading attendees...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
            
            <!-- Upload Tab -->
            <div id="uploadTab" class="tab-content">
                <div class="upload-card">
                    <div class="upload-icon">📄</div>
                    <h2 style="text-align: center; margin-bottom: 10px;">Bulk Upload Attendees</h2>
                    <p style="text-align: center; color: rgba(255,255,255,0.6); margin-bottom: 30px;">
                        Upload a CSV file with email addresses to bulk create attendee records.
                    </p>
                    
                    <form id="uploadForm">
                        <div class="upload-area" id="dropArea">
                            <i style="font-size: 48px;">☁️</i>
                            <h3>Drag & Drop CSV File</h3>
                            <p>or click to browse</p>
                            <input type="file" id="csvFile" accept=".csv" style="display: none;">
                            <button type="button" class="btn" style="margin-top: 20px;" 
                                    onclick="document.getElementById('csvFile').click()">
                                Browse Files
                            </button>
                            <p style="margin-top: 15px; font-size: 13px; color: rgba(255,255,255,0.4);">
                                Max file size: 5MB • CSV format only
                            </p>
                            <div class="file-selected" id="fileSelected"></div>
                        </div>
                        
                        <div class="csv-template">
                            <h4>CSV Template Format:</h4>
                            <div class="code-block">email,name
john@example.com,John Doe
jane@example.com,Jane Smith
alex@example.com,Alex Johnson</div>
                            <button type="button" class="btn" onclick="downloadTemplate()" 
                                    style="padding: 10px 20px; font-size: 14px;">
                                📥 Download Template
                            </button>
                        </div>
                        
                        <div style="text-align: center;">
                            <button type="submit" class="btn" id="uploadBtn">
                                Generate Invite Links
                            </button>
                        </div>
                    </form>
                    
                    <div id="status" class="status"></div>
                    
                    <div id="resultsSection" class="results-section">
                        <h3 style="margin-bottom: 25px; font-size: 22px;">Upload Results</h3>
                        <div class="results-summary">
                            <div class="result-stat success">
                                <div class="number" id="successCount">0</div>
                                <div class="label">Successfully Added</div>
                            </div>
                            <div class="result-stat skipped">
                                <div class="number" id="skippedCount">0</div>
                                <div class="label">Skipped (Duplicates)</div>
                            </div>
                        </div>
                        
                        <h4 style="margin-bottom: 15px;">Generated Invite Links</h4>
                        <div class="invite-list" id="inviteList"></div>
                    </div>
                </div>
            </div>
        </div>
        
        <script>
            const token = localStorage.getItem('access_token');
            let allAttendees = [];
            
            function logout() {
                localStorage.removeItem('access_token');
                document.cookie = 'access_token=; Max-Age=0; path=/';
                window.location.href = '/api/admin/portal/login';
            }
            
            function switchTab(tab) {
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                
                event.target.classList.add('active');
                document.getElementById(tab + 'Tab').classList.add('active');
                
                if (tab === 'attendees') {
                    loadAttendees();
                }
            }
            
            // Attendees Management
            async function loadAttendees() {
                const tbody = document.getElementById('attendeesTableBody');
                tbody.innerHTML = '<tr><td colspan="6" class="loading">Loading attendees...</td></tr>';

                try {
                    const response = await fetch('/api/admin/attendees', {
                        headers: { 'Authorization': `Bearer ${token}` }
                    });

                    if (!response.ok) throw new Error('Failed to load attendees');

                    allAttendees = await response.json();
                    displayAttendees(allAttendees);
                } catch (error) {
                    tbody.innerHTML = `<tr><td colspan="6" style="color: #fca5a5; text-align: center; padding: 40px;">Error: ${error.message}</td></tr>`;
                }
            }

            function displayAttendees(attendees) {
                const tbody = document.getElementById('attendeesTableBody');
                
                if (attendees.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 40px; color: rgba(255,255,255,0.5);">No attendees found.</td></tr>';
                    return;
                }

                tbody.innerHTML = attendees.map(a => `
                    <tr>
                        <td>${a.id}</td>
                        <td>${a.name}</td>
                        <td>${a.email}</td>
                        <td><span class="status-badge status-${a.status}">${a.status}</span></td>
                        <td>${a.invite_code || 'N/A'}</td>
                        <td><button class="delete-btn" onclick="deleteAttendee(${a.id}, '${a.email}')">Delete</button></td>
                    </tr>
                `).join('');
            }

            function searchAttendees() {
                const searchTerm = document.getElementById('searchInput').value.toLowerCase();
                const filtered = allAttendees.filter(a => 
                    a.name.toLowerCase().includes(searchTerm) || 
                    a.email.toLowerCase().includes(searchTerm)
                );
                displayAttendees(filtered);
            }

            async function deleteAttendee(id, email) {
                if (!confirm(`Delete ${email}?`)) return;

                try {
                    const response = await fetch(`/api/admin/attendees/${id}`, {
                        method: 'DELETE',
                        headers: { 'Authorization': `Bearer ${token}` }
                    });

                    if (response.ok) {
                        alert('Attendee deleted successfully');
                        loadAttendees();
                    } else {
                        throw new Error('Failed to delete');
                    }
                } catch (error) {
                    alert('Error: ' + error.message);
                }
            }
            
            // CSV Upload
            const csvFile = document.getElementById('csvFile');
            const uploadForm = document.getElementById('uploadForm');
            const dropArea = document.getElementById('dropArea');
            
            csvFile.addEventListener('change', function(e) {
                const fileName = e.target.files[0]?.name;
                const fileSelected = document.getElementById('fileSelected');
                if (fileName) {
                    fileSelected.textContent = `Selected: ${fileName}`;
                    fileSelected.style.display = 'block';
                }
            });
            
            // Drag and drop
            ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
                dropArea.addEventListener(eventName, preventDefaults, false);
            });
            
            function preventDefaults(e) {
                e.preventDefault();
                e.stopPropagation();
            }
            
            ['dragenter', 'dragover'].forEach(eventName => {
                dropArea.addEventListener(eventName, () => {
                    dropArea.classList.add('dragover');
                }, false);
            });
            
            ['dragleave', 'drop'].forEach(eventName => {
                dropArea.addEventListener(eventName, () => {
                    dropArea.classList.remove('dragover');
                }, false);
            });
            
            dropArea.addEventListener('drop', function(e) {
                const dt = e.dataTransfer;
                const files = dt.files;
                csvFile.files = files;
                
                const fileName = files[0]?.name;
                const fileSelected = document.getElementById('fileSelected');
                if (fileName) {
                    fileSelected.textContent = `Selected: ${fileName}`;
                    fileSelected.style.display = 'block';
                }
            });
            
            uploadForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                
                if (!csvFile.files[0]) {
                    showStatus('Please select a file', 'error');
                    return;
                }

                const formData = new FormData();
                formData.append('file', csvFile.files[0]);

                showStatus('Uploading and processing...', 'processing');
                document.getElementById('resultsSection').classList.remove('show');

                try {
                    const response = await fetch('/api/admin/upload-csv', {
                        method: 'POST',
                        headers: { 'Authorization': `Bearer ${token}` },
                        body: formData
                    });

                    const data = await response.json();

                    if (response.ok) {
                        if (data.success_count === 0) {
                            showStatus('⚠️ No new attendees added (all were duplicates)', 'error');
                        } else {
                            showStatus(`✅ Success! ${data.success_count} attendees added, ${data.skipped_count} skipped.`, 'success');
                            displayResults(data);
                        }
                    } else {
                        showStatus(data.detail || 'Upload failed', 'error');
                    }
                } catch (error) {
                    showStatus('Network error: ' + error.message, 'error');
                }
            });
            
            function showStatus(message, type) {
                const statusDiv = document.getElementById('status');
                statusDiv.className = `status ${type}`;
                if (type === 'processing') {
                    statusDiv.innerHTML = '<div class="spinner"></div>' + message;
                } else {
                    statusDiv.textContent = message;
                }
                statusDiv.style.display = type === 'processing' ? 'flex' : 'block';
            }
            
            function displayResults(data) {
                document.getElementById('successCount').textContent = data.success_count;
                document.getElementById('skippedCount').textContent = data.skipped_count;
                
                const inviteList = document.getElementById('inviteList');
                const baseUrl = window.location.origin;
                
                if (data.results && data.results.length > 0) {
                    inviteList.innerHTML = data.results.map(r => {
                        const link = `${baseUrl}/register?code=${r.invite_code}`;
                        return `
                            <div class="invite-item">
                                <div class="invite-name">${r.name}</div>
                                <div class="invite-email">${r.email}</div>
                                <div class="invite-link">
                                    <input type="text" value="${link}" readonly onclick="this.select()">
                                    <button class="copy-btn" onclick="copyToClipboard('${link}', this)">Copy</button>
                                </div>
                            </div>
                        `;
                    }).join('');
                    
                    document.getElementById('resultsSection').classList.add('show');
                }
                
                // Reset form
                csvFile.value = '';
                document.getElementById('fileSelected').style.display = 'none';
            }
            
            function copyToClipboard(text, button) {
                navigator.clipboard.writeText(text).then(() => {
                    const originalText = button.textContent;
                    button.textContent = 'Copied!';
                    button.style.background = 'rgba(34, 197, 94, 0.2)';
                    button.style.color = '#22c55e';
                    setTimeout(() => {
                        button.textContent = originalText;
                        button.style.background = '';
                        button.style.color = '';
                    }, 2000);
                });
            }
            
            function downloadTemplate() {
                const csv = 'email,name\\njohn@example.com,John Doe\\njane@example.com,Jane Smith';
                const blob = new Blob([csv], { type: 'text/csv' });
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'attendees_template.csv';
                a.click();
                window.URL.revokeObjectURL(url);
            }
            
            // Load attendees on page load
            loadAttendees();
        </script>
    </body>
    </html>
    """)