"""
FastAPI Backend Entry Point
AI Supported Sales Application
"""
import json
import math
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api import data_routes, ranking_routes, customer_routes, export_routes, internal_knowledge_routes


app = FastAPI(
    title="AI Sales App API",
    description="Backend API for AI Supported Sales Application",
    version="1.0.0",
)

# Allow React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(data_routes.router, prefix="/api/data", tags=["Data"])
app.include_router(ranking_routes.router, prefix="/api/ranking", tags=["Ranking"])
app.include_router(customer_routes.router, prefix="/api/customer", tags=["Customer"])
app.include_router(export_routes.router, prefix="/api/export", tags=["Export"])
app.include_router(internal_knowledge_routes.router, prefix="/api/internal-knowledge", tags=["Internal Knowledge"])


@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "AI Sales App Backend"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
