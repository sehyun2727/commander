"""Port: the only path through which agents may call AI provider APIs.

Concrete implementation lives in modules/provider_gateway. Agent Runtime
must depend only on this interface, never on a specific provider SDK.
"""

from abc import ABC, abstractmethod
from typing import Any


class ProviderGateway(ABC):
    @abstractmethod
    def complete(self, model_id: str, prompt: str, **options: Any) -> str:
        """Send a prompt to the given model via its provider and return the
        response text. Model -> provider routing is resolved internally via
        the Model Registry."""
