"""Contracts for future provider integrations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProviderHealth:
    name: str
    configured: bool
    mode: str
    detail: str = ""


class Provider(ABC):
    name = "provider"

    @abstractmethod
    def health(self) -> ProviderHealth:
        """Report configuration without exposing credentials."""


class TrendSource(Provider):
    @abstractmethod
    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Return normalized public signals with source URLs and timestamps."""


class CommerceChannel(Provider):
    @abstractmethod
    def publish_draft(self, product: dict[str, Any]) -> dict[str, Any]:
        """Create a draft only; live publication requires a separate approval."""


class FulfillmentProvider(Provider):
    @abstractmethod
    def quote(self, product: dict[str, Any], destination: dict[str, str]) -> dict[str, Any]:
        """Return a quote; do not place a supplier order."""
