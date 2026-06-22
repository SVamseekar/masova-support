"""
Authentication dependencies for the masova-support FastAPI endpoints.

Trust model (see docs/SECURITY_NOTES or task-1 report for full rationale):

This service has no access to the Java `shared-security` JWT signing key,
so it CANNOT independently verify a customer's identity JWT today. Instead:

- `require_caller_identity` gates `/agent/chat` behind a shared secret
  (`AGENT_API_KEY`), distinct from the existing `AGENT_TOKEN` used for
  outbound calls to the backend. A trusted caller (the API gateway) may also
  forward a `X-Customer-Id` header carrying the customer id it has already
  verified via JWT on its side. This service treats that header as the
  "verified" customerId for the duration of the request.
- `enforce_customer_id_match` rejects any request body `customerId` that
  does not match the header-derived identity, closing the impersonation gap
  where any caller with the shared API key could previously claim to be any
  customer purely via the request body.
- `require_internal_trigger_auth` gates `/agents/{name}/trigger` behind a
  SEPARATE secret (`INTERNAL_TRIGGER_SECRET`), since these endpoints fire
  internal scheduled jobs and have no concept of a "customer" caller at all.

IMPORTANT CAVEAT: because there is no cryptographic verification of the
`X-Customer-Id` header itself, the customerId trust still ultimately depends
on the gateway/caller being honest when it sets that header — this service
trusts whoever holds AGENT_API_KEY to have already done JWT verification
upstream. Real JWT verification (e.g. via the shared-security public key or
a JWKS endpoint) should replace this once available to this service.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from fastapi import Header, HTTPException

from .utils.config import get_config

logger = logging.getLogger(__name__)


@dataclass
class CallerIdentity:
    """Resolved identity of the caller, derived from a verified credential.

    `customer_id` is None for callers that authenticated with a valid
    AGENT_API_KEY but did not present a verified customer identity (e.g.
    anonymous/guest chat sessions).
    """
    customer_id: Optional[str] = None


def _extract_bearer_or_api_key(authorization: Optional[str], x_api_key: Optional[str]) -> Optional[str]:
    """Pull a raw credential value out of either header, preferring Authorization."""
    if authorization:
        if authorization.startswith("Bearer "):
            return authorization[len("Bearer "):].strip()
        return authorization.strip()
    if x_api_key:
        return x_api_key.strip()
    return None


def require_caller_identity(
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    x_customer_id: Optional[str] = Header(default=None, alias="X-Customer-Id"),
) -> CallerIdentity:
    """FastAPI dependency: require a valid AGENT_API_KEY credential.

    Returns a CallerIdentity whose `customer_id` is taken from the
    `X-Customer-Id` header (expected to be set by a trusted gateway that has
    already verified the customer's JWT), not from the request body.

    Raises 401 if no valid credential is presented, or if AGENT_API_KEY is
    not configured server-side (fail closed).
    """
    config = get_config()
    expected_key = getattr(config, "agent_api_key", "") or ""

    if not expected_key:
        logger.warning("AGENT_API_KEY not configured — rejecting all /agent/chat callers")
        raise HTTPException(status_code=401, detail="Authentication not configured")

    presented = _extract_bearer_or_api_key(authorization, x_api_key)
    if not presented or presented != expected_key:
        raise HTTPException(status_code=401, detail="Missing or invalid credentials")

    return CallerIdentity(customer_id=x_customer_id or None)


def enforce_customer_id_match(identity: CallerIdentity, body_customer_id: Optional[str]) -> None:
    """Reject requests where the body's customerId doesn't match the verified identity.

    - No body customerId claimed → always OK (anonymous chat, or caller
      simply didn't pass one even though it has a verified identity).
    - Body customerId claimed but caller has no verified identity → 403
      (caller is trying to impersonate a customer without proof).
    - Body customerId claimed and differs from verified identity → 403.
    """
    if body_customer_id is None:
        return

    if identity.customer_id is None or body_customer_id != identity.customer_id:
        logger.warning(
            "Rejected customerId mismatch: body claimed %r, verified identity was %r",
            body_customer_id,
            identity.customer_id,
        )
        raise HTTPException(status_code=403, detail="customerId does not match verified identity")


def require_internal_trigger_auth(
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> None:
    """FastAPI dependency: require a valid INTERNAL_TRIGGER_SECRET credential.

    Gates /agents/{name}/trigger, which fires internal scheduled jobs and
    must not be publicly callable. This is a service-to-service secret, not
    tied to any customer or manager identity (this service cannot verify a
    manager-role JWT — see module docstring).

    Raises 401 if no valid credential is presented, or if
    INTERNAL_TRIGGER_SECRET is not configured server-side (fail closed).
    """
    config = get_config()
    expected_secret = getattr(config, "internal_trigger_secret", "") or ""

    if not expected_secret:
        logger.warning("INTERNAL_TRIGGER_SECRET not configured — rejecting all trigger callers")
        raise HTTPException(status_code=401, detail="Authentication not configured")

    presented = _extract_bearer_or_api_key(authorization, x_api_key)
    if not presented or presented != expected_secret:
        raise HTTPException(status_code=401, detail="Missing or invalid credentials")
