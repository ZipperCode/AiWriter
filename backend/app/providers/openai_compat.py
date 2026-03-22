from collections.abc import AsyncIterator
from typing import Type

from openai import AsyncOpenAI
from pydantic import BaseModel

from app.providers.base import (
    BaseLLMProvider,
    ChatChunk,
    ChatMessage,
    ChatResponse,
)


class OpenAICompatProvider(BaseLLMProvider):
    def __init__(self, base_url: str, api_key: str):
        self.client = AsyncOpenAI(base_url=base_url, api_key=api_key)

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> ChatResponse:
        resp = await self.client.chat.completions.create(
            model=model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        choice = resp.choices[0]
        return ChatResponse(
            content=choice.message.content or "",
            model=resp.model,
            usage={
                "input_tokens": resp.usage.prompt_tokens if resp.usage else 0,
                "output_tokens": resp.usage.completion_tokens if resp.usage else 0,
            },
            raw=resp,
        )

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[ChatChunk]:
        stream = await self.client.chat.completions.create(
            model=model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield ChatChunk(content=delta.content)
        yield ChatChunk(content="", finished=True)

    async def structured_output(
        self,
        messages: list[ChatMessage],
        model: str,
        output_schema: Type[BaseModel],
        temperature: float = 0.3,
    ) -> BaseModel:
        resp = await self.client.chat.completions.create(
            model=model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content or "{}"
        return output_schema.model_validate_json(content)

    async def embedding(
        self, texts: list[str], model: str = "text-embedding-3-large"
    ) -> list[list[float]]:
        resp = await self.client.embeddings.create(model=model, input=texts)
        return [item.embedding for item in resp.data]
