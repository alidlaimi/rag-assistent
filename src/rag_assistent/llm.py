"""Zugriff auf das Sprachmodell (Anthropic Claude)."""
from dataclasses import dataclass

import anthropic

from rag_assistent.config import get_settings


@dataclass(frozen=True)
class LlmResult:
    text: str
    modell: str
    input_tokens: int
    output_tokens: int
    abgeschnitten: bool  # True, wenn die Antwort wegen max_tokens endete


def complete(system: str, user: str, max_tokens: int = 2048) -> LlmResult:
    """Schickt eine Anfrage an Claude und gibt Text und Token-Verbrauch zurück."""
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY fehlt – bitte in der Datei .env eintragen.")

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=settings.claude_model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    # Nur Textblöcke übernehmen (andere Blocktypen, z.B. Denkschritte, gehören nicht in die Antwort)
    text = "".join(block.text for block in response.content if block.type == "text")
    return LlmResult(
        text=text.strip(),
        modell=response.model,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        abgeschnitten=response.stop_reason == "max_tokens",
    )
