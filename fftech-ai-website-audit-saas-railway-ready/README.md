
# FF Tech AI Website Audit SaaS (Railway-ready)

FastAPI-based SaaS to audit websites against 200 metrics, generate a 5-page PDF, and export XLSX/PPTX. **Frontend-agnostic** API with a minimal Bootstrap/Chart.js UI. **Dockerfile** provided; production-ready on **Railway** with **Postgres** plugin.

## Quickstart (Local)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

## Deploy to Railway (Dockerfile / Metal Build)
1. Push this repository to GitHub.
2. In Railway: **New Project → Deploy from Repo**.
3. In **Service → Settings → Build**:
   - **Root Directory**: path that contains this `Dockerfile` (repo root unless you moved it)
   - **Builder**: **Use Metal Build Environment (Dockerfile)**
   - **Custom Build Command**: *(empty)*
   - **Start Command**: *(empty)*
4. Attach **Postgres** plugin (Railway sets `DATABASE_URL`).
5. Add variables (Service → Variables):
```
SECRET_KEY=<very-long-secret>
BASE_URL=https://<your-service>.up.railway.app
ENV=production
# DATABASE_URL auto-set by Railway when Postgres is attached
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASS=<your-smtp-api-key>
SMTP_FROM=reports@fftech.ai
PSI_API_KEY=
```
6. **Deploy**. The app will run on `$PORT` (Dockerfile uses `${PORT:-8000}`).

## Notes
- In **production**, the app **requires** `DATABASE_URL` (injected by Railway Postgres).
- Tables auto-create via SQLAlchemy on first boot.
- Open-access audits do **not** store history. Registered users (email magic link) get 10 saved audits on the free plan.
