"""Local estimates are not substitutes for provider-billed message usage."""
from functools import lru_cache
import tiktoken

@lru_cache(maxsize=1)
def encoding():
    return tiktoken.get_encoding("o200k_base")


def count_text(text: str) -> int:
    # Treat special-token-looking user strings as normal text.
    return len(encoding().encode(text, disallowed_special=()))
