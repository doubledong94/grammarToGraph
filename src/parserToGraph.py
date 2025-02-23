import os

from antlr4 import *
from ANTLRv4Lexer import ANTLRv4Lexer
from ANTLRv4Parser import ANTLRv4Parser
from ANTLRv4ParserVisitor import ANTLRv4ParserVisitor
from collections import defaultdict

terminal_node_color = '#aa6666'
starting_node_color = '#aa6666'


class TranslateToDotVisitor(ANTLRv4ParserVisitor):
    skipping_element = ['nls', 'NL', 'sep', 'SEMI']
    grammar_name = None
    current_rule_head = None
    grammar_map = defaultdict(list)
    rule_start_edge = defaultdict(list)
    terminal_node = []
    terminal_node_under_tree = []
    done_rule_under_head = defaultdict(list)

    def visitGrammarSpec(self, ctx: ANTLRv4Parser.GrammarSpecContext):
        self.grammar_name = ctx.grammarDecl().identifier().getText()
        return self.visitChildren(ctx)

    def visitParserRuleSpec(self, ctx: ANTLRv4Parser.ParserRuleSpecContext):
        rule_head = ctx.RULE_REF().getText()
        self.current_rule_head = rule_head
        print(rule_head)
        for n in self.visitRuleAltList(ctx.ruleBlock().ruleAltList()):
            self.grammar_map[rule_head].append([rule_head, n])
            self.rule_start_edge[rule_head].append(n)
        return ''

    def visitRuleAltList(self, ctx: ANTLRv4Parser.RuleAltListContext):
        rule_alt_starts = []
        for labeledAlt in ctx.labeledAlt():
            first_e, last_e = self.visitAlternative(labeledAlt.alternative())
            if isinstance(first_e, list):
                rule_alt_starts.extend(first_e)
            else:
                rule_alt_starts.append(first_e)
        return rule_alt_starts

    def visitAlternative(self, ctx: ANTLRv4Parser.AlternativeContext):
        last_e = None
        first_e = None
        for e in ctx.element():
            e = self.visitElement(e)
            if len(e) == 0:
                continue
            if e in self.skipping_element:
                continue
            # add edge between sequential items
            if last_e is not None:
                if isinstance(last_e, list):
                    last_es = last_e
                else:
                    last_es = [last_e]
                # e is a block
                if isinstance(e, list):
                    current_es, _ = e
                # e is an atom
                else:
                    current_es = [e]
                for e1 in last_es:
                    for e2 in current_es:
                        self.grammar_map[e1].append([self.current_rule_head, e2])
            # e is a block
            if isinstance(e, list):
                starts, ends = e
                if first_e is None:
                    first_e = starts
                last_e = ends
            # e is an atom
            else:
                if first_e is None:
                    first_e = e
                last_e = e
        return [first_e, last_e]

    def visitBlock(self, ctx: ANTLRv4Parser.BlockContext):
        start_nodes = []
        end_nodes = []
        for alternative in ctx.altList().alternative():
            start, end = self.visitAlternative(alternative)
            if isinstance(start, list):
                start_nodes.extend(start)
            else:
                start_nodes.append(start)
            if isinstance(end, list):
                end_nodes.extend(end)
            else:
                end_nodes.append(end)
        return [start_nodes, end_nodes]

    def visitElement(self, ctx: ANTLRv4Parser.ElementContext):
        if ctx.atom():
            return self.visitAtom(ctx.atom())
        elif ctx.labeledElement():
            if ctx.labeledElement().atom():
                return self.visitAtom(ctx.labeledElement().atom())
            elif ctx.labeledElement().block():
                return self.visitBlock(ctx.labeledElement().block())
        elif ctx.ebnf():
            return self.visitBlock(ctx.ebnf().block())
        elif ctx.actionBlock():
            return ''
        return ''

    def visitAtom(self, ctx: ANTLRv4Parser.AtomContext):
        if ctx.terminalDef():
            if ctx.terminalDef().TOKEN_REF():
                return ctx.terminalDef().TOKEN_REF().getText()
            else:
                return ctx.terminalDef().STRING_LITERAL().getText().replace("'", '"')
        elif ctx.ruleref():
            return ctx.ruleref().RULE_REF().getText()
        return ''

    def get_edge_of_tree(self, rule_head, tree_head, edges, max_depth, depth):
        if rule_head in self.done_rule_under_head and tree_head in self.done_rule_under_head[rule_head]:
            return
        self.done_rule_under_head[rule_head].append(tree_head)
        if tree_head in self.terminal_node:
            self.terminal_node_under_tree.append(tree_head)
        if tree_head in self.grammar_map:
            for rule_head_i, vi in self.grammar_map[tree_head]:
                if rule_head == rule_head_i:
                    edges.append([tree_head, vi])
                    self.get_edge_of_tree(rule_head, vi, edges, max_depth, depth)
                    if depth <= max_depth:
                        self.get_edge_of_tree(vi, vi, edges, max_depth, depth + 1)

    def to_dot_str(self, start_rule, depth):
        dot_str = '''digraph G {
            graph [size="10,10"];      
            graph [dpi=800]; // 设置分辨率为300 DPI
            rankdir=LR; // 从左到右排列
            node [style=filled];
            node [shape=box]; // 节点形状为方框
            '''
        edges = []
        self.get_edge_of_tree(start_rule, start_rule, edges, depth, 1)
        for edge in edges:
            if edge[0] in self.rule_start_edge and edge[1] in self.rule_start_edge[edge[0]]:
                dot_str += f'{edge[0]} -> {edge[1]} [style=dashed];\n'
            else:
                dot_str += f'{edge[0]} -> {edge[1]} [penwidth=3.0];\n'
        # special color for special node
        for n in self.terminal_node_under_tree:
            dot_str += f'{n} [fillcolor="{terminal_node_color}"];\n'
        dot_str += f'{start_rule} [fillcolor="{starting_node_color}"];\n'
        # edges
        dot_str += '}'
        return dot_str


