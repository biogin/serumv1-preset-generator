"""A scripted stand-in for the chat model at the pipeline seam.

Each structured-output call returns the next scripted object, which must be an
instance of the schema the pipeline asked for. Prompts are recorded so tests
can check what the model was told (e.g. validation errors on a retry).
"""

from typing import Any

from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from pydantic import BaseModel, PrivateAttr


class ScriptedModel(FakeListChatModel):
    responses: list[str] = ["unused"]
    _script: list[BaseModel] = PrivateAttr(default_factory=list)
    _prompts: list[str] = PrivateAttr(default_factory=list)

    _served_by: str = PrivateAttr(default="scripted")

    def __init__(self, script: list[BaseModel], served_by: str = "scripted") -> None:
        super().__init__()
        self._script = list(script)
        self._served_by = served_by

    @property
    def prompts(self) -> list[str]:
        return self._prompts

    def with_structured_output(self, schema: Any, **kwargs: Any) -> RunnableLambda:  # type: ignore[override]
        include_raw = kwargs.get("include_raw", False)

        def respond(messages: Any) -> Any:
            self._prompts.append(_as_text(messages))
            if not self._script:
                raise AssertionError(f"model called for {schema.__name__} but script is empty")
            response = self._script.pop(0)
            assert isinstance(response, schema), (
                f"script has {type(response).__name__}, pipeline asked for {schema.__name__}"
            )
            if include_raw:
                raw = AIMessage("", response_metadata={"model_name": self._served_by})
                return {"raw": raw, "parsed": response, "parsing_error": None}
            return response

        return RunnableLambda(respond)


def _as_text(messages: Any) -> str:
    if isinstance(messages, str):
        return messages
    parts = []
    for m in messages:
        content = getattr(m, "content", m)
        if isinstance(content, list):
            parts.extend(str(c.get("text", c)) if isinstance(c, dict) else str(c) for c in content)
        else:
            parts.append(str(content))
    return "\n".join(parts)
