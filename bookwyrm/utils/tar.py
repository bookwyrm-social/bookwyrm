from uuid import uuid4
from django.core.files import File
import tarfile
import io


class BookwyrmTarFile(tarfile.TarFile):
    def write_bytes(self, data: bytes, filename="archive.json"):
        """Add a file containing :data: bytestring with name :filename: to the archive"""
        buffer = io.BytesIO(data)
        info = tarfile.TarInfo("archive.json")
        info.size = len(data)
        self.addfile(info, fileobj=buffer)

    def add_image(self, image, filename=None, directory=""):
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

    def read(self, filename):
        with self.extractfile(filename) as reader:
            return reader.read()

    def write_image_to_file(self, filename, file_field):
        extension = filename.rsplit(".")[-1]
        with self.extractfile(filename) as reader:
            filename = f"{str(uuid4())}.{extension}"
            file_field.save(filename, File(reader))
