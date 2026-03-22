from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.truth_file import TruthFile
from app.schemas.project import ProjectCreate

TRUTH_FILE_TYPES = [
    "story_bible",
    "volume_outline",
    "book_rules",
    "current_state",
    "particle_ledger",
    "pending_hooks",
    "chapter_summaries",
    "subplot_board",
    "emotional_arcs",
    "character_matrix",
]


async def create_project_with_truth_files(
    db: AsyncSession, data: ProjectCreate
) -> Project:
    project = Project(**data.model_dump())
    db.add(project)
    await db.flush()

    # Initialize 10 truth files
    for file_type in TRUTH_FILE_TYPES:
        truth_file = TruthFile(
            project_id=project.id,
            file_type=file_type,
            content={},
            version=1,
        )
        db.add(truth_file)

    await db.flush()
    return project
