"""Allowlist policy: validation, canonicalization, and read-time matching.

Allowlisting is reversible by design. Entries never modify observables or
their sources; every read and export evaluates the *current* entries, so
adding or removing one takes effect immediately.
"""

from __future__ import annotations

import ipaddress
import uuid
from collections.abc import Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from cti.models.allowlist import AllowlistEntry, AllowlistKind
from cti.models.observable import ObservableType

# Canonical values are capped in UTF-8 *bytes*: the unique index on
# (kind, observable_type, value) cannot hold arbitrarily wide multibyte keys.
MAX_VALUE_BYTES = 2048
_MAX_HOSTNAME_LENGTH = 253
_MAX_LABEL_LENGTH = 63
# Characters that mean the value is a URL, email, host:port or wildcard pattern
# rather than a bare domain.
_NON_DOMAIN_CHARS = frozenset("/:@*?#\\")

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address
IPNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network


class AllowlistValidationError(ValueError):
    """The submitted entry is not a valid policy."""


class DuplicateAllowlistEntryError(Exception):
    """An entry with the same canonical policy already exists."""


# ── Canonicalization ─────────────────────────────────────────────────────


def normalize_hostname(value: str) -> str:
    """Canonical hostname form: trimmed, lowercase, without the root trailing dot."""
    host = value.strip().lower()
    if host.endswith("."):
        host = host[:-1]
    return host


def _validate_bare_domain(value: str, what: str) -> str:
    """Normalize and validate a bare hostname for exact and suffix entries alike."""
    host = normalize_hostname(value)
    if not host:
        raise AllowlistValidationError(f"{what} is required")
    if any(ch.isspace() or not ch.isprintable() or ch in _NON_DOMAIN_CHARS for ch in host):
        raise AllowlistValidationError(
            f"{what} must be a bare domain such as example.com "
            "(no scheme, port, path or wildcard)"
        )
    if len(host) > _MAX_HOSTNAME_LENGTH:
        raise AllowlistValidationError(f"{what} is too long")
    for label in host.split("."):
        if not label:
            raise AllowlistValidationError(
                f"{what} must not start with a dot or contain empty labels"
            )
        if len(label) > _MAX_LABEL_LENGTH:
            raise AllowlistValidationError("Domain labels must be 63 characters or fewer")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return host
    raise AllowlistValidationError("Use an exact or CIDR entry for IP addresses")


def canonicalize_entry(
    kind: AllowlistKind,
    value: str,
    observable_type: ObservableType | None,
) -> tuple[str, ObservableType]:
    """Validate an entry and return its canonical ``(value, observable_type)``.

    Raises:
        AllowlistValidationError: with a message suitable for showing to the user.
    """
    canonical, canonical_type = _canonicalize(kind, value, observable_type)
    if len(canonical.encode("utf-8")) > MAX_VALUE_BYTES:
        raise AllowlistValidationError(
            f"Value is too long: at most {MAX_VALUE_BYTES} bytes when UTF-8 encoded"
        )
    return canonical, canonical_type


def _canonicalize(
    kind: AllowlistKind,
    value: str,
    observable_type: ObservableType | None,
) -> tuple[str, ObservableType]:
    text = value.strip()
    if not text:
        raise AllowlistValidationError("Value is required")

    if kind is AllowlistKind.CIDR:
        if observable_type not in (None, ObservableType.IP_ADDR):
            raise AllowlistValidationError("CIDR entries apply only to ip-addr observables")
        try:
            network = ipaddress.ip_network(text, strict=False)
        except ValueError:
            raise AllowlistValidationError(
                "Value must be an IPv4 or IPv6 CIDR range such as 10.0.0.0/8 or 2001:db8::/32"
            ) from None
        return str(network), ObservableType.IP_ADDR

    if kind is AllowlistKind.DOMAIN_SUFFIX:
        if observable_type not in (None, ObservableType.DOMAIN_NAME):
            raise AllowlistValidationError(
                "Domain suffix entries apply only to domain-name observables"
            )
        return _validate_bare_domain(text, "Domain suffix"), ObservableType.DOMAIN_NAME

    # exact
    if observable_type is None:
        raise AllowlistValidationError("Exact entries require an observable type")
    if observable_type is ObservableType.IP_ADDR:
        try:
            return str(ipaddress.ip_address(text)), observable_type
        except ValueError:
            pass
        if "/" in text:
            raise AllowlistValidationError(
                "Exact ip-addr entries must be a single address; use a CIDR entry for ranges"
            )
        raise AllowlistValidationError("Value must be a valid IPv4 or IPv6 address")
    if observable_type is ObservableType.DOMAIN_NAME:
        return _validate_bare_domain(text, "Domain name"), observable_type
    # Remaining types are literal: compared verbatim, with no trimming, case
    # folding or host extraction.
    return value, observable_type


# ── Matching ─────────────────────────────────────────────────────────────


