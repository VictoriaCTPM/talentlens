"""
Service to convert a hired Candidate into a TeamMember.
Triggered when candidate.status changes to "hired".
"""
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.database import (
    Candidate,
    CandidateEvent,
    ExtractedData,
    Position,
    TeamMember,
)

logger = logging.getLogger(__name__)


def convert_hired_candidate_to_team_member(
    candidate_id: int,
    db: Session,
) -> TeamMember | None:
    """
    Create a TeamMember from a hired Candidate.

    Returns the new (or existing) TeamMember, or None if conversion fails.
    Does NOT commit — caller must commit the session.
    """
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        logger.warning("convert_hired: candidate %d not found", candidate_id)
        return None

    if candidate.status != "hired":
        logger.warning(
            "convert_hired: candidate %d status is '%s', not 'hired'",
            candidate_id, candidate.status,
        )
        return None

    # Idempotency: already converted
    if candidate.team_member_id:
        existing = db.get(TeamMember, candidate.team_member_id)
        if existing:
            logger.info(
                "convert_hired: candidate %d already linked to team_member %d",
                candidate_id, existing.id,
            )
            return existing

    # Duplicate check: same person already on team (same resume)
    if candidate.resume_document_id:
        position = db.get(Position, candidate.position_id)
        if position:
            duplicate = (
                db.query(TeamMember)
                .filter_by(
                    project_id=position.project_id,
                    resume_document_id=candidate.resume_document_id,
                )
                .first()
            )
            if duplicate:
                logger.info(
                    "convert_hired: TeamMember already exists with same resume "
                    "(member=%d, candidate=%d)",
                    duplicate.id, candidate_id,
                )
                candidate.team_member_id = duplicate.id
                _log_event(candidate_id, "converted_to_team_member", {
                    "team_member_id": duplicate.id,
                    "was_existing": True,
                }, db)
                return duplicate

    position = db.get(Position, candidate.position_id)
    if not position:
        logger.error(
            "convert_hired: position %d not found for candidate %d",
            candidate.position_id, candidate_id,
        )
        return None

    skills = _extract_skills_from_resume(candidate.resume_document_id, db)

    notes_parts = []
    if candidate.ai_score is not None:
        notes_parts.append(
            f"Hired via TalentLens. AI score: {candidate.ai_score:.0f}/100 "
            f"({candidate.ai_verdict or 'N/A'})"
        )
    if candidate.recruiter_notes:
        notes_parts.append(f"Recruiter: {candidate.recruiter_notes}")
    if candidate.interview_notes:
        notes_parts.append(f"Interview: {candidate.interview_notes[:200]}")

    team_member = TeamMember(
        project_id=position.project_id,
        name=candidate.name,
        role=position.title,
        level=position.level,
        start_date=None,
        status="active",
        resume_document_id=candidate.resume_document_id,
        skills=skills,
        notes="\n".join(notes_parts) if notes_parts else None,
    )
    db.add(team_member)
    db.flush()  # get id without committing

    candidate.team_member_id = team_member.id

    _log_event(candidate_id, "converted_to_team_member", {
        "team_member_id": team_member.id,
        "team_member_name": team_member.name,
        "role": team_member.role,
        "level": team_member.level,
        "skills_count": len(skills) if skills else 0,
        "was_existing": False,
    }, db)

    logger.info(
        "Converted candidate %d (%s) → team_member %d (role=%s, project=%d)",
        candidate_id, candidate.name, team_member.id,
        team_member.role, position.project_id,
    )

    return team_member


def _extract_skills_from_resume(resume_document_id: int | None, db: Session) -> list[str]:
    """Pull skills list from resume extracted data."""
    if not resume_document_id:
        return []
    ed = (
        db.query(ExtractedData)
        .filter_by(document_id=resume_document_id)
        .order_by(ExtractedData.id.desc())
        .first()
    )
    if not ed or not ed.structured_data:
        return []
    data = ed.structured_data
    skills = data.get("skills") or data.get("technical_skills") or []
    if isinstance(skills, str):
        skills = [s.strip() for s in skills.split(",") if s.strip()]
    return [str(s) for s in skills[:30]]


def _log_event(candidate_id: int, event_type: str, event_data: dict[str, Any], db: Session) -> None:
    db.add(CandidateEvent(
        candidate_id=candidate_id,
        event_type=event_type,
        event_data=event_data,
    ))
