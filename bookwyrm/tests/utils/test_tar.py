import os
import pytest
from bookwyrm.utils.tar import BookwyrmTarFile


@pytest.fixture
def read_tar():
    archive_path = "../data/bookwyrm_account_export.tar.gz"
    with open(archive_path, "rb") as archive_file:
        with BookwyrmTarFile.open(mode="r:gz", fileobj=archive_file) as tar:
            yield tar


@pytest.fixture
def write_tar():
    archive_path = "/tmp/test.tar.gz"
    with open(archive_path, "wb") as archive_file:
        with BookwyrmTarFile.open(mode="w:gz", fileobj=archive_file) as tar:
            yield tar

    os.remove(archive_path)


def test_write_bytes(write_tar):
    write_tar.write_bytes(b"ABCDEF")
