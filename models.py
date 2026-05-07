"""
Pydantic models for request/response validation in AI Code Manager Studio Pro v2.

These models enforce input constraints and provide clear documentation for all
API endpoints, including session management, AI analysis, code generation,
GitHub integration, and real-time streaming.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator


# ──────────────────────────────────────────────
#  Enums for constrained string fields
# ──────────────────────────────────────────────

class AnalysisDepth(str, Enum):
    """Depth of analysis to perform on a project or prompt."""
    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"


class CodeLanguage(str, Enum):
    """Supported programming languages for code generation."""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    CPP = "cpp"
    GO = "go"
    RUST = "rust"
    OTHER = "other"


class GenerationMode(str, Enum):
    """Mode for code generation – creation, refactoring, or fixing."""
    CREATE = "create"
    REFACTOR = "refactor"
    FIX = "fix"
    EXPLAIN = "explain"


class PushStrategy(str, Enum):
    """How to handle existing branches/repos on push."""
    CREATE_NEW = "create_new"
    FORCE_PUSH = "force_push"
    MERGE = "merge"


# ──────────────────────────────────────────────
#  Common base models
# ──────────────────────────────────────────────

class BaseRequest(BaseModel):
    """Shared fields for all requests (optional authentication/session)."""
    session_id: Optional[str] = Field(
        None, description="Unique session identifier (UUID). Created if omitted."
    )
    user_id: Optional[str] = Field(
        None, description="Authenticated user identifier, if applicable."
    )

    class Config:
        extra = "forbid"


class BaseResponse(BaseModel):
    """Shared fields for all responses."""
    status: str = Field("ok", description="Response status: 'ok' or 'error'.")
    error: Optional[str] = Field(None, description="Error message if status is 'error'.")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="UTC timestamp of the response.")


# ──────────────────────────────────────────────
#  Session management models
# ──────────────────────────────────────────────

class SessionCreateRequest(BaseRequest):
    """Request to create a new session."""
    name: str = Field("New Session", min_length=1, max_length=200, description="Human-readable session name.")
    description: Optional[str] = Field(None, max_length=1000, description="Optional session description.")


class SessionRenameRequest(BaseRequest):
    """Request to rename an existing session."""
    session_id: str = Field(..., description="UUID of the session to rename.")
    new_name: str = Field(..., min_length=1, max_length=200, description="New session name.")

    @field_validator("new_name")
    @classmethod
    def name_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Session name cannot be blank.")
        return v.strip()


class SessionResponse(BaseResponse):
    """Response containing a session object."""
    session: Optional[Dict[str, Any]] = Field(None, description="Session details: id, name, created_at, etc.")


class SessionListResponse(BaseResponse):
    """Response containing a list of sessions."""
    sessions: List[Dict[str, Any]] = Field(default_factory=list, description="List of session objects.")
    total: int = Field(0, description="Total number of sessions matching the query.")


# ──────────────────────────────────────────────
#  Chat and message models
# ──────────────────────────────────────────────

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

class ChatMessage(BaseModel):
    """A single message in a conversation."""
    role: MessageRole = Field(..., description="Who sent the message.")
    content: str = Field(..., description="Text content of the message.")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="When the message was sent.")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional extra data (e.g., model info).")


class SendMessageRequest(BaseRequest):
    """Request to send a chat message and get an AI response."""
    session_id: str = Field(..., description="Session to which this message belongs.")
    message: str = Field(..., min_length=1, max_length=10000, description="User's message text.")
    context: Optional[str] = Field(None, max_length=50000, description="Optional additional context (e.g., current code).")
    model: Optional[str] = Field(None, description="AI model identifier (e.g., 'gpt-4o', 'claude-3').")


class MessageListResponse(BaseResponse):
    """Response containing a list of messages for a session."""
    session_id: str = Field(..., description="Session identifier.")
    messages: List[ChatMessage] = Field(default_factory=list, description="Ordered list of messages.")


# ──────────────────────────────────────────────
#  Analysis models
# ──────────────────────────────────────────────

class AnalyzeRequest(BaseRequest):
    """Request to perform AI-powered analysis on a project/prompt."""
    session_id: str = Field(..., description="Session to run analysis in.")
    prompt: str = Field(..., min_length=1, max_length=20000, description="Prompt or description of what to analyze.")
    depth: AnalysisDepth = Field(AnalysisDepth.STANDARD, description="How thorough the analysis should be.")
    language: Optional[CodeLanguage] = Field(None, description="Primary language of the codebase, if known.")
    include_code: bool = Field(True, description="Whether to extract or include existing code in the analysis.")
    additional_context: Optional[str] = Field(None, max_length=5000, description="Extra context for the analysis.")


class AnalyzeResponse(BaseResponse):
    """Response from an analysis (used when not streaming)."""
    analysis_id: str = Field(..., description="Unique ID for the analysis result.")
    summary: str = Field(..., description="Text summary of the analysis.")
    insights: List[str] = Field(default_factory=list, description="Key insights as bullet points.")
    suggestions: List[str] = Field(default_factory=list, description="Suggested improvements or next steps.")
    code_blocks: Optional[Dict[str, str]] = Field(None, description="Extracted code blocks keyed by filename.")


# ──────────────────────────────────────────────
#  Code generation models
# ──────────────────────────────────────────────

class GenerateCodeRequest(BaseRequest):
    """Request to generate code based on an analysis or prompt."""
    session_id: str = Field(..., description="Session associated with this generation.")
    prompt: str = Field(..., min_length=1, max_length=20000, description="Description of the code to generate.")
    analysis_id: Optional[str] = Field(None, description="Optional ID of a prior analysis to use as context.")
    language: CodeLanguage = Field(CodeLanguage.PYTHON, description="Target programming language.")
    mode: GenerationMode = Field(GenerationMode.CREATE, description="Code generation mode.")
    include_comments: bool = Field(True, description="Whether to generate inline comments.")
    include_tests: bool = Field(False, description="Whether to generate unit tests.")
    max_tokens: int = Field(4000, ge=100, le=32000, description="Maximum tokens for the generated code.")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="Creativity of the model (0=deterministic).")

    @field_validator("max_tokens")
    @classmethod
    def tokens_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("max_tokens must be positive.")
        return v


class GenerateCodeResponse(BaseResponse):
    """Response containing generated code."""
    session_id: str = Field(..., description="Session where code was generated.")
    files: Dict[str, str] = Field(..., description="Generated files as {filename: content}.")
    explanation: Optional[str] = Field(None, description="Optional explanation of the generated code.")
    warnings: List[str] = Field(default_factory=list, description="Any warnings from the generation process.")


# ──────────────────────────────────────────────
#  GitHub push models
# ──────────────────────────────────────────────

class PushToGitHubRequest(BaseRequest):
    """Request to push generated code to a GitHub repository."""
    session_id: str = Field(..., description="Session containing the code to push.")
    repo_url: str = Field(..., description="Full GitHub repository URL (e.g., https://github.com/user/repo).")
    branch: str = Field("main", min_length=1, max_length=200, description="Branch name to push to.")
    commit_message: str = Field("AI-generated code", min_length=1, max_length=500, description="Commit message.")
    token: str = Field(..., description="GitHub personal access token (with repo scope).")
    strategy: PushStrategy = Field(PushStrategy.CREATE_NEW, description="How to handle existing branch/repo.")
    files: Optional[Dict[str, str]] = Field(None, description="Overrides: explicitly list files to push. If None, push all files in session.")

    @field_validator("repo_url")
    @classmethod
    def validate_github_url(cls, v: str) -> str:
        if not v.startswith("https://github.com/"):
            raise ValueError("repo_url must be a valid GitHub HTTPS URL starting with https://github.com/")
        return v.rstrip("/")

    @field_validator("commit_message")
    @classmethod
    def commit_message_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("commit_message cannot be blank.")
        return v.strip()


class PushToGitHubResponse(BaseResponse):
    """Response from a GitHub push operation."""
    push_id: str = Field(..., description="Unique identifier for the push operation.")
    repo_url: str = Field(..., description="Target repository URL.")
    branch: str = Field(..., description="Branch used for push.")
    commit_hash: Optional[str] = Field(None, description="SHA of the created commit (if successful).")
    files_pushed: int = Field(0, description="Number of files successfully pushed.")
    files_failed: List[str] = Field(default_factory=list, description="Filenames that failed to push.")


# ──────────────────────────────────────────────
#  Streaming event models (Server-Sent Events)
# ──────────────────────────────────────────────

class StreamEventType(str, Enum):
    """Event types used in SSE streams."""
    START = "start"
    CHUNK = "chunk"
    DONE = "done"
    ERROR = "error"
    STATUS = "status"
    CODE_BLOCK = "code_block"
    ANALYSIS_RESULT = "analysis_result"
    PROGRESS = "progress"

class StreamEvent(BaseModel):
    """A single event sent over SSE stream."""
    event: StreamEventType = Field(..., description="Type of the event.")
    data: Union[str, Dict[str, Any], List[Any]] = Field(..., description="Payload of the event.")
    id: Optional[str] = Field(None, description="Optional event ID (for Last-Event-ID).")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="When the event was emitted.")

    class Config:
        use_enum_values = True  # serialize enum as string


class StreamResponse(BaseModel):
    """Wrapper for SSE stream responses (used in endpoint return types)."""
    stream_id: str = Field(..., description="Unique stream identifier.")
    events: List[StreamEvent] = Field(default_factory=list, description="Queue of events to send.")


# ──────────────────────────────────────────────
#  Generic error / health models
# ──────────────────────────────────────────────

class ErrorResponse(BaseModel):
    """Standard error response body."""
    status: str = Field("error", description="Always 'error'.")
    error: str = Field(..., description="Human-readable error description.")
    code: Optional[str] = Field(None, description="Error code for programmatic handling (e.g., 'INVALID_INPUT').")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error context.")


class HealthResponse(BaseModel):
    """Response for health-check endpoint."""
    status: str = Field("ok", description="Service health status.")
    version: str = Field("2.0.0", description="Application version.")
    uptime_seconds: float = Field(0.0, description="Seconds since service started.")
    models_loaded: List[str] = Field(default_factory=list, description="List of AI models currently loaded.")