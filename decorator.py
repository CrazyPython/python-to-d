# AST ot AST approach (in contrast to bytecode approach)
import ast
import inspect
import textwrap
import typing
import ast_scope


class DExprString(ast.expr):
    def __init__(self, s, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.s = s

    def __str__(self):
        return self.s


class DTypeExpr(DExprString): pass


class DVarDeclaration(ast.stmt):
    def __init__(self, type_expression, identifier: str, expression=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.storage_classes = []
        self.type_expression = type_expression
        self.identifier = identifier
        self.expression: typing.Optional[ast.expr] = expression

    def __str__(self):
        alt_declarator = '\n'.join(self.storage_classes) + ' ' + str(self.type_expression) + ' ' + self.identifier
        if self.expression is None:
            return alt_declarator + ';'
        else:
            return alt_declarator + ' = ' + str(self.expression) + ';'


class DAssignExpression(ast.expr):
    def __init__(self, lvalue, rvalue, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lvalue = lvalue
        self.rvalue = rvalue

    def __str__(self):
        return str(self.lvalue) + ' = ' + str(self.rvalue)


class DExpressionStatement(ast.stmt):
    def __init__(self, expr, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.expr = expr

    def __str__(self):
        return str(self.expr) + ';'


class DCastExpression(ast.expr):
    def __init__(self, inner_type, expr, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.inner_type = inner_type
        self.expr = expr

    def __str__(self):
        return f'cast({self.inner_type})' + str(self.expr)


class DDynamicArrayOfTypeExpr(ast.expr):
    def __init__(self, inner_type, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.inner_type = inner_type

    def __str__(self):
        return str(self.inner_type) + '[]'


class DFunctionStatement(ast.stmt):
    def __init__(self, name, arguments, body, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = name
        self.arguments = arguments
        # fnction declarations would have an empty body
        self.body = body

    def __str__(self):
        return f'auto {self.name}({", ".join(f"{argument[0]} {argument[1]}" for argument in self.arguments)}) ' + '{' \
               + str(self.body) + '}'


class DEmptyStatement(ast.stmt):
    def __str__(self):
        return ';'


class DStatementList(ast.stmt):
    def __init__(self, statements, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.statements = statements

    def __str__(self):
        return ''.join(map(str, self.statements))


class DCallExpr(ast.expr):
    def __init__(self, fnexpr, parameter_list, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fnexpr = fnexpr
        self.parameter_list = parameter_list

    def __str__(self):
        return f'{self.fnexpr}({", ".join(map(str, self.parameter_list))})'


def generate_dlang_code(func):
    source = textwrap.dedent(inspect.getsource(func))  # unstable, bad for packing
    # should ideally generate a dlang AST directly, instead of going to a string first
    tree = ast.parse(source)
    result = NodeTranslator().visit(tree)
    return str(result)


def annotation_to_type_expression(annotation_ast):
    # doesn't support aliases or "typing.List" or anything more complex
    if isinstance(annotation_ast, ast.Subscript):
        if isinstance(annotation_ast.value, ast.Name) and isinstance(annotation_ast.slice, ast.Index):
            if annotation_ast.value.id == "list" or annotation_ast.value.id == "List":
                return DDynamicArrayOfTypeExpr(annotation_to_type_expression(annotation_ast.slice.value))
    elif isinstance(annotation_ast, ast.Name):
        if annotation_ast.id == "int":
            # bigint in python, would need support to make it different
            return DTypeExpr("int")
        elif annotation_ast.id == "float":
            return DTypeExpr("double")
        elif annotation_ast.id == "bool":
            return DTypeExpr("bool")
        else:
            return DTypeExpr(annotation_ast.value.id)
    raise ValueError()


def ensure_scope_initialized(ctx):
    if getattr(ctx, "seen_symbols", None) is None:
        ctx.seen_symbols = set()
    return ctx

def broaden_type():
    # Variant
    DDynamicArrayOfTypeExpr
    pass

class NodeTranslator(ast.NodeVisitor):
    def visit_List(self, node):
        # figure out: what kinds of things are in it?
        if len(node.elts) == 0:
            return DExprString("[]")
        return DCallExpr(DExprString("commonTypeOrVariantArray"), [self.visit(subnode) for subnode in node.elts])

    def visit_Constant(self, node: ast.Constant):
        if isinstance(node.value, str):
            return f'"{node.value}"'
        else:
            assert isinstance(node.value, int)
            return str(node.value)

    def visit_Assign(self, node: ast.Assign):
        assert node.targets != 0
        if len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name):
                scope = self.scope_info[target]
                ensure_scope_initialized(scope)
                if target.id not in scope.seen_symbols:
                    scope.seen_symbols.add(target.id)
                    return DVarDeclaration(DTypeExpr("auto"), target.id, DCallExpr("broaden", [self.visit(node.value)]))
                else:
                    return DExpressionStatement(DAssignExpression(target.id, self.visit(node.value)))
        else:
            # multiple assign could be handled with opAssign in the future
            raise Exception("assign unpacking is not supported")

    def visit_AnnAssign(self, node: ast.AnnAssign):
        # DVarDeclaration(node.target
        value = self.visit(node.value)
        try:
            type_expression = annotation_to_type_expression(node.annotation)
            use_cast = False
        except ValueError:
            type_expression = DTypeExpr('auto')
            use_cast = True
        if use_cast:
            return DVarDeclaration(type_expression, node.target.id, value)
        else:
            return DVarDeclaration(type_expression, node.target.id, value)

    def visit_Pass(self, node: ast.Pass):
        return DEmptyStatement()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        processed_arguments = []
        # todo: add arguments t
        for arg in node.args.args:
            type_expression = DTypeExpr('Variant')
            if arg.annotation is not None:
                try:
                    type_expression = annotation_to_type_expression(arg.annotation)
                except ValueError:
                    pass
            processed_arguments.append((type_expression, arg.arg))

        # translate union and any into variant for return type
        f = DFunctionStatement(node.name, processed_arguments, DStatementList(list(map(self.visit, node.body))))
        return f

    def visit_Module(self, node: ast.Module):
        return DStatementList(list(map(self.visit, node.body)))

    def visit(self, tree, *args, **kwargs):
        self.scope_info = ast_scope.annotate(tree)
        return super().visit(tree, *args, **kwargs)


# Only

"""
import std.variant;
"""
