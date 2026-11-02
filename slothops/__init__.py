"""slothops package exports."""

from slothops.domain import Document, DocumentStatus, DuplicateCandidate, VALID_CATEGORIES
from slothops.providers import AnalysisResponse, BaseAIProvider, HeuristicProvider, OllamaProvider, ProviderError, parse_analysis_payload

__all__ = [
    "Document",
    "DocumentStatus",
    "DuplicateCandidate",
    "VALID_CATEGORIES",
    "AnalysisResponse",
    "BaseAIProvider",
    "HeuristicProvider",
    "OllamaProvider",
    "ProviderError",
    "parse_analysis_payload",
]
