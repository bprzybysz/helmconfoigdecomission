from mcp.server.fastmcp import FastMCP
from file_system_mcp_server import FileSystemMCPServer
from typing import List, Dict, Any, Optional

mcp = FastMCP("File System MCP Server")
file_system_server = FileSystemMCPServer()

@mcp.tool()
def scan_files(
    path: str,
    filetypes_filter: Optional[List[str]] = None,
    scan_and_delete: bool = False,
    batch_size: int = 10
) -> List[Dict[str, Any]]:
    """Scans for files, with options for filtering, deletion, and batching.

    Args:
        path (str): The root directory to start scanning from.
        filetypes_filter (Optional[List[str]]): A list of file extensions (e.g., ['.txt', '.log']) to filter by. Defaults to None.
        scan_and_delete (bool): If True, files will be deleted during the scan if they are not in persistent storage. Defaults to False.
        batch_size (int): The number of file infos to return in each batch. Defaults to 10.

    Returns:
        List[Dict[str, Any]]: A list of dictionaries, each containing information about a scanned file (path, size, deleted, error).
    """
    all_results = []
    for batch in file_system_server.scan_and_process_files(path, filetypes_filter, scan_and_delete, batch_size):
        all_results.extend(batch)
    return all_results

@mcp.tool()
def process_files(
    files: List[str],
    scan_and_delete: bool = False,
    batch_size: int = 10,
    force_delete: bool = False
) -> List[Dict[str, Any]]:
    """Processes a list of files, with options for deletion and batching.

    Args:
        files (List[str]): A list of absolute file paths to process.
        scan_and_delete (bool): If True, files will be deleted during processing. Defaults to False.
        batch_size (int): The number of file infos to return in each batch. Defaults to 10.
        force_delete (bool): If True, allows deletion of files even if they are in persistent storage. Use with caution. Defaults to False.

    Returns:
        List[Dict[str, Any]]: A list of dictionaries, each containing information about a processed file (path, size, deleted, error).
    """
    all_results = []
    for batch in file_system_server.process_files(files, scan_and_delete, batch_size, force_delete):
        all_results.extend(batch)
    return all_results

if __name__ == '__main__':
    print("Starting File System MCP Server...")
    mcp.run()
