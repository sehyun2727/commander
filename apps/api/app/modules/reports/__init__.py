"""CEO Daily Report module.

Generates an on-demand executive summary of the prior 24h (missions moved,
decisions made, failures, Payroll) from the Timeline's own event history,
via the same ProviderGateway every other role uses — mock mode gets a
templated summary, real providers get one written by the model.
"""

from .routes import router
from .service import generate_report

__all__ = ["router", "generate_report"]
