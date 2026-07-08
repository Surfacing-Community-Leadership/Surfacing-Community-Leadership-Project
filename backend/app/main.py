from fastapi import FastAPI

app = FastAPI(title="Ours API")


@app.get("/health")
async def health_check():
    return {"status": "ok"}
