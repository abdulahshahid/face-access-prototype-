import io
import csv
import logging
from typing import List, Optional
from pathlib import Path

# --- FIXED IMPORTS HERE ---
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query, status, Request
from fastapi.responses import HTMLResponse, FileResponse
from sqlalchemy.orm import Session
from fastapi.responses import RedirectResponse
# --------------------------

from db.session import get_db
from models.attendee import Attendee
from core.deps import get_current_admin
from core.security import generate_invite_code
from core.qdrant_ops import qdrant_service
from schemas import AttendeeResponse, BatchUploadResponse

router = APIRouter()
logger = logging.getLogger(__name__)

# ==============================================================================
# 1. LIST ATTENDEES (With Search & Pagination)
# ==============================================================================

from core.security import decode_token

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
            payload = decode_token(token)
            if payload:
                return True, None  # Authenticated, no redirect needed
        except:
            pass
    
    # Not authenticated - check if this is an API request or HTML request
    accept_header = request.headers.get("Accept", "")
    if "text/html" in accept_header or request.url.path.endswith("/portal"):
        # HTML request - redirect to login
        return False, RedirectResponse(url="/api/admin/portal/login")
    else:
        # API request - return 401
        return False, None
@router.get("/")
async def admin_root(request: Request):
    """Redirect to portal"""
    return RedirectResponse(url="/api/admin/portal")

@router.get(
    "/attendees", 
    response_model=List[AttendeeResponse], 
)
def get_attendees(
    skip: int = 0, 
    limit: int = 100, 
    search: Optional[str] = None, 
    db: Session = Depends(get_db)
):
    """
    Get all attendees with pagination.
    Optional: ?search=john to filter by name or email.
    """
    query = db.query(Attendee)
    
    if search:
        # Case-insensitive search for Name OR Email
        search_fmt = f"%{search}%"
        query = query.filter(
            (Attendee.email.ilike(search_fmt)) | 
            (Attendee.name.ilike(search_fmt))
        )
    
    # Sort by creation date (newest first is better for admins)
    users = query.order_by(Attendee.created_at.desc()).offset(skip).limit(limit).all()
    
    return users


# ==============================================================================
# 2. DELETE ATTENDEE (Strict Consistency: SQL + Vector DB)
# ==============================================================================
@router.delete(
    "/attendees/{user_id}", 
)
def delete_attendee(user_id: int, db: Session = Depends(get_db)):
    """
    Hard Delete:
    1. Removes vector from Qdrant (prevent face access).
    2. Removes record from PostgreSQL.
    """
    # Step A: Check if user exists in SQL
    user = db.query(Attendee).filter(Attendee.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"User with ID {user_id} not found"
        )
    
    email_backup = user.email # Keep for logging
    
    # Step B: Delete from Vector DB (Qdrant)
    # We prioritize this to ensure security (access revocation)
    vector_deleted = False
    try:
        vector_deleted = qdrant_service.delete_user_vector(user_id)
        if not vector_deleted:
             logger.warning(f"⚠️ Vector deletion returned False for user {user_id}. Vector might not have existed.")
    except Exception as e:
        # We generally continue to delete the SQL user even if Qdrant fails, 
        # but we log it as a CRITICAL sync error.
        logger.error(f"❌ CRITICAL: Failed to delete vector for {user_id}: {e}")

    # Step C: Delete from Relational DB (Postgres)
    try:
        db.delete(user)
        db.commit()
        
        logger.info(f"🗑️ [Admin] Deleted user {user_id} ({email_backup}). Vector Removed: {vector_deleted}")
        
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


# ==============================================================================
# 3. BATCH CSV UPLOAD
# ==============================================================================
@router.post(
    "/upload-csv", 
    response_model=BatchUploadResponse, 
)
async def upload_csv(
    file: UploadFile = File(...), 
    db: Session = Depends(get_db)
):
    """
    Bulk import users.
    Required CSV Header: 'email'
    Optional CSV Header: 'name'
    """
    # 1. Validate File Type
    if not file.filename.lower().endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Invalid file format. Please upload a .csv file."
        )

    # 2. Read File
    try:
        content = await file.read()
        decoded_content = content.decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(decoded_content))
    except Exception as e:
        logger.error(f"CSV Reading Error: {e}")
        raise HTTPException(status_code=400, detail="Could not read or decode CSV file.")
    
    # 3. Validate Headers
    headers = [h.lower().strip() for h in csv_reader.fieldnames or []]
    if 'email' not in headers:
         raise HTTPException(
             status_code=400, 
             detail=f"CSV is missing required 'email' column. Found: {headers}"
         )

    new_attendees = []
    skipped_emails = []
    
    # 4. Process Rows
    for row in csv_reader:
        clean_row = {k.lower().strip(): v.strip() for k, v in row.items() if k}
        
        email = clean_row.get('email')
        name = clean_row.get('name', 'Unknown')

        if not email:
            continue

        # Check for existing user (SQL only is sufficient for this check)
        existing = db.query(Attendee).filter(Attendee.email == email).first()
        if existing:
            skipped_emails.append(email)
            continue

        # Create new record
        invite_code = generate_invite_code()
        attendee = Attendee(
            name=name,
            email=email,
            invite_code=invite_code,
            status="pending"
        )
        db.add(attendee)
        new_attendees.append(attendee)

    # 5. Commit Transaction
    try:
        db.commit()
        logger.info(f"✅ [Admin] Batch Import: {len(new_attendees)} created, {len(skipped_emails)} skipped.")
        
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


