from __future__ import annotations

import shutil
import typing as t
from pathlib import Path

from .core import Step
from .dependencies import pip_dependency, web_exec_dependency
from .simple import BaseCommandStep

if t.TYPE_CHECKING:
    from _typeshed import StrOrBytesPath


class CWebPStep(BaseCommandStep):
    """
    A WebP image conversion/optimization Step using cwebp.
    """
    def __init__(self,
                 quality: int = 75,
                 lossless: bool = False,
                 options: t.Iterable[str] = ()):
        """
        @quality controls the size of the output image, traded off with quality
        for lossy images and processing time for lossless images. @lossless can
        be used to avoid image degradation, at the cost of file size. See
        https://developers.google.com/speed/webp/docs/cwebp for further @options
        and explanations.
        """
        self.options = ['-q', str(quality)]
        if lossless:
            self.options.append('-lossless')
        self.options.extend(options)

    @classmethod
    def get_dependencies(cls):
        return super().get_dependencies() | {
            web_exec_dependency('cwebp', 'https://developers.google.com/speed/webp/download'),
        }

    def get_command(self, input_path: Path, output_path: Path) -> list[StrOrBytesPath]:
        return ['cwebp', input_path, *self.options, '-o', output_path]


class ImageMagickStep(BaseCommandStep):
    """
    A completely customizable image transformation Step using ImageMagick.
    """
    def __init__(self, options: t.Iterable[str] = ()):
        """
        If simple image conversion is desired, @options can be left empty.
        Otherwise, see https://imagemagick.org/script/command-line-options.php,
        or perhaps use `IMThumbnailStep()` instead.
        """
        self.options = options

    @classmethod
    def get_dependencies(cls):
        return super().get_dependencies() | {
            web_exec_dependency(
                'imagemagick',
                'https://imagemagick.org/script/download.php',
                'magick'
            ),
        }

    def get_command(self, input_path: Path, output_path: Path) -> list[StrOrBytesPath]:
        return ['magick', input_path, *self.options, output_path]


class IMThumbnailStep(ImageMagickStep):
    """
    A more specialized ImageMagick Step intended for thumbnailing.
    """
    def __init__(self,
                 dimensions: str = '300x300',
                 fill_color: str | None = None,
                 extra_options: t.Iterable[str] = ()):
        """
        @dimensions can be any "geometry" supported by imagemagick, and sets
        the target thumbnail size. Aspect ratio will be preserved. If output
        images need uniform dimensions, @fill_color can be supplied to fill the
        extra space; use something like '#0000' for transparent padding.
        Additional custom options may be passed using @extra_options.
        """
        options = ['-resize', dimensions]
        if fill_color:
            # https://legacy.imagemagick.org/discourse-server/viewtopic.php?t=26971
            options.extend([
                '-background', fill_color,
                '-gravity', 'center',
                '-extent', dimensions
            ])
        options.extend(extra_options)
        super().__init__(options)


class PillowStep(Step):
    """
    A simple Pillow step which can convert and/or thumbnail images.
    """
    def __init__(self, thumbnail: tuple[int, int] | None = None):
        self.thumbnail = thumbnail

    @classmethod
    def get_dependencies(cls):
        return super().get_dependencies() | {
            pip_dependency(
                'Pillow',
                check_name='PIL'
            ),
        }

    def __call__(self, path: Path, output_paths: list[Path]):
        from PIL import Image

        with Image.open(path) as img:
            if self.thumbnail:
                img.thumbnail(self.thumbnail)
            output_paths[0].parent.mkdir(parents=True, exist_ok=True)
            img.save(output_paths[0])

        for target_path in output_paths[1:]:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(output_paths[0], target_path)


class OptipngStep(BaseCommandStep):
    """
    A PNG optimization step using optipng.
    """
    def __init__(self,
                 optimization_level: int | None = None,
                 extra_options: t.Iterable[str] = ()):
        """
        The default @optimization_level may vary based on your build of optipng
        but is probably 2. Extra flags may be supplied using @extra_options.
        """
        self.options = ['-o', str(optimization_level)] if optimization_level is not None else []
        self.options.extend(extra_options)

    @classmethod
    def get_dependencies(cls):
        return super().get_dependencies() | {
            web_exec_dependency('optipng', 'http://optipng.sourceforge.net'),
        }

    def get_command(self, input_path: Path, output_path: Path) -> list[StrOrBytesPath]:
        return ['optipng', *self.options, input_path, '-out', output_path]
