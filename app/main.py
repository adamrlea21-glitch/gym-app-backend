from fastapi import FastAPI
from app.routers.auth import router as auth_router
from app.routers.me import router as me_router
from app.routers.nutrition import router as nutrition_router
from app.routers.workouts import router as workouts_router
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(title="Gym App API v2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://health-3n1484ovs-adam-leas-projects.vercel.app",
        "https://health-app-nine-pi.vercel.app",  # keep if you use this alias
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router)
app.include_router(me_router)
app.include_router(nutrition_router)
app.include_router(workouts_router)



@app.get("/health")
def health():
    return {"ok": True}

