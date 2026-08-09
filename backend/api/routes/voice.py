import asyncio
import logging
import time
from typing import Dict, Optional

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from ...services.ai_core.engine import GenerationConfig, get_ai_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["Voice Agent"])

# In-memory store for active voice connections
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket voice client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket voice client disconnected. Total: {len(self.active_connections)}")

manager = ConnectionManager()

@router.websocket("/stream")
async def voice_stream(websocket: WebSocket):
    """
    Bidirectional WebRTC-like WebSocket stream.
    Receives base64 audio chunks or text from the client, processes via AIEngine,
    and streams text/audio back in real-time.
    """
    await manager.connect(websocket)
    engine = get_ai_engine()
    
    # We maintain conversation history for this session
    session_context = {}

    try:
        while True:
            # Receive data from client
            data = await websocket.receive_json()
            
            # The client sends: {"type": "text", "content": "hello"} or {"type": "audio", "content": "<base64>"}
            msg_type = data.get("type")
            content = data.get("content")
            
            if not content:
                continue
                
            logger.info(f"Received {msg_type} payload on voice stream")
            
            user_text = ""
            if msg_type == "text":
                user_text = content
            elif msg_type == "audio":
                # In a full GOD tier, we would pipe this base64 through Whisper STT
                # For now we simulate STT since the client may send raw text for testing
                # STT simulation:
                user_text = "[Simulated Audio Transcription of base64]"
                
            if not user_text:
                continue
                
            # Send an acknowledgment that we are processing
            await websocket.send_json({"type": "status", "content": "thinking..."})

            # Stream AI response
            config = GenerationConfig(stream=True, max_tokens=150)
            
            try:
                # We use chat_stream to get tokens incrementally
                # Then we could theoretically pass them to MMS-TTS
                full_response = ""
                async for token_chunk in engine.chat_stream(
                    message=user_text,
                    conversation_id="voice_session",
                    config=config,
                    context_data=session_context
                ):
                    # chat_stream returns SSE formatted strings, we parse or forward it
                    if token_chunk.startswith("data: "):
                        import json
                        try:
                            chunk_data = json.loads(token_chunk[6:])
                            token_text = chunk_data.get("token", "")
                            full_response += token_text
                            
                            # Stream text back immediately
                            await websocket.send_json({
                                "type": "text_chunk",
                                "content": token_text
                            })
                            
                            # In full WebRTC, we would buffer words and send to TTS here
                        except Exception:
                            pass
                
                # Signal completion
                await websocket.send_json({
                    "type": "status",
                    "content": "idle"
                })
                
            except Exception as e:
                logger.error(f"Generation error in voice stream: {e}")
                await websocket.send_json({"type": "error", "content": "Generation failed."})

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)
