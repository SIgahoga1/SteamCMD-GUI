"""RCON-клиент (Source RCON Protocol, собственная реализация — работает с CS2)."""
from __future__ import annotations

import re
import socket
import struct
import threading
from typing import List, Optional

from app.models.player import Player
from app.services.logger import AppLogger

SERVERDATA_AUTH = 3
SERVERDATA_AUTH_RESPONSE = 2
SERVERDATA_EXECCOMMAND = 2
SERVERDATA_RESPONSE_VALUE = 0

TIMEOUT = 6.0


class RCONError(Exception):
    pass


class RCONClient:
    """Source RCON клиент. Потокобезопасный (lock на send)."""

    def __init__(self, host: str, port: int, password: str) -> None:
        self.host = host
        self.port = port
        self.password = password
        self._sock: Optional[socket.socket] = None
        self._req_id = 0
        self._lock = threading.Lock()

    # --- низкий уровень ---

    def _pack(self, req_id: int, ptype: int, body: str) -> bytes:
        payload = struct.pack("<ii", req_id, ptype) + body.encode("utf-8") + b"\x00\x00"
        return struct.pack("<i", len(payload)) + payload

    def _recv_exact(self, n: int) -> bytes:
        assert self._sock is not None
        data = b""
        while len(data) < n:
            chunk = self._sock.recv(n - len(data))
            if not chunk:
                raise RCONError("Соединение закрыто сервером")
            data += chunk
        return data

    def _recv_packet(self) -> tuple[int, int, str]:
        size = struct.unpack("<i", self._recv_exact(4))[0]
        payload = self._recv_exact(size)
        req_id, ptype = struct.unpack("<ii", payload[:8])
        body = payload[8:-2].decode("utf-8", errors="replace")
        return req_id, ptype, body

    # --- API ---

    @property
    def connected(self) -> bool:
        return self._sock is not None

    def connect(self) -> bool:
        self.disconnect()
        try:
            sock = socket.create_connection((self.host, self.port), timeout=TIMEOUT)
            sock.settimeout(TIMEOUT)
            self._sock = sock
            self._req_id = 1
            sock.sendall(self._pack(self._req_id, SERVERDATA_AUTH, self.password))
            # Ответ: иногда пустой RESPONSE_VALUE + AUTH_RESPONSE
            for _ in range(2):
                req_id, ptype, _body = self._recv_packet()
                if ptype == SERVERDATA_AUTH_RESPONSE:
                    if req_id == -1:
                        self.disconnect()
                        raise RCONError("Неверный RCON пароль")
                    AppLogger.info("RCON подключен: %s:%s", self.host, self.port)
                    return True
            self.disconnect()
            raise RCONError("Сервер не подтвердил авторизацию")
        except (OSError, struct.error) as exc:
            self.disconnect()
            raise RCONError(f"RCON соединение не удалось: {exc}") from exc

    def disconnect(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    def send_command(self, command: str) -> str:
        """Выполняет команду, возвращает текст ответа."""
        with self._lock:
            if self._sock is None:
                self.connect()
            assert self._sock is not None
            try:
                self._req_id += 1
                cmd_id = self._req_id
                self._sock.sendall(self._pack(cmd_id, SERVERDATA_EXECCOMMAND, command))
                # терминатор для многопакетных ответов
                self._req_id += 1
                term_id = self._req_id
                self._sock.sendall(self._pack(term_id, SERVERDATA_RESPONSE_VALUE, ""))
                parts: List[str] = []
                while True:
                    req_id, _ptype, body = self._recv_packet()
                    if req_id == term_id:
                        break
                    if req_id == cmd_id:
                        parts.append(body)
                return "".join(parts)
            except (OSError, RCONError) as exc:
                self.disconnect()
                raise RCONError(f"Ошибка RCON команды: {exc}") from exc

    # --- высокоуровневые команды ---

    def get_players(self) -> List[Player]:
        return parse_status_players(self.send_command("status"))

    def kick_player(self, player_id: str, reason: str = "") -> bool:
        cmd = f"kickid {player_id}" + (f" {reason}" if reason else "")
        self.send_command(cmd)
        return True

    def ban_player(self, steam_id: str, duration: int = 0, reason: str = "") -> bool:
        """duration в минутах, 0 = навсегда. Использует css_ban при наличии SimpleAdmin,
        иначе banid."""
        try:
            out = self.send_command(f"css_ban {steam_id} {duration} \"{reason}\"")
            if "Unknown command" not in out:
                return True
        except RCONError:
            pass
        self.send_command(f"banid {duration} {steam_id}")
        self.send_command("writeid")
        return True

    def change_map(self, map_name: str) -> bool:
        safe = re.sub(r"[^A-Za-z0-9_\-/]", "", map_name)
        self.send_command(f"changelevel {safe}")
        return True


STATUS_PLAYER_RE = re.compile(
    r"^#?\s*(?P<userid>\d+)\s+(?:\d+\s+)?\"(?P<name>.*)\"\s+(?P<steamid>\[?U:\d:\d+\]?|STEAM_\d:\d:\d+|\d{17})"
    r"(?P<rest>.*)$"
)
# CS2-формат: id time ping loss state rate adr name
CS2_ROW_RE = re.compile(
    r"^\s*(?P<userid>\d+)\s+(?P<time>[\d:]+)\s+(?P<ping>\d+)\s+(?P<loss>\d+)\s+"
    r"(?P<state>\w+)\s+(?P<rate>\d+)\s+(?P<adr>[\d.:]+|loopback)\s+'(?P<name>.*)'\s*$"
)


def parse_status_players(status_output: str) -> List[Player]:
    """Парсит вывод `status` (поддержка форматов CS:GO и CS2)."""
    players: List[Player] = []
    for line in status_output.splitlines():
        line = line.rstrip()
        m = CS2_ROW_RE.match(line)
        if m:
            if "BOT" in m.group("name").upper() and m.group("adr") == "loopback":
                status = "bot"
            else:
                status = "active" if m.group("state").lower() == "active" else m.group("state")
            players.append(Player(
                slot=int(m.group("userid")),
                userid=m.group("userid"),
                nickname=m.group("name"),
                steam_id="",
                ip=m.group("adr"),
                ping=int(m.group("ping")),
                time_online=m.group("time"),
                status=status,
            ))
            continue
        m = STATUS_PLAYER_RE.match(line.strip())
        if m:
            rest = m.group("rest")
            ping = 0
            ip = ""
            ping_m = re.search(r"\s(\d+)\s+\d+\s+\w+", rest)
            if ping_m:
                ping = int(ping_m.group(1))
            ip_m = re.search(r"(\d{1,3}(?:\.\d{1,3}){3}:\d+)", rest)
            if ip_m:
                ip = ip_m.group(1)
            players.append(Player(
                slot=int(m.group("userid")),
                userid=m.group("userid"),
                nickname=m.group("name"),
                steam_id=m.group("steamid"),
                ip=ip,
                ping=ping,
            ))
    return players
