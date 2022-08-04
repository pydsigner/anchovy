import typing as t

import tinycss2
import tinycss2.ast as c2ast


Rule = c2ast.AtRule | c2ast.QualifiedRule
LineNodes = Rule | c2ast.Declaration


def strip_whitespace(content: list[c2ast.Node], beginning: bool = True, end: bool = True):
    start = 0
    stop = len(content) - 1
    if beginning:
        while start < stop:
            if not isinstance(content[start], c2ast.WhitespaceToken):
                break
            start += 1
    if end:
        while stop > start:
            if not isinstance(content[stop], c2ast.WhitespaceToken):
                break
            stop -= 1
    return content[start:stop+1]


def mk_whitespace(node: c2ast.Node, whitespace: str):
    if isinstance(node, Rule) and node.content:
        line = node.content[-1].source_line
        col = node.content[-1].source_column
    else:
        line = node.source_line
        col = node.source_column

    return c2ast.WhitespaceToken(
        line,
        col,
        whitespace
    )


def wrap_newlines(content: t.Iterable[c2ast.Node]):
    first = True
    for node in content:
        if first:
            yield mk_whitespace(node, '\n')
            first = False
        if not isinstance(node, c2ast.WhitespaceToken):
            yield node
            if isinstance(node, LineNodes):
                yield mk_whitespace(node, '\n')


def find_selector_start(index: int, content: list[c2ast.Node]):
    while index:
        node = content[index]
        if isinstance(node, c2ast.LiteralToken) and node == ';':
            index += 1
            break
        if isinstance(node, c2ast.CurlyBracketsBlock):
            index += 1
            break
        index -= 1
    while isinstance(content[index], c2ast.WhitespaceToken):
        index += 1
    return index


def split_selector(content: list[c2ast.Node]):
    selector: list[c2ast.Node] = []
    for node in content:
        if isinstance(node, c2ast.LiteralToken) and node == ',':
            yield strip_whitespace(selector, end=False)
            selector = []
        else:
            selector.append(node)

    if selector:
        yield strip_whitespace(selector, end=False)


def merge_selectors(sel_1: list[c2ast.Node], sel_2: list[c2ast.Node]):
    sel_1 = strip_whitespace(sel_1)
    sel_2 = strip_whitespace(sel_2)
    first = sel_2[0]
    if isinstance(first, c2ast.LiteralToken) and first.value in {'&', ':'}:
        if first == '&':
            sel_2 = strip_whitespace(sel_2[1:])
            assert not isinstance(sel_2[0], c2ast.IdentToken)
    else:
        sel_1.append(mk_whitespace(sel_1[-1], ' '))

    sel_2.append(mk_whitespace(sel_2[-1], ' '))
    return [*sel_1, *sel_2]


def pump_at_rule(parent: c2ast.QualifiedRule, at_rule: c2ast.AtRule):
    new_qualified = c2ast.QualifiedRule(
        at_rule.source_line,
        at_rule.source_column,
        parent.prelude,
        []
    )
    new_at = c2ast.AtRule(
        at_rule.source_line,
        at_rule.source_column,
        at_rule.at_keyword,
        at_rule.lower_at_keyword,
        at_rule.prelude,
        [new_qualified]
    )

    for node in t.cast(list[c2ast.Node], at_rule.content):
        if isinstance(node, c2ast.QualifiedRule):
            new_at.content.extend(
                flatten_qual(
                    merge_selectors(parent.prelude, node.prelude),
                    node.content,
                    parse_declarations=False
                )
            )
        else:
            new_qualified.content.append(node)

    new_qualified.content = list(wrap_newlines(tinycss2.parse_declaration_list(new_qualified.content)))
    new_at.content = list(wrap_newlines(new_at.content))
    return new_at


def flatten_at(rule: c2ast.AtKeywordToken, sel: list[c2ast.Node], body: list[c2ast.Node]):
    at_rule = c2ast.AtRule(
        rule.source_line,
        rule.source_column,
        rule.value,
        rule.lower_value,
        list(sel),
        []
    )
    at_rule.content.extend(flatten_children(at_rule, body))
    at_rule.content = list(wrap_newlines(at_rule.content))
    yield at_rule


def flatten_qual(sel: list[c2ast.Node], body: list[c2ast.Node], parse_declarations=True):
    rule = c2ast.QualifiedRule(
        sel[0].source_line,
        sel[0].source_column,
        list(sel),
        []
    )
    children: list[Rule] = []
    for child in flatten_children(rule, body):
        if isinstance(child, c2ast.QualifiedRule):
            child.prelude = merge_selectors(sel, child.prelude)
            children.append(child)
        elif isinstance(child, c2ast.AtRule):
            children.append(pump_at_rule(rule, child))
    rule.prelude = strip_whitespace(rule.prelude, end=False)
    if parse_declarations:
        rule.content = tinycss2.parse_declaration_list(rule.content)
    rule.content = list(wrap_newlines(rule.content))
    yield rule
    yield from children


def flatten_children(parent: Rule, content: list[c2ast.Node]):
    last_safe = 0
    for i, node in enumerate(content):
        if isinstance(node, c2ast.CurlyBracketsBlock):
            start = find_selector_start(i-1, content)
            assert start >= last_safe
            parent.content.extend(strip_whitespace(content[last_safe:start]))
            sel = strip_whitespace(content[start:i], end=False)
            if isinstance(sel[0], c2ast.AtKeywordToken):
                yield from flatten_at(sel[0], sel[1:], node.content)
            else:
                for sub_sel in split_selector(sel):
                    yield from flatten_qual(sub_sel, node.content)
            last_safe = i + 1

    parent.content.extend(strip_whitespace(content[last_safe:]))


def flatten_one(node: c2ast.Node):
    if isinstance(node, c2ast.AtRule) and node.content:
        token = c2ast.AtKeywordToken(node.source_line, node.source_column, node.at_keyword)
        yield from flatten_at(token, node.prelude, node.content)
    elif isinstance(node, c2ast.QualifiedRule):
        yield from flatten_qual(node.prelude, node.content)
    elif not isinstance(node, c2ast.WhitespaceToken):
        yield node


def flatten_all(nodes: list[c2ast.Node]):
    for node in nodes:
        yield from wrap_newlines(flatten_one(node))


def process(code: str):
    return tinycss2.serialize(flatten_all(tinycss2.parse_stylesheet(code)))
