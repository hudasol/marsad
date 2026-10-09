"""Marsad service layer: REST/SSE API (``create_app``), shared state store, request models.

``marsad.api.state`` and ``marsad.api.models`` only need pydantic; ``create_app`` needs FastAPI.
"""


def __getattr__(name):
    if name == "create_app":
        from .app import create_app
        return create_app
    raise AttributeError(name)


__all__ = ["create_app"]
