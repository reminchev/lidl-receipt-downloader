#!/usr/bin/env python3
"""Publish generated reports to GitHub Pages.

This script helps copy reports to the docs/reports directory and
prepare them for GitHub Pages deployment.

Usage:
    python publish_to_github_pages.py <report_file>
    python publish_to_github_pages.py <report_directory>
"""

import sys
import shutil
from pathlib import Path
from typing import Optional, List


def publish_report(source_path: str, gh_pages_dir: Optional[str] = None) -> List[str]:
    """Publish one or more reports to GitHub Pages.
    
    Args:
        source_path: Path to report file or directory
        gh_pages_dir: Path to GitHub Pages docs directory (defaults to ./docs)
        
    Returns:
        List of published file paths
    """
    source = Path(source_path).resolve()
    
    if not source.exists():
        raise FileNotFoundError(f"File or directory not found: {source}")
    
    # Determine GitHub Pages directory
    if gh_pages_dir:
        gh_dir = Path(gh_pages_dir).resolve()
    else:
        # Default to ./docs in the project root
        script_dir = Path(__file__).resolve().parent
        gh_dir = script_dir / "docs"
    
    reports_dir = gh_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    published = []
    
    if source.is_file():
        # Copy single file
        if source.suffix.lower() in {'.html', '.xlsx'}:
            dest = reports_dir / source.name
            shutil.copy2(source, dest)
            published.append(str(dest))
            print(f"✓ Published: {dest}")
        else:
            print(f"⚠ Skipped (unsupported format): {source.name}")
    
    elif source.is_dir():
        # Copy all reports from directory
        for file in source.iterdir():
            if file.suffix.lower() in {'.html', '.xlsx'} and 'lidl_receipts' in file.name:
                dest = reports_dir / file.name
                shutil.copy2(file, dest)
                published.append(str(dest))
                print(f"✓ Published: {dest}")
    
    if not published:
        print("⚠ No reports were published.")
        return []
    
    print(f"\n📊 Successfully published {len(published)} file(s)")
    print(f"📁 Location: {reports_dir}")
    print(f"🌐 Available at: https://your-username.github.io/lidl-receipt-downloader/reports/")
    
    return published


def generate_metadata(reports_dir: Path, output_file: Path) -> None:
    """Generate metadata JSON for the index page.
    
    Args:
        reports_dir: Directory containing reports
        output_file: Path to output metadata JSON
    """
    import json
    from datetime import datetime
    
    metadata = {
        "last_updated": datetime.now().isoformat(),
        "reports": []
    }
    
    if reports_dir.exists():
        for file in sorted(reports_dir.iterdir()):
            if file.is_file() and file.suffix.lower() in {'.html', '.xlsx'}:
                metadata["reports"].append({
                    "name": file.name,
                    "size": file.stat().st_size,
                    "modified": datetime.fromtimestamp(file.stat().st_mtime).isoformat(),
                    "url": f"reports/{file.name}"
                })
    
    output_file.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding='utf-8')


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python publish_to_github_pages.py <report_file_or_directory>")
        print("\nExample:")
        print("  python publish_to_github_pages.py ~/Documents/lidl_receipts_20250120_120000_price_analysis.xlsx")
        print("  python publish_to_github_pages.py ~/Documents/")
        sys.exit(1)
    
    source_path = sys.argv[1]
    gh_pages_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        published = publish_report(source_path, gh_pages_dir)
        
        if published:
            # Generate metadata
            if gh_pages_dir:
                gh_dir = Path(gh_pages_dir)
            else:
                gh_dir = Path(__file__).resolve().parent / "docs"
            
            generate_metadata(gh_dir / "reports", gh_dir / "reports-metadata.json")
            print("\n✨ Metadata updated!")
            
            print("\n📝 Next steps:")
            print("  1. Review files in docs/reports/")
            print("  2. Run: git add docs/reports/")
            print("  3. Run: git commit -m 'Publish price analysis reports'")
            print("  4. Run: git push origin main")
            print("\n🚀 Reports will be available at GitHub Pages!")
            
        sys.exit(0)
    
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
