"""
Plugin: JSON Formatter
Kullanım: plugins/ klasörüne at, uygulama otomatik yükler.
TOOL_DEF ve execute() zorunludur.
"""
import json

TOOL_DEF = {
    "type": "function",
    "function": {
        "name": "format_json",
        "description": "Ham JSON string'ini güzelleştirir (pretty-print) ve doğrular.",
        "parameters": {
            "type": "object",
            "properties": {
                "raw": {
                    "type": "string",
                    "description": "Formatlanacak ham JSON string"
                },
                "indent": {
                    "type": "integer",
                    "description": "Girinti miktarı (varsayılan: 2)"
                }
            },
            "required": ["raw"]
        }
    }
}


def execute(raw: str, indent: int = 2) -> str:
    try:
        parsed = json.loads(raw)
        formatted = json.dumps(parsed, indent=indent, ensure_ascii=False)
        return f"✅ Geçerli JSON ({len(formatted)} karakter):\n\n{formatted}"
    except json.JSONDecodeError as e:
        return f"❌ Geçersiz JSON: {e}"
