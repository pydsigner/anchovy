import sys
import typing as t


def simple_frontmatter_parser(content: str) -> dict:
    """
    Read metadata from the front of a markdown-formatted text in a very simple
    YAML-like format, without value parsing.
    """
    meta = {}
    lines = content.splitlines()

    for line in lines:
        if ':' not in line:
            break
        key, value = line.split(':', 1)
        if not key.isidentifier():
            break
        meta[key.strip()] = value.strip()

    print(meta, '...')
    return meta


def get_toml_frontmatter_parser():
    if sys.version_info < (3, 11):
        import tomli as tomllib
    else:
        import tomllib
    return tomllib.loads


def get_yaml_frontmatter_parser():
    from ruamel.yaml import YAML
    return YAML(typ='safe').load


FrontMatterParser = t.Callable[[str], dict]
FrontMatterParserName = t.Literal['simple', 'toml', 'yaml']

FRONTMATTER_PARSER_FACTORIES: dict[FrontMatterParserName, t.Callable[[], FrontMatterParser]] = {
    'simple': lambda: simple_frontmatter_parser,
    'toml': get_toml_frontmatter_parser,
    'yaml': get_yaml_frontmatter_parser,
}


def get_frontmatter_parser(parser: FrontMatterParserName | FrontMatterParser) -> FrontMatterParser:
    if callable(parser):
        return parser
    return FRONTMATTER_PARSER_FACTORIES[parser]()
