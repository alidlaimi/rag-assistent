"""Zugriff auf das Sprachmodell (Anthropic Claude)."""

from dataclasses import dataclass

import anthropic

from rag_assistent import stub_llm
from rag_assistent.config import get_settings, testmodus


@dataclass(frozen=True)
class LlmResult:
    text: str
    modell: str
    input_tokens: int
    output_tokens: int
    abgeschnitten: bool  # True, wenn die Antwort wegen max_tokens endete


def _client() -> anthropic.Anthropic:
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY fehlt – bitte in der Datei .env eintragen."
        )
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def text_of(response) -> str:
    """Nur Textblöcke übernehmen (Werkzeugaufrufe oder Denkschritte gehören nicht in die Antwort)."""
    return "".join(
        block.text for block in response.content if block.type == "text"
    ).strip()


def create(
    system: str,
    messages: list,
    tools: list | None = None,
    tool_choice: dict | None = None,
    max_tokens: int = 2048,
):
    """Roher Modellaufruf – für die Agent-Schleife, die die Antwortblöcke selbst auswertet."""
    if testmodus():
        # Einzige Stelle, an der der Testmodus eingreift: Alles davor (Personendaten-Filter,
        # Suche) und danach (Werkzeuge, Zitatprüfung, Protokoll) läuft unverändert.
        return stub_llm.create(system, messages, tools, tool_choice, max_tokens)
    kwargs = {"tools": tools} if tools else {}
    if tool_choice:
        kwargs["tool_choice"] = tool_choice
    return _client().messages.create(
        model=get_settings().claude_model,
        max_tokens=max_tokens,
        system=system,
        messages=messages,
        **kwargs,
    )


def complete(system: str, user: str, max_tokens: int = 2048) -> LlmResult:
    """Einfacher Aufruf ohne Werkzeuge: eine Frage, eine Antwort."""
    response = create(
        system, [{"role": "user", "content": user}], max_tokens=max_tokens
    )
    return LlmResult(
        text=text_of(response),
        modell=response.model,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        abgeschnitten=response.stop_reason == "max_tokens",
    )
