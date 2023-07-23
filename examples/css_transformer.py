import tinycss2
import tinycss2.ast as c2ast

from anchovy.css.parser import flatten_all, Rule


TEST_STYLES = '''
@import foo;

.orange {
    color: #abc;
}

.a, .b {
    .c, .d {
        color: #def;
    }
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


if __name__ == '__main__':
    nodes = flatten_all(tinycss2.parse_stylesheet(TEST_STYLES))
    for n in nodes:
        display_node(n)
