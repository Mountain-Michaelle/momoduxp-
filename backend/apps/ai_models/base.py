"""
Base AI client interface.
DRY: Common interface for all AI providers.
"""

from abc import ABC, abstractmethod
from typing import Optional


class BaseAIClient(ABC):
    """Base class for AI providers."""

    @abstractmethod
    async def generate_content(self, prompt: str, **kwargs) -> str:
        """Generate content from a prompt."""
        pass

    @abstractmethod
    async def optimize_content(self, content: str, goal: str, **kwargs) -> str:
        """Optimize existing content for a specific goal."""
        pass

    @abstractmethod
    async def generate_variations(self, content: str, count: int = 3, **kwargs) -> list[str]:
        """Generate multiple variations of content."""
        pass

    async def close(self):
        """Close any open connections. Override if needed."""
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
