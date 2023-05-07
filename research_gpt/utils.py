import hashlib


def generate_hash(input: str) -> str:
    """
    Generate a SHA256 hash of the input text.

    Args:
        url: The input string.

    Returns:
        The SHA256 hash of the input string.
    """
    sha256_hash = hashlib.sha256(input.encode("utf-8")).hexdigest()
    return sha256_hash