BASE_DIR = Path(__file__).parent.parent.parent  # Goes up to 'app' directory
ADMIN_PORTAL_DIR = BASE_DIR / "admin-portal"

# Ensure admin portal directory exists
ADMIN_PORTAL_DIR.mkdir(exist_ok=True)

# Simple in-memory token storage for admin portal access
admin_portal_tokens = {}

@router.get("/portal", response_class=HTMLResponse)
async def admin_portal(request: Request):
    """Serve the main admin portal page"""
    
    # Check auth
    is_auth, redirect_response = check_auth_and_redirect(request)
    if not is_auth and redirect_response:
        return redirect_response
    
    portal_page = ADMIN_PORTAL_DIR / "index.html"
    if portal_page.exists():
        return FileResponse(portal_page)
    
    # Fallback: simple admin portal
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Admin Portal - Face Access Control</title>
        <style>
            body { font-family: Arial, sans-serif; padding: 40px; background: #0a0a0f; color: white; }
            .container { max-width: 800px; margin: 0 auto; }
            h1 { color: #6366f1; }
            .card { background: rgba(255,255,255,0.05); padding: 20px; border-radius: 10px; margin: 20px 0; }
            .btn { background: #6366f1; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Admin Portal</h1>
            <div class="card">
                <h3>Face Access Control System Admin</h3>
                <p>Manage attendees, upload CSV files, and monitor system access.</p>
                <div style="margin-top: 20px;">
                    <button class="btn" onclick="window.location.href='/api/admin/attendees'">View Attendees</button>
                    <button class="btn" onclick="window.location.href='/api/admin/upload-csv'">Upload CSV</button>
                </div>
            </div>
            <div class="card">
                <h4>Quick Links:</h4>
                <ul>
                    <li><a href="/api/admin/attendees" style="color: #a855f7;">List All Attendees</a></li>
                    <li><a href="/api/admin/upload-csv" style="color: #a855f7;">Bulk Upload CSV</a></li>
                    <li><a href="/docs" style="color: #a855f7;">API Documentation</a></li>
                </ul>
            </div>
        </div>
    </body>
    </html>
    """)

@router.get("/portal/login", response_class=HTMLResponse)
async def admin_portal_login():
    """Serve the admin portal login page"""
    login_page = ADMIN_PORTAL_DIR / "login.html"
    if login_page.exists():
        return FileResponse(login_page)
    
    # Fallback: simple login form
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Admin Login</title>
        <style>
            body { font-family: Arial, sans-serif; padding: 40px; background: #0a0a0f; color: white; }
            .login-box { max-width: 400px; margin: 100px auto; background: rgba(255,255,255,0.05); padding: 40px; border-radius: 10px; }
            input { width: 100%; padding: 10px; margin: 10px 0; background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2); color: white; border-radius: 5px; }
            button { width: 100%; padding: 12px; background: #6366f1; color: white; border: none; border-radius: 5px; cursor: pointer; margin-top: 20px; }
        </style>
    </head>
    <body>
        <div class="login-box">
            <h2>Admin Login</h2>
            <p>Enter your admin credentials to access the portal.</p>
            <form onsubmit="login(event)">
                <input type="email" id="email" placeholder="Admin Email" required>
                <input type="password" id="password" placeholder="Password" required>
                <button type="submit">Login</button>
            </form>
            <p style="margin-top: 20px; font-size: 12px; color: rgba(255,255,255,0.5);">
                Note: This uses the same JWT authentication as the API.
            </p>
        </div>
        <script>
            async function login(e) {
                e.preventDefault();
                const email = document.getElementById('email').value;
                const password = document.getElementById('password').value;
                
                // Use the existing auth endpoint
                const response = await fetch('/api/auth/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({email: email, password: password})
                });
                
                if (response.ok) {
                    const data = await response.json();
                    // Store the token
                    localStorage.setItem('access_token', data.access_token);
                    // Redirect to admin portal
                    window.location.href = '/api/admin/portal';
                } else {
                    alert('Login failed. Please check your credentials.');
                }
            }
        </script>
    </body>
    </html>
    """)

@router.get("/portal/{filename:path}")
async def admin_portal_static(filename: str):
    """Serve static files for admin portal (CSS, JS, etc.)"""
    # Security: prevent directory traversal
    if ".." in filename or filename.startswith("/"):
        raise HTTPException(status_code=403, detail="Access denied")
    
    file_path = ADMIN_PORTAL_DIR / filename
    
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    
    raise HTTPException(status_code=404, detail="File not found")