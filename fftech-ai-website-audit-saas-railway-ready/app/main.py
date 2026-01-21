import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, Request, Depends, HTTPException, Header, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse, PlainTextResponse, RedirectResponse

from sqlalchemy.orm import Session
import jwt
from pydantic import EmailStr, BaseModel

from .config import settings
from .database import init_db, SessionLocal
from .models import User, Audit
from .routers import auth as auth_router
from .audit.analyzer import analyze
from .audit.grader import overall_score, to_grade
from .audit.report import build_pdf

# ── Optional: Import Gemini for AI summaries ────────────────────────────────
try:
    import google.generativeai as genai
    genai.configure(api_key=settings.GEMINI_API_KEY)
    GEMINI_AVAILABLE = True
except Exception:
    GEMINI_AVAILABLE = False
    print("Warning: Gemini not configured or unavailable")

app = FastAPI(
    title=f"{settings.BRAND_NAME} AI Website Audit",
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url=None,
)

# ── Middleware & Static Files ───────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

app.include_router(auth_router.router)


# ── Startup Event ────────────────────────────────────────────────────────────
@app.on_event("startup")
def on_startup():
    init_db()
    os.makedirs(settings.REPORT_DIR, exist_ok=True)
    os.makedirs(settings.EXPORT_DIR, exist_ok=True)


# ── Database Dependency ──────────────────────────────────────────────────────
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Current User Dependency (JWT or None for open access) ────────────────────
class UserOut(BaseModel):
    id: int
    email: EmailStr
    is_subscribed: bool


def get_current_user(
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> Optional[User]:
    if not authorization:
        return None  # Open / anonymous access

    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid authentication scheme")

        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")

        user = db.query(User).filter(User.email == email).first()
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception:
        raise HTTPException(status_code=401, detail="Authentication failed")


# ── Google Site Verification ─────────────────────────────────────────────────
@app.get("/googlee889836d4b830bda.html", response_class=PlainTextResponse)
async def google_verify():
    return "google-site-verification: googlee889836d4b830bda.html"


# ── UI Pages ─────────────────────────────────────────────────────────────────
@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/register")
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@app.get("/dashboard")
async def dashboard_page(request: Request, current_user: Optional[User] = Depends(get_current_user)):
    if not current_user:
        return RedirectResponse(url="/login?next=/dashboard")
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": current_user,
    })


@app.get("/audit_detail")
async def audit_detail_page(
    request: Request,
    id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Login required to view audit details")

    audit = db.query(Audit).filter(Audit.id == id, Audit.user_id == current_user.id).first()
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found or access denied")

    return templates.TemplateResponse("audit_detail.html", {
        "request": request,
        "audit": audit,
        "user": current_user,
    })


# ── API: Run Audit (Open + Registered) ───────────────────────────────────────
from .schemas import AuditRequest, AuditResponse


@app.post("/api/audit", response_model=AuditResponse)
async def run_audit(
    payload: AuditRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    url = payload.url.strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, detail="URL must start with http:// or https://")

    # ── Enforce free user limit ──────────────────────────────────────────────
    if current_user and not current_user.is_subscribed:
        count = db.query(Audit).filter(Audit.user_id == current_user.id).count()
        if count >= settings.AUDIT_LIMIT_FREE:
            raise HTTPException(
                status_code=403,
                detail=f"Free plan limit reached ({settings.AUDIT_LIMIT_FREE} audits). Upgrade for more."
            )

    # ── Perform the audit ────────────────────────────────────────────────────
    result = await analyze(url, payload.competitors or [])

    ovr_score = overall_score(result["category_scores"])
    grade = to_grade(ovr_score)

    # ── AI-powered executive summary (Gemini) ────────────────────────────────
    summary = {
        "executive_summary": f"Basic AI audit completed for {url}.",
        "strengths": ["Crawlability OK"],
        "weaknesses": ["Further optimization needed"],
        "priority_fixes": ["Check broken links"],
    }

    if GEMINI_AVAILABLE:
        try:
            model = genai.GenerativeModel(settings.GEMINI_MODEL)
            prompt = (
                f"Create a concise executive summary (150-200 words) for a website audit of {url}.\n"
                f"Include: key strengths, main weaknesses, top 3 priority fixes.\n"
                f"Base it on these category scores: {result['category_scores']}\n"
                f"Be professional, objective, and actionable."
            )
            response = model.generate_content(prompt)
            summary_text = response.text.strip()

            # Simple parsing (you can improve this)
            summary["executive_summary"] = summary_text
            # Could also parse strengths/weaknesses if Gemini returns structured output
        except Exception as e:
            print(f"Gemini summary failed: {e}")

    # ── Save audit only for logged-in users ──────────────────────────────────
    audit_id = None
    pdf_path = None

    if current_user:
        audit = Audit(
            user_id=current_user.id,
            url=url,
            overall_score=ovr_score,
            grade=grade,
            summary=summary,
            category_scores=result["category_scores"],
            metrics=result.get("metrics", {}),
        )
        db.add(audit)
        db.commit()
        db.refresh(audit)
        audit_id = audit.id

        # Generate professional 5-page PDF
        pdf_path = build_pdf(
            audit_id=audit.id,
            url=url,
            overall_score=ovr_score,
            grade=grade,
            category_scores=result["category_scores"],
            metrics=result.get("metrics", {}),
            summary=summary,
            out_dir=settings.REPORT_DIR,
        )
        audit.report_pdf_path = pdf_path
        db.commit()

    return AuditResponse(
        audit_id=audit_id,
        url=url,
        overall_score=ovr_score,
        grade=grade,
        summary=summary,
        category_scores=result["category_scores"],
        metrics=result.get("metrics", {}),
        pdf_available=bool(pdf_path),
    )


# ── Download PDF Report (only owner) ─────────────────────────────────────────
@app.get("/api/reports/pdf/{audit_id}")
async def get_pdf(
    audit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user:
        raise HTTPException(401, "Login required to download reports")

    audit = db.query(Audit).filter(
        Audit.id == audit_id,
        Audit.user_id == current_user.id
    ).first()

    if not audit or not audit.report_pdf_path:
        raise HTTPException(404, "Report not found or access denied")

    if not os.path.exists(audit.report_pdf_path):
        raise HTTPException(404, "PDF file missing on server")

    return FileResponse(
        audit.report_pdf_path,
        media_type="application/pdf",
        filename=f"{settings.BRAND_NAME}_Audit_Report_{audit_id}.pdf",
    )
