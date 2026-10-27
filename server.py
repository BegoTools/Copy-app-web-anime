#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Anime Rift - PS5 Edition (13.60 Jailbreak)
Backend API & Stream Proxy Server
Reversed from com.riftapps.animerift v3.13.5 (libapp.so Dart 3.10.7 AOT)
"""

import os
import sys
import time
import json
import uuid
import hmac
import base64
import socket
import hashlib
import datetime
import threading
import mimetypes
import urllib.parse
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(ROOT_DIR, "web")
DATA_DIR = os.path.join(ROOT_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

SESSION_FILE = os.path.join(DATA_DIR, "device_session.json")
USER_DATA_FILE = os.path.join(DATA_DIR, "user_data.json")

BASE_API_URL = "https://gateway.anime-rift.com/api/v4"
REGISTER_SECRET = "6a9f3e19b7d2c84c0fa9e5183c4bda7c2e8a41e4f37dffb8b42a9a9d6ef02173564a8d6ada6z8d468"
APP_VERSION = "3.13.5"


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def sign_jwt(scope: str, secret: str) -> str:
    """
    Signs the exact HS256 JWT token expected in the `integrity: Bearer <jwt>` header
    (reversed from libapp.so @ 0x55775c .. 0x55797c).
    """
    now = int(time.time()) - 2
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"scope": scope, "exp": now + 10, "iat": now}
    h_b64 = b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    p_b64 = b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{h_b64}.{p_b64}".encode("ascii")
    sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{h_b64}.{p_b64}.{b64url(sig)}"


class AnimeRiftClient:
    def __init__(self):
        self.lock = threading.Lock()
        self.device_id = str(uuid.uuid4())
        self.device_os_id = "UP1A.231005.007"
        self.firebase_id = uuid.uuid4().hex[:22]
        self.session_key = None
        self.public_id = None
        self.language = "ar"
        self._load_session()

    def _load_session(self):
        if os.path.exists(SESSION_FILE):
            try:
                with open(SESSION_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.device_id = data.get("device_id", self.device_id)
                self.device_os_id = data.get("device_os_id", self.device_os_id)
                self.firebase_id = data.get("firebase_id", self.firebase_id)
                self.session_key = data.get("session_key")
                self.public_id = data.get("public_id")
                self.language = data.get("language", "ar")
            except Exception as e:
                print(f"[Session] Failed to load session file: {e}")

    def _save_session(self):
        try:
            with open(SESSION_FILE, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "device_id": self.device_id,
                        "device_os_id": self.device_os_id,
                        "firebase_id": self.firebase_id,
                        "session_key": self.session_key,
                        "public_id": self.public_id,
                        "language": self.language,
                        "updated_at": datetime.datetime.now().isoformat(),
                    },
                    f,
                    indent=2,
                    ensure_ascii=False,
                )
        except Exception as e:
            print(f"[Session] Failed to save session file: {e}")

    def make_headers(self, scope: str, secret: str, lang: str = None) -> dict:
        """
        Builds the exact HTTP headers required by gateway.anime-rift.com
        (reversed from libapp.so @ 0xa830b4 .. 0xa83404).
        """
        jwt_token = sign_jwt(scope, secret)
        pub_str = "null" if self.public_id is None else self.public_id
        return {
            "Content-Type": "application/json; charset=UTF-8",
            "User-Agent": "Dart/3.10 (dart:io)",
            "x-platform": "Mobile",
            "x-os": "android",
            "x-device-timezone": datetime.datetime.now().isoformat(),
            "x-device-language": lang or self.language or "ar",
            "x-device-release-version": APP_VERSION,
            "x-installation-source": "IS_INSTALLED_FROM_PLAY_STORE",
            "Authorization": f"Bearer {pub_str}",
            "integrity": f"Bearer {jwt_token}",
            "x-firebase-app-check": "null",
            "x-device-id": self.device_id,
            "x-device-os-id": self.device_os_id,
            "x-firebase-id": self.firebase_id,
        }

    def register_device(self, force_new: bool = False) -> str:
        with self.lock:
            if self.session_key and not force_new:
                return self.session_key
            if force_new:
                self.device_id = str(uuid.uuid4())
                self.firebase_id = uuid.uuid4().hex[:22]

            reg_body = {
                "deviceId": self.device_id,
                "current_app_version": APP_VERSION,
                "device_os": "android",
                "device_environment": "production",
                "device_info": json.dumps(
                    {
                        "model": "PlayStation 5 (13.60)",
                        "brand": "google",
                        "manufacturer": "Google",
                        "device": "husky",
                        "hardware": "husky",
                        "product": "husky",
                        "androidVersion": "14",
                        "sdkInt": 34,
                        "securityPatch": "2024-05-05",
                        "isPhysicalDevice": True,
                        "supportedAbis": ["arm64-v8a", "armeabi-v7a", "armeabi"],
                        "tags": "release-keys",
                        "type": "user",
                        "buildId": self.device_os_id,
                        "host": "abfarm-release-2004-0105",
                        "fingerprint": f"google/husky/husky:14/{self.device_os_id}/10754064:user/release-keys",
                    }
                ),
                "install_source": "IS_INSTALLED_FROM_PLAY_STORE",
                "deviceOsId": self.device_os_id,
                "firebaseInstallationId": self.firebase_id,
                "apn_token": None,
                "install_mode": 2,
            }

            url = f"{BASE_API_URL}/auth/register/device"
            data = json.dumps(reg_body).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers=self.make_headers("USER.AUTH.DEVICE.REGISTER", REGISTER_SECRET),
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                self.session_key = res["sessionKey"]
                self._save_session()
                print(f"[Auth] Registered PS5 device session: {self.device_id}")
                return self.session_key

    def call_api(
        self,
        method: str,
        path: str,
        scope: str,
        params: dict = None,
        body: dict = None,
        lang: str = None,
        retry: bool = True,
    ):
        if not self.session_key:
            self.register_device()

        url = f"{BASE_API_URL}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = self.make_headers(scope, self.session_key, lang=lang)
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            print(f"[API Error {e.code}] {method} {path}: {err_body[:300]}")
            if e.code in (401, 403) and retry:
                print("[Auth] Session expired or rejected, re-registering device...")
                self.register_device(force_new=True)
                return self.call_api(
                    method, path, scope, params=params, body=body, lang=lang, retry=False
                )
            raise RuntimeError(f"HTTP {e.code}: {err_body}")


client = AnimeRiftClient()


def load_user_data() -> dict:
    default_data = {
        "favorites": [],
        "watch_history": [],
        "progress": {},
        "settings": {
            "language": "ar",
            "auto_skip_intro": True,
            "auto_skip_outro": False,
            "preferred_quality": "1080P",
            "preferred_server": "CR2",
        },
    }
    if os.path.exists(USER_DATA_FILE):
        try:
            with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                default_data.update(saved)
        except Exception as e:
            print(f"[UserData] Error loading user_data.json: {e}")
    return default_data


def save_user_data(data: dict):
    with open(USER_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


class PS5RequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def log_message(self, format, *args):
        sys.stdout.write(f"[Server] {self.address_string()} - {format % args}\n")

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Range, Authorization")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def _send_json(self, data, status=200):
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw) if raw else {}

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)
        lang = qs.get("lang", [client.language])[0]

        try:
            if path == "/api/home":
                data = client.call_api(
                    "GET",
                    "/library/home_content",
                    "ANIME.LIBRARY.HOME_CONTENT",
                    params={"with_genres": "true"},
                    lang=lang,
                )
                return self._send_json(data)

            elif path == "/api/schedule":
                data = client.call_api(
                    "GET",
                    "/library/schedule",
                    "ANIME.LIBRARY.SCHEDULE",
                    lang=lang,
                )
                return self._send_json(data)

            elif path.startswith("/api/details/"):
                anime_id = path.split("/api/details/", 1)[1].strip("/")
                data = client.call_api(
                    "GET",
                    f"/library/details/{anime_id}",
                    "ANIME.LIBRARY.DETAILS",
                    lang=lang,
                )
                return self._send_json(data)

            elif path.startswith("/api/episodes/"):
                anime_id = path.split("/api/episodes/", 1)[1].strip("/")
                sort_dir = qs.get("sort", ["-1"])[0]
                data = client.call_api(
                    "GET",
                    f"/library/episodes/{anime_id}",
                    "ANIME.LIBRARY.EPISODES.ALL",
                    params={
                        "sort_by_latest": sort_dir,
                        "with_arcs": "true",
                        "with_favorites": "true",
                    },
                    lang=lang,
                )
                return self._send_json(data)

            elif path == "/api/userdata":
                return self._send_json(load_user_data())

            elif path == "/api/stream":
                return self._handle_stream_proxy(qs)

            elif path == "/api/status":
                return self._send_json(
                    {
                        "ok": True,
                        "version": APP_VERSION,
                        "platform": "PS5 13.60 Jailbreak Edition",
                        "device_id": client.device_id,
                        "session_active": bool(client.session_key),
                    }
                )

        except Exception as e:
            return self._send_json({"error": str(e)}, status=500)

        return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)
        lang = qs.get("lang", [client.language])[0]

        try:
            body = self._read_json_body()

            if path == "/api/sources":
                anime_id = body.get("animeId")
                episode_id = body.get("episodeId")
                episode_number = int(body.get("episode_number", 1))
                data = client.call_api(
                    "POST",
                    "/library/episode/sources",
                    "ANIME.LIBRARY.EPISODES.SOURCES.ALL",
                    body={
                        "animeId": anime_id,
                        "episodeId": episode_id,
                        "episode_number": episode_number,
                    },
                    lang=lang,
                )
                return self._send_json(data)

            elif path == "/api/play":
                source_id = body.get("sourceId") or body.get("id")
                episode_id = body.get("episodeId")
                quality = body.get("quality") or "720P"

                # Step 1: Request sessionId from /library/episode/source/can_play
                can_play = client.call_api(
                    "POST",
                    "/library/episode/source/can_play",
                    "ANIME.LIBRARY.EPISODES.SOURCES.CHECK_AVAILABILITY",
                    body={
                        "episodeId": episode_id,
                        "hostId": source_id,
                        "is_download": False,
                        "event_name": "play_episode_unlocked",
                    },
                    lang=lang,
                )
                session_id = can_play.get("sessionId")

                # Step 2: Request direct stream URL from /library/episode/source/direct_link
                dl = client.call_api(
                    "POST",
                    "/library/episode/source/direct_link",
                    "ANIME.LIBRARY.EPISODES.SOURCES.DIRECT_LINK",
                    body={
                        "id": source_id,
                        "quality": quality,
                        "with_internal_player": "1",
                        "sessionId": session_id,
                    },
                    lang=lang,
                )

                # Step 3: Handle Streamtape ticket_response if returned
                if dl.get("ticket_response") and dl.get("fileId") and dl.get("ticket"):
                    wait_sec = min(int(dl.get("wait_time", 2)), 5)
                    time.sleep(wait_sec)
                    st_url = f"https://api.streamtape.com/file/dl?file={urllib.parse.quote(dl['fileId'])}&ticket={urllib.parse.quote(dl['ticket'])}"
                    st_req = urllib.request.Request(
                        st_url, headers={"User-Agent": "Mozilla/5.0"}
                    )
                    with urllib.request.urlopen(st_req, timeout=15) as st_resp:
                        st_data = json.loads(st_resp.read().decode("utf-8"))
                        if st_data.get("result") and st_data["result"].get("url"):
                            dl["videoUrl"] = st_data["result"]["url"]
                            dl["url_response"] = True
                            dl["is_hls"] = ".m3u8" in dl["videoUrl"]

                video_url = dl.get("videoUrl") or dl.get("url")
                http_headers = dl.get("http_headers") or {}
                if video_url:
                    hdr_json = base64.urlsafe_b64encode(
                        json.dumps(http_headers).encode("utf-8")
                    ).decode("ascii")
                    dl["proxyUrl"] = (
                        f"/api/stream?url={urllib.parse.quote(video_url, safe='')}&h={hdr_json}"
                    )
                dl["can_play_info"] = can_play
                return self._send_json(dl)

            elif path == "/api/search":
                search_body = {
                    "page": int(body.get("page", 1)),
                    "sort_by": body.get("sort_by", "latest_episode_released"),
                    "sort_direction": int(body.get("sort_direction", -1)),
                    "text_direction": body.get("text_direction", "ltr"),
                }
                if body.get("query"):
                    search_body["query"] = body["query"]
                for k in (
                    "multi_genres",
                    "multi_release_status",
                    "multi_content_types",
                    "multi_age_rating",
                    "multi_release_year",
                    "multi_seasons",
                    "country_origin",
                    "multi_tags",
                ):
                    if body.get(k):
                        search_body[k] = body[k]

                data = client.call_api(
                    "POST",
                    "/library/search",
                    "ANIME.LIBRARY.SEARCH",
                    body=search_body,
                    lang=lang,
                )
                return self._send_json(data)

            elif path == "/api/userdata":
                current = load_user_data()
                current.update(body)
                if "settings" in body and isinstance(body["settings"], dict):
                    if body["settings"].get("language"):
                        client.language = body["settings"]["language"]
                        client._save_session()
                save_user_data(current)
                return self._send_json({"ok": True, "data": current})

        except Exception as e:
            return self._send_json({"error": str(e)}, status=500)

        self._send_json({"error": "Not found"}, status=404)

    def _handle_stream_proxy(self, qs: dict):
        """
        Proxies .m3u8 HLS playlists, .ts/.m4s segments, .mp4 streams (with HTTP Range support),
        and .vtt subtitles so PS5 WebKit plays every stream with zero CORS issues.
        """
        target_url = qs.get("url", [None])[0]
        if not target_url:
            return self._send_json({"error": "Missing url parameter"}, status=400)

        h_b64 = qs.get("h", [""])[0]
        extra_headers = {}
        if h_b64:
            try:
                extra_headers = json.loads(
                    base64.urlsafe_b64decode(h_b64.encode("ascii")).decode("utf-8")
                )
            except Exception:
                pass

        req_headers = {
            "User-Agent": extra_headers.get("User-Agent", "Dart/3.10 (dart:io)"),
            "Accept": "*/*",
        }
        for k, v in extra_headers.items():
            if k and v:
                req_headers[str(k)] = str(v)

        client_range = self.headers.get("Range")
        if client_range:
            req_headers["Range"] = client_range

        req = urllib.request.Request(target_url, headers=req_headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=30) as upstream:
                content_type = upstream.headers.get("Content-Type", "")
                is_m3u8 = (
                    ".m3u8" in target_url.lower()
                    or "mpegurl" in content_type.lower()
                )

                if is_m3u8:
                    raw_text = upstream.read().decode("utf-8", errors="replace")
                    rewritten_lines = []
                    for line in raw_text.splitlines():
                        stripped = line.strip()
                        if not stripped:
                            rewritten_lines.append(line)
                        elif stripped.startswith("#"):
                            # Rewrite URI="..." inside #EXT-X-KEY or #EXT-X-MAP or #EXT-X-MEDIA
                            if 'URI="' in stripped:
                                def repl_uri(match):
                                    u = match.group(1)
                                    abs_u = urllib.parse.urljoin(target_url, u)
                                    prox = f"/api/stream?url={urllib.parse.quote(abs_u, safe='')}&h={h_b64}"
                                    return f'URI="{prox}"'
                                import re
                                line = re.sub(r'URI="([^"]+)"', repl_uri, line)
                            rewritten_lines.append(line)
                        else:
                            abs_url = urllib.parse.urljoin(target_url, stripped)
                            prox_url = f"/api/stream?url={urllib.parse.quote(abs_url, safe='')}&h={h_b64}"
                            rewritten_lines.append(prox_url)

                    out_bytes = "\n".join(rewritten_lines).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/vnd.apple.mpegurl")
                    self.send_header("Content-Length", str(len(out_bytes)))
                    self.end_headers()
                    self.wfile.write(out_bytes)
                    return

                # Binary stream (.mp4, .ts, .m4s, .vtt)
                self.send_response(upstream.status)
                for hdr in (
                    "Content-Type",
                    "Content-Length",
                    "Content-Range",
                    "Accept-Ranges",
                ):
                    val = upstream.headers.get(hdr)
                    if val:
                        self.send_header(hdr, val)
                if not upstream.headers.get("Accept-Ranges"):
                    self.send_header("Accept-Ranges", "bytes")
                self.end_headers()

                while True:
                    chunk = upstream.read(65536)
                    if not chunk:
                        break
                    try:
                        self.wfile.write(chunk)
                    except (BrokenPipeError, ConnectionResetError):
                        break
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            self.end_headers()
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            print(f"[StreamProxy] Error streaming {target_url}: {e}")


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def main():
    port = int(os.environ.get("PORT", "8080"))
    local_ip = get_local_ip()

    print("=" * 68)
    print("  🎮 Anime Rift - PlayStation 5 Edition (FW 13.60 Jailbreak) 🎮")
    print("=" * 68)
    try:
        client.register_device()
    except Exception as e:
        print(f"[Warning] Initial device registration deferred: {e}")

    print(f"  🌐 Local URL (PC):      http://localhost:{port}")
    print(f"  📺 PS5 Console URL:     http://{local_ip}:{port}")
    print("=" * 68)

    server = ThreadingHTTPServer(("0.0.0.0", port), PS5RequestHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Server] Shutting down...")
        server.server_close()


if __name__ == "__main__":
    main()
