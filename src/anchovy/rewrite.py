"""
Steps for rewriting references to input files to their corresponding output
paths.
"""
import typing as t
from pathlib import Path


from .dependencies import Dependency, PipDependency
from .simple import BaseStandardStep


def no_op(reference: str):
    return reference


class BaseRewriteStep(BaseStandardStep):
    """
    A Step which rewrites references to files in the build based on a chooser
    function and the custodian graph.
    """
    def __init__(self,
                 chooser: t.Callable[[str, set[str]], str],
                 preprocess: t.Callable[[str], str] | None = None,
                 postprocess: t.Callable[[str], str] | None = None):
        self.chooser = chooser
        self.preprocess = preprocess or no_op
        self.postprocess = postprocess or no_op

    def find_descendants(self, key: str):
        """
        Find all descendants of the given key in the custodian graph.
        """
        immediate = (k for k in self.context.custodian.graph if key in self.context.custodian.graph[k])
        descendants = set()
        for k in immediate:
            descendants.add(k)
            descendants.update(self.find_descendants(k))
        return descendants

    def translate_reference(self, reference: str):
        """
        Find and select a descendant of the given reference, applying pre- and
        post-processing.
        """
        options = self.find_descendants(self.preprocess(reference))
        chosen = self.chooser(reference, options) if options else reference
        return self.postprocess(chosen)


class HTMLRewriteStep(BaseRewriteStep):
    """
    A Step which rewrites URLs in HTML to replace references to input files
    with their corresponding output files.
    """
    @classmethod
    def get_dependencies(cls) -> set[Dependency]:
        return {
            PipDependency('lxml'),
        }

    def __call__(self, path: Path, output_paths: list[Path]):
        import lxml.html
        data = path.read_text(encoding=self.encoding)
        transformed = t.cast(str, lxml.html.rewrite_links(data, self.translate_reference))
        with self.ensure_outputs(output_paths):
            with output_paths[0].open('w', encoding=self.encoding) as f:
                f.write(transformed)
