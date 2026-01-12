"""
Lexer for Sinter Programming Language
Tokenizes source code into a stream of tokens
"""

import re
from enum import Enum
from typing import List, Optional, Tuple


class TokenType(Enum):
    # Keywords
    CLASS = "CLASS"
    FUNCTION = "FUNCTION"
    METHOD = "METHOD"
    PARAMETRIZED = "PARAMETRIZED"
    EXTENDS = "EXTENDS"
    IMPLEMENTS = "IMPLEMENTS"
    PRIVATE = "PRIVATE"
    PROTECTED = "PROTECTED"
    PUBLIC = "PUBLIC"
    VAR = "VAR"
    CONST = "CONST"
    RETURN = "RETURN"
    IF = "IF"
    ELSE = "ELSE"
    WHILE = "WHILE"
    FOR = "FOR"
    IN = "IN"
    BREAK = "BREAK"
    CONTINUE = "CONTINUE"
    TRUE = "TRUE"
    FALSE = "FALSE"
    NULL = "NULL"
    NEW = "NEW"
    THIS = "THIS"
    SELF = "SELF"
    PRINT = "PRINT"
    PRINTLN = "PRINTLN"
    INTERFACE = "INTERFACE"
    ABSTRACT = "ABSTRACT"

    # Types
    INT = "INT"
    FLOAT = "FLOAT"
    DOUBLE = "DOUBLE"
    BOOLEAN = "BOOLEAN"
    STR = "STR"
    VOID = "VOID"

    # Operators
    PLUS = "PLUS"
    MINUS = "MINUS"
    MULTIPLY = "MULTIPLY"
    DIVIDE = "DIVIDE"
    MODULO = "MODULO"
    ASSIGN = "ASSIGN"
    EQUALS = "EQUALS"
    NOT_EQUALS = "NOT_EQUALS"
    LESS_THAN = "LESS_THAN"
    GREATER_THAN = "GREATER_THAN"
    LESS_EQUAL = "LESS_EQUAL"
    GREATER_EQUAL = "GREATER_EQUAL"
    AND = "AND"
    OR = "OR"
    NOT = "NOT"
    INCREMENT = "INCREMENT"
    DECREMENT = "DECREMENT"
    PLUS_ASSIGN = "PLUS_ASSIGN"
    MINUS_ASSIGN = "MINUS_ASSIGN"
    MULTIPLY_ASSIGN = "MULTIPLY_ASSIGN"
    DIVIDE_ASSIGN = "DIVIDE_ASSIGN"

    # Pointer operators
    DEREFERENCE = "DEREFERENCE"  # *
    ADDRESS_OF = "ADDRESS_OF"  # &

    # Delimiters
    LEFT_PAREN = "LEFT_PAREN"
    RIGHT_PAREN = "RIGHT_PAREN"
    LEFT_BRACE = "LEFT_BRACE"
    RIGHT_BRACE = "RIGHT_BRACE"
    LEFT_BRACKET = "LEFT_BRACKET"
    RIGHT_BRACKET = "RIGHT_BRACKET"
    LEFT_ANGLE = "LEFT_ANGLE"  # <
    RIGHT_ANGLE = "RIGHT_ANGLE"  # >
    SEMICOLON = "SEMICOLON"
    COLON = "COLON"
    COMMA = "COMMA"
    DOT = "DOT"
    ARROW = "ARROW"  # ->

    # Special
    IDENTIFIER = "IDENTIFIER"
    INTEGER_LITERAL = "INTEGER_LITERAL"
    FLOAT_LITERAL = "FLOAT_LITERAL"
    STRING_LITERAL = "STRING_LITERAL"
    D_STRING_LITERAL = "D_STRING_LITERAL"  # Dynamic string
    ANNOTATION = "ANNOTATION"  # @attribute(...)

    # End of file
    EOF = "EOF"


class Token:
    def __init__(self, type: TokenType, value: str, line: int, column: int):
        self.type = type
        self.value = value
        self.line = line
        self.column = column

    def __repr__(self):
        return f"Token({self.type.name}, '{self.value}', {self.line}:{self.column})"

    def __str__(self):
        return f"{self.type.name}('{self.value}')"


