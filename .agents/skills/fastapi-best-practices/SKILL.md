---
name: fastapi-best-practices
description: Use when designing or refactoring FastAPI routes, schemas, dependencies, database sessions, error handlers, or project structure for scalable backend services.
---

# FastAPI Best Practices

## Overview
A production-grade reference for building clean, maintainable, and robust FastAPI backends based on real-world engineering lessons and [zhanymkanov/fastapi-best-practices](../../references/repositories/fastapi-best-practices/README.md).

## When to Use
- Designing project folder structure and modules
- Implementing route handlers (`async def` vs `def`)
- Defining Pydantic v2 schemas and validation
- Configuring Dependency Injection (`Annotated[T, Depends(...)]`)
- Managing database sessions, transactions, and connection pools
- Handling errors globally and preventing credential leaks

## Core Architecture Patterns

### 1. Domain-Driven Project Structure
Organize backend services by business domain (bounded context), not by generic file types:

```text
backend/
├── api/
│   ├── routes/              # Routers grouped by feature or domain
│   │   ├── health.py
│   │   ├── receptionist.py
│   │   └── analyst.py
│   └── router.py            # Main API v1 router aggregator
├── core/
│   ├── config.py            # Pydantic Settings & environment variables
│   ├── logging.py           # Structured logging configuration
│   └── exceptions.py        # Custom exception classes
├── database/
│   ├── connection.py        # Engine, SessionLocal, get_db dependency
│   ├── models.py            # SQLAlchemy DeclarativeBase & ORM models
│   └── init_db.py           # Schema initialization & seeders
├── schemas/                 # Pydantic v2 request/response models
├── services/                # Business logic decoupled from API transport
└── main.py                  # FastAPI app factory & lifespan
```

### 2. Async vs Sync Route Rules
- **Non-blocking I/O (Async DB, HTTP clients, AI APIs)**: Use `async def`.
  ```python
  @router.get("/conversations")
  async def get_conversations(db: Session = Depends(get_db)):
      return await service.fetch_conversations()
  ```
- **Blocking I/O without async support**: Use `def` (FastAPI automatically runs sync routes in an external thread pool).
- **Blocking code inside an `async def` route**: NEVER call blocking functions directly (e.g. `time.sleep()`, synchronous file I/O). Wrap with `run_in_threadpool`:
  ```python
  from fastapi.concurrency import run_in_threadpool
  
  result = await run_in_threadpool(sync_heavy_task, arg)
  ```
- **CPU-bound tasks (>50ms)**: Offload to a background worker queue or process pool.

### 3. Pydantic v2 Data Modeling
- Separate **Database Models (SQLAlchemy ORM)** from **Transport Schemas (Pydantic)**.
- Use `model_config = ConfigDict(from_attributes=True)` on output schemas to serialize SQLAlchemy ORM objects directly.
- Avoid generic `dict` responses; define explicit response models for OpenAPI docs and type safety:
  ```python
  from pydantic import BaseModel, ConfigDict, Field

  class CustomerResponse(BaseModel):
      model_config = ConfigDict(from_attributes=True)
      
      id: int
      name: str
      phone: str = Field(..., pattern=r"^\+?[1-9]\d{1,14}$")
      is_qualified_lead: bool = False
  ```

### 4. Clean Dependency Injection
Use `typing.Annotated` with `Depends` for reusable and testable dependencies:
```python
from typing import Annotated
from fastapi import Depends
from sqlalchemy.orm import Session
from backend.database.connection import get_db

DBSession = Annotated[Session, Depends(get_db)]

@router.get("/leads")
async def list_leads(db: DBSession):
    return db.query(Lead).all()
```

### 5. Safe Database Session Management
Ensure sessions commit on success, rollback on error, and always close:
```python
def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
```

## Anti-Patterns & Common Mistakes
- **Leaking Secrets**: Never return raw exception strings in 500 error responses.
- **Global DB Sessions**: Never store a DB session in global state or request state. Always use `Depends(get_db)`.
- **Mixing Transport & Business Logic**: Route functions should parse inputs and call a service; do not write 100-line database operations inside router handlers.
- **Blocking the Event Loop**: Do not use `requests` or `time.sleep` in `async def` routes. Use `httpx.AsyncClient` and `asyncio.sleep`.

## Local Repository Reference
The full source code, guides, and AGENTS.md specification are located at:
`references/repositories/fastapi-best-practices/`
- [README.md](../../references/repositories/fastapi-best-practices/README.md)
- [AGENTS.md](../../references/repositories/fastapi-best-practices/AGENTS.md)
