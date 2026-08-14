"""
Service-Layer Error Types

Typed failures raised by the service layer so routers can map an exception to
an HTTP status by *type* rather than by sniffing substrings out of the message
(#4700). Substring matching silently mis-classified every service-outage
condition as 400 Bad Request and broke the moment a message was reworded.

All of these subclass ``ValueError`` so pre-existing ``except ValueError``
handlers and tests keep working while call sites migrate.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""


class ServiceError(ValueError):
    """Base class for service-layer failures with a known HTTP classification."""


class ServiceUnavailable(ServiceError):
    """A required component (player, state manager, library) is not initialized → 503."""


class InvalidRequest(ServiceError):
    """The caller supplied arguments the service cannot act on → 400."""


class ResourceNotFound(ServiceError):
    """The requested entity does not exist → 404."""


class OperationFailed(ServiceError):
    """A downstream operation reported failure for no caller-attributable reason → 500."""


__all__ = [
    'ServiceError',
    'ServiceUnavailable',
    'InvalidRequest',
    'ResourceNotFound',
    'OperationFailed',
]
