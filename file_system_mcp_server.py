import os
import logging
from pathlib import Path
from typing import List, Iterator, Dict, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class FileSystemMCPServer:
    def __init__(self):
        self.constraints = {
            'max_file_size': 10 * 1024 * 1024,  # 10MB limit
            'exclude_dirs': ['.git', 'node_modules', '__pycache__', '.pytest_cache', 'vendor', 'target', 'build', 'dist']
        }

    def is_persistent_storage(self, path: str) -> bool:
        """Checks if the given path is on persistent storage."""
        # Simple heuristic: check for common mount points for persistent storage
        # This can be expanded based on environment variables or more robust checks.
        return path.startswith('/mnt/') or path.startswith('/persistence')

    def _scan_directory(self, directory: Path, filetypes_filter: Optional[List[str]]) -> Iterator[Path]:
        """Recursively scans a directory for files, respecting exclusion constraints."""
        for entry in directory.iterdir():
            if entry.is_dir():
                if entry.name in self.constraints['exclude_dirs']:
                    continue
                yield from self._scan_directory(entry, filetypes_filter)
            elif entry.is_file():
                if entry.stat().st_size > self.constraints['max_file_size']:
                    logging.warning(f"Skipping large file: {entry}")
                    continue
                if filetypes_filter and entry.suffix not in filetypes_filter:
                    continue
                yield entry

    def scan_and_process_files(
        self, 
        path: str, 
        filetypes_filter: Optional[List[str]] = None,
        scan_and_delete: bool = False,
        batch_size: int = 10
    ) -> Iterator[List[Dict[str, Any]]]:
        """Scans for files, with options for filtering, deletion, and batching."""
        root_path = Path(path)
        if not root_path.is_dir():
            logging.error(f"Provided path is not a valid directory: {path}")
            return

        logging.info(f"Starting scan in {'persistent' if self.is_persistent_storage(path) else 'local'} storage: {path}")

        batch = []
        for file_path in self._scan_directory(root_path, filetypes_filter):
            file_info = {
                'path': str(file_path),
                'size': file_path.stat().st_size,
                'deleted': False
            }

            if scan_and_delete:
                if not self.is_persistent_storage(str(file_path.parent)):
                    try:
                        os.remove(file_path)
                        file_info['deleted'] = True
                        logging.info(f"Deleted file: {file_path}")
                    except OSError as e:
                        file_info['error'] = str(e)
                        logging.error(f"Error deleting file {file_path}: {e}")
                else:
                    file_info['error'] = 'Cannot delete from persistent storage without force_delete=True'
                    logging.warning(f"Prevented deletion of file in persistent storage: {file_path}")
            
            batch.append(file_info)
            if len(batch) >= batch_size:
                yield batch
                batch = []
        
        if batch:
            yield batch

    def process_files(
        self,
        files: List[str],
        scan_and_delete: bool = False,
        batch_size: int = 10,
        force_delete: bool = False
    ) -> Iterator[List[Dict[str, Any]]]:
        """Processes a list of files, with options for deletion and batching."""
        logging.info(f"Starting processing of {len(files)} files.")

        batch = []
        for file_path_str in files:
            file_path = Path(file_path_str)
            if not file_path.is_file():
                logging.warning(f"Skipping non-existent file: {file_path_str}")
                continue

            file_info = {
                'path': str(file_path),
                'size': file_path.stat().st_size,
                'deleted': False
            }

            if scan_and_delete:
                if force_delete or not self.is_persistent_storage(str(file_path.parent)):
                    try:
                        os.remove(file_path)
                        file_info['deleted'] = True
                        logging.info(f"Deleted file: {file_path}")
                    except OSError as e:
                        file_info['error'] = str(e)
                        logging.error(f"Error deleting file {file_path}: {e}")
                else:
                    file_info['error'] = 'Cannot delete from persistent storage without force_delete=True'
                    logging.warning(f"Prevented deletion of file in persistent storage: {file_path}")
            
            batch.append(file_info)
            if len(batch) >= batch_size:
                yield batch
                batch = []
        
        if batch:
            yield batch
