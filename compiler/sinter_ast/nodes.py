"""
Abstract Syntax Tree nodes for Sinter Programming Language
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Optional, Dict, Any


class Visibility(Enum):
    PRIVATE = "private"
    PROTECTED = "protected"
    PUBLIC = "public"


class AttributeAnnotation:
    """Represents an @attribute annotation"""
    def __init__(
        self,
        read_only: bool = False,
        write_only: bool = False,
        derived: bool = False,
        serializable: bool = False
    ):
        self.read_only = read_only
        self.write_only = write_only
        self.derived = derived
        self.serializable = serializable

    @classmethod
    def parse(cls, annotation_str: str) -> "AttributeAnnotation":
        """Parse annotation string like '@attribute' or '@attribute(read_only=true)'"""
        if "(" not in annotation_str:
            return cls(serializable=True)  # Default: serializable
        
        # Parse parameters
        params_str = annotation_str[annotation_str.index("(")+1:annotation_str.rindex(")")]
        params = {}
        for param in params_str.split(","):
            if "=" in param:
                key, value = param.split("=", 1)
                params[key.strip()] = value.strip() == "true"
        
        return cls(
            read_only=params.get("read_only", False),
            write_only=params.get("write_only", False),
            derived=params.get("derived", False),
            serializable=params.get("serializable", True)
        )


class ASTNode(ABC):
    """Base class for all AST nodes"""
    def __init__(self, line: int = 0, column: int = 0):
        self.line = line
        self.column = column

    @abstractmethod
    def __repr__(self) -> str:
        pass


class Program(ASTNode):
    """Root node representing the entire program"""
    def __init__(self, declarations: List[ASTNode]):
        super().__init__()
        self.declarations = declarations

    def __repr__(self):
        return f"Program({len(self.declarations)} declarations)"


class ClassDeclaration(ASTNode):
    """Represents a class definition"""
    def __init__(
        self,
        name: str,
        type_parameters: Optional[List[str]] = None,
        extends: Optional[str] = None,
        implements: List[str] = None,
        members: List[ASTNode] = None,
        line: int = 0,
        column: int = 0
    ):
        super().__init__(line, column)
        self.name = name
        self.type_parameters = type_parameters or []
        self.extends = extends
        self.implements = implements or []
        self.members = members or []

    def __repr__(self):
        params = f"<{', '.join(self.type_parameters)}>" if self.type_parameters else ""
        extends_str = f" extends {self.extends}" if self.extends else ""
        impl_str = f" implements {', '.join(self.implements)}" if self.implements else ""
        return f"Class({self.name}{params}{extends_str}{impl_str})"


class ScopeBlock(ASTNode):
    """Represents a visibility scope block (private, protected, public)"""
    def __init__(self, visibility: Visibility, members: List[ASTNode]):
        super().__init__()
        self.visibility = visibility
        self.members = members

    def __repr__(self):
        return f"ScopeBlock({self.visibility.value}, {len(self.members)} members)"


class FieldDeclaration(ASTNode):
    """Represents a field/attribute declaration"""
    def __init__(
        self,
        name: str,
        type_name: str,
        is_const: bool,
        initial_value: Optional[ASTNode] = None,
        annotation: Optional[AttributeAnnotation] = None,
        line: int = 0,
        column: int = 0
    ):
        super().__init__(line, column)
        self.name = name
        self.type_name = type_name
        self.is_const = is_const
        self.initial_value = initial_value
        self.annotation = annotation

    def __repr__(self):
        const_str = "const " if self.is_const else "var "
        annot_str = f" {self.annotation}" if self.annotation else ""
        init_str = f" = {self.initial_value}" if self.initial_value else ""
        return f"Field({const_str}{self.name}: {self.type_name}{annot_str}{init_str})"


class MethodDeclaration(ASTNode):
    """Represents a method declaration"""
    def __init__(
        self,
        name: str,
        parameters: List[Any],  # Parameter
        return_type: str,
        body: Any,  # Block
        is_static: bool = False,
        line: int = 0,
        column: int = 0
    ):
        super().__init__(line, column)
        self.name = name
        self.parameters = parameters
        self.return_type = return_type
        self.body = body
        self.is_static = is_static  # True for 'function', False for 'method'

    def __repr__(self):
        static_str = "function " if self.is_static else "method "
        params_str = ", ".join(str(p) for p in self.parameters)
        return f"{static_str}{self.name}({params_str}) -> {self.return_type}"


class FunctionDeclaration(ASTNode):
    """Represents a function declaration (outside of class)"""
    def __init__(
        self,
        name: str,
        parameters: List[Any],  # Parameter
        return_type: str,
        body: Any,  # Block
        line: int = 0,
        column: int = 0
    ):
        super().__init__(line, column)
        self.name = name
        self.parameters = parameters
        self.return_type = return_type
        self.body = body

    def __repr__(self):
        params_str = ", ".join(str(p) for p in self.parameters)
        return f"function {self.name}({params_str}) -> {self.return_type}"


class Parameter(ASTNode):
    """Represents a function/method parameter"""
    def __init__(self, name: str, type_name: str, line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.name = name
        self.type_name = type_name

    def __repr__(self):
        return f"{self.name}: {self.type_name}"


class Block(ASTNode):
    """Represents a block of statements"""
    def __init__(self, statements: List[ASTNode]):
        super().__init__()
        self.statements = statements

    def __repr__(self):
        return f"Block({len(self.statements)} statements)"


class Expression(ASTNode):
    """Base class for expressions"""
    pass


class BinaryExpression(Expression):
    """Represents a binary operation"""
    def __init__(self, left: Expression, operator: str, right: Expression):
        super().__init__()
        self.left = left
        self.operator = operator
        self.right = right

    def __repr__(self):
        return f"({self.left} {self.operator} {self.right})"


class UnaryExpression(Expression):
    """Represents a unary operation"""
    def __init__(self, operator: str, operand: Expression):
        super().__init__()
        self.operator = operator
        self.operand = operand

    def __repr__(self):
        return f"({self.operator}{self.operand})"


class Literal(Expression):
    """Represents a literal value"""
    def __init__(self, value: Any, literal_type: str):
        super().__init__()
        self.value = value
        self.literal_type = literal_type

    def __repr__(self):
        return f"Literal({self.value})"


class Identifier(Expression):
    """Represents an identifier/variable reference"""
    def __init__(self, name: str, line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.name = name

    def __repr__(self):
        return f"Identifier({self.name})"


class MemberAccess(Expression):
    """Represents member access (obj.member)"""
    def __init__(self, object_expr: Expression, member: str):
        super().__init__()
        self.object_expr = object_expr
        self.member = member

    def __repr__(self):
        return f"({self.object_expr}.{self.member})"


class MethodCall(Expression):
    """Represents a method/function call"""
    def __init__(self, callee: Expression, arguments: List[Expression]):
        super().__init__()
        self.callee = callee
        self.arguments = arguments

    def __repr__(self):
        args_str = ", ".join(str(arg) for arg in self.arguments)
        return f"{self.callee}({args_str})"


class NewExpression(Expression):
    """Represents a 'new' expression for object instantiation"""
    def __init__(self, class_name: str, type_arguments: List[str], arguments: List[Expression]):
        super().__init__()
        self.class_name = class_name
        self.type_arguments = type_arguments
        self.arguments = arguments

    def __repr__(self):
        type_args = f"<{', '.join(self.type_arguments)}>" if self.type_arguments else ""
        args_str = ", ".join(str(arg) for arg in self.arguments)
        return f"new {self.class_name}{type_args}({args_str})"


class PointerExpression(Expression):
    """Represents pointer operations (*ptr or &var)"""
    def __init__(self, operator: str, operand: Expression):
        super().__init__()
        self.operator = operator  # "*" or "&"
        self.operand = operand

    def __repr__(self):
        return f"({self.operator}{self.operand})"


class Statement(ASTNode):
    """Base class for statements"""
    pass


class ExpressionStatement(Statement):
    """Represents an expression used as a statement"""
    def __init__(self, expression: Expression):
        super().__init__()
        self.expression = expression

    def __repr__(self):
        return f"{self.expression};"


class ReturnStatement(Statement):
    """Represents a return statement"""
    def __init__(self, value: Optional[Expression] = None):
        super().__init__()
        self.value = value

    def __repr__(self):
        return f"return {self.value if self.value else ''}"


class VariableDeclaration(Statement):
    """Represents a variable declaration"""
    def __init__(self, name: str, type_name: str, initial_value: Optional[Expression] = None):
        super().__init__()
        self.name = name
        self.type_name = type_name
        self.initial_value = initial_value

    def __repr__(self):
        init_str = f" = {self.initial_value}" if self.initial_value else ""
        return f"var {self.name}: {self.type_name}{init_str}"


class IfStatement(Statement):
    """Represents an if statement"""
    def __init__(self, condition: Expression, then_block: Block, else_block: Optional[Block] = None):
        super().__init__()
        self.condition = condition
        self.then_block = then_block
        self.else_block = else_block

    def __repr__(self):
        else_str = f" else {self.else_block}" if self.else_block else ""
        return f"if ({self.condition}) {self.then_block}{else_str}"


class WhileStatement(Statement):
    """Represents a while loop"""
    def __init__(self, condition: Expression, body: Block):
        super().__init__()
        self.condition = condition
        self.body = body

    def __repr__(self):
        return f"while ({self.condition}) {self.body}"


class AssignmentStatement(Statement):
    """Represents an assignment statement"""
    def __init__(self, target: Expression, value: Expression):
        super().__init__()
        self.target = target
        self.value = value

    def __repr__(self):
        return f"{self.target} = {self.value}"


class ForStatement(Statement):
    """Represents a for loop: for (init; condition; update) { body }"""
    def __init__(self, init: Optional[Statement], condition: Optional[Expression],
                 update: Optional[Expression], body: Block):
        super().__init__()
        self.init = init
        self.condition = condition
        self.update = update
        self.body = body

    def __repr__(self):
        return f"for ({self.init}; {self.condition}; {self.update}) {self.body}"


class ForEachStatement(Statement):
    """Represents a for-each loop: for (item in collection) { body }"""
    def __init__(self, var_name: str, var_type: str, collection: Expression, body: Block):
        super().__init__()
        self.var_name = var_name
        self.var_type = var_type
        self.collection = collection
        self.body = body

    def __repr__(self):
        return f"for ({self.var_name}: {self.var_type} in {self.collection}) {self.body}"


class BreakStatement(Statement):
    """Represents a break statement"""
    def __init__(self):
        super().__init__()

    def __repr__(self):
        return "break"


class ContinueStatement(Statement):
    """Represents a continue statement"""
    def __init__(self):
        super().__init__()

    def __repr__(self):
        return "continue"


class PrintStatement(Statement):
    """Represents a print/println statement"""
    def __init__(self, arguments: List[Expression], newline: bool = True):
        super().__init__()
        self.arguments = arguments
        self.newline = newline

    def __repr__(self):
        fn = "println" if self.newline else "print"
        args = ", ".join(str(a) for a in self.arguments)
        return f"{fn}({args})"


class ArrayLiteral(Expression):
    """Represents an array literal [e1, e2, ...]"""
    def __init__(self, elements: List[Expression]):
        super().__init__()
        self.elements = elements

    def __repr__(self):
        elems = ", ".join(str(e) for e in self.elements)
        return f"[{elems}]"


class ArrayAccess(Expression):
    """Represents array indexing arr[index]"""
    def __init__(self, array: Expression, index: Expression):
        super().__init__()
        self.array = array
        self.index = index

    def __repr__(self):
        return f"{self.array}[{self.index}]"


class InterfaceDeclaration(ASTNode):
    """Represents an interface definition"""
    def __init__(self, name: str, methods: List['MethodDeclaration'], line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.name = name
        self.methods = methods

    def __repr__(self):
        return f"Interface({self.name}, {len(self.methods)} methods)"
