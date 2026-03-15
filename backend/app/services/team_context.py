"""
TeamContextService — builds structured team context strings for AI prompts.

Used by all 4 analysis modes to ground the AI in the actual project team
composition, skills coverage, and what people are currently working on.
"""
import logging
from collections import Counter

logger = logging.getLogger(__name__)


class TeamContextService:
    """Builds team context string for AI prompts from live DB data."""

    # ── Public API ──────────────────────────────────────────────────────────

    def get_team_context(self, project_id: int) -> str:
        """
        Returns a formatted string describing the current team.
        Injected into ALL AI analysis mode prompts.
        """
        from app.models.database import Document, ExtractedData, SessionLocal, TeamMember

        db = SessionLocal()
        try:
            members = (
                db.query(TeamMember)
                .filter(
                    TeamMember.project_id == project_id,
                    TeamMember.status == "active",
                )
                .order_by(TeamMember.role, TeamMember.name)
                .all()
            )

            if not members:
                return ""

            # Group by role
            role_groups: dict[str, list] = {}
            for m in members:
                role_groups.setdefault(m.role or "Other", []).append(m)

            # Build skill frequency across whole team
            all_skills: list[str] = []
            for m in members:
                if m.skills:
                    all_skills.extend(m.skills)
            skill_counts = Counter(all_skills)
            top_skills = [f"{sk} ({cnt})" for sk, cnt in skill_counts.most_common(8)]
            # Skills present on 0 members — detect obvious gaps from JD baseline
            # (we can't know what we don't know, so just note uncovered areas)

            lines: list[str] = [
                f"## Current Project Team ({len(members)} active members)",
                "",
            ]

            for role, role_members in role_groups.items():
                lines.append(f"### {role} ({len(role_members)}):")
                for m in role_members:
                    since = ""
                    if m.start_date:
                        since = f" (since {m.start_date.strftime('%b %Y')})"
                    # Only prepend level if not already contained in role name
                    level_str = ""
                    if m.level and m.level.lower() not in (m.role or "").lower():
                        level_str = f"{m.level.capitalize()} "
                    lines.append(f"- {m.name}, {level_str}{m.role}{since}")

                    if m.skills:
                        lines.append(f"  Skills: {', '.join(m.skills[:12])}")

                    # Pull recent work from linked reports
                    recent_work = self._get_recent_work(m.id, db)
                    if recent_work:
                        lines.append(f"  Recent work: {recent_work}")

                lines.append("")

            # Team skill summary
            lines.append("### Team Skill Summary:")
            if top_skills:
                lines.append(f"Strong in: {', '.join(top_skills)}")

            # Report-based observations
            observations = self._get_team_observations(project_id, db)
            if observations:
                lines.append("")
                lines.append("### Team Observations from Reports:")
                for obs in observations:
                    lines.append(f"- {obs}")

            return "\n".join(lines)

        except Exception as e:
            logger.warning("TeamContextService.get_team_context failed: %s", e)
            return ""
        finally:
            db.close()

    def get_reports_context(self, project_id: int, member_id: int | None = None) -> str:
        """
        Returns a concise summary of what the team (or a specific member) has
        actually been working on, based on weekly reports and interview notes.
        Used for the JD Reality Check and context enrichment.
        """
        from app.models.database import Document, ExtractedData, SessionLocal

        db = SessionLocal()
        try:
            q = (
                db.query(Document)
                .filter(
                    Document.project_id == project_id,
                    Document.doc_type.in_(["report", "client_report"]),
                    Document.status == "processed",
                )
                .order_by(Document.created_at.desc())
            )
            if member_id is not None:
                q = q.filter(Document.team_member_id == member_id)

            reports = q.limit(10).all()
            if not reports:
                return ""

            lines: list[str] = [
                f"## Weekly Reports Summary ({len(reports)} reports):",
                "",
            ]

            for doc in reports:
                ed = (
                    db.query(ExtractedData)
                    .filter_by(document_id=doc.id)
                    .first()
                )
                if not ed:
                    continue
                data = ed.structured_data or {}
                date_str = doc.created_at.strftime("%b %d") if doc.created_at else ""

                # Extract key info from report
                author = data.get("author") or data.get("developer_name") or ""
                next_steps = data.get("next_steps") or []
                blockers = data.get("blockers") or []
                submitted = data.get("candidates_submitted") or []
                placed = data.get("candidates_placed") or []

                parts = []
                if author:
                    parts.append(f"Author: {author}")
                if submitted:
                    parts.append(f"Submitted: {len(submitted)} candidate(s)")
                if placed:
                    parts.append(f"Placed: {len(placed)}")
                if blockers:
                    parts.append(f"Blockers: {'; '.join(str(b) for b in blockers[:2])}")
                if next_steps:
                    parts.append(f"Next steps: {'; '.join(str(s) for s in next_steps[:2])}")

                if parts:
                    lines.append(f"[{date_str}] {' | '.join(parts)}")

            return "\n".join(lines)

        except Exception as e:
            logger.warning("TeamContextService.get_reports_context failed: %s", e)
            return ""
        finally:
            db.close()

    # ── Private helpers ──────────────────────────────────────────────────────

    def _get_recent_work(self, member_id: int, db) -> str:
        """Extract a one-line summary of what this member is working on from reports."""
        from app.models.database import Document, ExtractedData

        reports = (
            db.query(Document)
            .filter(
                Document.team_member_id == member_id,
                Document.doc_type.in_(["report", "client_report"]),
                Document.status == "processed",
            )
            .order_by(Document.created_at.desc())
            .limit(2)
            .all()
        )

        items: list[str] = []
        for doc in reports:
            ed = db.query(ExtractedData).filter_by(document_id=doc.id).first()
            if not ed:
                continue
            data = ed.structured_data or {}
            next_steps = data.get("next_steps") or []
            for s in next_steps[:1]:
                text = str(s).strip()
                if text and len(text) < 120:
                    items.append(text)

        return "; ".join(items) if items else ""

    def _get_team_observations(self, project_id: int, db) -> list[str]:
        """
        Scan the most recent reports across all team members and extract
        recurring themes, blockers, and patterns.
        """
        from app.models.database import Document, ExtractedData

        reports = (
            db.query(Document)
            .filter(
                Document.project_id == project_id,
                Document.doc_type.in_(["report", "client_report"]),
                Document.status == "processed",
            )
            .order_by(Document.created_at.desc())
            .limit(6)
            .all()
        )

        all_blockers: list[str] = []
        all_next_steps: list[str] = []
        placed_count = 0

        for doc in reports:
            ed = db.query(ExtractedData).filter_by(document_id=doc.id).first()
            if not ed:
                continue
            data = ed.structured_data or {}
            all_blockers.extend(data.get("blockers") or [])
            all_next_steps.extend(data.get("next_steps") or [])
            placed = data.get("candidates_placed") or []
            placed_count += len(placed)

        observations: list[str] = []

        if placed_count > 0:
            observations.append(
                f"{placed_count} candidate(s) placed across recent reports"
            )

        # Surface unique blockers (cap at 2)
        seen: set[str] = set()
        for b in all_blockers[:4]:
            text = str(b).strip()[:100]
            if text and text.lower() not in seen:
                seen.add(text.lower())
                observations.append(f"Blocker: {text}")
            if len(observations) >= 3:
                break

        return observations
