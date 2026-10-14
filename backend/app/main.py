from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.config import settings
from app.database import engine, Base, SessionLocal
from app.seed import seed_database

# Routers
from app.api.auth import router as auth_router
from app.api.medications import router as med_router
from app.api.prescriptions import router as rx_router
from app.api.cartridges import router as cart_router
from app.api.schedules import router as sched_router
from app.api.doses import router as dose_router
from app.api.caregiver import router as cg_router
from app.api.device import router as dev_router
from app.api.simulator import router as sim_router

from app.database import engine, Base, SessionLocal, run_schema_migrations

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables
    Base.metadata.create_all(bind=engine)
    run_schema_migrations(engine)
    # Seed default demonstration data
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API Routers
app.include_router(auth_router, prefix=settings.API_PREFIX)
app.include_router(med_router, prefix=settings.API_PREFIX)
app.include_router(rx_router, prefix=settings.API_PREFIX)
app.include_router(cart_router, prefix=settings.API_PREFIX)
app.include_router(sched_router, prefix=settings.API_PREFIX)
app.include_router(dose_router, prefix=settings.API_PREFIX)
app.include_router(cg_router, prefix=settings.API_PREFIX)
app.include_router(dev_router, prefix=settings.API_PREFIX)
app.include_router(sim_router, prefix=settings.API_PREFIX)

@app.get("/")
def root():
    return {
        "system": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs": "/docs",
        "api_prefix": settings.API_PREFIX,
        "status": "online"
    }

@app.get("/health")
def health():
    return {"status": "healthy"}
