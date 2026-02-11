import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from cti.core.database import get_db
from cti.core.dependencies import CurrentUser
from cti.schemas.report import ReportCreate, ReportListResponse, ReportResponse
from cti.services import report_service

router = APIRouter()


@router.post("", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def create_report(
    data: ReportCreate,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> ReportResponse:
    """Create a new report and queue generation."""
    report = await report_service.create_report(db, data, user.id)
    from cti.worker import generate_report_task

    generate_report_task.delay(str(report.id))
    return ReportResponse.model_validate(report)


@router.get("", response_model=ReportListResponse)
async def list_reports(
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
) -> ReportListResponse:
    """List all reports with pagination."""
    items, total = await report_service.list_reports(db, page=page, size=size)
    return ReportListResponse(
        items=[ReportResponse.model_validate(r) for r in items],
        total=total,
    )


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(
    report_id: uuid.UUID,
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> ReportResponse:
    """Get a single report by ID."""
    report = await report_service.get_report(db, report_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Report not found"
        )
    return ReportResponse.model_validate(report)


@router.get("/{report_id}/download")
async def download_report(
    report_id: uuid.UUID,
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Download a generated report file."""
    report = await report_service.get_report(db, report_id)
    if not report or not report.file_path or report.status != "ready":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found or not ready",
        )
    return FileResponse(
        report.file_path,
        media_type="text/html",
        filename=f"{report.title}.html",
    )


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report(
    report_id: uuid.UUID,
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a report and its generated file."""
    deleted = await report_service.delete_report(db, report_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Report not found"
        )
