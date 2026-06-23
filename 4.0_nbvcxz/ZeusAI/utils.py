"""
Plugin: Utils — UUID ve hash üreteci
"""
import uuid
import hashlib

TOOL_DEF = {
    "type": "function",
    "function": {
        "name": "generate_utils",
        "description": "UUID veya hash (md5/sha256) üretir.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "'uuid4', 'uuid7', 'md5', 'sha256' değerlerinden biri"
                },
                "text": {
                    "type": "string",
                    "description": "Hash için kaynak metin (action=md5 veya sha256 ise)"
                }
            },
            "required": ["action"]
        }
    }
}


def execute(action: str, text: str = "") -> str:
    action = action.lower().strip()
    if action == "uuid4":
        return str(uuid.uuid4())
    elif action in ("uuid7", "uuid1"):
        return str(uuid.uuid1())
    elif action == "md5":
        if not text:
            return "Hata: md5 için 'text' gerekli."
        return hashlib.md5(text.encode()).hexdigest()
    elif action == "sha256":
        if not text:
            return "Hata: sha256 için 'text' gerekli."
        return hashlib.sha256(text.encode()).hexdigest()
    else:
        return f"Hata: Bilinmeyen action '{action}'. Geçerli: uuid4, uuid7, md5, sha256"
