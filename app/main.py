from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.auth_routes import router as auth_router
from app.routes.evaluation_routes import router as evaluation_router
from app.routes.upload_routes import router as upload_router
from app.routes.result_routes import router as result_router
from app.routes.ocr_accuracy_routes import router as ocr_accuracy_router
from app.routes.profile_routes import router as profile_router
from app.routes.maintenance_routes import router as maintenance_router

app = FastAPI(title="AutoGrade Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://autograde.toshankanwar.in"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(evaluation_router)
app.include_router(upload_router)
app.include_router(result_router)
app.include_router(ocr_accuracy_router)
app.include_router(profile_router)
app.include_router(maintenance_router)
@app.get("/health")
async def health():
    return {"status": "ok bhai sahi hai. Toshan Bhai ka Server 😀😁😄"}