"""Contract 10: Authorization — real per-operation permission enforcement.

Roles are resolved from a bearer/API token:
- ``admin`` when the token equals ``GRAPHRAG_ADMIN_TOKEN`` (constant-time
  compared with :func:`hmac.compare_digest`).
- ``anonymous`` otherwise (the localhost dashboard path).

The default policy keeps all read operations open for ``anonymous`` and
reserves ingestion/deletion for ``admin``. Every check returns an auditable
:class:`PermissionResult`; :meth:`require` raises for denied calls.
"""

from __future__ import annotations

import hmac
import os
from typing import Any

from mcp_server.protocol_extensions import (
    AccessPolicy,
    PermissionDecision,
    PermissionResult,
)

_ADMIN_TOKEN_ENV = "GRAPHRAG_ADMIN_TOKEN"


class AuthorizationContract:
    """Contract 10: permission checks over an :class:`AccessPolicy`.

    Args:
        policy: Policy to enforce (defaults to the standard policy).
        admin_token: Admin secret; defaults to ``GRAPHRAG_ADMIN_TOKEN``.
            When the env var is unset, admin operations are denied and the
            reason states so explicitly (fail closed, never silently open).
    """

    def __init__(self, policy: AccessPolicy | None = None, admin_token: str | None = None) -> None:
        self._policy = policy or AccessPolicy()
        self._admin_token = admin_token if admin_token is not None else os.environ.get(_ADMIN_TOKEN_ENV)

    @property
    def policy(self) -> AccessPolicy:
        return self._policy

    # -- role resolution --------------------------------------------------------

    def resolve_role(self, token: str | None = None, user_id: str | None = None) -> str:
        """Map a token (or explicit user id) onto a policy role.

        Args:
            token: Presented secret; compared in constant time.
            user_id: Optional identity override (``'admin'`` grants admin).

        Returns:
            The role name (``'admin'`` or the policy's ``default_role``).
        """
        if token and self._admin_token and hmac.compare_digest(str(token), str(self._admin_token)):
            return self._policy.admin_role
        return self._policy.default_role

    # -- checks -----------------------------------------------------------------

    def check_permission(
        self,
        operation: str,
        graph_id: str | None = None,
        user_id: str | None = None,
        resource_filter: dict[str, Any] | None = None,
        token: str | None = None,
    ) -> PermissionResult:
        """Decide whether ``operation`` may run for the caller.

        Args:
            operation: Operation name (e.g. ``'ingest'``, ``'local_search'``).
            graph_id: Target graph, echoed for audit.
            user_id: Optional identity override.
            resource_filter: Optional resource scope, echoed for audit.
            token: Presented bearer secret.

        Returns:
            An auditable :class:`PermissionResult` (always populated).
        """
        if not operation:
            raise ValueError("check_permission requires a non-empty operation")
        role = self.resolve_role(token=token, user_id=user_id)
        if role == self._policy.admin_role:
            allowed = operation in self._policy.allow_admin or operation in self._policy.allow_anonymous
            reason = (
                "admin role: operation permitted"
                if allowed
                else f"admin role: unknown operation {operation!r}"
            )
        else:
            allowed = operation in self._policy.allow_anonymous
            reason = (
                "anonymous role: read operation permitted"
                if allowed
                else (
                    f"anonymous role: {operation!r} requires the admin role "
                    f"({_ADMIN_TOKEN_ENV} not configured)"
                    if not self._admin_token
                    else f"anonymous role: {operation!r} requires an admin token"
                )
            )
        if resource_filter:
            reason = f"{reason}; scope={sorted(resource_filter)}"
        return PermissionResult(
            allowed=allowed,
            decision=PermissionDecision.ALLOW if allowed else PermissionDecision.DENY,
            role=role,
            operation=operation,
            graph_id=graph_id,
            reason=reason,
        )

    def get_allowed_operations(
        self,
        user_id: str | None = None,
        graph_id: str | None = None,
        token: str | None = None,
    ) -> list[str]:
        """List the operations the caller may perform (sorted, auditable)."""
        role = self.resolve_role(token=token, user_id=user_id)
        ops = set(self._policy.allow_anonymous)
        if role == self._policy.admin_role:
            ops |= set(self._policy.allow_admin)
        return sorted(ops)

    def require(
        self,
        operation: str,
        graph_id: str | None = None,
        user_id: str | None = None,
        token: str | None = None,
    ) -> PermissionResult:
        """Enforce a permission, raising :class:`PermissionError` when denied.

        Raises:
            PermissionError: If the operation is not allowed for the caller.
        """
        result = self.check_permission(
            operation=operation, graph_id=graph_id, user_id=user_id, token=token
        )
        if not result.allowed:
            raise PermissionError(f"{operation}: {result.reason}")
        return result
