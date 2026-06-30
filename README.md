# DevPulse

> AI-powered engineering standup and bottleneck intelligence for small teams.

DevPulse connects to your GitHub repos and automatically surfaces what's slowing your team down — stale PRs, blocked issues, review lag, sprint velocity drops — and generates daily standups from real commit and PR data. Ask it anything in plain English: *"Why was last sprint slow?"*

---

## What it does

- **Auto-standups** — generates per-engineer standups from real commits and PRs. No more writing them manually.
- **Bottleneck detection** — flags PRs open > 48h, review lag, blocked issues, deploy frequency drops.
- **Natural language queries** — ask *"who's been blocked the longest this week?"* and get a real answer from your data.
- **Team dashboard** — cycle time, PR turnaround, sprint velocity delta. At a glance.
- **Slack digest** — posts standups and weekly bottleneck reports directly to your channel.

---

## Tech stack

| Layer | Tool | Why |
|---|---|---|
| Backend | FastAPI | Fast, async, great DX |
| Scheduling | APScheduler | Cron-style sync jobs, no broker needed |
| Database | SQLite → PostgreSQL (RDS) | SQLite locally, Postgres in prod |
| LLM | Groq API (Qwen 3.6 27B) | Fast inference, generous free tier |
| Frontend | Next.js | Dashboard UI |
| Auth | OAuth 2.0 | GitHub + Slack |
| Infra | AWS EC2 t2.micro + RDS | Using AWS credits |
| Notifications | Slack Incoming Webhooks | Simple, no Slack SDK needed |

---

## Architecture

```
GitHub API
    │
    │  OAuth + REST (PRs, commits, issues)
    ▼
FastAPI ──────────────────── SQLite / PostgreSQL
    │                              ▲
    │                              │
APScheduler (hourly sync) ─────────┘
    │
    ▼
Bottleneck Engine (pure Python)
    │  PR lag, cycle time, velocity delta
    ▼
Groq API (Llama 3 70B)
    │  Standup generation + NL query synthesis
    ├──► Next.js Dashboard
    └──► Slack Incoming Webhook
```

---

## Local setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- GitHub OAuth App ([create one here](https://github.com/settings/applications/new))
- Groq API key ([free at console.groq.com](https://console.groq.com))
- Slack Incoming Webhook URL ([create here](https://api.slack.com/messaging/webhooks))

### 1. Clone and install

```bash
git clone https://github.com/nish-debug15/DevPulse.git
cd devpulse

# Backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Frontend
cd frontend
npm install
```

### 2. Environment variables

```bash
cp .env.example .env
```

Fill in `.env`:

```env
GITHUB_CLIENT_ID=your_github_oauth_client_id
GITHUB_CLIENT_SECRET=your_github_oauth_client_secret
GROQ_API_KEY=your_groq_api_key
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
DATABASE_URL=sqlite:///./devpulse.db
SECRET_KEY=generate_a_random_string_here
```

### 3. Run locally

```bash
# Backend (from root)
uvicorn backend.main:app --reload --port 8000

# Frontend (from /frontend)
npm run dev
```

Visit `http://localhost:3000` to see the dashboard. The backend API runs at `http://localhost:8000` — you can test the GitHub OAuth flow directly at `http://localhost:8000/auth/login`.

---

## Deployment (AWS EC2)

### EC2 setup

```bash
# SSH into your instance
ssh -i your-key.pem ubuntu@your-ec2-ip

# Install dependencies
sudo apt update && sudo apt install -y python3-pip python3-venv nginx git

# Clone repo
git clone https://github.com/nish-debug15/DevPulse.git
cd devpulse

# Setup venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Set env vars
nano .env  # paste your variables

# Run (keep alive)
nohup uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
```

### Point GitHub OAuth to your EC2 IP

Update your GitHub OAuth App's callback URL:
```
http://your-ec2-ip:8000/auth/callback
```

### (Optional) RDS Postgres

Free tier: `db.t3.micro`, 20GB. Update `DATABASE_URL` in `.env`:
```
DATABASE_URL=postgresql://user:password@your-rds-endpoint:5432/devpulse
```

---

## Project structure

```
devpulse/
├── backend/
│   ├── main.py              # FastAPI app entry
│   ├── auth/                # GitHub OAuth flow
│   ├── github/              # GitHub API client
│   ├── scheduler/           # APScheduler sync jobs
│   ├── engine/              # Bottleneck detection logic
│   ├── llm/                 # Groq API integration
│   ├── slack/               # Slack webhook sender
│   └── db/                  # SQLite/Postgres models
├── frontend/                # Next.js dashboard
├── .env.example
├── requirements.txt
└── README.md
```

---

## API endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/auth/login` | Initiate GitHub OAuth |
| `GET` | `/auth/callback` | OAuth callback |
| `GET` | `/team/summary` | Team bottleneck summary |
| `GET` | `/team/standups` | Today's auto-generated standups |
| `GET` | `/pr/bottlenecks` | PRs flagged as blocked |
| `POST` | `/query` | Natural language query → LLM answer |
| `POST` | `/slack/send` | Push digest to Slack |

---

## Contributing

Built solo as a learning project. PRs welcome for:
- Additional data sources (Linear, Jira)
- Smarter bottleneck heuristics
- Multi-team / org support

---

## License

MIT
