from hashlib import md5
import math
import os

# from https://github.com/girder/django-s3-file-field/blob/master/s3_file_field/_multipart.py
from typing import List, Optional, Tuple


def mb(bytes_size: int) -> int:
    return bytes_size * 2 ** 20


def gb(bytes_size: int) -> int:
    return bytes_size * 2 ** 30


def tb(bytes_size: int) -> int:
    return bytes_size * 2 ** 40


class DANDIEtag:

    REGEX = r"[0-9a-f]{32}-\d{1,4}"
    MAX_LENGTH = 37

    def __init__(self, file_size: int):
        self._file_size: int = file_size
        self._part_sizes: Optional[Tuple[int, ...]] = None
        self._md5_digests: List[bytes] = []

    @property
    def part_sizes(self) -> Tuple[int, ...]:
        if self._part_sizes is None:
            self._part_sizes = self.gen_part_sizes(self._file_size)
        return self._part_sizes

    def __str__(self) -> str:
        if len(self._md5_digests) != len(self._part_sizes):
            # TODO: too harsh for __str__? just say "incomplete"?
            raise RuntimeError(
                f"Collected {len(self._md5_digests)} out of {len(self._part_sizes)}"
            )
        parts_digest = md5(b"".join(self._md5_digests)).hexdigest()
        return f"{parts_digest}-{len(self._md5_digests)}"

    # from https://github.com/girder/django-s3-file-field/blob/master/s3_file_field/_multipart.py
    # but removing yielding sequential index. Could be wrapped
    # with enumerate where needed
    @classmethod
    def gen_part_sizes(cls, file_size: int) -> Tuple[int, ...]:
        """Generator to yield sequential part sizes given a file size"""
        part_size = mb(64)  # cls.part_size

        # S3 multipart limits: https://docs.aws.amazon.com/AmazonS3/latest/dev/qfacts.html

        if file_size > tb(5):
            raise ValueError("File is larger than the S3 maximum object size.")

        # 10k is the maximum number of allowed parts allowed by S3
        max_parts = 10_000
        if math.ceil(file_size / part_size) >= max_parts:
            part_size = math.ceil(file_size / max_parts)

        # 5MB is the minimum part size allowed by S3
        min_part_size = mb(5)
        if part_size < min_part_size:
            part_size = min_part_size

        # 5GB is the maximum part size allowed by S3
        max_part_size = gb(5)
        if part_size > max_part_size:
            part_size = max_part_size

        d, m = divmod(file_size, part_size)
        sizes = [part_size] * d
        if m:
            sizes.append(m)
        return tuple(sizes)

    @classmethod
    def from_file(cls, path: str) -> "DANDIEtag":
        etag = cls(file_size=os.path.getsize(path))
        with open(path, "rb") as f:
            for part in etag.part_sizes:
                etag.update(f.read(part))
        return etag

    def update(self, block):
        """Update etag with the new block of data"""
        if len(self._md5_digests) == self.part_sizes:
            raise RuntimeError(
                f"Trying to update {self} with a new block having already"
                f" processed {len(self._md5_digests)}"
            )
        self._md5_digests.append(md5(block).digest())


if __name__ == "__main__":
    import sys

    print(f"Get {len(DANDIEtag.gen_part_sizes(tb(5)))} parts for 5TB file")
    for p in sys.argv[1:]:
        print(f"{p}: {DANDIEtag.from_file(p)}")
