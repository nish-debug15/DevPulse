# DevPulse

> AI-driven bottleneck isolation & automated standups for engineering teams.

DevPulse connects to your GitHub account and automatically surfaces what's slowing you down — stale PRs, merge lag, commit velocity drops — and generates daily standups from real commit and PR data using an LLM. Track your own metrics or add teammates to monitor their pipeline health from a single dashboard.

**Live:** [devpulse-nish.vercel.app](https://devpulse-nish.vercel.app/)

---

## What it does

- **Auto-standups** — generates per-developer standups from real commits and PRs via Groq Llama-3. No more writing them manually.
- **Bottleneck detection** — flags PRs open > 48h with severity classification (stale / warning / critical).
- **Commit velocity tracking** — week-over-week commit comparison with trend indicators.
- **Merge lag analysis** — average hours from PR creation to merge over the last 30 days.
- **Natural language queries** — ask *"who's been blocked the longest this week?"* and get a real answer from your data.
- **Team tracking** — add any GitHub user to your dashboard and monitor their metrics using your own OAuth token.
- **Slack digest** — push standup summaries and bottleneck alerts to a Slack channel via webhook.

---

## Tech stack

| Layer | Tool | Why |
|---|---|---|
| Backend | FastAPI (Python 3.14) | Async, fast, great DX |
| Scheduling | APScheduler | Hourly sync jobs, no broker needed |
| Database | SQLite + SQLAlchemy 2.0 | Simple, zero-config, file-based |
| LLM | Groq API (Llama-3 8B) | Fast inference, generous free tier |
| Frontend | Next.js 15 (App Router) + Tailwind + shadcn/ui | Server components, edge middleware |
| Auth | GitHub OAuth 2.0 + JWT (HS256) | httpOnly cookies, Fernet-encrypted tokens at rest |
| Infra | AWS EC2 (t3.micro) + Vercel | Backend on EC2 with systemd, frontend on Vercel edge CDN |
| Notifications | Slack Incoming Webhooks | Simple, no Slack SDK needed |

---

## Architecture

```
GitHub OAuth ◄──── User Browser ────► Vercel (Next.js)
     │                                      │
     ▼                                      │ fetch /standup, /bottlenecks
GitHub API                                  ▼
     │                              FastAPI (EC2:8000)
     │  PRs, Commits                   │         │
     ▼                                 ▼         ▼
APScheduler ──► SQLite           BottleneckEngine  QueryEngine
(hourly sync)    ▲                     │              │
                 │                     ▼              ▼
                 │               Groq Llama-3    Groq Llama-3
                 │                     │
                 │                     ├──► Dashboard (Next.js)
                 │                     └──► Slack Webhook
                 │
                 └── Fernet-encrypted access tokens
```

---

## Local setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- GitHub OAuth App ([create one here](https://github.com/settings/applications/new))
  - Callback URL: `http://127.0.0.1:8000/auth/callback`
- Groq API key ([free at console.groq.com](https://console.groq.com))
- (Optional) Slack Incoming Webhook URL ([create here](https://api.slack.com/messaging/webhooks))

### 1. Clone and install

```bash
git clone https://github.com/nish-debug15/DevPulse.git
cd DevPulse

# Backend
cd backend
python -m venv venv
source venv/bin/activate        # Linux/Mac
# .\\venv\\Scripts\\Activate.ps1  # Windows PowerShell
pip install -r ../requirements.txt

# Frontend
cd ../frontend
npm install
```

### 2. Environment variables

Create `backend/.env`:

```env
GITHUB_CLIENT_ID=your_github_oauth_client_id
GITHUB_CLIENT_SECRET=your_github_oauth_client_secret
GROQ_API_KEY=your_groq_api_key
ENCRYPTION_KEY=<generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">
JWT_SECRET=<generate with: python -c "import secrets; print(secrets.token_urlsafe(32))">
FRONTEND_URL=http://localhost:3000
ENVIRONMENT=development
SLACK_WEBHOOK_URL=                # optional
```

### 3. Run locally

```bash
# Backend (from /backend directory)
uvicorn main:app --reload --port 8000

# Frontend (from /frontend directory)
npm run dev
```

Visit `http://localhost:3000` for the dashboard. Backend API at `http://localhost:8000`. Test OAuth at `http://localhost:8000/auth/login`.

---

## Deployment

### Backend — AWS EC2 (t3.micro, Ubuntu)

```bash
ssh -i your-key.pem ubuntu@your-ec2-ip

sudo apt update && sudo apt install -y python3-pip python3-venv git
git clone https://github.com/nish-debug15/DevPulse.git
cd DevPulse/backend

python3 -m venv venv
source venv/bin/activate
pip install -r ../requirements.txt

nano .env   # paste your environment variables (set ENVIRONMENT=production)
```

Managed via systemd for auto-restart:

```bash
sudo cat > /etc/systemd/system/devpulse.service << 'EOF'
[Unit]
Description=DevPulse FastAPI Backend
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/DevPulse/backend
Environment="PATH=/home/ubuntu/DevPulse/backend/venv/bin:/usr/bin"
EnvironmentFile=/home/ubuntu/DevPulse/backend/.env
ExecStart=/home/ubuntu/DevPulse/backend/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable devpulse
sudo systemctl start devpulse
```

Update your GitHub OAuth App callback URL to: `http://your-ec2-ip:8000/auth/callback`

### Frontend — Vercel

1. Import the repo in [Vercel](https://vercel.com).
2. Set root directory to `frontend`.
3. Add environment variable: `NEXT_PUBLIC_BACKEND_URL = http://your-ec2-ip:8000`
4. Deploy. Vercel auto-deploys on every push to `main`.

---

## Project structure

```
DevPulse/
├── backend/
│   ├── main.py                       # FastAPI app, routes, scheduler setup
│   ├── auth/
│   │   ├── github_oauth.py           # OAuth login/callback + cross-domain token relay
│   │   ├── jwt_handler.py            # JWT creation and verification (HS256)
│   │   └── dependencies.py           # get_authenticated_user dependency
│   ├── db/
│   │   ├── database.py               # SQLAlchemy engine + session factory
│   │   └── models.py                 # User, TrackedDeveloper, PullRequest, Commit
│   ├── services/
│   │   ├── engine.py                 # BottleneckEngine (stale PRs, velocity, merge lag)
│   │   ├── ai_synthesis.py           # StandupGenerator (Groq Llama-3 + Pydantic validation)
│   │   ├── github_fetcher.py         # Async GitHub API client (pagination, rate-limit, backoff)
│   │   ├── query_engine.py           # Natural language query → LLM → answer
│   │   └── slack_notifier.py         # Slack webhook sender
│   └── tests/                        # 22-test pytest suite
├── frontend/
│   ├── app/
│   │   ├── page.tsx                  # Landing page (GitHub sign-in)
│   │   └── dashboard/[username]/
│   │       └── page.tsx              # Dashboard (metrics + AI standup)
│   ├── components/
│   │   ├── bottleneck-register.tsx   # Accordion PR blockage viewer
│   │   └── team-sidebar.tsx          # Team member management sidebar
│   └── middleware.ts                 # Token interception + auth guard
├── requirements.txt
└── README.md
```

---

## API endpoints

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/` | No | Health check |
| `GET` | `/auth/login` | No | Initiate GitHub OAuth |
| `GET` | `/auth/callback` | No | OAuth callback, creates session |
| `GET` | `/auth/me` | Yes | Current authenticated user |
| `POST` | `/auth/logout` | No | Clear session cookie |
| `POST` | `/users/{username}/sync` | Yes | Trigger background GitHub data sync |
| `GET` | `/users/{username}/standup` | Yes | AI-generated standup report (10/min) |
| `GET` | `/pr/bottlenecks` | Yes | PR bottleneck data with severity (30/min) |
| `POST` | `/slack/send` | Yes | Push standup or bottleneck alert to Slack (10/min) |
| `POST` | `/query` | Yes | Natural language query against metrics (10/min) |
| `POST` | `/team/add` | Yes | Add a GitHub user to tracked team |
| `GET` | `/team` | Yes | List tracked developers |
| `DELETE` | `/team/{username}` | Yes | Remove tracked developer |
| `POST` | `/team/{username}/sync` | Yes | Sync a specific tracked developer |

---

## Security

- **Token encryption at rest** — GitHub access tokens encrypted with Fernet (AES-128-CBC) before storage.
- **httpOnly cookies** — JWT session token stored in httpOnly cookie, inaccessible to client-side JS.
- **No hardcoded secrets** — all secrets loaded from `.env`, server crashes on startup if any are missing.
- **Rate limiting** — SlowAPI on all LLM and notification endpoints.
- **22 backend tests** — pytest suite covering auth, sync, and engine logic.

---

## Known limitations

- Backend runs on plain HTTP (no TLS). JWT cookie travels in cleartext.
- Cross-domain auth uses JWT-in-URL relay (functional but leaks token to browser history/logs).
- SQLite + in-process APScheduler — no horizontal scaling without migration to PostgreSQL + Celery.
- No CI/CD — deploys are manual SSH + restart.
- No observability (Sentry, structured logging, LLM latency metrics).
- Frontend has no test coverage.

---

## License

MIT
