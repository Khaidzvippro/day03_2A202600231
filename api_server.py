"""
FastAPI Backend for ArXivInsight ReAct Agent.
Serves a REST API for the React Frontend to communicate with.
"""

import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from src.core.openai_provider import OpenAIProvider
from src.core.gemini_provider import GeminiProvider
from src.agent.agent import ReActAgent
from src.tools import ALL_TOOLS

# Initialize FastAPI App
app = FastAPI(title="ArXivInsight Agent API")

# Allow CORS for React Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load configuration and initialize Agent
load_dotenv()

provider_name = os.getenv("DEFAULT_PROVIDER", "openai").lower()
model_name = os.getenv("DEFAULT_MODEL", "gpt-4o")

if provider_name == "google":
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set in .env")
    provider = GeminiProvider(model_name=model_name, api_key=api_key)
else:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set in .env")
    provider = OpenAIProvider(model_name=model_name, api_key=api_key)

max_steps = int(os.getenv("AGENT_MAX_STEPS", "20"))
agent = ReActAgent(llm=provider, tools=ALL_TOOLS, max_steps=max_steps)

class ChatRequest(BaseModel):
    query: str

class ChatResponse(BaseModel):
    answer: str

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    try:
        if not request.query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty.")
        
        answer = agent.run(request.query)
        return ChatResponse(answer=answer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "agent": "ArXivInsight ReAct v1.0", "tools_count": len(ALL_TOOLS)}

if __name__ == "__main__":
    import uvicorn
    # Run server manually using: python api_server.py
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)
