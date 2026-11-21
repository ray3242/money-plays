"""Minimal Meko client: MCP (Streamable HTTP, JSON-RPC 2.0) with the standard library only.

Works against Meko Cloud (https://mcp.mekodata.ai/mcp + an mko_tkn_ API key) and against a
local open-source Meko (http://127.0.0.1:7777/mcp + `meko token`).
"""
import base64
import json
import os
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request

DEFAULT_LOCAL_URL = "http://127.0.0.1:7777/mcp"
CLOUD_URL = "https://mcp.mekodata.ai/mcp"


class MekoError(RuntimeError):
    pass


def _local_token():
    exe = shutil.which("meko") or os.path.expanduser("~/.local/bin/meko")
    if not os.path.exists(exe):
        return None
    try:
        out = subprocess.run([exe, "token"], capture_output=True, text=True, timeout=10).stdout
        lines = [l.strip() for l in out.splitlines() if l.strip()]
        return lines[-1] if lines else None
    except Exception:
        return None


class Meko:
    def __init__(self, url=None, api_key=None, datapack_id=None, timeout=120):
        self.api_key = api_key or os.environ.get("MEKO_API_KEY")
        self.url = url or os.environ.get("MEKO_URL") or (CLOUD_URL if self.api_key else DEFAULT_LOCAL_URL)
        if not self.api_key and self.url.startswith(("http://127.0.0.1", "http://localhost")):
            self.api_key = _local_token()
        if not self.api_key:
            raise MekoError(
                "No Meko credentials. Set MEKO_API_KEY (Meko Cloud) or start a local Meko with `meko start`."
            )
        self.datapack_id = datapack_id or os.environ.get("MEKO_DATAPACK_ID")
        self.timeout = timeout
        self._id = 0
        self._lock = threading.Lock()
        self._session = None
        self._tools = None
        self.calls = []  # audit log of every Meko call: (tool, ms, ok)

    # ---- transport -------------------------------------------------------------------------
    def _rpc(self, method, params=None, notify=False):
        with self._lock:
            self._id += 1
            rid = self._id
        body = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            body["params"] = params
        if not notify:
            body["id"] = rid
        headers = {
            "Authorization": "Bearer " + self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "User-Agent": "nightshift/0.1 (meko-mcp-client)",
        }
        if self._session:
            headers["Mcp-Session-Id"] = self._session
        req = urllib.request.Request(self.url, data=json.dumps(body).encode(), headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                sid = resp.headers.get("Mcp-Session-Id")
                if sid:
                    self._session = sid
                raw = resp.read().decode("utf-8", "replace")
                ctype = resp.headers.get("Content-Type", "")
        except urllib.error.HTTPError as e:
            raise MekoError(f"Meko HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}") from None
        except urllib.error.URLError as e:
            raise MekoError(f"Cannot reach Meko at {self.url}: {e.reason}") from None
        if notify or not raw.strip():
            return None
        if "text/event-stream" in ctype:
            payload = None
            for line in raw.splitlines():
                if line.startswith("data:"):
                    try:
                        msg = json.loads(line[5:].strip())
                    except ValueError:
                        continue
                    if msg.get("id") == rid:
                        payload = msg
            if payload is None:
                raise MekoError("No JSON-RPC response in event stream")
        else:
            payload = json.loads(raw)
        if "error" in payload:
            raise MekoError(f"{method}: {payload['error']}")
        return payload.get("result")

    def connect(self):
        """MCP handshake (needed by Meko Cloud; harmless locally) + tool discovery."""
        try:
            self._rpc(
                "initialize",
                {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "nightshift", "version": "0.1.0"},
                },
            )
            self._rpc("notifications/initialized", notify=True)
        except MekoError:
            pass  # stateless servers answer tools/* without a handshake
        self._tools = {t["name"] for t in self._rpc("tools/list")["tools"]}
        return self

    @property
    def tools(self):
        if self._tools is None:
            self.connect()
        return self._tools

    def has(self, tool):
        return tool in self.tools

    def call(self, tool, **args):
        args = {k: v for k, v in args.items() if v is not None}
        if self.datapack_id and "datapack_id" not in args and tool != "datapack_create":
            args["datapack_id"] = self.datapack_id
        t0 = time.time()
        ok = False
        try:
            res = self._rpc("tools/call", {"name": tool, "arguments": args})
            data = None
            for part in (res or {}).get("content", []):
                if part.get("type") == "text":
                    try:
                        data = json.loads(part["text"])
                    except ValueError:
                        data = {"text": part["text"]}
                    break
            if (res or {}).get("isError") and not (isinstance(data, dict) and data.get("results")):
                detail = data.get("error") or data.get("text") if isinstance(data, dict) else data
                raise MekoError(f"{tool}: {detail}")
            if isinstance(data, dict) and data.get("error") and not data.get("results"):
                raise MekoError(f"{tool}: {data.get('error')}: {data.get('detail', '')}")
            ok = True
            return data
        finally:
            self.calls.append({"tool": tool, "ms": int((time.time() - t0) * 1000), "ok": ok})

    # ---- datapacks -------------------------------------------------------------------------
    def ensure_datapack(self, name):
        """Find or create the datapack that is this team's shared brain."""
        boot = self._rpc("tools/call", {"name": "conversation_create", "arguments": {"agent_id": "nightshift:setup", "title": "nightshift setup"}})
        boot_id = json.loads(boot["content"][0]["text"])["id"]
        found = self._rpc("tools/call", {"name": "datapack_list", "arguments": {"conversation_id": boot_id, "query": name}})
        packs = json.loads(found["content"][0]["text"])
        packs = packs.get("datapacks", packs.get("data", packs)) if isinstance(packs, dict) else packs
        for p in packs or []:
            if (p.get("datapack_name") or p.get("name")) == name:
                self.datapack_id = p.get("datapack_id") or p.get("id")
                return self.datapack_id
        made = self.call("datapack_create", conversation_id=boot_id, name=name)
        self.datapack_id = made["datapack_id"]
        return self.datapack_id

    def delete_datapack(self):
        if self.datapack_id:
            self._rpc("tools/call", {"name": "datapack_delete", "arguments": {"datapack_id": self.datapack_id}})
            self.datapack_id = None

    # ---- conversations = decision traces --------------------------------------------------
    def conversation(self, agent_id, title, metadata=None, run_id=None):
        return self.call("conversation_create", agent_id=agent_id, title=title, metadata=metadata, run_id=run_id)["id"]

    def trace(self, conversation_id, agent_id, input, output, reasoning=None, plan=None, metadata=None):
        return self.call(
            "conversation_add_message",
            conversation_id=conversation_id,
            agent_id=agent_id,
            input=input,
            output=output,
            reasoning=reasoning,
            plan=plan,
            metadata=metadata,
        )

    def get_conversation(self, conversation_id, agent_id):
        return self.call("conversation_get", conversation_id=conversation_id, agent_id=agent_id, include_messages=True)

    # ---- recall -----------------------------------------------------------------------------
    def context_search(self, conversation_id, agent_id, query, limit=5):
        res = self.call("context_search", conversation_id=conversation_id, agent_id=agent_id, query=query, limit=limit)
        r = (res or {}).get("results") or {}
        return {
            "memory": r.get("memory") or [],
            "knowledge_base": r.get("knowledge_base") or [],
            "conversation": (r.get("conversation") or {}).get("hits") or [],
            "match_quality": (res or {}).get("match_quality"),
            "agent_hint": (res or {}).get("agent_hint"),
            "raw": res,
        }

    def memory_search(self, conversation_id, agent_id, query, limit=5):
        return (self.call("memory_search", conversation_id=conversation_id, agent_id=agent_id, query=query, limit=limit) or {}).get("results") or []

    def kb_search(self, conversation_id, agent_id, query, limit=3):
        return (self.call("knowledgebase_search", conversation_id=conversation_id, agent_id=agent_id, query=query, limit=limit) or {}).get("results") or []

    # ---- writes -----------------------------------------------------------------------------
    def remember(self, conversation_id, agent_id, text, metadata=None):
        res = self.call("memory_add", conversation_id=conversation_id, agent_id=agent_id, text=text, metadata=metadata)
        items = (res or {}).get("results") or []
        return items[0]["id"] if items else None

    def revise(self, conversation_id, agent_id, memory_id, text):
        return self.call("memory_update", conversation_id=conversation_id, agent_id=agent_id, memory_id=memory_id, text=text)

    def forget(self, conversation_id, agent_id, memory_id):
        return self.call("memory_delete_by_id", conversation_id=conversation_id, agent_id=agent_id, memory_id=memory_id)

    def promote(self, conversation_id, agent_id, memory_ids):
        return self.call("memory_promote", conversation_id=conversation_id, agent_id=agent_id, memory_ids=memory_ids)

    def all_memories(self, conversation_id, agent_id=None, promoted=None):
        res = self.call("memory_get_all", conversation_id=conversation_id, agent_id=agent_id, promoted=promoted)
        return (res or {}).get("memories") or []

    def put_artifact(self, conversation_id, agent_id, filename, content, content_type="text/markdown"):
        if isinstance(content, str):
            content = content.encode()
        return self.call(
            "artifact_put",
            conversation_id=conversation_id,
            agent_id=agent_id,
            filename=filename,
            content_type=content_type,
            content_base64=base64.b64encode(content).decode(),
        )

    def get_artifact(self, conversation_id, agent_id, content_hash):
        res = self.call("artifact_get", conversation_id=conversation_id, agent_id=agent_id, content_hash=content_hash)
        b64 = (res or {}).get("content_base64")
        return base64.b64decode(b64).decode("utf-8", "replace") if b64 else None

    def upload_knowledge(self, conversation_id, path, wait=60):
        """Index a file into the shared knowledge base. Local Meko reads the path directly;
        Meko Cloud hands back a presigned URL that we POST the bytes to."""
        path = os.path.abspath(path)
        if self.has("knowledgebase_upload_file"):
            res = self.call("knowledgebase_upload_file", conversation_id=conversation_id, path=path)
        else:
            import hashlib

            data = open(path, "rb").read()
            res = self.call(
                "knowledgebase_upload_document",
                conversation_id=conversation_id,
                filename=os.path.basename(path),
                size=len(data),
                content_hash=hashlib.sha256(data).hexdigest(),
                content_head_base64=base64.b64encode(data[:3072]).decode(),
            )
            url = res.get("upload_url") or res.get("url")
            if url and not res.get("already_uploaded"):
                _presigned_post(url, res.get("fields") or {}, os.path.basename(path), data)
        key = (res or {}).get("document_key") or (res or {}).get("key")
        deadline = time.time() + wait
        while key and not (res or {}).get("already_uploaded") and time.time() < deadline:
            st = self.call("knowledgebase_document_status", conversation_id=conversation_id, document_key=key)
            if st.get("state") in ("completed", "failed", "abandoned", "oversized"):
                return st
            time.sleep(1)
        return res

    def track_tokens(self, conversation_id, name, input_tokens, output_tokens, model="policy"):
        """Meko Cloud exposes track_token_usage; local builds may not. Best effort."""
        if not self.has("track_token_usage"):
            return None
        try:
            return self.call(
                "track_token_usage",
                conversation_id=conversation_id,
                name=name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                model=model,
            )
        except MekoError:
            return None

    def selflearning_status(self, conversation_id):
        if not self.has("selflearning_status"):
            return None
        try:
            return self.call("selflearning_status", conversation_id=conversation_id)
        except MekoError:
            return None


def _presigned_post(url, fields, filename, data):
    boundary = "----nightshift" + base64.b16encode(os.urandom(8)).decode()
    parts = []
    for k, v in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n".encode()
        + data
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    req = urllib.request.Request(url, data=b"".join(parts), headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    urllib.request.urlopen(req, timeout=120).read()
