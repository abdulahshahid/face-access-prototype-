# 🔐 Face Access Control System (Prototype)

A privacy-focused, biometric access control system built with **FastAPI**, **Qdrant (Vector DB)**, and **Docker**. This system allows organizers to upload attendee lists, generates unique invite codes, and verifies access using facial recognition embeddings without storing raw photos.

## 🚀 Tech Stack

* **Backend:** Python (FastAPI), SQLAlchemy, Pydantic
* **AI/ML:** `face_recognition` (dlib), OpenCV, NumPy
* **Database:** PostgreSQL (User metadata), Qdrant (Vector storage for face embeddings)
* **Frontend:** Vanilla JavaScript, HTML5, CSS3 (served via Nginx)
* **Infrastructure:** Docker, Docker Compose, Nginx (Reverse Proxy)

## 📂 Project Structure

face-access-prototype/
├── backend/
│ ├── app/
│ │ ├── main.py
│ │ ├── core/
│ │ ├── api/routes/
│ │ ├── services/
│ │ ├── models/
│ │ ├── db/
│ │ └── utils/
│ ├── Dockerfile
│ └── requirements.txt
├── frontend/
│ ├── organizer/
│ ├── register/
│ └── access/
├── docker-compose.yml
└── nginx.conf


## 🛠️ Setup & Installation

### Prerequisites

* [Docker](https://www.docker.com/) and Docker Compose installed.

### 1. Clone the Repository

```bash
git clone <repository-url>
cd face-access-prototype

2. Environment Configuration

Create a .env file in backend/ (optional; defaults are in docker-compose.yml):

POSTGRES_USER=faceaccess
POSTGRES_PASSWORD=1234
POSTGRES_DB=faceaccess
SECRET_KEY=your_secret_key
ENVIRONMENT=development

3. Build and Run

docker compose up -d --build

Access the application at:

    Frontend: http://localhost

    API Docs: http://localhost:8000/docs

📖 Usage Workflow
Organizer Portal (/organizer)

    Navigate to http://localhost/organizer.

    Upload a .csv file with name and email.

    System generates unique Invite Codes.

User Registration (/register)

    Navigate to http://localhost/register.

    Enter the Invite Code.

    Capture your face to register (embedding generated, raw image discarded).

Access Check (/access)

    Navigate to http://localhost/access.

    Stand in front of the camera for verification.

🔧 Maintenance & Debugging
View Logs

docker compose logs -f backend
docker compose logs --tail=50 backend

Restarting Services

docker compose restart backend
docker compose up -d --build backend
docker compose restart nginx

Database Management

docker compose exec postgres psql -U faceaccess -d faceaccess

Useful commands:

    \dt - List tables

    SELECT * FROM attendees; - View registered users

Stopping the System

docker compose stop
docker compose down
docker compose down -v

⚠️ Troubleshooting
Camera Not Working

    Local: Use http://localhost

    Remote: Enable insecure origin in Chrome

    Production: Use HTTPS/SSL

"Entity Too Large" Error

Check client_max_body_size in nginx.conf.
Backend Crashes (Exit Code 137)

Ensure Docker host has ≥2GB RAM.
📜 License

MIT License

