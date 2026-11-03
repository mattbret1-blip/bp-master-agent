from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel

from agent.audio import build_audio_adapter, guess_mime_type
from agent.config import Settings
from agent.core import BrazilianPortugueseAgent
from agent.providers import build_adapter
from agent.research import DisabledResearchAdapter, LocalKnowledgeAdapter

load_dotenv()


class ChatRequest(BaseModel):
    message: str


class ProviderRequest(BaseModel):
    provider: str


class SynthesizeRequest(BaseModel):
    text: str
    voice: str | None = None


def create_app() -> FastAPI:
    settings = Settings.from_env()
    app = FastAPI(title="Brazilian Portuguese Master Agent", version="3.1.0")

    if settings.cors_origins.strip():
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[x.strip() for x in settings.cors_origins.split(",") if x.strip()],
            allow_credentials=True,
            allow_methods=["GET", "POST"],
            allow_headers=["*"],
        )

    agent_holder: dict[str, BrazilianPortugueseAgent] = {}
    audio_holder: dict[str, object] = {}

    def get_audio_adapter():
        """Voice adapter, built lazily so voice config never blocks the app.

        Raises RuntimeError when voice is unconfigured; endpoints map that
        to 503 instead of crashing.
        """
        if "audio" not in audio_holder:
            missing = settings.validate_voice_credentials()
            if missing:
                raise RuntimeError(
                    f"Voice is not configured: missing {', '.join(missing)}. "
                    "Set them in .env before using voice."
                )
            audio_holder["audio"] = build_audio_adapter(settings)
        return audio_holder["audio"]

    def get_agent() -> BrazilianPortugueseAgent:
        if "agent" not in agent_holder:
            active = settings.ai_provider
            missing = settings.validate_provider_credentials(active)
            if missing:
                raise RuntimeError(
                    f"Missing configuration for {active}: {', '.join(missing)}"
                )
            research = (
                LocalKnowledgeAdapter(settings.local_knowledge_path)
                if settings.research_enabled
                else DisabledResearchAdapter()
            )
            agent_holder["agent"] = BrazilianPortugueseAgent(
                build_adapter(active, settings),
                active,
                research_adapter=research,
            )
        return agent_holder["agent"]

    app.state.get_agent = get_agent
    app.state.settings = settings

    @app.get("/health")
    def health():
        return {"ok": True, "version": app.version}

    @app.get("/ready")
    def ready():
        try:
            agent = get_agent()
            return {
                "ok": True,
                "provider": agent.provider_name,
                "state_path": str(agent.db.path),
            }
        except Exception as exc:
            raise HTTPException(503, detail=str(exc)) from exc

    @app.get("/", response_class=HTMLResponse)
    def home():
        return Path(__file__).with_name("index.html").read_text(encoding="utf-8")

    @app.get("/api/status")
    def status():
        return get_agent().status()

    @app.get("/api/next")
    def next_action():
        return get_agent().next_action()

    @app.get("/api/review")
    def review():
        return {"action": "review", "items": get_agent().next_action().get("items", [])}

    @app.post("/api/chat")
    def chat(req: ChatRequest):
        message = req.message.strip()
        if not message:
            raise HTTPException(400, "message is required")
        try:
            return {"response": get_agent().respond(message)}
        except RuntimeError as exc:
            raise HTTPException(503, detail=str(exc)) from exc

    @app.post("/api/provider")
    def provider(req: ProviderRequest):
        if req.provider not in {"openai", "anthropic", "gemini"}:
            raise HTTPException(400, "unsupported provider")
        missing = settings.validate_provider_credentials(req.provider)
        if missing:
            raise HTTPException(
                400,
                detail=f"Missing configuration for {req.provider}: {', '.join(missing)}",
            )
        try:
            new_adapter = build_adapter(req.provider, settings)
        except Exception as exc:
            raise HTTPException(400, detail=str(exc)) from exc
        agent = get_agent()
        agent.set_provider(req.provider, new_adapter)
        return {"ok": True, "provider": req.provider}

    @app.post("/api/reset")
    def reset():
        get_agent().reset()
        return {"ok": True}

    @app.get("/api/export")
    def export():
        return get_agent().export()

    @app.post("/voice/transcribe")
    async def voice_transcribe(file: UploadFile = File(...)):
        data = await file.read()
        if not data:
            raise HTTPException(400, "uploaded audio file is empty")
        try:
            adapter = get_audio_adapter()
        except RuntimeError as exc:
            raise HTTPException(503, detail=str(exc)) from exc
        try:
            transcript = adapter.transcribe(data, file.content_type or guess_mime_type(file.filename or ""))
        except Exception as exc:
            raise HTTPException(503, detail=f"Transcription failed: {exc}") from exc
        return {
            "text": transcript.text,
            "language": transcript.language,
            "confidence": transcript.confidence,
            "duration_ms": transcript.duration_ms,
        }

    @app.post("/voice/synthesize")
    def voice_synthesize(req: SynthesizeRequest):
        text = req.text.strip()
        if not text:
            raise HTTPException(400, "text is required")
        try:
            adapter = get_audio_adapter()
        except RuntimeError as exc:
            raise HTTPException(503, detail=str(exc)) from exc
        try:
            audio = adapter.synthesize(text, req.voice or "default")
        except Exception as exc:
            raise HTTPException(503, detail=f"Synthesis failed: {exc}") from exc
        return Response(content=audio, media_type="audio/wav")

    return app


app = create_app()
