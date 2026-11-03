from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.endpoints import complaints, citizens
from app.db.base import Base
from app.db.session import engine

# إنشاء الجداول تلقائياً في SQLite عند الإقلاع
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Government Complaints Platform", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(complaints.router, prefix="/api/v1/complaints", tags=["Complaints"])
app.include_router(citizens.router, prefix="/api/v1/citizens", tags=["Citizens"])

@app.get("/")
def root():
    return {"message": "Government Complaints API is running successfully!"}