class AllowlistMatcher:
    """In-memory snapshot of the allowlist for matching many observables.

    Build one per request from the current entries; do not cache it across
    requests, or a policy change would not take effect immediately.
    """

    def __init__(self, entries: Iterable[AllowlistEntry] = ()) -> None:
        self._exact: dict[tuple[ObservableType, str], list[uuid.UUID]] = {}
        self._suffixes: dict[str, list[uuid.UUID]] = {}
        self._networks: dict[int, list[tuple[IPNetwork, uuid.UUID]]] = {4: [], 6: []}
        # version → prefix length → integer network address → entry ids. An
        # address lookup probes one key per distinct prefix length (at most
        # 33 for IPv4, 129 for IPv6) instead of scanning every network.
        self._network_index: dict[int, dict[int, dict[int, list[uuid.UUID]]]] = {4: {}, 6: {}}
        # Exact IP entries as address objects, for range-valued observables.
        self._exact_ips: dict[int, list[tuple[IPAddress, uuid.UUID]]] = {4: [], 6: []}
        self._empty = True

        for entry in entries:
            self._empty = False
            if entry.kind is AllowlistKind.EXACT:
                key = (entry.observable_type, entry.value)
                self._exact.setdefault(key, []).append(entry.id)
                if entry.observable_type is ObservableType.IP_ADDR:
                    try:
                        address = ipaddress.ip_address(entry.value)
                    except ValueError:
                        continue
                    self._exact_ips[address.version].append((address, entry.id))
            elif entry.kind is AllowlistKind.DOMAIN_SUFFIX:
                self._suffixes.setdefault(entry.value, []).append(entry.id)
            elif entry.kind is AllowlistKind.CIDR:
                try:
                    network = ipaddress.ip_network(entry.value, strict=False)
                except ValueError:
                    continue  # unreachable for validated rows; never match on garbage
                self._networks[network.version].append((network, entry.id))
                self._network_index[network.version].setdefault(network.prefixlen, {}).setdefault(
                    int(network.network_address), []
                ).append(entry.id)

    @property
    def empty(self) -> bool:
        return self._empty

    def match(self, obs_type: ObservableType, value: str) -> list[uuid.UUID]:
        """Return the IDs of every entry that allowlists this observable."""
        if self._empty:
            return []
        if obs_type is ObservableType.IP_ADDR:
            return self._match_ip(value)
        if obs_type is ObservableType.DOMAIN_NAME:
            return self._match_domain(value)
        # No implicit host matching for URLs/emails: verbatim, type-specific only.
        return list(self._exact.get((obs_type, value), ()))

    def is_allowlisted(self, obs_type: ObservableType, value: str) -> bool:
        return bool(self.match(obs_type, value))

    def _match_ip(self, value: str) -> list[uuid.UUID]:
        text = value.strip()

        try:
            address = ipaddress.ip_address(text)
        except ValueError:
            address = None
        if address is not None:
            matched = list(self._exact.get((ObservableType.IP_ADDR, str(address)), ()))
            value_int = int(address)
            for prefixlen, by_network in self._network_index[address.version].items():
                shift = address.max_prefixlen - prefixlen
                matched.extend(by_network.get((value_int >> shift) << shift, ()))
            return matched

        if "/" not in text:
            return []
        try:
            network = ipaddress.ip_network(text, strict=False)
        except ValueError:
            return []
        # A range-valued indicator is suppressed when it covers any allowlisted
        # address or overlaps any allowlisted range: exporting it would still
        # block protected addresses.
        matched = [eid for ip, eid in self._exact_ips[network.version] if ip in network]
        matched.extend(
            eid
            for net, eid in self._networks[network.version]
            if network.overlaps(net)  # type: ignore[arg-type]
        )
        return matched

    def _match_domain(self, value: str) -> list[uuid.UUID]:
        host = normalize_hostname(value)
        matched = list(self._exact.get((ObservableType.DOMAIN_NAME, host), ()))
        if self._suffixes and host:
            labels = host.split(".")
            # Label-boundary suffixes: "a.example.com" → itself, "example.com", "com".
            for i in range(len(labels)):
                matched.extend(self._suffixes.get(".".join(labels[i:]), ()))
        return matched


# ── Persistence ──────────────────────────────────────────────────────────


async def list_entries(db: AsyncSession) -> list[AllowlistEntry]:
    result = await db.execute(
        select(AllowlistEntry).order_by(AllowlistEntry.created_at.desc(), AllowlistEntry.id)
    )
    return list(result.scalars().all())


async def load_matcher(db: AsyncSession) -> AllowlistMatcher:
    """Load the current policy from the database (authoritative, uncached)."""
    result = await db.execute(select(AllowlistEntry).order_by(AllowlistEntry.created_at))
    return AllowlistMatcher(result.scalars().all())


async def create_entry(
    db: AsyncSession,
    kind: AllowlistKind,
    value: str,
    observable_type: ObservableType | None,
    reason: str,
) -> AllowlistEntry:
    """Validate, canonicalize and store an entry.

    Raises:
        AllowlistValidationError: invalid value/type combination.
        DuplicateAllowlistEntryError: same canonical policy already exists.
    """
    canonical, canonical_type = canonicalize_entry(kind, value, observable_type)

    existing = await db.execute(
        select(AllowlistEntry.id).where(
            AllowlistEntry.kind == kind,
            AllowlistEntry.observable_type == canonical_type,
            AllowlistEntry.value == canonical,
        )
    )
    if existing.first() is not None:
        raise DuplicateAllowlistEntryError

    entry = AllowlistEntry(
        kind=kind, value=canonical, observable_type=canonical_type, reason=reason
    )
    db.add(entry)
    try:
        await db.flush()
    except IntegrityError:
        # Lost a race with a concurrent identical create.
        await db.rollback()
        raise DuplicateAllowlistEntryError from None
    await db.refresh(entry)
    return entry


async def delete_entry(db: AsyncSession, entry_id: uuid.UUID) -> bool:
    entry = await db.get(AllowlistEntry, entry_id)
    if entry is None:
        return False
    await db.delete(entry)
    await db.flush()
    return True


def filter_values(
    matcher: AllowlistMatcher, obs_type: ObservableType, values: Sequence[str]
) -> list[str]:
    """Drop allowlisted values of a single observable type, preserving order."""
    if matcher.empty:
        return list(values)
    return [v for v in values if not matcher.is_allowlisted(obs_type, v)]
