"""manage tar files for user exports"""
import io
import tarfile
from typing import Any, Optional
from uuid import uuid4
from django.core.files import File


class BookwyrmTarFile(tarfile.TarFile):
    """Create tar files for user exports"""

    def write_bytes(self, data: bytes) -> None:
        """Add a file containing bytes to the archive"""
        buffer = io.BytesIO(data)
        info = tarfile.TarInfo("archive.json")
        info.size = len(data)
        self.addfile(info, fileobj=buffer)

    def add_image(
        self, image: Any, filename: Optional[str] = None, directory: Any = ""
    ) -> None:
        """
        Add an image to the tar archive
        :param str filename: overrides the file name set by image
        :param str directory: the directory in the archive to put the image
        """
        if filename is not None:
            file_type = image.name.rsplit(".", maxsplit=1)[-1]
            filename = f"{directory}{filename}.{file_type}"
        else:
            filename = f"{directory}{image.name}"

        info = tarfile.TarInfo(name=filename)
        info.size = image.size

        self.addfile(info, fileobj=image)

    def read(self, filename: str) -> Any:
        """read data from the tar"""
        if reader := self.extractfile(filename):
            return reader.read()
        return None

    def write_image_to_file(self, filename: str, file_field: Any) -> None:
        """add an image to the tar"""
        extension = filename.rsplit(".")[-1]
        if buf := self.extractfile(filename):
            filename = f"{str(uuid4())}.{extension}"
            file_field.save(filename, File(buf))