# 解析输入
def main(file_path, start_rule, depth):
    input_stream = FileStream(file_path)
    lexer = ANTLRv4Lexer(input_stream)
    stream = CommonTokenStream(lexer)
    parser = ANTLRv4Parser(stream)
    tree = parser.grammarSpec()

    # 使用自定义的visitor
    visitor = TranslateToDotVisitor()
    visitor.visit(tree)

    with open(f'../dot/{visitor.grammar_name}_{start_rule}.dot', 'w', encoding='utf-8') as file:
        file.write(visitor.to_dot_str(start_rule, depth))
    os.system(f'dot ../dot/{visitor.grammar_name}_{start_rule}.dot -T png -o ../graphs/{visitor.grammar_name}_{start_rule}.png')
    # os.system(f'neato ../dot/{visitor.grammar_name}_{start_rule}.dot -T png -o ../graphs/{visitor.grammar_name}_{start_rule}.png')
    # os.system(f'fdp ../dot/{visitor.grammar_name}_{start_rule}.dot -T png -o ../graphs/{visitor.grammar_name}_{start_rule}.png')
    # os.system(f'sfdp ../dot/{visitor.grammar_name}_{start_rule}.dot -T png -o ../graphs/{visitor.grammar_name}_{start_rule}.png')
    # os.system(f'twopi ../dot/{visitor.grammar_name}_{start_rule}.dot -T png -o ../graphs/{visitor.grammar_name}_{start_rule}.png')
    # os.system(f'circo ../dot/{visitor.grammar_name}_{start_rule}.dot -T png -o ../graphs/{visitor.grammar_name}_{start_rule}.png')


if __name__ == '__main__':
    main("../grammars/C.g4", 'compilationUnit', 5)
