from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..models import ProviderResponse


class Provider(ABC):
    @abstractmethod
    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ProviderResponse:
        raise NotImplementedError
