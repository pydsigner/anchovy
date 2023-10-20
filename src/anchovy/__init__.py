"""
Anchovy is a minimal, unopinionated file-processing framework equipped with a
complete static website generation toolkit.
"""
from .core import Context, InputBuildSettings, Matcher, PathCalc, Rule, Step
from .css import AnchovyCSSStep
from .custody import Custodian, CustodyEntry
from .dependencies import Dependency, PipDependency, WebExecDependency
from .images import CWebPStep, ImageMagickStep, IMThumbnailStep, PillowStep, OptipngStep
from .include import RequestsFetchStep, UnpackArchiveStep, URLLibFetchStep
from .jinja import JinjaExtendedMarkdownStep, JinjaMarkdownStep, JinjaRenderStep
from .minify import AssetMinifierStep, CSSMinifierStep, HTMLMinifierStep, ResourcePackerStep
from .paths import DirPathCalc, OutputDirPathCalc, REMatcher, WorkingDirPathCalc
from .simple import DirectCopyStep
