import logging
import os
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from cti.models.report import Report
from cti.schemas.report import ReportCreate

logger = logging.getLogger(__name__)


async def create_report(
    db: AsyncSession, data: ReportCreate, user_id: uuid.UUID
) -> Report:
    report = Report(
        title=data.title,
        report_type=data.report_type,
        parameters=data.parameters,
        format=data.format,
        status="pending",
        generated_by=user_id,
    )
    db.add(report)
    await db.flush()
    await db.refresh(report)
    return report


async def get_report(db: AsyncSession, report_id: uuid.UUID) -> Report | None:
    result = await db.execute(select(Report).where(Report.id == report_id))
    return result.scalar_one_or_none()


async def list_reports(
    db: AsyncSession,
    user_id: uuid.UUID | None = None,
    page: int = 1,
    size: int = 20,
) -> tuple[list[Report], int]:
    query = select(Report)
    count_query = select(func.count()).select_from(Report)

    if user_id is not None:
        query = query.where(Report.generated_by == user_id)
        count_query = count_query.where(Report.generated_by == user_id)

    total = await db.scalar(count_query) or 0

    offset = (page - 1) * size
    query = query.order_by(Report.created_at.desc()).offset(offset).limit(size)
    result = await db.execute(query)
    items = list(result.scalars().all())

    return items, total


async def delete_report(db: AsyncSession, report_id: uuid.UUID) -> bool:
    report = await get_report(db, report_id)
    if not report:
        return False

    # Delete the file from disk if it exists
    if report.file_path and os.path.exists(report.file_path):
        try:
            os.remove(report.file_path)
        except OSError:
            logger.warning("Failed to delete report file: %s", report.file_path)

    await db.delete(report)
    await db.flush()
    return True
