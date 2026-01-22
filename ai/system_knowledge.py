"""System Knowledge Service - Provides self-awareness to the AI.

This module gathers static information about the system structure, codebase,
and documentation to give the AI context about "what it is" and "where it lives".
"""

import logging
import os

logger = logging.getLogger(__name__)


class SystemKnowledge:
    """Service for retrieving system architecture and codebase structure."""

    def __init__(self, root_path: str) -> None:
        """Initialize with the project root path."""
        self.root_path = root_path

    def get_system_overview(self) -> str:
        """Get a high-level overview of the system from README.md."""
        readme_path = os.path.join(self.root_path, "README.md")
        try:
            if os.path.exists(readme_path):
                with open(readme_path, "r") as f:
                    content = f.read()
                    # Extract the first 50 lines or until the first major section
                    lines = content.split("\n")
                    summary = []
                    for line in lines:
                        if line.startswith("## Project Structure"):
                            break
                        summary.append(line)
                    return "\n".join(summary)
            return "System overview not available."
        except Exception as e:
            logger.error(f"Failed to read README.md: {e}")
            return "Error reading system overview."

    def get_project_structure(self) -> str:
        """Scan the directory to generate a tree view of key components."""
        structure = ["Project Structure:"]

        # Define key directories to scan
        key_dirs = {
            "backend/src/homepot": "Backend Core",
            "frontend/src/pages": "Frontend Pages",
            "ai": "AI Services",
            "docs": "Documentation",
        }

        for rel_path, description in key_dirs.items():
            full_path = os.path.join(self.root_path, rel_path)
            if os.path.exists(full_path):
                structure.append(f"\n{description} ({rel_path}):")
                try:
                    # List files, excluding __pycache__ and hidden files
                    files = sorted(
                        [
                            f
                            for f in os.listdir(full_path)
                            if not f.startswith(".") and not f.startswith("__")
                        ]
                    )
                    # Limit to top 15 files to avoid context overflow
                    for f in files[:15]:
                        structure.append(f"  - {f}")
                    if len(files) > 15:
                        structure.append(f"  - ... ({len(files) - 15} more)")
                except Exception as e:
                    structure.append(f"  - Error scanning: {e}")

        return "\n".join(structure)

    def get_database_schema_info(self) -> str:
        """Extract database schema from SQLAlchemy models."""
        schema = ["Database Schema (derived from SQLAlchemy models):"]
        
        model_files = [
            "backend/src/homepot/models.py",
            "backend/src/homepot/app/models/AnalyticsModel.py"
        ]

        for rel_path in model_files:
            full_path = os.path.join(self.root_path, rel_path)
            if not os.path.exists(full_path):
                continue
                
            try:
                with open(full_path, "r") as f:
                    content = f.read()
                    lines = content.split("\n")
                    
                    current_table = None
                    for line in lines:
                        line = line.strip()
                        if line.startswith("class ") and "(Base)" in line:
                            current_table = line.split("class ")[1].split("(")[0]
                            schema.append(f"\nTable: {current_table}")
                        elif current_table and " = Column(" in line:
                            # Extract column name and type roughly
                            col_name = line.split(" = ")[0]
                            col_def = line.split("Column(")[1].split(")")[0]
                            schema.append(f"  - {col_name}: {col_def}")
            except Exception as e:
                logger.error(f"Failed to parse model file {rel_path}: {e}")

        return "\n".join(schema)

    def get_full_system_context(self) -> str:
        """Combine overview, structure, and DB schema into a single context string."""
        return (
            f"SYSTEM IDENTITY:\n{self.get_system_overview()}\n\n"
            f"{self.get_database_schema_info()}\n\n"
            f"{self.get_project_structure()}"
        )
