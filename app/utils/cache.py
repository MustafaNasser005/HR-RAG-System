import json
from pathlib import Path
from typing import Dict, Any, Optional

def load_from_cache(cache_file: Path) -> Optional[Dict[str, Any]]:
    """Load data from cache file if it exists"""
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading cache file {cache_file}: {e}")
    return None

def save_to_cache(cache_file: Path, data: Dict[str, Any]):
    """Save data to cache file"""
    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error writing to cache file {cache_file}: {e}")