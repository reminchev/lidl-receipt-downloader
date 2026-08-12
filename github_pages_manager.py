"""GitHub Pages deployment utilities.

Provides helpers for organizing and publishing reports to GitHub Pages.
"""

import json
from pathlib import Path
from typing import Optional, Dict, List


class GitHubPagesManager:
    """Manages organization of files for GitHub Pages deployment."""

    def __init__(self, gh_pages_dir: Optional[str] = None):
        """Initialize GitHub Pages manager.
        
        Args:
            gh_pages_dir: Path to docs folder (defaults to ./docs)
        """
        self.gh_pages_dir = Path(gh_pages_dir or "docs")
        self.reports_dir = self.gh_pages_dir / "reports"
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        """Create necessary directories."""
        self.gh_pages_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        
        # Create .nojekyll to prevent Jekyll processing
        nojekyll = self.gh_pages_dir / ".nojekyll"
        if not nojekyll.exists():
            nojekyll.touch()

    def copy_report_file(self, source: Path, dest_name: Optional[str] = None) -> Path:
        """Copy a report file to GitHub Pages reports directory.
        
        Args:
            source: Source file path
            dest_name: Optional destination filename (defaults to source name)
            
        Returns:
            Path to the copied file
        """
        source = Path(source)
        if not source.exists():
            raise FileNotFoundError(f"File not found: {source}")
        
        dest_name = dest_name or source.name
        dest = self.reports_dir / dest_name
        dest.write_bytes(source.read_bytes())
        return dest

    def create_index_metadata(self, files_info: Dict[str, str]) -> None:
        """Create metadata JSON for index.html to know which reports are available.
        
        Args:
            files_info: Dict with keys like 'xlsx', 'chart', 'seasonal', etc.
        """
        metadata_file = self.gh_pages_dir / "reports-metadata.json"
        
        # Convert absolute paths to relative for web access
        web_paths = {}
        for key, path in files_info.items():
            if path:
                path_obj = Path(path)
                web_paths[key] = f"reports/{path_obj.name}"
        
        metadata_file.write_text(json.dumps(web_paths, indent=2, ensure_ascii=False), encoding='utf-8')
        return str(metadata_file)

    def get_published_reports(self) -> Dict[str, str]:
        """Get list of all published reports.
        
        Returns:
            Dict mapping report type to relative web path
        """
        metadata_file = self.gh_pages_dir / "reports-metadata.json"
        
        if not metadata_file.exists():
            return {}
        
        return json.loads(metadata_file.read_text(encoding='utf-8'))

    def list_reports(self) -> List[str]:
        """List all report files in the reports directory.
        
        Returns:
            List of report filenames
        """
        if not self.reports_dir.exists():
            return []
        
        return sorted([f.name for f in self.reports_dir.iterdir() if f.is_file()])

    def cleanup_old_reports(self, keep_latest: int = 5) -> List[str]:
        """Remove old reports, keeping only the latest N.
        
        Args:
            keep_latest: Number of latest reports to keep
            
        Returns:
            List of deleted files
        """
        if not self.reports_dir.exists():
            return []
        
        # Get all files sorted by modification time (newest first)
        files = sorted(
            self.reports_dir.iterdir(),
            key=lambda f: f.stat().st_mtime,
            reverse=True
        )
        
        deleted = []
        for f in files[keep_latest:]:
            if f.is_file():
                f.unlink()
                deleted.append(f.name)
        
        return deleted

    def generate_manifest(self) -> str:
        """Generate a manifest file listing all reports.
        
        Returns:
            Path to the generated manifest file
        """
        manifest_path = self.gh_pages_dir / "MANIFEST.md"
        
        reports = self.list_reports()
        manifest_content = "# Published Reports\n\n"
        
        if reports:
            manifest_content += "## Available Reports\n\n"
            for report in reports:
                manifest_content += f"- [`{report}`](reports/{report})\n"
        else:
            manifest_content += "No reports published yet.\n"
        
        manifest_path.write_text(manifest_content, encoding='utf-8')
        return str(manifest_path)


def setup_github_pages(enable: bool = True) -> Dict[str, Path]:
    """Quick setup for GitHub Pages.
    
    Args:
        enable: Whether to enable GitHub Pages setup
        
    Returns:
        Dict with paths to created/managed directories
    """
    manager = GitHubPagesManager()
    
    return {
        'docs_dir': manager.gh_pages_dir,
        'reports_dir': manager.reports_dir,
        'index_file': manager.gh_pages_dir / 'index.html',
        'nojekyll_file': manager.gh_pages_dir / '.nojekyll',
    }
