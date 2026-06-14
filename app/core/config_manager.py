"""Чтение/запись конфигов сервера + шаблоны."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Dict, List

from app.services.logger import AppLogger

TEMPLATES: Dict[str, str] = {
    "Public": """// SteamCMD v2 — шаблон Public
hostname "{hostname}"
sv_lan 0
sv_cheats 0
mp_autoteambalance 1
mp_maxrounds 30
mp_match_can_clinch 1
mp_warmuptime 30
sv_alltalk 0
sv_deadtalk 1
rcon_password "{rcon_password}"
exec banned_user.cfg
exec banned_ip.cfg
""",
    "Retake": """// SteamCMD v2 — шаблон Retake
hostname "{hostname} | RETAKE"
sv_cheats 0
mp_roundtime 1.92
mp_freezetime 1
mp_maxrounds 0
mp_timelimit 0
mp_warmuptime 10
mp_autoteambalance 0
mp_limitteams 0
sv_alltalk 0
rcon_password "{rcon_password}"
""",
    "Arena": """// SteamCMD v2 — шаблон Arena (1v1)
hostname "{hostname} | ARENA 1v1"
sv_cheats 0
mp_roundtime 1.5
mp_freezetime 1
mp_warmuptime 5
mp_autoteambalance 0
mp_limitteams 0
sv_alltalk 1
rcon_password "{rcon_password}"
""",
    "Bhop": """// SteamCMD v2 — шаблон Bhop
hostname "{hostname} | BHOP"
sv_cheats 1
sv_autobunnyhopping 1
sv_enablebunnyhopping 1
sv_staminamax 0
sv_staminajumpcost 0
sv_staminalandcost 0
sv_staminarecoveryrate 0
sv_airaccelerate 1000
sv_falldamage_scale 0
mp_roundtime 60
mp_freezetime 0
mp_warmuptime 0
mp_ignore_round_win_conditions 1
rcon_password "{rcon_password}"
""",
    "Deathmatch": """// SteamCMD v2 — шаблон Deathmatch
hostname "{hostname} | DM"
sv_cheats 0
mp_roundtime 10
mp_freezetime 0
mp_warmuptime 0
mp_respawn_on_death_t 1
mp_respawn_on_death_ct 1
mp_buy_anywhere 1
mp_buytime 60000
mp_death_drop_gun 0
mp_free_armor 2
sv_infinite_ammo 1
rcon_password "{rcon_password}"
""",
    "Training": """// SteamCMD v2 — шаблон Training
hostname "{hostname} | TRAINING"
sv_cheats 1
mp_roundtime 60
mp_freezetime 0
mp_warmuptime 0
mp_maxmoney 65535
mp_startmoney 65535
mp_buytime 60000
mp_buy_anywhere 1
sv_infinite_ammo 1
sv_grenade_trajectory_prac_pipreview 1
sv_showimpacts 1
mp_ignore_round_win_conditions 1
bot_kick
rcon_password "{rcon_password}"
""",
    "Custom": """// SteamCMD v2 — пустой шаблон
hostname "{hostname}"
rcon_password "{rcon_password}"
""",
}


class ConfigManager:
    def __init__(self, server_path: str) -> None:
        self.server_path = Path(server_path)
        self.cfg_dir = self.server_path / "game" / "csgo" / "cfg"

    def list_configs(self) -> List[Path]:
        if not self.cfg_dir.is_dir():
            return []
        return sorted(self.cfg_dir.glob("*.cfg"), key=lambda p: p.name.lower())

    def read(self, path: Path) -> str:
        return path.read_text(encoding="utf-8", errors="replace")

    def write(self, path: Path, content: str, make_backup: bool = True) -> None:
        """Сохраняет конфиг, предварительно создав .bak копию."""
        if make_backup and path.exists():
            shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        AppLogger.info("Конфиг сохранён: %s", path)

    def create_from_template(self, template_name: str, filename: str,
                             hostname: str = "CS2 Server",
                             rcon_password: str = "") -> Path:
        if template_name not in TEMPLATES:
            raise KeyError(f"Неизвестный шаблон: {template_name}")
        content = TEMPLATES[template_name].format(
            hostname=hostname, rcon_password=rcon_password)
        if not filename.endswith(".cfg"):
            filename += ".cfg"
        path = self.cfg_dir / filename
        self.write(path, content, make_backup=True)
        return path
