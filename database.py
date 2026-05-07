from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    String,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine

from app.core.config import settings  # assumes settings.DATABASE_URL is defined

# Re-export for convenience
Base = None  # placeholder, will be defined below

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DATABASE_ECHO,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(AsyncAttrs, DeclarativeBase):
    """Declarative base with async support."""

    pass


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    __table_args__ = (
        UniqueConstraint("name"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="active"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    # Relationships
    messages: Mapped[List["Message"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", lazy="selectin"
    )
    projects: Mapped[List["Project"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<ChatSession(id={self.id}, name={self.name!r}, status={self.status!r})>"


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False)  # 'user', 'assistant', 'system'
    content: Mapped[str] = mapped_column(Text, nullable=False)
    code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    files_plan: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    # Relationships
    session: Mapped["ChatSession"] = relationship(
        back_populates="messages", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Message(id={self.id}, role={self.role!r}, session_id={self.session_id})>"


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("session_id", "name"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    files: Mapped[dict] = mapped_column(JSON, nullable=False)  # list of file objects
    repo_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    pushed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    # Relationships
    session: Mapped["ChatSession"] = relationship(
        back_populates="projects", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Project(id={self.id}, name={self.name!r}, session_id={self.session_id})>"


# Helper to get an async session (context manager usage)
async def get_session():
    """Yield an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


# For convenience (used in app startup)
async def init_db():
    """Create all tables if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Dispose the engine."""
    await engine.dispose()