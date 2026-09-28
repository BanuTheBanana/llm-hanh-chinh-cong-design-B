"""Lazy exports keep standalone grounding/benchmark imports free of cycles."""

from importlib import import_module

_MODULES = {
    "AIProvider": "base",
    "GenerationResult": "base",
    "GroundedGenerationResult": "grounded_base",
    "GroundedProvider": "grounded_base",
    "LocalGroundedProvider": "local_grounded",
    "MockProvider": "mock",
    "TemplateGroundedProvider": "template_grounded",
}


def __getattr__(name):
    if name not in _MODULES:
        raise AttributeError(name)
    return getattr(import_module(f"app.providers.{_MODULES[name]}"), name)


__all__ = [
    "AIProvider",
    "GenerationResult",
    "GroundedGenerationResult",
    "GroundedProvider",
    "LocalGroundedProvider",
    "MockProvider",
    "TemplateGroundedProvider",
]
