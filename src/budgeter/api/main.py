from fastapi import FastAPI

from budgeter.api.routers import health

app = FastAPI(title="Budgeter API")
app.include_router(health.router)
