"""API route modules initialization - Modular API.

All endpoints organized by domain:
- auth.py: Authentication endpoints
- chat.py: Chat and conversation endpoints
- content.py: Content processing, TTS, OCR, embeddings
- batch.py: Hardware-optimized batch processing
- health_routes.py: Health, monitoring, admin, profile
- library.py: Browse and search the ingested NCERT curriculum
- tutor.py: Grounded explanations in a chosen language

Optimized for:
- Native Apple Silicon (M4) with MPS/ANE acceleration
- Multi-tier caching (L1 memory, L2 Redis, L3 SQLite)
- Concurrent processing with batching
"""

from fastapi import APIRouter

from .auth import router as auth_router
from .batch import router as batch_router
from .chat import router as chat_router
from .content import router as content_router
from .health_routes import router as health_router
from .library import router as library_router
from .tutor import router as tutor_router
from .voice import router as voice_router

# Create main router that includes all modular routers
router = APIRouter()

# Include sub-routers without prefixes, as they already define their full paths
router.include_router(auth_router)
router.include_router(chat_router)
router.include_router(content_router)
router.include_router(batch_router)
router.include_router(health_router)
router.include_router(library_router)
router.include_router(tutor_router)
router.include_router(voice_router)

# Backwards compatibility alias
v2_router = router

__all__ = [
    "auth_router",
    "batch_router",
    "chat_router",
    "content_router",
    "health_router",
    "router",
    "v2_router",
]
