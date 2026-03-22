from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Type

from pydantic import BaseModel


@dataclass
class ChatMessage:
    role: str  # system / user / assistant
    content: str


@dataclass
class ChatResponse:
    content: str
    model: str
    usage: dict = field(default_factory=dict)
    raw: Any = None


@dataclass
class ChatChunk:
    content: str
    finished: bool = False


class BaseLLMProvider(ABC):
    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> ChatResponse: ...

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[ChatChunk]: ...

    @abstractmethod
    async def structured_output(
        self,
        messages: list[ChatMessage],
        model: str,
        output_schema: Type[BaseModel],
        temperature: float = 0.3,
    ) -> BaseModel: ...

    @abstractmethod
    async def embedding(
        self, texts: list[str], model: str = "text-embedding-3-large"
    ) -> list[list[float]]: ...

    def count_tokens(self, text: str, model: str = "gpt-4o") -> int:
        import tiktoken

        try:
            enc = tiktoken.encoding_for_model(model)
        except KeyError:
            enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
