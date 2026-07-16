"""
SHA-256 document fingerprinting.

The original notebook defined this hashing logic twice (once as a standalone
`generate_sha256` function, once again as `StatefulVectorPipeline.calculate_file_hash`,
byte-for-byte identical apart from chunk size). This is the single copy both
the registry and the pipeline now import.
"""

import hashlib


def generate_sha256(file_path, chunk_size: int = 65536) -> str:
    """
    Generate the SHA-256 hash of a file's contents.

    Parameters:
        file_path: Path to the file (PDF).
        chunk_size: Bytes read per iteration.

    Returns:
        Hex digest string.
    """
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for block in iter(lambda: f.read(chunk_size), b""):
            sha256.update(block)
    return sha256.hexdigest()
