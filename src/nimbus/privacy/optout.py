import tomllib
from pathlib import Path

CONFIG_PATH = Path.home() / ".nimbus" / "config.toml"


def load_opt_out_prefixes(config_path: Path = CONFIG_PATH) -> list[str]:
    """Return the list of MAC prefixes/addresses to silently ignore."""
    if not config_path.exists():
        return []
    with config_path.open("rb") as f:
        raw = tomllib.load(f)
    return [str(p) for p in raw.get("privacy", {}).get("opt_out", [])]


def is_opted_out(mac: str, prefixes: list[str]) -> bool:
    """Return True if this MAC matches any opt-out prefix."""
    normalized = mac.lower().replace("-", ":").strip()
    return any(normalized.startswith(p.lower()) for p in prefixes)
