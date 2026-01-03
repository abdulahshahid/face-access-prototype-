import io
import csv
import logging
from typing import List, Optional
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query, status, Request
from fastapi.responses import HTMLResponse, FileResponse
from sqlalchemy.orm import Session

# --- Project Imports ---
from db.session import get_db
from models.attendee import Attendee
from core.deps import get_current_admin
from core.security import generate_invite_code
from core.qdrant_ops import qdrant_service
from schemas import AttendeeResponse, BatchUploadResponse

router = APIRouter()
logger = logging.getLogger(__name__)

# ==============================================================================
# 1. LIST ATTENDEES (LOCKED 🔒)
# ==============================================================================
@router.get("/attendees", response_model=List[AttendeeResponse], dependencies=[Depends(get_current_admin)])
def get_attendees(skip: int = 0, limit: int = 100, search: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Attendee)
    if search:
        search_fmt = f"%{search}%"
        query = query.filter((Attendee.email.ilike(search_fmt)) | (Attendee.name.ilike(search_fmt)))
    return query.order_by(Attendee.created_at.desc()).offset(skip).limit(limit).all()

# ==============================================================================
# 2. DELETE ATTENDEE (LOCKED 🔒)
# ==============================================================================
@router.delete("/attendees/{user_id}", dependencies=[Depends(get_current_admin)])
def delete_attendee(user_id: int, db: Session = Depends(get_db)):
    user = db.query(Attendee).filter(Attendee.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User {user_id} not found")
    
    email_backup = user.email
    vector_deleted = False
    try:
        vector_deleted = qdrant_service.delete_user_vector(user_id)
    except Exception as e:
        logger.error(f"❌ CRITICAL: Failed to delete vector: {e}")

    try:
        db.delete(user)
        db.commit()
        return {"status": "success", "message": f"User {email_backup} deleted.", "vector_cleaned": vector_deleted}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database delete failed")

# ==============================================================================
# 3. BATCH CSV UPLOAD (LOCKED 🔒)
# ==============================================================================
@router.post("/upload-csv", response_model=BatchUploadResponse, dependencies=[Depends(get_current_admin)])
async def upload_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.lower().endswith('.csv'):
        raise HTTPException(status_code=400, detail="Invalid file format")

    try:
        content = await file.read()
        decoded = content.decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(decoded))
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read CSV")

    headers = [h.lower().strip() for h in csv_reader.fieldnames or []]
    if 'email' not in headers:
         raise HTTPException(status_code=400, detail="CSV missing 'email' column")

    new_attendees = []
    skipped_emails = []
    
    for row in csv_reader:
        clean = {k.lower().strip(): v.strip() for k, v in row.items() if k}
        email = clean.get('email')
        if not email: continue
        
        if db.query(Attendee).filter(Attendee.email == email).first():
            skipped_emails.append(email)
            continue

        attendee = Attendee(
            name=clean.get('name', 'Unknown'), 
            email=email, 
            invite_code=generate_invite_code(), 
            status="pending"
        )
        db.add(attendee)
        new_attendees.append(attendee)

    try:
        db.commit()
        return {"total_processed": len(new_attendees)+len(skipped_emails), "success_count": len(new_attendees), "skipped_emails": skipped_emails}
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Commit failed")

# ==============================================================================
# 4. ADMIN PORTAL (PUBLIC HTML - The JS inside handles the lock)
# ==============================================================================
BASE_DIR = Path(__file__).parent.parent.parent
ADMIN_PORTAL_DIR = BASE_DIR / "admin-portal"

@router.get("/portal", response_class=HTMLResponse)
async def admin_portal(request: Request):
    """Serve the main admin portal page (Public Endpoint)"""
    # ... (Your existing HTML code here, no changes needed to logic) ...
    # Simplified for brevity in this response, keep your existing HTML string
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Admin Portal</title>
        <script>
            // Check auth immediately
            const token = localStorage.getItem('access_token');
            if (!token) window.location.href = '/api/admin/portal/login';
        </script>
        <style>body { background: #0a0a0f; color: white; padding: 40px; font-family: sans-serif; }</style>
    </head>
    <body>
        <h1>Admin Portal</h1>
        <p>Welcome. <a href="#" onclick="localStorage.removeItem('access_token'); location.reload()">Logout</a></p>
        </body>
    </html>
    """)

@router.get("/portal/login", response_class=HTMLResponse)
async def admin_portal_login():
    """Serve the login page (Public Endpoint)"""
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Admin Login</title>
        <style>
            body { background: #0a0a0f; color: white; font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
            .box { background: rgba(255,255,255,0.05); padding: 40px; border-radius: 8px; width: 300px; }
            input { width: 100%; padding: 10px; margin: 10px 0; border: none; border-radius: 4px; }
            button { width: 100%; padding: 10px; background: #6366f1; color: white; border: none; cursor: pointer; }
        </style>
    </head>
    <body>
        <div class="box">
            <h2>Login</h2>
            <form onsubmit="handleLogin(event)">
                <input type="text" id="username" placeholder="Username (admin)" required>
                <input type="password" id="password" placeholder="Password" required>
                <button type="submit">Sign In</button>
            </form>
        </div>
        <script>
            async function handleLogin(e) {
                e.preventDefault();
                const username = document.getElementById('username').value;
                const password = document.getElementById('password').value;

                // FIX: Use URLSearchParams for OAuth2 Form Data
                const formData = new URLSearchParams();
                formData.append('username', username);
                formData.append('password', password);

                try {
                    const res = await fetch('/api/auth/login', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                        body: formData
                    });
                    
                    if (res.ok) {
                        const data = await res.json();
                        localStorage.setItem('access_token', data.access_token);
                        window.location.href = '/api/admin/portal';
                    } else {
                        alert('Invalid credentials');
                    }
                } catch (err) {
                    alert('Login error');
                }
            }
        </script>
    </body>
    </html>
    """)