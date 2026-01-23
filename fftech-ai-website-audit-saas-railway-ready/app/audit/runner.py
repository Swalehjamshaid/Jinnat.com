
# app/audit/runner.py
"""
Shim module so existing imports keep working:
    from app.audit.runner import run_audit

This delegates to the implementation currently defined in app/audit/grader.py.
No other files need to change.
"""

from .grader import run_audit

__all__ = ["run_audit"]
