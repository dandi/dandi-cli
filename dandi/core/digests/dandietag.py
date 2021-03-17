# from https://github.com/girder/django-s3-file-field/blob/master/s3_file_field/_multipart.py
from hashlib import md5
import math
import os
from typing import List, Optional, Tuple


def mb(bytes_size: int) -> int:
    return bytes_size * 2 ** 20


def gb(bytes_size: int) -> int:
    return bytes_size * 2 ** 30


def tb(bytes_size: int) -> int:
    return bytes_size * 2 ** 40


class DandiETag:
    REGEX = r"[0-9a-f]{32}-\d{1,4}"
    MAX_STR_LENGTH = 37

    # S3 multipart limits: https://docs.aws.amazon.com/AmazonS3/latest/dev/qfacts.html
    # 10k is the maximum number of allowed parts allowed by S3
    MAX_PARTS = 10_000
    # 5MB is the minimum part size allowed by S3
    MIN_PART_SIZE = mb(5)
    # 5GB is the maximum part size allowed by S3
    MAX_PART_SIZE = gb(5)

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
        """Method to calculate sequential part sizes given a file size"""
        part_size = mb(64)

        if file_size > tb(5):
            raise ValueError("File is larger than the S3 maximum object size.")

        if math.ceil(file_size / part_size) >= cls.MAX_PARTS:
            part_size = math.ceil(file_size / cls.MAX_PARTS)

        if part_size < cls.MIN_PART_SIZE:
            part_size = cls.MIN_PART_SIZE

        if part_size > cls.MAX_PART_SIZE:
            part_size = cls.MAX_PART_SIZE

        d, m = divmod(file_size, part_size)
        sizes = [part_size] * d
        if m:
            sizes.append(m)
        return tuple(sizes)

    @classmethod
    def from_file(cls, path: str) -> "DandiETag":
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

    print(f"Get {len(DandiETag.gen_part_sizes(tb(5)))} parts for 5TB file")
    for p in sys.argv[1:]:
        print(f"{p}: {DandiETag.from_file(p)}")
