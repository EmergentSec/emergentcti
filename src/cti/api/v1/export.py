"""Blocklist, JSON/text export, and saved export profile endpoints.

Every export applies the *current* allowlist and the *current* TLP policy:
matching observables stay in the database but are never emitted. Ad-hoc
exports use the ``internal`` destination; profiles use their own. TLP:RED
never leaves through any export.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from cti.api.v1.filters import parse_tag_names
from cti.core.database import get_db
from cti.core.dependencies import AuthSubject, get_current_auth, require_admin
from cti.core.redis import cache_get, cache_set
from cti.models.export_profile import ExportDestination, ExportFormat, ExportProfile
from cti.models.observable import Observable, ObservableType
from cti.schemas.export import (
    MAX_AGE_DAYS_LIMIT,
    ExcludedByTlp,
    ExportObservable,
    ExportProfileCreate,
    ExportProfilePreview,
    ExportProfileResponse,
    ExportProfileUpdate,
    JsonExportResponse,
)
from cti.services import (
    allowlist_service,
    export_profile_service,
    observable_service,
    tag_service,
)
from cti.services.tlp import effective_tlp_map

router = APIRouter()

# Ad-hoc exports go to this organization's own controls (firewalls, SIEM).
_AD_HOC_DESTINATION = "internal"
_TAG_QUERY = Query(default=None, description="Match ANY listed tag (repeatable)")


async def _json_export_response(
    db: AsyncSession, observables: list[Observable], filters: dict
) -> JsonExportResponse:
    markings = await effective_tlp_map(db, (obs.id for obs in observables))
    return JsonExportResponse(
        exported_at=datetime.now(UTC),
        count=len(observables),
        filters=filters,
        observables=[
            ExportObservable(
                type=obs.type,
                value=obs.value,
                confidence_score=obs.confidence_score,
                last_seen=obs.last_seen,
                sources=[s.feed.name for s in obs.sources if s.feed],
                tlp=markings.get(obs.id),
                tags=sorted(tag.name for tag in obs.tags),
            )
            for obs in observables
        ],
    )


@router.get("/blocklist/{obs_type}", response_class=PlainTextResponse)
async def get_blocklist(
    obs_type: ObservableType,
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(get_current_auth),
    confidence_min: int = Query(default=70, ge=0, le=100),
    max_age_days: int | None = Query(default=None, ge=1, le=MAX_AGE_DAYS_LIMIT),
    feed_id: uuid.UUID | None = None,
    tag: list[str] | None = _TAG_QUERY,
) -> PlainTextResponse:
    """Plain text blocklist — one IOC per line. For FW/EDL integration."""
    tags = parse_tag_names(tag)
    cache_key = f"blocklist:{obs_type.value}:{confidence_min}:{max_age_days}:{feed_id}"
    if tags:
        cache_key += ":tags=" + ",".join(sorted(tags))

    # The cache only ever holds the pre-policy list. The current allowlist and
    # TLP markings are applied on every request, hit or miss, so a policy or
    # marking change is never masked by a cached blocklist (including entries
    # cached before the allowlist or TLP existed). Only line-safe values are
    # cached or served; lines from an older cache entry are re-checked in case
    # it predates that rule.
    cached = await cache_get(cache_key)
    if cached is not None:
        candidates = [
            v for v in cached.split("\n") if v and observable_service.is_line_safe(v)
        ]
        cache_status = "HIT"
    else:
        candidates = await observable_service.get_blocklist(
            db,
            obs_type=obs_type,
            confidence_min=confidence_min,
            max_age_days=max_age_days,
            feed_id=feed_id,
            tags=tags,
            apply_allowlist=False,
        )
        await cache_set(cache_key, "\n".join(candidates), ttl_seconds=300)
        cache_status = "MISS"

    values, tlp_excluded = await observable_service.apply_blocklist_policy(
        db,
        candidates,
        obs_type=obs_type,
        destination=_AD_HOC_DESTINATION,
    )

    return PlainTextResponse(
        content="\n".join(values),
        media_type="text/plain",
        headers={
            "X-Observable-Count": str(len(values)),
            "X-Cache": cache_status,
            "X-TLP-Excluded": str(tlp_excluded),
        },
    )


@router.get("/json")
async def export_json(
    response: Response,
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(get_current_auth),
    type: ObservableType | None = None,
    confidence_min: int = Query(default=0, ge=0, le=100),
    max_age_days: int | None = Query(default=None, ge=1, le=MAX_AGE_DAYS_LIMIT),
    feed_id: uuid.UUID | None = None,
    limit: int = Query(default=10000, ge=1, le=100000),
    tag: list[str] | None = _TAG_QUERY,
) -> JsonExportResponse:
    """JSON export with filters."""
    tags = parse_tag_names(tag)
    allowlist = await allowlist_service.load_matcher(db)
    observables = await observable_service.get_export_json(
        db,
        obs_type=type,
        confidence_min=confidence_min,
        max_age_days=max_age_days,
        feed_id=feed_id,
        limit=limit,
        tags=tags,
        destination=_AD_HOC_DESTINATION,
        allowlist=allowlist,
    )
    excluded = await observable_service.count_tlp_excluded(
        db,
        obs_type=type,
        confidence_min=confidence_min,
        max_age_days=max_age_days,
        feed_id=feed_id,
        tags=tags,
        destination=_AD_HOC_DESTINATION,
        allowlist=allowlist,
    )
    response.headers["X-TLP-Excluded"] = str(sum(excluded.values()))

    filters: dict = {}
    if type:
        filters["type"] = type.value
    if confidence_min:
        filters["confidence_min"] = confidence_min
    if max_age_days:
        filters["max_age_days"] = max_age_days
    if tags:
        filters["tags"] = tags

    return await _json_export_response(db, observables, filters)


@router.get("/text", response_class=PlainTextResponse)
async def export_text(
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(get_current_auth),
    confidence_min: int = Query(default=0, ge=0, le=100),
    max_age_days: int | None = Query(default=None, ge=1, le=MAX_AGE_DAYS_LIMIT),
    tag: list[str] | None = _TAG_QUERY,
) -> PlainTextResponse:
    """Plain text export — all types mixed, one per line. Never truncated."""
    values, _excluded, tlp_excluded = await observable_service.get_export_values(
        db,
        confidence_min=confidence_min,
        max_age_days=max_age_days,
        tags=parse_tag_names(tag),
        destination=_AD_HOC_DESTINATION,
        line_safe=True,
    )
    return PlainTextResponse(
        content="\n".join(values),
        media_type="text/plain",
        headers={
            "X-Observable-Count": str(len(values)),
            "X-TLP-Excluded": str(sum(tlp_excluded.values())),
        },
    )


# ── Saved export profiles ────────────────────────────────────────────────


async def _get_profile_or_404(db: AsyncSession, profile_id: uuid.UUID) -> ExportProfile:
    profile = await export_profile_service.get_profile(db, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Export profile not found")
    return profile


def _profile_filename(profile: ExportProfile) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", profile.name).strip("-.") or "export"
    return f"{slug}.{'txt' if profile.format is ExportFormat.TEXT else 'json'}"


def _duplicate_name() -> HTTPException:
    return HTTPException(
        status_code=409, detail="An export profile with this name already exists"
    )


def _unknown_feed() -> HTTPException:
    return HTTPException(status_code=422, detail="Feed not found")


def _bad_tags(exc: Exception) -> HTTPException:
    return HTTPException(status_code=422, detail=str(exc))


@router.get("/profiles", response_model=list[ExportProfileResponse])
async def list_export_profiles(
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(get_current_auth),
) -> list[ExportProfileResponse]:
    profiles = await export_profile_service.list_profiles(db)
    return [ExportProfileResponse.model_validate(p) for p in profiles]


@router.post("/profiles", response_model=ExportProfileResponse, status_code=201)
async def create_export_profile(
    data: ExportProfileCreate,
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(require_admin),
) -> ExportProfileResponse:
    try:
        profile = await export_profile_service.create_profile(db, data.model_dump())
    except export_profile_service.DuplicateProfileNameError:
        raise _duplicate_name() from None
    except export_profile_service.ProfileFeedNotFoundError:
        raise _unknown_feed() from None
    except (tag_service.TagValidationError, tag_service.TagNotFoundError) as exc:
        raise _bad_tags(exc) from None
    await db.commit()
    return ExportProfileResponse.model_validate(profile)


@router.get("/profiles/{profile_id}", response_model=ExportProfileResponse)
async def get_export_profile(
    profile_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(get_current_auth),
) -> ExportProfileResponse:
    return ExportProfileResponse.model_validate(await _get_profile_or_404(db, profile_id))


@router.put("/profiles/{profile_id}", response_model=ExportProfileResponse)
async def update_export_profile(
    profile_id: uuid.UUID,
    data: ExportProfileUpdate,
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(require_admin),
) -> ExportProfileResponse:
    profile = await _get_profile_or_404(db, profile_id)
    try:
        profile = await export_profile_service.update_profile(
            db, profile, data.model_dump(exclude_unset=True)
        )
    except export_profile_service.DuplicateProfileNameError:
        raise _duplicate_name() from None
    except export_profile_service.ProfileFeedNotFoundError:
        raise _unknown_feed() from None
    except (tag_service.TagValidationError, tag_service.TagNotFoundError) as exc:
        raise _bad_tags(exc) from None
    await db.commit()
    return ExportProfileResponse.model_validate(profile)


@router.delete("/profiles/{profile_id}", status_code=204)
async def delete_export_profile(
    profile_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(require_admin),
) -> None:
    profile = await _get_profile_or_404(db, profile_id)
    await export_profile_service.delete_profile(db, profile)
    await db.commit()


@router.get("/profiles/{profile_id}/preview", response_model=ExportProfilePreview)
async def preview_export_profile(
    profile_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(get_current_auth),
) -> ExportProfilePreview:
    """Count what the profile would export right now, with a small sample."""
    profile = await _get_profile_or_404(db, profile_id)
    values, excluded, by_tlp = await export_profile_service.get_profile_values(db, profile)
    return ExportProfilePreview(
        count=len(values),
        excluded_allowlisted=excluded,
        excluded_by_tlp=ExcludedByTlp.model_validate(by_tlp),
        sample=values[: export_profile_service.PREVIEW_SAMPLE_SIZE],
    )


@router.get("/profiles/{profile_id}/download", response_model=None)
async def download_export_profile(
    profile_id: uuid.UUID,
    response: Response,
    db: AsyncSession = Depends(get_db),
    _auth: AuthSubject = Depends(get_current_auth),
) -> PlainTextResponse | JsonExportResponse:
    """Evaluate the saved filters against current data and the current allowlist.

    Both formats return every eligible observable — there is no row cap, so
    the download always agrees with the preview count.
    """
    profile = await _get_profile_or_404(db, profile_id)

    tags = export_profile_service.profile_tag_names(profile)
    if profile.format is ExportFormat.TEXT:
        values, _excluded, by_tlp = await export_profile_service.get_profile_values(db, profile)
        return PlainTextResponse(
            content="\n".join(values),
            media_type="text/plain",
            headers={
                "X-Observable-Count": str(len(values)),
                "X-TLP-Excluded": str(sum(by_tlp.values())),
                "Content-Disposition": f'attachment; filename="{_profile_filename(profile)}"',
            },
        )

    allowlist = await allowlist_service.load_matcher(db)
    _, _excluded, by_tlp = await export_profile_service.get_profile_values(db, profile)
    response.headers["X-TLP-Excluded"] = str(sum(by_tlp.values()))
    observables = await observable_service.get_export_json(
        db,
        obs_type=profile.type,
        confidence_min=profile.confidence_min,
        max_age_days=profile.max_age_days,
        feed_id=profile.feed_id,
        limit=None,
        tags=tags,
        destination=profile.destination.value,
        allowlist=allowlist,
    )
    filters: dict = {"profile": profile.name, "confidence_min": profile.confidence_min}
    # Only non-default additions, so pre-#15 profiles produce identical output.
    if profile.destination is not ExportDestination.INTERNAL:
        filters["destination"] = profile.destination.value
    if profile.type:
        filters["type"] = profile.type.value
    if profile.max_age_days:
        filters["max_age_days"] = profile.max_age_days
    if profile.feed_id:
        filters["feed_id"] = str(profile.feed_id)
    if tags:
        filters["tags"] = tags
    return await _json_export_response(db, observables, filters)
