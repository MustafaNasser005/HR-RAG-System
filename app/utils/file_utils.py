import re
from typing import Dict, Any, Union
import hashlib
from pathlib import Path

def get_file_hash(file_path: Path) -> str:
    """Calculate MD5 hash of a file"""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def ensure_directory_exists(directory_path: Path):
    """Ensure a directory exists, create if it doesn't"""
    directory_path.mkdir(parents=True, exist_ok=True)

def clean_dict_keys(d):
    """
    Recursively clean dictionary keys:
    - Remove keys starting with underscore (_)
    - Remove keys starting with double underscore (__)
    - Strip whitespace from keys
    - Handle nested dictionaries and lists
    """
    if not isinstance(d, dict):
        return d

    cleaned = {}
    for k, v in d.items():
        # Skip any key that starts with underscore
        if str(k).startswith("_"):
            continue
            
        # Clean the key
        new_key = str(k).strip()
        
        # Recursively clean the value
        if isinstance(v, dict):
            cleaned_value = clean_dict_keys(v)
            if cleaned_value:  # Only add if not empty after cleaning
                cleaned[new_key] = cleaned_value
        elif isinstance(v, list):
            cleaned_list = []
            for item in v:
                if isinstance(item, dict):
                    cleaned_item = clean_dict_keys(item)
                    if cleaned_item:  # Only add if not empty after cleaning
                        cleaned_list.append(cleaned_item)
                else:
                    cleaned_list.append(item)
            cleaned[new_key] = cleaned_list
        else:
            cleaned[new_key] = v
    
    return cleaned