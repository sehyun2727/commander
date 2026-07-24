"""Situation Report module.

A glanceable, PM-voiced one-liner on the current company state (pending
decisions, missions in flight, last notable event) for the Headquarters
page. Deliberately distinct from reports/ (the trailing-24h Daily Report):
ephemeral, uncached, regenerated on every request. See service.py.
"""

from .routes import router

__all__ = ["router"]
