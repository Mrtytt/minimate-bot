import hashlib
import json
import os

TRACK_FILE = "analyzed_games.json"

def load_analyzed_games():
    if not os.path.exists(TRACK_FILE):
        return {}
    with open(TRACK_FILE, "r") as f:
        return json.load(f)

def save_analyzed_games(data):
    with open(TRACK_FILE, "w") as f:
        json.dump(data, f, indent=2)

def game_hash(pgn_text):
    """PGN'den benzersiz bir hash üretir."""
    clean_text = pgn_text.strip().replace("\n", "").replace(" ", "")
    return hashlib.md5(clean_text.encode("utf-8")).hexdigest()

def is_already_analyzed(pgn_text):
    """Eğer analiz edilmişse metadata ile birlikte döner."""
    data = load_analyzed_games()
    game_id = game_hash(pgn_text)
    return data.get(game_id)

def mark_as_analyzed(pgn_text, metadata):
    """Analiz edilen oyunu metadata ile kaydeder."""
    data = load_analyzed_games()
    game_id = game_hash(pgn_text)
    data[game_id] = metadata
    save_analyzed_games(data)
