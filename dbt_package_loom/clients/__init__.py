# Copyright 2023 Nicholas Yager and Contributors. Adapted under Apache 2.0.


def is_gzipped(content: bytes) -> bool:
    return content[:2] == b"\x1f\x8b"
