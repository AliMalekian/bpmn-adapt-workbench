"""Authority-separated repository implementations and compatibility errors."""


class DatabaseConfigurationError(RuntimeError):
    pass


class ApprovalRequired(PermissionError):
    pass


from .core import RelationalCoreRepository
from .rag import RelationalRagRepository

__all__ = [
    "ApprovalRequired", "DatabaseConfigurationError",
    "RelationalCoreRepository", "RelationalRagRepository",
]
