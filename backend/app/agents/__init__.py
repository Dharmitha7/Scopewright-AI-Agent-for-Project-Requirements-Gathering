"""Agents lane (D23, D36, D45-D48).

The generic phase-runner graph lives in graph.py, phase templates in
templates.py, and the transport-agnostic entry points in runner.py.

Deliberately empty: an eager `from app.agents.runner import ...` here made
importing ANY app.agents submodule (e.g. inference from the belief layer)
execute runner -> graph -> knowledge -> cards -> belief, a circular import
that only ever worked by import-order luck. Import from app.agents.runner
directly.
"""
