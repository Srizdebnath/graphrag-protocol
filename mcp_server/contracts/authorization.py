"""Contract 10: Authorization — 5-tier RBAC and capability tokens.

Roles:
- ``anonymous``: standard read queries (local/global/hybrid search, entity, schema, provenance).
- ``analyst``: + export, evaluate, batch, diff, aggregate, temporal search.
- ``editor``: + ingest, update (cannot delete or mutate backend federation).
- ``admin``: + delete, jobs, backend federation registration.
- ``super_admin``: full capability token issuance, policy configuration.

Supports bearer tokens (matching GRAPHRAG_ADMIN_TOKEN) and signed HMAC/JWT capability tokens.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any

from mcp_server.protocol_extensions import (
    AccessPolicy,
    PermissionDecision,
    PermissionResult,
)

_ADMIN_TOKEN_ENV = "GRAPHRAG_ADMIN_TOKEN"
_SECRET_KEY = os.environ.get("GRAPHRAG_SECRET_KEY", "graphrag-protocol-signing-secret")

_ANONYMOUS_OPS = {
    "local_search", "global_search", "hybrid_search", "entity_lookup",
    "path_search", "neighborhood", "community_members", "search",
    "get_schema", "get_entity_types", "get_relationship_types",
    "get_sample_entities", "get_statistics", "trace_citation",
    "get_traversal_trajectory", "get_source_documents",
    "audit_provenance_completeness", "format_context",
    "subscribe", "health", "similarity", "entity_similarity",
    "batch_similarity", "temporal_search", "explain", "explain_path",
}

_ANALYST_OPS = _ANONYMOUS_OPS | {
    "diff", "diff_queries", "count", "group_by", "top_n", "stats_summary",
    "export_subgraph", "batch", "evaluate",
}

_EDITOR_OPS = _ANALYST_OPS | {
    "ingest", "update_document", "job_status",
}

_ADMIN_OPS = _EDITOR_OPS | {
    "delete_document", "admin_status", "register_backend", "federated_search",
    "cross_graph_entity_link", "audit_log",
}

_SUPER_ADMIN_OPS = _ADMIN_OPS | {
    "issue_capability_token", "configure_policy",
}

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "anonymous": _ANONYMOUS_OPS,
    "analyst": _ANALYST_OPS,
    "editor": _EDITOR_OPS,
    "admin": _ADMIN_OPS,
    "super_admin": _SUPER_ADMIN_OPS,
}


class AuthorizationContract:
    """Contract 10: 5-tier RBAC and capability token enforcement."""

    def __init__(self, policy: AccessPolicy | None = None, admin_token: str | None = None) -> None:
        self._policy = policy or AccessPolicy()
        self._admin_token = admin_token if admin_token is not None else os.environ.get(_ADMIN_TOKEN_ENV)

    @property
    def policy(self) -> AccessPolicy:
        return self._policy

    # ------------------------------------------------------------------
    # Capability Token Minting & Verification
    # ------------------------------------------------------------------

    def issue_capability_token(
        self,
        role: str = "analyst",
        operations: list[str] | None = None,
        ttl_seconds: int = 3600,
        subject: str = "agent",
        admin_token: str | None = None,
    ) -> str:
        """Issue a signed capability token granting specific roles or operations."""
        # Require admin or super_admin to issue tokens
        issuer_role = self.resolve_role(token=admin_token)
        if issuer_role not in ("admin", "super_admin"):
            raise PermissionError("Issuing capability tokens requires admin privileges")

        role = role.lower()
        if role not in ROLE_PERMISSIONS:
            raise ValueError(f"Unknown role: {role!r}")

        exp = int(time.time()) + ttl_seconds
        payload = {
            "sub": subject,
            "role": role,
            "ops": operations or list(ROLE_PERMISSIONS[role]),
            "exp": exp,
            "iat": int(time.time()),
        }
        encoded_data = base64.urlsafe_b64encode(json.dumps(payload, sort_keys=True).encode()).decode()
        sig = hmac.new(_SECRET_KEY.encode(), encoded_data.encode(), hashlib.sha256).hexdigest()
        return f"cap_{encoded_data}.{sig}"

    def verify_capability_token(self, token: str) -> dict[str, Any] | None:
        """Verify and decode a capability token. Returns claims if valid."""
        if not token or not token.startswith("cap_") or "." not in token:
            return None
        raw = token[4:]
        data_part, sig = raw.rsplit(".", 1)
        expected_sig = hmac.new(_SECRET_KEY.encode(), data_part.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        try:
            payload = json.loads(base64.urlsafe_b64decode(data_part.encode()).decode())
            if payload.get("exp", 0) < time.time():
                return None
            return payload
        except Exception:  # noqa: BLE001
            return None

    # ------------------------------------------------------------------
    # Role & Permission Resolution
    # ------------------------------------------------------------------

    def resolve_role(self, token: str | None = None, user_id: str | None = None) -> str:
        """Map a token (static admin secret or capability token) onto an RBAC role."""
        if user_id and user_id in ROLE_PERMISSIONS:
            return user_id

        if token:
            # 1. Check capability token
            claims = self.verify_capability_token(token)
            if claims and "role" in claims:
                return claims["role"]

            # 2. Check static admin token
            if self._admin_token and hmac.compare_digest(str(token), str(self._admin_token)):
                return "admin"

        return "anonymous"

    def check_permission(
        self,
        operation: str,
        graph_id: str | None = None,
        user_id: str | None = None,
        resource_filter: dict[str, Any] | None = None,
        token: str | None = None,
    ) -> PermissionResult:
        """Decide whether operation may run for the caller."""
        if not operation:
            raise ValueError("check_permission requires a non-empty operation")

        # Check explicit capability token operations allowlist first
        claims = self.verify_capability_token(token or "")
        if claims and "ops" in claims:
            allowed = operation in claims["ops"]
            role = claims.get("role", "capability")
            reason = f"capability token: operation {'permitted' if allowed else 'not in granted operations'}"
            return PermissionResult(
                allowed=allowed,
                decision=PermissionDecision.ALLOW if allowed else PermissionDecision.DENY,
                role=role,
                operation=operation,
                graph_id=graph_id,
                reason=reason,
            )

        role = self.resolve_role(token=token, user_id=user_id)
        permitted_ops = ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS["anonymous"])
        allowed = operation in permitted_ops

        if allowed:
            reason = f"{role} role: operation permitted"
        else:
            reason = (
                f"{role} role: {operation!r} not permitted. "
                f"requires higher privileges or an admin token."
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
        """List the operations the caller may perform."""
        claims = self.verify_capability_token(token or "")
        if claims and "ops" in claims:
            return sorted(claims["ops"])
        role = self.resolve_role(token=token, user_id=user_id)
        return sorted(ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS["anonymous"]))

    def require(
        self,
        operation: str,
        graph_id: str | None = None,
        user_id: str | None = None,
        token: str | None = None,
    ) -> PermissionResult:
        result = self.check_permission(
            operation=operation, graph_id=graph_id, user_id=user_id, token=token
        )
        if not result.allowed:
            raise PermissionError(f"{operation}: {result.reason}")
        return result
