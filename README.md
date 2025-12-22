Here is a complete, professional `README.md` for your project. It includes everything from the architecture overview to practical commands for debugging and maintenance.

Since you are a CS student, I have structured this to look good on a GitHub portfolio, highlighting the "Microservices" and "AI/ML" aspects.

---

### `README.md`

```markdown
# 🔐 Face Access Control System (Prototype)

A privacy-focused, biometric access control system built with **FastAPI**, **Qdrant (Vector DB)**, and **Docker**. This system allows organizers to upload attendee lists, generates unique invite codes, and verifies access using facial recognition embeddings without storing raw photos.

## 🚀 Tech Stack

* **Backend:** Python (FastAPI), SQLAlchemy, Pydantic
* **AI/ML:** `face_recognition` (dlib), OpenCV, NumPy
* **Database:** PostgreSQL (User metadata), Qdrant (Vector storage for face embeddings)
* **Frontend:** Vanilla JavaScript, HTML5, CSS3 (served via Nginx)
* **Infrastructure:** Docker, Docker Compose, Nginx (Reverse Proxy)

---

## 📂 Project Structure

```text
face-access-prototype/
│
├── backend/                 # Python FastAPI Application
│   ├── app/
│   │   ├── main.py          # App entry point
│   │   ├── core/            # Config and Security
│   │   ├── api/routes/      # API Endpoints (Upload, Register, Access)
│   │   ├── services/        # Logic for Face Detection & Embedding
│   │   ├── models/          # SQLAlchemy Models
│   │   ├── db/              # Database Connection Logic
│   │   └── utils/           # Helper scripts (Crypto, Image processing)
│   ├── Dockerfile           # Python 3.10-slim-bullseye build
│   └── requirements.txt
│
├── frontend/                # Static Frontend Files
│   ├── organizer/           # Admin Portal (Upload CSV)
│   ├── register/            # User Registration (Camera + Invite Code)
│   └── access/              # Access Check Terminal
│
├── docker-compose.yml       # Orchestration for App, DB, Qdrant, Nginx
└── nginx.conf               # Reverse proxy config

```

---

## 🛠️ Setup & Installation

### Prerequisites

* [Docker](https://www.docker.com/) and Docker Compose installed.

### 1. Clone the Repository

```bash
git clone <repository-url>
cd face-access-prototype

```

### 2. Environment Configuration

Create a `.env` file in the `backend/` directory (or rely on defaults in `docker-compose.yml`).

```bash
# Example .env (Optional - defaults are set in docker-compose.yml)
POSTGRES_USER=faceaccess
POSTGRES_PASSWORD=1234
POSTGRES_DB=faceaccess
SECRET_KEY=your_secret_key
ENVIRONMENT=development

```

### 3. Build and Run

This will pull the images and build the backend (compiling `dlib` might take a few minutes).

```bash
docker compose up -d --build

```

Access the application at:

* **Frontend:** `http://localhost` (or your server IP)
* **API Docs:** `http://localhost:8000/docs`

---

## 📖 Usage Workflow

### 1. Organizer Portal (`/organizer`)

1. Navigate to `http://localhost/organizer`.
2. Upload a `.csv` file containing columns: `name`, `email`.
3. The system generates unique **Invite Codes** for each attendee.

### 2. User Registration (`/register`)

1. Navigate to `http://localhost/register`.
2. Enter the unique **Invite Code** generated in step 1.
3. The camera will activate. Capture your face to register.
* *Note:* The system generates a vector embedding and discards the raw image.



### 3. Access Check (`/access`)

1. Navigate to `http://localhost/access`.
2. Stand in front of the camera.
3. The system compares your live face against the Qdrant vector database to grant or deny access.

---

## 🔧 Maintenance & Debugging

### View Logs

Monitor the backend logs for errors or access attempts:

```bash
# Follow logs in real-time
docker compose logs -f backend

# View last 50 lines
docker compose logs --tail=50 backend

```

### Restarting Services

If you modify code, you may need to rebuild or restart specific containers.

**Restart Backend Only:**

```bash
docker compose restart backend

```

**Rebuild Backend (after changing `requirements.txt` or Dockerfile):**

```bash
docker compose up -d --build backend

```

**Restart Nginx (after changing `nginx.conf`):**

```bash
docker compose restart nginx

```

### Database Management

Access the PostgreSQL database directly:

```bash
docker compose exec postgres psql -U faceaccess -d faceaccess

```

*Useful commands:*

* `\dt` - List tables
* `SELECT * FROM attendees;` - View registered users and invite codes.

### Stopping the System

```bash
# Stop containers but keep data
docker compose stop

# Stop and remove containers (data persists in volumes)
docker compose down

# Stop and remove volumes (WARNING: Deletes database data)
docker compose down -v

```

---

## ⚠️ Troubleshooting

### Camera Not Working

Modern browsers block camera access on "insecure" HTTP origins (non-HTTPS), unless the origin is `localhost`.

* **Fix 1 (Local):** Access via `http://localhost`.
* **Fix 2 (Remote Server):** Use Chrome flag `chrome://flags/#unsafely-treat-insecure-origin-as-secure` to allow your IP.
* **Fix 3 (Production):** Set up SSL/HTTPS using Let's Encrypt.

### "Entity Too Large" Error

If uploading high-res images fails, check `nginx.conf`. Ensure `client_max_body_size` is set to at least `10M`.

### Backend Crashes (Exit Code 137)

This usually means "Out of Memory". `dlib` face recognition is memory intensive. Ensure your Docker host has at least 2GB of RAM (or 1GB + Swap).

---

## 📜 License

[MIT License](https://www.google.com/search?q=LICENSE)

```

```
