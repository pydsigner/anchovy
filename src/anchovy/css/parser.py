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
    for n in content:
        if first:
            yield mk_whitespace(n, '\n')
            first = False
        if not isinstance(n, c2ast.WhitespaceToken):
            yield n
            if isinstance(n, LineNodes):
                yield mk_whitespace(n, '\n')


def find_selector_start(index: int, content: list[c2ast.Node]):
    while index:
        n = content[index]
        if isinstance(n, c2ast.LiteralToken) and n == ';':
            index += 1
            break
        if isinstance(n, c2ast.CurlyBracketsBlock):
            index += 1
            break
        index -= 1
    while isinstance(content[index], c2ast.WhitespaceToken):
        index += 1
    return index


def split_selector(content: list[c2ast.Node]):
    selector: list[c2ast.Node] = []
    for n in content:
        if isinstance(n, c2ast.LiteralToken) and n == ',':
            yield strip_whitespace(selector, end=False)
            selector = []
        else:
            selector.append(n)

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

    for n in t.cast(list[c2ast.Node], at_rule.content):
        if isinstance(n, c2ast.QualifiedRule):
            new_at.content.extend(
                flatten_qual(
                    merge_selectors(parent.prelude, n.prelude),
                    n.content,
                    parse_declarations=False
                )
            )
        else:
            new_qualified.content.append(n)

    new_qualified.content = list(wrap_newlines(tinycss2.parse_declaration_list(new_qualified.content)))
    new_at.content = list(wrap_newlines(new_at.content))
    return new_at


def flatten_at(ar: c2ast.AtKeywordToken, sel: list[c2ast.Node], body: list[c2ast.Node]):
    rule = c2ast.AtRule(
        ar.source_line,
        ar.source_column,
        ar.value,
        ar.lower_value,
        list(sel),
        []
    )
    rule.content.extend(flatten_children(rule, body))
    rule.content = list(wrap_newlines(rule.content))
    yield rule


def flatten_qual(sel: list[c2ast.Node], body: list[c2ast.Node], parse_declarations=True):
    rule = c2ast.QualifiedRule(
        sel[0].source_line,
        sel[0].source_column,
        list(sel),
        []
    )
    children: list[Rule] = []
    for c in flatten_children(rule, body):
        if isinstance(c, c2ast.QualifiedRule):
            c.prelude = merge_selectors(sel, c.prelude)
            children.append(c)
        elif isinstance(c, c2ast.AtRule):
            children.append(pump_at_rule(rule, c))
    rule.prelude = strip_whitespace(rule.prelude, end=False)
    if parse_declarations:
        rule.content = tinycss2.parse_declaration_list(rule.content)
    rule.content = list(wrap_newlines(rule.content))
    yield rule
    yield from children


def flatten_children(parent: Rule, content: list[c2ast.Node]):
    last_safe = 0
    for i, n in enumerate(content):
        if isinstance(n, c2ast.CurlyBracketsBlock):
            start = find_selector_start(i-1, content)
            assert start >= last_safe
            parent.content.extend(strip_whitespace(content[last_safe:start]))
            sel = strip_whitespace(content[start:i], end=False)
            if isinstance(sel[0], c2ast.AtKeywordToken):
                yield from flatten_at(sel[0], sel[1:], n.content)
            else:
                for sub_sel in split_selector(sel):
                    yield from flatten_qual(sub_sel, n.content)
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


if __name__ == '__main__':
    stylesheet = '''
@import foo;

.orange {
    color: #abc;
}

p {
    color: #fff;
    a {
        color: #55f;
    }
    .red {
        color: #f55;

        background-color: #f55;
    }
    :hover {
        color: #eee;
    }
    .orange, span, & .yellow {
        color: #ff5;
    }
    @media (max-width: 1000px) {
        width: 10px;
        height: 10px;
        span {
            margin: 0;
        }
    }
}

a {
    color: #fff;
    @swizzle .orange;
}

@media (min-width: 800px) and (max-width: 1000px) {
    h1 {
        font-size: 15px;
    }
    h2 {
        font-size: 12px;
        span {
            color: orange;
        }
    }
}

@when media(width >= 400px) and media(pointer: fine) {
    h1 {
        font-size: 20px;
    }
}
@else media(width < 200px) {
    h1 {
        font-style: bold;
    }
}
    '''
    def display_node(node: c2ast.Node, indent=0):
        if isinstance(node, Rule):
            print('\t'*indent, node, node.prelude)
        elif isinstance(node, c2ast.Declaration):
            print('\t'*indent, node, node.value)
        elif not isinstance(node, c2ast.WhitespaceToken):
            print('\t'*indent, node)
        if isinstance(node, Rule) and node.content:
            for child in node.content:
                display_node(child, indent+1)

    nodes = flatten_all(tinycss2.parse_stylesheet(stylesheet))
    for n in nodes:
        display_node(n)
    #print(process(stylesheet))
