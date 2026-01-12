"""
Parser for Sinter Programming Language
Builds an AST from a stream of tokens
"""

from typing import List, Optional
from compiler.lexer.lexer import Token, TokenType
from compiler.sinter_ast.nodes import (
    Program, ClassDeclaration, ScopeBlock, FieldDeclaration, MethodDeclaration,
    FunctionDeclaration, Parameter, Block, Expression, BinaryExpression,
    UnaryExpression, Literal, Identifier, MemberAccess, MethodCall,
    NewExpression, PointerExpression, Statement, ExpressionStatement,
    ReturnStatement, VariableDeclaration, IfStatement, WhileStatement,
    AssignmentStatement, Visibility, AttributeAnnotation, ASTNode,
    ForStatement, ForEachStatement, BreakStatement, ContinueStatement,
    PrintStatement, ArrayLiteral, ArrayAccess, InterfaceDeclaration
)


class Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    def current_token(self) -> Optional[Token]:
        """Get current token or None if EOF"""
        if self.pos >= len(self.tokens):
            return None
        return self.tokens[self.pos]

    def peek_token(self, offset: int = 1) -> Optional[Token]:
        """Peek ahead by offset tokens"""
        peek_pos = self.pos + offset
        if peek_pos >= len(self.tokens):
            return None
        return self.tokens[peek_pos]

    def advance(self) -> Optional[Token]:
        """Advance to next token"""
        if self.pos < len(self.tokens):
            token = self.tokens[self.pos]
            self.pos += 1
            return token
        return None

    def expect(self, token_type: TokenType, error_msg: str = None) -> Token:
        """Expect a specific token type, raise error if not found"""
        token = self.current_token()
        if not token or token.type != token_type:
            msg = error_msg or f"Expected {token_type.name}, got {token.type.name if token else 'EOF'}"
            raise SyntaxError(f"{msg} at line {token.line if token else '?'}, column {token.column if token else '?'}")
        self.advance()
        return token

    # Type keywords that are valid as type names
    TYPE_KEYWORDS = {
        TokenType.INT, TokenType.FLOAT, TokenType.DOUBLE,
        TokenType.BOOLEAN, TokenType.STR, TokenType.VOID
    }

    def parse_type(self) -> str:
        """Parse a type name (identifier or type keyword), including pointer types"""
        token = self.current_token()
        if not token:
            raise SyntaxError("Expected type name, got EOF")
        
        base_type = None
        if token.type == TokenType.IDENTIFIER:
            self.advance()
            base_type = token.value
        elif token.type in self.TYPE_KEYWORDS:
            self.advance()
            base_type = token.value
        else:
            raise SyntaxError(f"Expected type name at line {token.line}, column {token.column}")
        
        # Check for pointer type (*)
        while self.current_token() and self.current_token().type == TokenType.DEREFERENCE:
            self.advance()
            base_type = base_type + "*"
        
        return base_type

    def parse(self) -> Program:
        """Parse the entire program"""
        declarations = []
        
        while self.current_token() and self.current_token().type != TokenType.EOF:
            if self.current_token().type == TokenType.CLASS:
                declarations.append(self.parse_class())
            elif self.current_token().type == TokenType.FUNCTION:
                declarations.append(self.parse_function())
            elif self.current_token().type == TokenType.INTERFACE:
                declarations.append(self.parse_interface())
            else:
                raise SyntaxError(f"Unexpected token at top level: {self.current_token()}")
        
        return Program(declarations)

    def parse_class(self) -> ClassDeclaration:
        """Parse a class declaration"""
        token = self.expect(TokenType.CLASS)
        name_token = self.expect(TokenType.IDENTIFIER, "Expected class name")
        name = name_token.value
        
        # Check for parametrized
        type_parameters = []
        if self.current_token() and self.current_token().type == TokenType.PARAMETRIZED:
            self.advance()  # skip 'parametrized'
            self.expect(TokenType.LEFT_ANGLE)
            while self.current_token() and self.current_token().type != TokenType.RIGHT_ANGLE:
                type_param = self.expect(TokenType.IDENTIFIER, "Expected type parameter")
                type_parameters.append(type_param.value)
                if self.current_token() and self.current_token().type == TokenType.COMMA:
                    self.advance()
            self.expect(TokenType.RIGHT_ANGLE)
        
        # Check for extends
        extends = None
        if self.current_token() and self.current_token().type == TokenType.EXTENDS:
            self.advance()
            extends_token = self.expect(TokenType.IDENTIFIER, "Expected base class name")
            extends = extends_token.value
        
        # Check for implements
        implements = []
        if self.current_token() and self.current_token().type == TokenType.IMPLEMENTS:
            self.advance()
            while True:
                impl_token = self.expect(TokenType.IDENTIFIER, "Expected interface name")
                implements.append(impl_token.value)
                if self.current_token() and self.current_token().type == TokenType.COMMA:
                    self.advance()
                else:
                    break
        
        # Parse class body
        self.expect(TokenType.LEFT_BRACE)
        members = []
        
        current_visibility = Visibility.PUBLIC  # Default visibility
        
        while self.current_token() and self.current_token().type != TokenType.RIGHT_BRACE:
            # Check for visibility modifier
            if self.current_token().type == TokenType.PRIVATE:
                self.advance()
                self.expect(TokenType.COLON)
                current_visibility = Visibility.PRIVATE
            elif self.current_token().type == TokenType.PROTECTED:
                self.advance()
                self.expect(TokenType.COLON)
                current_visibility = Visibility.PROTECTED
            elif self.current_token().type == TokenType.PUBLIC:
                self.advance()
                self.expect(TokenType.COLON)
                current_visibility = Visibility.PUBLIC
            else:
                # Parse member (field or method)
                member = self.parse_class_member(current_visibility)
                members.append(member)
        
        self.expect(TokenType.RIGHT_BRACE)
        
        return ClassDeclaration(name, type_parameters, extends, implements, members, token.line, token.column)

    def parse_class_member(self, visibility: Visibility) -> ASTNode:
        """Parse a class member (field or method)"""
        # Check for annotation (for fields)
        annotation = None
        if self.current_token() and self.current_token().type == TokenType.ANNOTATION:
            annotation_str = self.current_token().value
            annotation = AttributeAnnotation.parse(annotation_str)
            self.advance()
        
        # Check if it's a method/function or field
        if self.current_token().type in [TokenType.METHOD, TokenType.FUNCTION]:
            return self.parse_method_declaration(visibility)
        else:
            return self.parse_field_declaration(visibility, annotation)

    def parse_field_declaration(self, visibility: Visibility, annotation: Optional[AttributeAnnotation]) -> FieldDeclaration:
        """Parse a field declaration"""
        is_const = False
        if self.current_token().type == TokenType.CONST:
            is_const = True
            self.advance()
        elif self.current_token().type == TokenType.VAR:
            self.advance()
        else:
            raise SyntaxError(f"Expected 'var' or 'const', got {self.current_token().type.name}")
        
        name_token = self.expect(TokenType.IDENTIFIER, "Expected field name")
        self.expect(TokenType.COLON)
        type_name = self.parse_type()
        
        initial_value = None
        if self.current_token() and self.current_token().type == TokenType.ASSIGN:
            self.advance()
            initial_value = self.parse_expression()
        
        # Semicolon is optional for fields (allows cleaner syntax)
        if self.current_token() and self.current_token().type == TokenType.SEMICOLON:
            self.advance()
        
        return FieldDeclaration(
            name_token.value,
            type_name,
            is_const,
            initial_value,
            annotation,
            name_token.line,
            name_token.column
        )

    def parse_method_declaration(self, visibility: Visibility) -> MethodDeclaration:
        """Parse a method or function declaration"""
        is_static = self.current_token().type == TokenType.FUNCTION
        self.advance()  # skip 'method' or 'function'
        
        name_token = self.expect(TokenType.IDENTIFIER, "Expected method name")
        self.expect(TokenType.LEFT_PAREN)
        
        parameters = []
        if self.current_token() and self.current_token().type != TokenType.RIGHT_PAREN:
            while True:
                param = self.parse_parameter()
                parameters.append(param)
                if self.current_token() and self.current_token().type == TokenType.COMMA:
                    self.advance()
                else:
                    break
        
        self.expect(TokenType.RIGHT_PAREN)
        self.expect(TokenType.ARROW)
        return_type = self.parse_type()
        
        body = self.parse_block()
        
        return MethodDeclaration(
            name_token.value,
            parameters,
            return_type,
            body,
            is_static,
            name_token.line,
            name_token.column
        )

    def parse_interface(self) -> InterfaceDeclaration:
        """Parse an interface declaration"""
        token = self.expect(TokenType.INTERFACE)
        name = self.expect(TokenType.IDENTIFIER, "Expected interface name")
        
        self.expect(TokenType.LEFT_BRACE)
        
        methods = []
        while self.current_token() and self.current_token().type != TokenType.RIGHT_BRACE:
            # Parse method signature (no body)
            self.expect(TokenType.METHOD)
            method_name = self.expect(TokenType.IDENTIFIER, "Expected method name")
            self.expect(TokenType.LEFT_PAREN)
            
            parameters = []
            if self.current_token() and self.current_token().type != TokenType.RIGHT_PAREN:
                while True:
                    param_name = self.expect(TokenType.IDENTIFIER, "Expected parameter name")
                    self.expect(TokenType.COLON)
                    param_type = self.parse_type()
                    parameters.append(Parameter(param_name.value, param_type))
                    
                    if self.current_token() and self.current_token().type == TokenType.COMMA:
                        self.advance()
                    else:
                        break
            
            self.expect(TokenType.RIGHT_PAREN)
            self.expect(TokenType.ARROW)
            return_type = self.parse_type()
            self.expect(TokenType.SEMICOLON)
            
            methods.append(MethodDeclaration(
                method_name.value, parameters, return_type, None,  # No body
                False, line=method_name.line, column=method_name.column
            ))
        
        self.expect(TokenType.RIGHT_BRACE)
        
        return InterfaceDeclaration(name.value, methods, line=token.line, column=token.column)
    
    def parse_function(self) -> FunctionDeclaration:
        """Parse a function declaration (outside of class)"""
        token = self.expect(TokenType.FUNCTION)
        name_token = self.expect(TokenType.IDENTIFIER, "Expected function name")
        self.expect(TokenType.LEFT_PAREN)
        
        parameters = []
        if self.current_token() and self.current_token().type != TokenType.RIGHT_PAREN:
            while True:
                param = self.parse_parameter()
                parameters.append(param)
                if self.current_token() and self.current_token().type == TokenType.COMMA:
                    self.advance()
                else:
                    break
        
        self.expect(TokenType.RIGHT_PAREN)
        self.expect(TokenType.ARROW)
        return_type = self.parse_type()
        
        body = self.parse_block()
        
        return FunctionDeclaration(
            name_token.value,
            parameters,
            return_type,
            body,
            token.line,
            token.column
        )

    def parse_parameter(self) -> Parameter:
        """Parse a function/method parameter"""
        name_token = self.expect(TokenType.IDENTIFIER, "Expected parameter name")
        self.expect(TokenType.COLON)
        type_name = self.parse_type()
        return Parameter(name_token.value, type_name, name_token.line, name_token.column)

    def parse_block(self) -> Block:
        """Parse a block of statements"""
        self.expect(TokenType.LEFT_BRACE)
        statements = []
        
        while self.current_token() and self.current_token().type != TokenType.RIGHT_BRACE:
            statements.append(self.parse_statement())
        
        self.expect(TokenType.RIGHT_BRACE)
        return Block(statements)

    def parse_statement(self) -> Statement:
        """Parse a statement"""
        token = self.current_token()
        
        if not token:
            raise SyntaxError("Unexpected end of file")
        
        if token.type == TokenType.RETURN:
            return self.parse_return_statement()
        elif token.type == TokenType.IF:
            return self.parse_if_statement()
        elif token.type == TokenType.WHILE:
            return self.parse_while_statement()
        elif token.type == TokenType.FOR:
            return self.parse_for_statement()
        elif token.type == TokenType.VAR:
            return self.parse_variable_declaration()
        elif token.type == TokenType.BREAK:
            self.advance()
            self.expect(TokenType.SEMICOLON)
            return BreakStatement()
        elif token.type == TokenType.CONTINUE:
            self.advance()
            self.expect(TokenType.SEMICOLON)
            return ContinueStatement()
        elif token.type == TokenType.PRINT:
            return self.parse_print_statement(newline=False)
        elif token.type == TokenType.PRINTLN:
            return self.parse_print_statement(newline=True)
        else:
            # Expression statement
            expr = self.parse_expression()
            self.expect(TokenType.SEMICOLON)
            return ExpressionStatement(expr)
    
    def parse_for_statement(self) -> Statement:
        """Parse a for statement (traditional or for-each)"""
        self.expect(TokenType.FOR)
        self.expect(TokenType.LEFT_PAREN)
        
        # Check if it's a for-each: for (var x: Type in collection)
        if self.current_token().type == TokenType.VAR:
            self.advance()
            var_name = self.expect(TokenType.IDENTIFIER, "Expected variable name")
            self.expect(TokenType.COLON)
            var_type = self.parse_type()
            
            if self.current_token() and self.current_token().type == TokenType.IN:
                self.advance()
                collection = self.parse_expression()
                self.expect(TokenType.RIGHT_PAREN)
                body = self.parse_block()
                return ForEachStatement(var_name.value, var_type, collection, body)
            else:
                # It's a regular for with var declaration
                init = VariableDeclaration(var_name.value, var_type, None)
                if self.current_token() and self.current_token().type == TokenType.ASSIGN:
                    self.advance()
                    init.initial_value = self.parse_expression()
                self.expect(TokenType.SEMICOLON)
                condition = self.parse_expression() if self.current_token().type != TokenType.SEMICOLON else None
                self.expect(TokenType.SEMICOLON)
                update = self.parse_expression() if self.current_token().type != TokenType.RIGHT_PAREN else None
                self.expect(TokenType.RIGHT_PAREN)
                body = self.parse_block()
                return ForStatement(init, condition, update, body)
        else:
            # Traditional for: for (init; condition; update)
            init = None
            if self.current_token().type != TokenType.SEMICOLON:
                expr = self.parse_expression()
                if isinstance(expr, AssignmentStatement):
                    init = expr
                else:
                    init = ExpressionStatement(expr)
            self.expect(TokenType.SEMICOLON)
            
            condition = None
            if self.current_token().type != TokenType.SEMICOLON:
                condition = self.parse_expression()
            self.expect(TokenType.SEMICOLON)
            
            update = None
            if self.current_token().type != TokenType.RIGHT_PAREN:
                update = self.parse_expression()
            self.expect(TokenType.RIGHT_PAREN)
            
            body = self.parse_block()
            return ForStatement(init, condition, update, body)
    
    def parse_print_statement(self, newline: bool) -> PrintStatement:
        """Parse a print or println statement"""
        self.advance()  # skip print/println
        self.expect(TokenType.LEFT_PAREN)
        
        arguments = []
        if self.current_token() and self.current_token().type != TokenType.RIGHT_PAREN:
            while True:
                arguments.append(self.parse_expression())
                if self.current_token() and self.current_token().type == TokenType.COMMA:
                    self.advance()
                else:
                    break
        
        self.expect(TokenType.RIGHT_PAREN)
        self.expect(TokenType.SEMICOLON)
        return PrintStatement(arguments, newline)

    def parse_return_statement(self) -> ReturnStatement:
        """Parse a return statement"""
        self.expect(TokenType.RETURN)
        value = None
        if self.current_token() and self.current_token().type != TokenType.SEMICOLON:
            value = self.parse_expression()
        self.expect(TokenType.SEMICOLON)
        return ReturnStatement(value)

    def parse_if_statement(self) -> IfStatement:
        """Parse an if statement"""
        self.expect(TokenType.IF)
        self.expect(TokenType.LEFT_PAREN)
        condition = self.parse_expression()
        self.expect(TokenType.RIGHT_PAREN)
        then_block = self.parse_block()
        
        else_block = None
        if self.current_token() and self.current_token().type == TokenType.ELSE:
            self.advance()
            else_block = self.parse_block()
        
        return IfStatement(condition, then_block, else_block)

    def parse_while_statement(self) -> WhileStatement:
        """Parse a while statement"""
        self.expect(TokenType.WHILE)
        self.expect(TokenType.LEFT_PAREN)
        condition = self.parse_expression()
        self.expect(TokenType.RIGHT_PAREN)
        body = self.parse_block()
        return WhileStatement(condition, body)

    def parse_variable_declaration(self) -> VariableDeclaration:
        """Parse a variable declaration"""
        self.expect(TokenType.VAR)
        name_token = self.expect(TokenType.IDENTIFIER, "Expected variable name")
        self.expect(TokenType.COLON)
        type_name = self.parse_type()
        
        initial_value = None
        if self.current_token() and self.current_token().type == TokenType.ASSIGN:
            self.advance()
            initial_value = self.parse_expression()
        
        self.expect(TokenType.SEMICOLON)
        return VariableDeclaration(name_token.value, type_name, initial_value)

    def parse_expression(self) -> Expression:
        """Parse an expression (using operator precedence)"""
        return self.parse_assignment()

    def parse_assignment(self) -> Expression:
        """Parse assignment expression"""
        left = self.parse_logical_or()
        
        if self.current_token() and self.current_token().type == TokenType.ASSIGN:
            self.advance()
            right = self.parse_assignment()
            return AssignmentStatement(left, right)
        
        return left

    def parse_logical_or(self) -> Expression:
        """Parse logical OR expression"""
        left = self.parse_logical_and()
        
        while self.current_token() and self.current_token().type == TokenType.OR:
            op_token = self.advance()
            right = self.parse_logical_and()
            left = BinaryExpression(left, op_token.value, right)
        
        return left

    def parse_logical_and(self) -> Expression:
        """Parse logical AND expression"""
        left = self.parse_equality()
        
        while self.current_token() and self.current_token().type == TokenType.AND:
            op_token = self.advance()
            right = self.parse_equality()
            left = BinaryExpression(left, op_token.value, right)
        
        return left

    def parse_equality(self) -> Expression:
        """Parse equality expressions"""
        left = self.parse_relational()
        
        while self.current_token() and self.current_token().type in [TokenType.EQUALS, TokenType.NOT_EQUALS]:
            op_token = self.advance()
            right = self.parse_relational()
            left = BinaryExpression(left, op_token.value, right)
        
        return left

    def parse_relational(self) -> Expression:
        """Parse relational expressions"""
        left = self.parse_additive()
        
        while self.current_token() and self.current_token().type in [
            TokenType.LEFT_ANGLE, TokenType.RIGHT_ANGLE,
            TokenType.LESS_EQUAL, TokenType.GREATER_EQUAL
        ]:
            op_token = self.advance()
            right = self.parse_additive()
            left = BinaryExpression(left, op_token.value, right)
        
        return left

    def parse_additive(self) -> Expression:
        """Parse additive expressions"""
        left = self.parse_multiplicative()
        
        while self.current_token() and self.current_token().type in [TokenType.PLUS, TokenType.MINUS]:
            op_token = self.advance()
            right = self.parse_multiplicative()
            left = BinaryExpression(left, op_token.value, right)
        
        return left

    def parse_multiplicative(self) -> Expression:
        """Parse multiplicative expressions"""
        left = self.parse_unary()
        
        while self.current_token() and self.current_token().type in [
            TokenType.MULTIPLY, TokenType.DEREFERENCE, TokenType.DIVIDE, TokenType.MODULO
        ]:
            op_token = self.advance()
            right = self.parse_unary()
            left = BinaryExpression(left, op_token.value, right)
        
        return left

    def parse_unary(self) -> Expression:
        """Parse unary expressions"""
        token = self.current_token()
        
        if token and token.type in [TokenType.NOT, TokenType.MINUS, TokenType.DEREFERENCE, TokenType.ADDRESS_OF]:
            self.advance()
            operand = self.parse_unary()
            return UnaryExpression(token.value, operand)
        
        return self.parse_postfix()

    def parse_postfix(self) -> Expression:
        """Parse postfix expressions (member access, method calls, array access)"""
        expr = self.parse_primary()
        
        while True:
            token = self.current_token()
            if not token:
                break
            
            if token.type == TokenType.DOT:
                self.advance()
                # Accept identifier or 'new' keyword as member name
                member_token = self.current_token()
                if member_token and member_token.type == TokenType.NEW:
                    self.advance()
                    expr = MemberAccess(expr, "new")
                elif member_token and member_token.type == TokenType.IDENTIFIER:
                    self.advance()
                    expr = MemberAccess(expr, member_token.value)
                else:
                    raise SyntaxError(f"Expected member name at line {member_token.line if member_token else '?'}, column {member_token.column if member_token else '?'}")
            elif token.type == TokenType.LEFT_PAREN:
                self.advance()
                arguments = []
                if self.current_token() and self.current_token().type != TokenType.RIGHT_PAREN:
                    while True:
                        arguments.append(self.parse_expression())
                        if self.current_token() and self.current_token().type == TokenType.COMMA:
                            self.advance()
                        else:
                            break
                self.expect(TokenType.RIGHT_PAREN)
                expr = MethodCall(expr, arguments)
            elif token.type == TokenType.LEFT_BRACKET:
                # Array access
                self.advance()
                index = self.parse_expression()
                self.expect(TokenType.RIGHT_BRACKET)
                expr = ArrayAccess(expr, index)
            elif token.type == TokenType.INCREMENT or token.type == TokenType.DECREMENT:
                self.advance()
                expr = UnaryExpression(token.value, expr)
            else:
                break
        
        return expr

    def parse_primary(self) -> Expression:
        """Parse primary expressions"""
        token = self.current_token()
        
        if not token:
            raise SyntaxError("Unexpected end of file in expression")
        
        if token.type == TokenType.IDENTIFIER:
            self.advance()
            return Identifier(token.value, token.line, token.column)
        
        elif token.type == TokenType.INTEGER_LITERAL:
            self.advance()
            return Literal(int(token.value), "int")
        
        elif token.type == TokenType.FLOAT_LITERAL:
            self.advance()
            return Literal(float(token.value), "float")
        
        elif token.type == TokenType.STRING_LITERAL:
            self.advance()
            return Literal(token.value, "str")
        
        elif token.type == TokenType.D_STRING_LITERAL:
            self.advance()
            return Literal(token.value, "d_str")
        
        elif token.type == TokenType.TRUE:
            self.advance()
            return Literal(True, "boolean")
        
        elif token.type == TokenType.FALSE:
            self.advance()
            return Literal(False, "boolean")
        
        elif token.type == TokenType.NULL:
            self.advance()
            return Literal(None, "null")
        
        elif token.type == TokenType.NEW:
            return self.parse_new_expression()
        
        elif token.type == TokenType.LEFT_PAREN:
            self.advance()
            expr = self.parse_expression()
            self.expect(TokenType.RIGHT_PAREN)
            return expr
        
        elif token.type == TokenType.LEFT_BRACKET:
            # Array literal
            self.advance()
            elements = []
            if self.current_token() and self.current_token().type != TokenType.RIGHT_BRACKET:
                while True:
                    elements.append(self.parse_expression())
                    if self.current_token() and self.current_token().type == TokenType.COMMA:
                        self.advance()
                    else:
                        break
            self.expect(TokenType.RIGHT_BRACKET)
            return ArrayLiteral(elements)
        
        else:
            raise SyntaxError(f"Unexpected token in expression: {token.type.name}")

    def parse_new_expression(self) -> NewExpression:
        """Parse a 'new' expression"""
        self.expect(TokenType.NEW)
        class_token = self.expect(TokenType.IDENTIFIER, "Expected class name")
        
        type_arguments = []
        if self.current_token() and self.current_token().type == TokenType.LEFT_ANGLE:
            self.advance()
            while self.current_token() and self.current_token().type != TokenType.RIGHT_ANGLE:
                type_arg = self.expect(TokenType.IDENTIFIER, "Expected type argument")
                type_arguments.append(type_arg.value)
                if self.current_token() and self.current_token().type == TokenType.COMMA:
                    self.advance()
            self.expect(TokenType.RIGHT_ANGLE)
        
        self.expect(TokenType.LEFT_PAREN)
        arguments = []
        if self.current_token() and self.current_token().type != TokenType.RIGHT_PAREN:
            while True:
                arguments.append(self.parse_expression())
                if self.current_token() and self.current_token().type == TokenType.COMMA:
                    self.advance()
                else:
                    break
        self.expect(TokenType.RIGHT_PAREN)
        
        return NewExpression(class_token.value, type_arguments, arguments)
