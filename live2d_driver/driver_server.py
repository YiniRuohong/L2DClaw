from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

import websockets

LOGGER = logging.getLogger(__name__)


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 12393
DEFAULT_SLICE_LENGTH = 20


class Live2DDriverServer:
    """WebSocket bridge for the Live2D frontend.

    Serves static frontend assets via the websocket HTTP handler and
    broadcasts Live2D actions to connected clients.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        self._config = config
        self._running = False
        self._server: Optional[websockets.server.Serve] = None
        self._connections: set[websockets.WebSocketServerProtocol] = set()
        self._history: List[Dict[str, Any]] = []
        self._model_info = self._load_model_info()
        self._frontend_root = Path(__file__).resolve().parent / "frontend"

    async def start(self) -> None:
        if self._running:
            return

        host = self._config.get("server", {}).get("driver_ws_host", DEFAULT_HOST)
        port = int(self._config.get("server", {}).get("driver_ws_port", DEFAULT_PORT))

        self._running = True
        self._server = await websockets.serve(
            self._handle_client,
            host,
            port,
            process_request=self._process_request,
        )
        LOGGER.info("Live2D driver listening on ws://%s:%s/client-ws", host, port)

        while self._running:
            await asyncio.sleep(1)

    async def stop(self) -> None:
        self._running = False
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def send_action(self, text: str, emotion: str, motion: str) -> None:
        payload = self._build_audio_payload(text, emotion, motion)
        await self._broadcast(payload)

    async def _handle_client(self, websocket: websockets.WebSocketServerProtocol) -> None:
        self._connections.add(websocket)
        client_uid = str(uuid4())
        try:
            await self._send_initial_messages(websocket, client_uid)
            async for message in websocket:
                await self._handle_message(websocket, client_uid, message)
        except websockets.ConnectionClosed:
            LOGGER.info("Live2D client disconnected")
        finally:
            self._connections.discard(websocket)

    async def _send_initial_messages(
        self, websocket: websockets.WebSocketServerProtocol, client_uid: str
    ) -> None:
        await websocket.send(
            json.dumps({"type": "full-text", "text": "Connection established"})
        )
        await websocket.send(
            json.dumps(
                {
                    "type": "set-model-and-conf",
                    "model_info": self._model_info,
                    "conf_name": "default",
                    "conf_uid": "local",
                    "client_uid": client_uid,
                }
            )
        )
        await websocket.send(json.dumps({"type": "control", "text": "start-mic"}))

    async def _handle_message(
        self, websocket: websockets.WebSocketServerProtocol, client_uid: str, raw: str
    ) -> None:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            LOGGER.warning("Invalid JSON from client")
            return

        msg_type = data.get("type")
        if msg_type == "fetch-configs":
            await websocket.send(json.dumps({"type": "config-files", "configs": []}))
        elif msg_type == "fetch-backgrounds":
            await websocket.send(
                json.dumps({"type": "background-files", "files": []})
            )
        elif msg_type == "fetch-history-list":
            await websocket.send(
                json.dumps({"type": "history-list", "histories": self._history})
            )
        elif msg_type == "create-new-history":
            history_uid = str(uuid4())
            history_entry = {
                "uid": history_uid,
                "latest_message": None,
                "timestamp": datetime.utcnow().isoformat(),
            }
            self._history.insert(0, history_entry)
            await websocket.send(
                json.dumps({"type": "new-history-created", "history_uid": history_uid})
            )
        elif msg_type == "delete-history":
            history_uid = data.get("history_uid")
            before = len(self._history)
            self._history = [item for item in self._history if item["uid"] != history_uid]
            success = len(self._history) != before
            await websocket.send(
                json.dumps(
                    {
                        "type": "history-deleted",
                        "success": success,
                        "history_uid": history_uid,
                    }
                )
            )
        elif msg_type == "fetch-and-set-history":
            await websocket.send(
                json.dumps({"type": "history-data", "messages": []})
            )
        elif msg_type == "heartbeat":
            await websocket.send(json.dumps({"type": "heartbeat-ack"}))
        elif msg_type == "text-input":
            LOGGER.info("Frontend text input: %s", data.get("text", ""))
        elif msg_type == "interrupt-signal":
            LOGGER.info("Frontend interrupt signal")
        elif msg_type == "audio-play-start":
            LOGGER.info("Frontend audio playback started")

    async def _broadcast(self, payload: Dict[str, Any]) -> None:
        if not self._connections:
            return

        message = json.dumps(payload)
        await asyncio.gather(
            *[
                self._safe_send(connection, message)
                for connection in list(self._connections)
            ]
        )

    async def _safe_send(
        self, websocket: websockets.WebSocketServerProtocol, message: str
    ) -> None:
        try:
            await websocket.send(message)
        except websockets.ConnectionClosed:
            self._connections.discard(websocket)

    def _build_audio_payload(self, text: str, emotion: str, motion: str) -> Dict[str, Any]:
        display_text = {"text": text, "name": "Claw", "avatar": None}
        expressions = self._map_emotion_to_expression(emotion)
        actions = {"expressions": expressions} if expressions else None
        return {
            "type": "audio",
            "audio": None,
            "volumes": [],
            "slice_length": DEFAULT_SLICE_LENGTH,
            "display_text": display_text,
            "actions": actions,
            "forwarded": False,
        }

    def _map_emotion_to_expression(self, emotion: str) -> Optional[List[int]]:
        if not emotion or not self._model_info:
            return None

        emotion_key = emotion.lower()
        mapped = {
            "happy": "joy",
            "sad": "sadness",
            "surprised": "surprise",
            "neutral": "neutral",
            "thinking": "neutral",
            "angry": "anger",
        }.get(emotion_key, emotion_key)

        emo_map = self._model_info.get("emotionMap", {})
        index = emo_map.get(mapped)
        if index is None:
            return None
        return [index]

    def _load_model_info(self) -> Dict[str, Any]:
        model_dict_path = Path(__file__).resolve().parent / "frontend" / "model_dict.json"
        try:
            with model_dict_path.open("r", encoding="utf-8") as handle:
                models = json.load(handle)
        except FileNotFoundError:
            LOGGER.warning("model_dict.json not found at %s", model_dict_path)
            return {}
        except json.JSONDecodeError:
            LOGGER.warning("model_dict.json is invalid JSON")
            return {}

        if not models:
            return {}
        return models[0]

    def _process_request(
        self, path: str, request_headers: Dict[str, str]
    ) -> Optional[Tuple[int, List[Tuple[str, str]], bytes]]:
        if path.startswith("/client-ws"):
            return None

        if "?" in path:
            path = path.split("?", 1)[0]

        if path == "/":
            path = "/index.html"

        if path == "/live2d-models/info":
            payload = self._build_live2d_info_payload()
            return self._http_response(200, json.dumps(payload).encode("utf-8"), "application/json")

        file_path = self._resolve_static_path(path)
        if file_path is None or not file_path.exists() or not file_path.is_file():
            return self._http_response(404, b"Not Found", "text/plain")

        content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        if file_path.suffix == ".js":
            content_type = "application/javascript"
        elif file_path.suffix == ".wasm":
            content_type = "application/wasm"

        return self._http_response(200, file_path.read_bytes(), content_type)

    def _resolve_static_path(self, path: str) -> Optional[Path]:
        if path.startswith("/live2d-models/"):
            base = self._frontend_root / "live2d-models"
            relative = path[len("/live2d-models/") :]
            return self._safe_join(base, relative)

        relative_path = path.lstrip("/")
        return self._safe_join(self._frontend_root, relative_path)

    def _safe_join(self, base: Path, relative: str) -> Optional[Path]:
        candidate = (base / relative).resolve()
        try:
            candidate.relative_to(base.resolve())
        except ValueError:
            return None
        return candidate

    def _build_live2d_info_payload(self) -> Dict[str, Any]:
        models_dir = self._frontend_root / "live2d-models"
        characters: List[Dict[str, Any]] = []

        if models_dir.exists():
            for entry in models_dir.iterdir():
                if not entry.is_dir():
                    continue
                model_path = entry / "runtime" / f"{entry.name}.model3.json"
                if not model_path.exists():
                    continue

                avatar_path = None
                for ext in (".png", ".jpg", ".jpeg"):
                    candidate = entry / f"{entry.name}{ext}"
                    if candidate.exists():
                        avatar_path = f"/live2d-models/{entry.name}/{candidate.name}"
                        break

                characters.append(
                    {
                        "name": entry.name,
                        "avatar": avatar_path,
                        "model_path": f"/live2d-models/{entry.name}/runtime/{entry.name}.model3.json",
                    }
                )

        return {
            "type": "live2d-models/info",
            "count": len(characters),
            "characters": characters,
        }

    def _http_response(
        self, status: int, body: bytes, content_type: str
    ) -> Tuple[int, List[Tuple[str, str]], bytes]:
        headers = [
            ("Content-Type", content_type),
            ("Content-Length", str(len(body))),
            ("Access-Control-Allow-Origin", "*"),
        ]
        return status, headers, body
