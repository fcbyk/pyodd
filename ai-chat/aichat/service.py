from dataclasses import dataclass
from typing import Any, Dict, Generator, Iterable, List, Union

from openai import OpenAI, APIError, AuthenticationError, APIConnectionError, Timeout


JsonDict = Dict[str, Any]


@dataclass(frozen=True)
class ChatRequest:
    messages: List[JsonDict]
    model: str
    api_key: str
    api_url: str
    stream: bool = False
    timeout: int = 30
    extra_body: Dict[str, Any] = None


class AIServiceError(RuntimeError):
    
    @classmethod
    def network_error(cls):
        return cls("网络错误")
    
    @classmethod
    def api_key_error(cls):
        return cls("API Key 错误")
    
    @classmethod
    def backend_error(cls, detail: str = ""):
        msg = "后端逻辑错误"
        if detail:
            msg += f": {detail}"
        return cls(msg)


class AIService:

    def __init__(self):
        pass

    def chat(self, req: ChatRequest) -> Union[JsonDict, Iterable[JsonDict]]:
        if not req.api_key:
            raise AIServiceError.api_key_error()

        try:
            client = OpenAI(
                api_key=req.api_key,
                base_url=req.api_url.replace('/chat/completions', '') if '/chat/completions' in req.api_url else req.api_url,
                timeout=req.timeout
            )

            params = {
                "model": req.model,
                "messages": req.messages,
                "stream": req.stream,
            }
            
            # Add extra_body if provided (for features like reasoning)
            if req.extra_body:
                params["extra_body"] = req.extra_body

            if req.stream:
                return self._stream_chunks(client, params)
            else:
                return self._parse_response(client, params)

        except AuthenticationError:
            raise AIServiceError.api_key_error()
        except (APIConnectionError, Timeout):
            raise AIServiceError.network_error()
        except APIError as e:
            raise AIServiceError.backend_error(str(e))
        except Exception as e:
            raise AIServiceError.backend_error(str(e))

    def _parse_response(self, client: OpenAI, params: dict) -> JsonDict:
        try:
            response = client.chat.completions.create(**params)
            return response.model_dump()
        except (AuthenticationError, APIConnectionError, Timeout, APIError):
            raise
        except Exception as e:
            raise AIServiceError.backend_error(f"响应解析失败: {e}")

    def _stream_chunks(self, client: OpenAI, params: dict) -> Generator[JsonDict, None, None]:
        try:
            stream = client.chat.completions.create(**params)
            for chunk in stream:
                yield chunk.model_dump()
        except (AuthenticationError, APIConnectionError, Timeout, APIError):
            raise
        except Exception as e:
            raise AIServiceError.backend_error(f"流式读取失败: {e}")


def extract_assistant_reply(response: JsonDict) -> str:
    return response['choices'][0]['message']['content']


def extract_assistant_reply_from_stream(chunks: Iterable[JsonDict]) -> str:
    reply = ""
    for chunk in chunks:
        delta = chunk['choices'][0]['delta'].get('content', '')
        reply += delta
    return reply