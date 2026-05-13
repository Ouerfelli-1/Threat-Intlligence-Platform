from tip_common.auth_bootstrap import (
    fetch_auth_public_key,
    obtain_service_jwt,
    wire_auth,
)
from tip_common.bootstrap import create_service_app
from tip_common.correlation import CorrelationIdMiddleware, correlation_id_var, get_correlation_id
from tip_common.errors import (
    TIPError,
    NotFoundError,
    ConflictError,
    ValidationError,
    UpstreamError,
    register_error_handlers,
)
from tip_common.lifespan import build_lifespan
from tip_common.logging_setup import configure_logging, get_logger
from tip_common.settings import BaseServiceSettings

__all__ = [
    "BaseServiceSettings",
    "CorrelationIdMiddleware",
    "ConflictError",
    "NotFoundError",
    "TIPError",
    "UpstreamError",
    "ValidationError",
    "build_lifespan",
    "configure_logging",
    "correlation_id_var",
    "create_service_app",
    "fetch_auth_public_key",
    "get_correlation_id",
    "get_logger",
    "obtain_service_jwt",
    "register_error_handlers",
    "wire_auth",
]
