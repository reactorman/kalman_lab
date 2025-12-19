#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Archive files by timestamp

This script finds all files matching a given timestamp pattern and archives them
into a compressed file in the archive directory.

Usage:
    python scripts/archive_by_timestamp.py <timestamp>
    
    timestamp: Date/time pattern to match (e.g., "20251219_123124" or "20251219_1231")
    
Examples:
    python scripts/archive_by_timestamp.py 20251219_123124
    python scripts/archive_by_timestamp.py 20251219_1231
    
The script searches in:
    - logs/
    - measurements/
    
Matching files are compressed into a single archive file placed in:
    - archive/
"""

import os
import sys
import zipfile
from pathlib import Path


def find_files_by_timestamp(timestamp_pattern: str, search_dirs: list) -> list:
    """
    Find all files matching the timestamp pattern in the given directories.
    
    Args:
        timestamp_pattern: Timestamp pattern to search for (e.g., "20251219_123124")
        search_dirs: List of directories to search
        
    Returns:
        List of Path objects for matching files
    """
    matching_files = []
    
    for search_dir in search_dirs:
        if not os.path.exists(search_dir):
            print(f"Warning: Directory {search_dir} does not exist, skipping...")
            continue
            
        for root, dirs, files in os.walk(search_dir):
            for file in files:
                if timestamp_pattern in file:
                    file_path = Path(root) / file
                    matching_files.append(file_path)
    
    return matching_files


def create_archive(files: list, timestamp_pattern: str, archive_dir: Path) -> Path:
    """
    Create a compressed archive containing the given files.
    
    Args:
        files: List of file paths to archive
        timestamp_pattern: Timestamp pattern used for naming the archive
        archive_dir: Directory where the archive will be created
        
    Returns:
        Path to the created archive file
    """
    # Create archive directory if it doesn't exist
    archive_dir.mkdir(parents=True, exist_ok=True)
    
    # Create archive filename
    archive_name = f"archive_{timestamp_pattern}.zip"
    archive_path = archive_dir / archive_name
    
    # If archive already exists, add a counter
    counter = 1
    while archive_path.exists():
        archive_name = f"archive_{timestamp_pattern}_{counter}.zip"
        archive_path = archive_dir / archive_name
        counter += 1
    
    # Create zip archive
    print(f"Creating archive: {archive_path}")
    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in files:
            # Preserve directory structure relative to project root
            # Get relative path from project root
            try:
                arcname = file_path.relative_to(Path.cwd())
            except ValueError:
                # If file is outside project root, use just the filename
                arcname = file_path.name
            
            print(f"  Adding: {file_path} -> {arcname}")
            zipf.write(file_path, arcname)
    
    return archive_path


def main():
    """Main function."""
    if len(sys.argv) != 2:
        print("Usage: python scripts/archive_by_timestamp.py <timestamp>")
        print("\nExample:")
        print("  python scripts/archive_by_timestamp.py 20251219_123124")
        sys.exit(1)
    
    timestamp_pattern = sys.argv[1]
    
    # Get project root (assuming script is in scripts/ directory)
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    # Directories to search
    search_dirs = [
        project_root / "logs",
        project_root / "measurements",
    ]
    
    print(f"Searching for files matching timestamp: {timestamp_pattern}")
    print(f"Search directories: {[str(d) for d in search_dirs]}")
    print()
    
    # Find matching files
    matching_files = find_files_by_timestamp(timestamp_pattern, search_dirs)
    
    if not matching_files:
        print(f"No files found matching timestamp pattern: {timestamp_pattern}")
        sys.exit(1)
    
    print(f"Found {len(matching_files)} matching file(s):")
    for file_path in matching_files:
        print(f"  - {file_path}")
    print()
    
    # Create archive
    archive_dir = project_root / "archive"
    archive_path = create_archive(matching_files, timestamp_pattern, archive_dir)
    
    print()
    print(f"Archive created successfully: {archive_path}")
    print(f"Archive size: {archive_path.stat().st_size / 1024:.2f} KB")
    print(f"\nOriginal files remain in their original locations.")
    print(f"Only the compressed archive is in: {archive_dir}")


if __name__ == '__main__':
    main()

