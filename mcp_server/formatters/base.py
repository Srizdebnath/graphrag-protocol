"""Abstract context formatter interface.

Formatters convert a SubgraphContext into LLM-ready text (Contract 8).
Different formats trade off token efficiency, structure, and prompt
compatibility for different models.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from mcp_server.protocol import Entity, Relationship, SubgraphContext


class BaseFormatter(ABC):
    """Contract 8: Abstract interface for SubgraphContext formatters."""

    @abstractmethod
    def format_context(
        self,
        context: SubgraphContext,
        max_tokens: int = 4096,
    ) -> str:
        """Serialize a SubgraphContext into LLM-ready text.

        The output must be bounded to approximately ``max_tokens`` by
        prioritizing the highest-scoring entities, relationships, paths,
        communities, and chunks.

        Args:
            context: The subgraph context to format.
            max_tokens: Approximate maximum token budget for the output.

        Returns:
            Formatted context text suitable for a prompt.
        """
        ...

    @abstractmethod
    def format_entity(self, entity: Entity) -> str:
        """Serialize a single entity into the formatter's format."""
        ...

    @abstractmethod
    def format_relationship(self, relationship: Relationship) -> str:
        """Serialize a single relationship into the formatter's format."""
        ...