class Lexer:
    KEYWORDS = {
        "class": TokenType.CLASS,
        "function": TokenType.FUNCTION,
        "method": TokenType.METHOD,
        "parametrized": TokenType.PARAMETRIZED,
        "extends": TokenType.EXTENDS,
        "implements": TokenType.IMPLEMENTS,
        "private": TokenType.PRIVATE,
        "protected": TokenType.PROTECTED,
        "public": TokenType.PUBLIC,
        "var": TokenType.VAR,
        "const": TokenType.CONST,
        "return": TokenType.RETURN,
        "if": TokenType.IF,
        "else": TokenType.ELSE,
        "while": TokenType.WHILE,
        "for": TokenType.FOR,
        "in": TokenType.IN,
        "break": TokenType.BREAK,
        "continue": TokenType.CONTINUE,
        "true": TokenType.TRUE,
        "false": TokenType.FALSE,
        "null": TokenType.NULL,
        "new": TokenType.NEW,
        "this": TokenType.THIS,
        "self": TokenType.SELF,
        "print": TokenType.PRINT,
        "println": TokenType.PRINTLN,
        "interface": TokenType.INTERFACE,
        "abstract": TokenType.ABSTRACT,
        "int": TokenType.INT,
        "float": TokenType.FLOAT,
        "double": TokenType.DOUBLE,
        "boolean": TokenType.BOOLEAN,
        "str": TokenType.STR,
        "void": TokenType.VOID,
    }

    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.column = 1
        self.tokens: List[Token] = []

    def current_char(self) -> Optional[str]:
        """Get current character or None if EOF"""
        if self.pos >= len(self.source):
            return None
        return self.source[self.pos]

    def peek_char(self, offset: int = 1) -> Optional[str]:
        """Peek ahead by offset characters"""
        peek_pos = self.pos + offset
        if peek_pos >= len(self.source):
            return None
        return self.source[peek_pos]

    def advance(self) -> Optional[str]:
        """Advance position and return current character"""
        if self.pos >= len(self.source):
            return None
        char = self.source[self.pos]
        self.pos += 1
        if char == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return char

    def skip_whitespace(self):
        """Skip whitespace characters"""
        while self.current_char() and self.current_char() in " \t\r\n":
            self.advance()

    def skip_comment(self):
        """Skip single-line comments (//) and multi-line comments (/* */)"""
        if self.current_char() == "/" and self.peek_char() == "/":
            # Single-line comment
            while self.current_char() and self.current_char() != "\n":
                self.advance()
        elif self.current_char() == "/" and self.peek_char() == "*":
            # Multi-line comment
            self.advance()  # skip /
            self.advance()  # skip *
            while self.current_char():
                if self.current_char() == "*" and self.peek_char() == "/":
                    self.advance()  # skip *
                    self.advance()  # skip /
                    break
                self.advance()

    def read_string(self, is_dynamic: bool = False) -> str:
        """Read a string literal (regular or dynamic D-string)"""
        quote_char = self.current_char()  # " or '
        self.advance()  # skip opening quote
        
        value = ""
        while self.current_char() and self.current_char() != quote_char:
            if self.current_char() == "\\":
                self.advance()  # skip backslash
                if self.current_char():
                    # Handle escape sequences
                    esc = self.current_char()
                    if esc == "n":
                        value += "\n"
                    elif esc == "t":
                        value += "\t"
                    elif esc == "\\":
                        value += "\\"
                    elif esc == quote_char:
                        value += quote_char
                    else:
                        value += "\\" + esc
                    self.advance()
                else:
                    value += "\\"
            else:
                value += self.current_char()
                self.advance()
        
        if self.current_char() == quote_char:
            self.advance()  # skip closing quote
        else:
            raise SyntaxError(f"Unterminated string at line {self.line}, column {self.column}")
        
        return value

    def read_number(self) -> Tuple[str, TokenType]:
        """Read a number (integer or float)"""
        num_str = ""
        is_float = False
        
        # Read digits
        while self.current_char() and self.current_char().isdigit():
            num_str += self.current_char()
            self.advance()
        
        # Check for decimal point
        if self.current_char() == ".":
            is_float = True
            num_str += self.current_char()
            self.advance()
            while self.current_char() and self.current_char().isdigit():
                num_str += self.current_char()
                self.advance()
        
        return num_str, TokenType.FLOAT_LITERAL if is_float else TokenType.INTEGER_LITERAL

    def read_identifier_or_keyword(self) -> str:
        """Read an identifier or keyword"""
        ident = ""
        while self.current_char() and (self.current_char().isalnum() or self.current_char() == "_"):
            ident += self.current_char()
            self.advance()
        return ident

    def read_annotation(self) -> str:
        """Read an annotation like @attribute or @attribute(read_only=true)"""
        annotation = "@"
        self.advance()  # skip @
        
        # Read identifier
        while self.current_char() and (self.current_char().isalnum() or self.current_char() == "_"):
            annotation += self.current_char()
            self.advance()
        
        # Check for parameters
        if self.current_char() == "(":
            annotation += "("
            self.advance()
            paren_count = 1
            while self.current_char() and paren_count > 0:
                if self.current_char() == "(":
                    paren_count += 1
                elif self.current_char() == ")":
                    paren_count -= 1
                annotation += self.current_char()
                self.advance()
        
        return annotation

    def tokenize(self) -> List[Token]:
        """Tokenize the source code"""
        self.tokens = []
        
        while self.pos < len(self.source):
            self.skip_whitespace()
            
            if self.pos >= len(self.source):
                break
            
            char = self.current_char()
            start_line = self.line
            start_col = self.column
            
            # Check for comments
            if char == "/" and self.peek_char() in ["/", "*"]:
                self.skip_comment()
                continue
            
            # Check for dynamic string (D"...")
            if char == "D" and self.peek_char() in ['"', "'"]:
                self.advance()  # skip D
                value = self.read_string(is_dynamic=True)
                self.tokens.append(Token(TokenType.D_STRING_LITERAL, value, start_line, start_col))
                continue
            
            # Check for string literal
            if char in ['"', "'"]:
                value = self.read_string()
                self.tokens.append(Token(TokenType.STRING_LITERAL, value, start_line, start_col))
                continue
            
            # Check for annotation
            if char == "@":
                value = self.read_annotation()
                self.tokens.append(Token(TokenType.ANNOTATION, value, start_line, start_col))
                continue
            
            # Check for numbers
            if char.isdigit():
                value, token_type = self.read_number()
                self.tokens.append(Token(token_type, value, start_line, start_col))
                continue
            
            # Check for identifiers and keywords
            if char.isalpha() or char == "_":
                value = self.read_identifier_or_keyword()
                token_type = self.KEYWORDS.get(value, TokenType.IDENTIFIER)
                self.tokens.append(Token(token_type, value, start_line, start_col))
                continue
            
            # Operators and delimiters
            if char == "+":
                if self.peek_char() == "+":
                    self.advance()
                    self.advance()
                    self.tokens.append(Token(TokenType.INCREMENT, "++", start_line, start_col))
                elif self.peek_char() == "=":
                    self.advance()
                    self.advance()
                    self.tokens.append(Token(TokenType.PLUS_ASSIGN, "+=", start_line, start_col))
                else:
                    self.advance()
                    self.tokens.append(Token(TokenType.PLUS, "+", start_line, start_col))
            elif char == "-":
                if self.peek_char() == ">":
                    self.advance()
                    self.advance()
                    self.tokens.append(Token(TokenType.ARROW, "->", start_line, start_col))
                elif self.peek_char() == "-":
                    self.advance()
                    self.advance()
                    self.tokens.append(Token(TokenType.DECREMENT, "--", start_line, start_col))
                elif self.peek_char() == "=":
                    self.advance()
                    self.advance()
                    self.tokens.append(Token(TokenType.MINUS_ASSIGN, "-=", start_line, start_col))
                else:
                    self.advance()
                    self.tokens.append(Token(TokenType.MINUS, "-", start_line, start_col))
            elif char == "*":
                self.advance()
                self.tokens.append(Token(TokenType.DEREFERENCE, "*", start_line, start_col))
            elif char == "&":
                if self.peek_char() == "&":
                    self.advance()
                    self.advance()
                    self.tokens.append(Token(TokenType.AND, "&&", start_line, start_col))
                else:
                    self.advance()
                    self.tokens.append(Token(TokenType.ADDRESS_OF, "&", start_line, start_col))
            elif char == "|":
                if self.peek_char() == "|":
                    self.advance()
                    self.advance()
                    self.tokens.append(Token(TokenType.OR, "||", start_line, start_col))
                else:
                    raise LexerError(f"Unexpected character '{char}' at line {start_line}, column {start_col}")
            elif char == "^":
                self.advance()
                self.tokens.append(Token(TokenType.MULTIPLY, "^", start_line, start_col))  # XOR as MULTIPLY temporarily
            elif char == "=":
                if self.peek_char() == "=":
                    self.advance()
                    self.advance()
                    self.tokens.append(Token(TokenType.EQUALS, "==", start_line, start_col))
                else:
                    self.advance()
                    self.tokens.append(Token(TokenType.ASSIGN, "=", start_line, start_col))
            elif char == "!":
                if self.peek_char() == "=":
                    self.advance()
                    self.advance()
                    self.tokens.append(Token(TokenType.NOT_EQUALS, "!=", start_line, start_col))
                else:
                    self.advance()
                    self.tokens.append(Token(TokenType.NOT, "!", start_line, start_col))
            elif char == "<":
                if self.peek_char() == "=":
                    self.advance()
                    self.advance()
                    self.tokens.append(Token(TokenType.LESS_EQUAL, "<=", start_line, start_col))
                else:
                    self.advance()
                    self.tokens.append(Token(TokenType.LEFT_ANGLE, "<", start_line, start_col))
            elif char == ">":
                if self.peek_char() == "=":
                    self.advance()
                    self.advance()
                    self.tokens.append(Token(TokenType.GREATER_EQUAL, ">=", start_line, start_col))
                else:
                    self.advance()
                    self.tokens.append(Token(TokenType.RIGHT_ANGLE, ">", start_line, start_col))
            elif char == "/":
                if self.peek_char() == "=":
                    self.advance()
                    self.advance()
                    self.tokens.append(Token(TokenType.DIVIDE_ASSIGN, "/=", start_line, start_col))
                else:
                    self.advance()
                    self.tokens.append(Token(TokenType.DIVIDE, "/", start_line, start_col))
            elif char == "%":
                if self.peek_char() == "=":
                    self.advance()
                    self.advance()
                    self.tokens.append(Token(TokenType.MODULO, "%=", start_line, start_col))
                else:
                    self.advance()
                    self.tokens.append(Token(TokenType.MODULO, "%", start_line, start_col))
            elif char == "(":
                self.advance()
                self.tokens.append(Token(TokenType.LEFT_PAREN, "(", start_line, start_col))
            elif char == ")":
                self.advance()
                self.tokens.append(Token(TokenType.RIGHT_PAREN, ")", start_line, start_col))
            elif char == "{":
                self.advance()
                self.tokens.append(Token(TokenType.LEFT_BRACE, "{", start_line, start_col))
            elif char == "}":
                self.advance()
                self.tokens.append(Token(TokenType.RIGHT_BRACE, "}", start_line, start_col))
            elif char == "[":
                self.advance()
                self.tokens.append(Token(TokenType.LEFT_BRACKET, "[", start_line, start_col))
            elif char == "]":
                self.advance()
                self.tokens.append(Token(TokenType.RIGHT_BRACKET, "]", start_line, start_col))
            elif char == ";":
                self.advance()
                self.tokens.append(Token(TokenType.SEMICOLON, ";", start_line, start_col))
            elif char == ":":
                self.advance()
                self.tokens.append(Token(TokenType.COLON, ":", start_line, start_col))
            elif char == ",":
                self.advance()
                self.tokens.append(Token(TokenType.COMMA, ",", start_line, start_col))
            elif char == ".":
                self.advance()
                self.tokens.append(Token(TokenType.DOT, ".", start_line, start_col))
            else:
                raise SyntaxError(f"Unexpected character '{char}' at line {self.line}, column {self.column}")
        
        # Add EOF token
        self.tokens.append(Token(TokenType.EOF, "", self.line, self.column))
        return self.tokens
