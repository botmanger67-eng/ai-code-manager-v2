import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

# ------------------------------------------------------------------
# Database and session imports (placeholders – adapt to your project)
# ------------------------------------------------------------------
from app.database import get_db, init_db  # your async database module
from app.models import Session as SessionModel  # your SQLAlchemy model
from app.schemas import SessionOut, AnalyzeRequest, GenerateCodeRequest, GitHubPushRequest
from app.services.analyzer import analyze_project
from app.services.codegen import generate_code_stream
from app.services.github import push_to_github

# ------------------------------------------------------------------
# Logging setup
# ------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

# ------------------------------------------------------------------
# Application lifespan – init database tables
# ------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up, initializing database...")
    await init_db()  # e.g., create tables
    yield
    logger.info("Shutting down, cleaning up resources...")
    # optionally close engine

# ------------------------------------------------------------------
# FastAPI application
# ------------------------------------------------------------------
app = FastAPI(
    title="AI Code Manager Studio Pro v2",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ------------------------------------------------------------------
# Static files & templates
# ------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# ------------------------------------------------------------------
# Global exception handler
# ------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception while processing request %s %s", request.method, request.url)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please try again later."},
    )

# ------------------------------------------------------------------
# Helper to get async db session
# ------------------------------------------------------------------
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)() as session:
        yield session
# (The engine should be created in your database module; if not, you can create it here)
# For simplicity, we assume `init_db` also sets `app.state.db_engine`.
# Below we use a dependency that gets the session from somewhere.
# You can replace `get_db` imported above with your own.

# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def serve_index(request: Request):
    """Serve the main SPA (index.html)."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/sessions")
async def list_sessions(db: AsyncSession = Depends(get_db)):
    """Return list of all sessions (id, name, created_at, modified_at)."""
    from sqlalchemy import select
    result = await db.execute(
        select(SessionModel).order_by(SessionModel.modified_at.desc())
    )
    sessions = result.scalars().all()
    # Convert to Pydantic schema for serialisation
    return [SessionOut.from_orm(s) for s in sessions]

@app.get("/api/session/{session_id}")
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """Return full session data including conversation and generated code."""
    from sqlalchemy import select
    result = await db.execute(
        select(SessionModel).where(SessionModel.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionOut.from_orm(session)

@app.post("/api/analyze")
async def analyze_endpoint(
    request: AnalyzeRequest,
    db: AsyncSession = Depends(get_db)
):
    """Analyze a project description and return structured plan."""
    try:
        plan = await analyze_project(request.project_description)
        # Optionally store plan in session
        session = SessionModel(name=request.project_name or "Untitled", plan=plan)
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return {"session_id": session.id, "plan": plan}
    except Exception as e:
        logger.exception("Analysis failed")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.post("/api/generate-code")
async def generate_code_endpoint(
    request: GenerateCodeRequest,
    db: AsyncSession = Depends(get_db)
):
    """Stream generated code via SSE."""
    # Validate session exists
    from sqlalchemy import select
    result = await db.execute(
        select(SessionModel).where(SessionModel.id == request.session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    async def event_generator():
        try:
            async for chunk in generate_code_stream(session.plan, request.module_selection):
                yield f"data: {chunk}\n\n"
            # Signal completion
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.exception("Error during code generation")
            yield f"data: [ERROR] {str(e)}\n\n"
        finally:
            # Optionally update session with generated code
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )

@app.post("/api/push-to-github")
async def push_to_github_endpoint(
    request: GitHubPushRequest,
    db: AsyncSession = Depends(get_db)
):
    """Push generated code to a GitHub repository."""
    from sqlalchemy import select
    result = await db.execute(
        select(SessionModel).where(SessionModel.id == request.session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.generated_code:
        raise HTTPException(status_code=400, detail="No generated code to push")
    try:
        github_url = await push_to_github(
            repo_name=request.repo_name or session.name,
            code=session.generated_code,
            token=request.github_token,
            branch=request.branch or "main",
            commit_message=request.commit_message or "AI generated code"
        )
        return {"message": "Code pushed successfully", "url": github_url}
    except Exception as e:
        logger.exception("GitHub push failed")
        raise HTTPException(status_code=500, detail=f"GitHub push failed: {str(e)}")

@app.delete("/api/session/{session_id}")
async def delete_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a session by ID."""
    from sqlalchemy import select, delete
    result = await db.execute(select(SessionModel).where(SessionModel.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    await db.delete(session)
    await db.commit()
    return {"message": "Session deleted"}

@app.put("/api/session/{session_id}/rename")
async def rename_session(
    session_id: str,
    new_name: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """Rename an existing session."""
    from sqlalchemy import select
    result = await db.execute(select(SessionModel).where(SessionModel.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.name = new_name
    await db.commit()
    await db.refresh(session)
    return {"session_id": session.id, "name": session.name}