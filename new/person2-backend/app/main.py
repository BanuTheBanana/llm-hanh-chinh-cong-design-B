from fastapi import FastAPI

app = FastAPI(title="LLM Hanh Chinh Cong - New Backend")

@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
