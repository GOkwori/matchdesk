"""ID3I disposable read-only host preflight, never a live execution authority.

The enclosing host must authenticate identities and inspect database grants through
independent trusted channels. CI supplies only synthetic implementations here.
Neither a signed ID3H receipt nor this preflight can run SQL or enable deployment.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Literal, Protocol

from matchdesk.domain.id3h_approval_reservations import DisposableApprovalReservationStore
from matchdesk.domain.id3h_ci_evidence import EvidenceBoundCIHostSource
from matchdesk.domain.id3h_qualification_host import DisposableApprovalQualificationHost
from matchdesk.domain.id3h_release_approval import (
    ACTION,
    ENVIRONMENT,
    ObservedReleaseFacts,
    ReleaseDenied,
)

_DENIED = "ID3I read-only preflight denied"
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_ROLE = "ci-catalog-reader"


@dataclass(frozen=True, slots=True)
class ObservedCatalogAccess:
    """Host-observed CI role capabilities, not caller-provided privilege claims."""

    workload_id: str
    database_fingerprint: str
    role_name: str
    can_read_catalog: bool
    can_write_data: bool
    can_manage_roles: bool
    can_edit_migration_receipts: bool


class TrustedReadOnlyHostContext(Protocol):
    """Host-side identity and actual privilege inspection contract.

    Implementations used in tests are NOT genuine authentication or DB catalog
    services. Untrusted requests and agent output must never implement this port.
    """

    def authenticated_human(self) -> str:
        """Return an independently verified interactive operator identity."""
        ...

    def observe_catalog_access(self) -> ObservedCatalogAccess:
        """Inspect the current workload role, target and effective privileges."""
        ...


@dataclass(frozen=True, slots=True)
class ReadOnlyPreflightReceipt:
    """Proof of offline inspection only: deliberately carries no execution grant."""

    approval_id: str
    environment: Literal["disposable-ci"] = "disposable-ci"
    execution_authorized: Literal[False] = False
    database_writes_authorized: Literal[False] = False


class DisposableReadOnlyHostPreflight:
    """Combine human separation, read-only role and ID3H one-use checks.

    There is no SQL connection, migration callback, credential, live key service,
    public route or permission to mutate a target. This cannot qualify a real DB.
    """

    def __init__(
        self,
        *,
        source: EvidenceBoundCIHostSource,
        context: TrustedReadOnlyHostContext,
        reservations: DisposableApprovalReservationStore,
    ) -> None:
        """Require the evidence-bound CI source and durable CI reservation type."""
        if (
            type(source) is not EvidenceBoundCIHostSource
            or type(reservations) is not DisposableApprovalReservationStore
            or not callable(getattr(context, "authenticated_human", None))
            or not callable(getattr(context, "observe_catalog_access", None))
        ):
            raise ReleaseDenied(_DENIED)
        self._source = source
        self._context = context
        self._reservations = reservations

    @staticmethod
    def _allowed(
        workload: str,
        human: str,
        access: ObservedCatalogAccess,
        observed: ObservedReleaseFacts,
    ) -> bool:
        """Only an isolated CI catalog-reader identity may inspect this scope."""
        return (
            type(workload) is str
            and _ID.fullmatch(workload) is not None
            and type(human) is str
            and _ID.fullmatch(human) is not None
            and human != workload
            and type(observed) is ObservedReleaseFacts
            and observed.action == ACTION
            and observed.environment == ENVIRONMENT
            and observed.operator_id == workload
            and type(access) is ObservedCatalogAccess
            and access.workload_id == workload
            and access.database_fingerprint == observed.database_fingerprint
            and access.role_name == _ROLE
            and access.can_read_catalog is True
            and access.can_write_data is False
            and access.can_manage_roles is False
            and access.can_edit_migration_receipts is False
        )

    def inspect(self, signed_envelope: str) -> ReadOnlyPreflightReceipt:
        """Deny drift, self-review, role escalation and replay; never run SQL.

        The ID3H approval is for an offline inspection only, not an execution
        grant. Every host observation is repeated after durable consumption;
        a failed post-consumption recheck never restores the single-use ID.
        """
        try:
            workload = self._source.verified_actor()
            human = self._context.authenticated_human()
            access = self._context.observe_catalog_access()
            observed = self._source.observe_release()
            if not self._allowed(workload, human, access, observed):
                raise ReleaseDenied(_DENIED)
            receipt = DisposableApprovalQualificationHost(
                source=self._source, reservations=self._reservations
            ).qualify(signed_envelope)
            # ID3H verifies the exact signed JSON (including duplicate-key
            # rejection) before any reviewer field is used for separation.
            envelope = json.loads(signed_envelope)
            reviewer = envelope["claims"]["reviewer_id"]
            if type(reviewer) is not str or reviewer == human:
                raise ReleaseDenied(_DENIED)
            if (
                self._source.verified_actor() != workload
                or self._context.authenticated_human() != human
                or self._context.observe_catalog_access() != access
                or self._source.observe_release() != observed
            ):
                raise ReleaseDenied(_DENIED)
            return ReadOnlyPreflightReceipt(approval_id=receipt.approval_id)
        except Exception:
            # Do not reveal privileged evidence, or turn an outage into a pass.
            raise ReleaseDenied(_DENIED) from None
