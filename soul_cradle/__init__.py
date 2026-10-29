"""Witness Gate — an accountable-AI trust layer.

A minimal, standalone extract: eight evidence-fed witness assessors
(:mod:`soul_cradle.assessors`), a tamper-evident hash-chained attestation
record (:mod:`soul_cradle.emotional_chain`), and the signed standing
matrix that seals assessor declarations (:mod:`soul_cradle.standing`).

No external dependencies beyond the Python standard library.
"""

from . import assessors, emotional_chain, standing

__all__ = ["assessors", "emotional_chain", "standing"]
__version__ = "2026.1"
