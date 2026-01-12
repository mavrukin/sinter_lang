"""
Semantic Analyzer for Sinter Programming Language
Performs type checking, scope validation, and builds type information
"""

from typing import Dict, List, Optional, Tuple
from compiler.sinter_ast.nodes import (
    ASTNode, Program, ClassDeclaration, MethodDeclaration, FunctionDeclaration,
    FieldDeclaration, Parameter, Block, Expression, BinaryExpression,
    UnaryExpression, Literal, Identifier, MemberAccess, MethodCall,
    NewExpression, PointerExpression, Statement, ExpressionStatement,
    ReturnStatement, VariableDeclaration, IfStatement, WhileStatement,
    AssignmentStatement, Visibility, AttributeAnnotation, ScopeBlock,
    ForStatement, ForEachStatement, BreakStatement, ContinueStatement,
    PrintStatement, ArrayLiteral, ArrayAccess
)
from compiler.sinter_types.types import (
    SinterType, PrimitiveType, VoidType, NullType, StringType, DStringType,
    PointerType, ArrayType, ClassType, FunctionType, TypeRegistry,
    FieldInfo, MethodInfo
)
from compiler.sinter_types.symbol_table import SymbolTable, Symbol, SymbolKind, Scope


class SemanticError(Exception):
    """Raised when semantic analysis fails"""
    pass


class PointerCleanupError(Exception):
    """Raised when pointer cleanup validation fails"""
    pass


class SemanticAnalyzer:
    """Performs semantic analysis on the AST"""
    
    def __init__(self):
        self.type_registry = TypeRegistry()
        self.symbol_table = SymbolTable()
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.current_class: Optional[ClassType] = None
        self.current_method: Optional[MethodInfo] = None
        self.current_return_type: Optional[SinterType] = None
    
    def analyze(self, ast: Program) -> Tuple[TypeRegistry, SymbolTable]:
        """Perform semantic analysis on the program"""
        self.errors = []
        self.warnings = []
        
        # First pass: Register all classes (forward declarations)
        for decl in ast.declarations:
            if isinstance(decl, ClassDeclaration):
                self._register_class(decl)
        
        # Second pass: Build class hierarchies and resolve types
        for decl in ast.declarations:
            if isinstance(decl, ClassDeclaration):
                self._resolve_class_hierarchy(decl)
        
        # Third pass: Analyze class members
        for decl in ast.declarations:
            if isinstance(decl, ClassDeclaration):
                self._analyze_class(decl)
        
        # Fourth pass: Analyze functions
        for decl in ast.declarations:
            if isinstance(decl, FunctionDeclaration):
                self._analyze_function(decl)
        
        if self.errors:
            raise SemanticError("\n".join(self.errors))
        
        return self.type_registry, self.symbol_table
    
    def _register_class(self, decl: ClassDeclaration):
        """Register a class in the type registry"""
        if self.type_registry.get(decl.name):
            self._error(f"Duplicate class definition: {decl.name}", decl.line, decl.column)
            return
        
        class_type = ClassType(decl.name, decl.type_parameters)
        self.type_registry.register(class_type)
        
        # Register in symbol table
        self.symbol_table.define(
            decl.name, SymbolKind.CLASS, class_type,
            llvm_name=f"@class.{decl.name}"
        )
    
    def _resolve_class_hierarchy(self, decl: ClassDeclaration):
        """Resolve class inheritance and interfaces"""
        class_type = self.type_registry.get(decl.name)
        if not isinstance(class_type, ClassType):
            return
        
        # Resolve parent class
        if decl.extends:
            parent_type = self.type_registry.get(decl.extends)
            if not parent_type:
                self._error(f"Base class '{decl.extends}' not found", decl.line, decl.column)
            elif not isinstance(parent_type, ClassType):
                self._error(f"'{decl.extends}' is not a class", decl.line, decl.column)
            else:
                class_type.parent_class = parent_type
                # Inherit fields from parent
                for name, field in parent_type.fields.items():
                    class_type.fields[name] = field
                # Inherit vtable from parent
                class_type.vtable = parent_type.vtable.copy()
        
        # Register interfaces
        class_type.interfaces = decl.implements
    
    def _analyze_class(self, decl: ClassDeclaration):
        """Analyze a class declaration"""
        class_type = self.type_registry.get(decl.name)
        if not isinstance(class_type, ClassType):
            return
        
        self.current_class = class_type
        self.symbol_table.enter_scope(f"class_{decl.name}")
        
        # Process members with their visibility
        current_visibility = "public"
        
        for member in decl.members:
            if isinstance(member, ScopeBlock):
                current_visibility = member.visibility.value
                for sub_member in member.members:
                    self._analyze_class_member(sub_member, class_type, current_visibility)
            else:
                self._analyze_class_member(member, class_type, current_visibility)
        
        self.symbol_table.exit_scope()
        self.current_class = None
    
    def _analyze_class_member(self, member: ASTNode, class_type: ClassType, visibility: str):
        """Analyze a class member (field or method)"""
        if isinstance(member, FieldDeclaration):
            self._analyze_field(member, class_type, visibility)
        elif isinstance(member, MethodDeclaration):
            self._analyze_method(member, class_type, visibility)
    
    def _analyze_field(self, field: FieldDeclaration, class_type: ClassType, visibility: str):
        """Analyze a field declaration"""
        field_type = self._resolve_type(field.type_name)
        if not field_type:
            self._error(f"Unknown type '{field.type_name}'", field.line, field.column)
            field_type = self.type_registry.get("int")  # Default to int
        
        # Check annotation attributes
        is_serializable = False
        is_derived = False
        is_read_only = False
        is_write_only = False
        
        if field.annotation:
            is_serializable = field.annotation.serializable
            is_derived = field.annotation.derived
            is_read_only = field.annotation.read_only
            is_write_only = field.annotation.write_only
            
            # Validate: only public fields can be serializable
            if is_serializable and visibility != "public":
                self._error(
                    f"Field '{field.name}' cannot be serializable because it's not public",
                    field.line, field.column
                )
            
            # Derived fields shouldn't be serialized
            if is_derived and is_serializable:
                self._warning(
                    f"Field '{field.name}' is derived and should not be serializable",
                    field.line, field.column
                )
        
        # Analyze initial value if present
        if field.initial_value:
            init_type = self._analyze_expression(field.initial_value)
            if init_type and not self._types_compatible(field_type, init_type):
                self._error(
                    f"Type mismatch: cannot assign {init_type.name} to {field_type.name}",
                    field.line, field.column
                )
        
        field_info = FieldInfo(
            field.name, field_type, 0,  # offset calculated later
            field.is_const, visibility,
            is_serializable, is_derived, is_read_only, is_write_only,
            default_value=field.initial_value  # Store the AST expression
        )
        class_type.add_field(field_info)
    
    def _analyze_method(self, method: MethodDeclaration, class_type: ClassType, visibility: str):
        """Analyze a method declaration"""
        return_type = self._resolve_type(method.return_type)
        if not return_type:
            self._error(f"Unknown return type '{method.return_type}'", method.line, method.column)
            return_type = self.type_registry.get("void")
        
        # Analyze parameters
        param_types = []
        param_names = []
        for param in method.parameters:
            param_type = self._resolve_type(param.type_name)
            if not param_type:
                self._error(f"Unknown parameter type '{param.type_name}'", param.line, param.column)
                param_type = self.type_registry.get("int")
            param_types.append(param_type)
            param_names.append(param.name)
        
        method_info = MethodInfo(
            method.name, return_type, param_types, param_names,
            method.is_static, visibility
        )
        class_type.add_method(method_info)
        
        # Analyze method body
        self.current_method = method_info
        self.current_return_type = return_type
        scope_name = f"method_{class_type.name}_{method.name}"
        self.symbol_table.enter_scope(scope_name)
        
        # Add 'this' for non-static methods
        if not method.is_static:
            this_type = self.type_registry.get_or_create_pointer(class_type)
            self.symbol_table.define("this", SymbolKind.PARAMETER, this_type, llvm_name="%this")
        
        # Add parameters to scope
        for name, ptype in zip(param_names, param_types):
            self.symbol_table.define(name, SymbolKind.PARAMETER, ptype)
        
        # Analyze body
        if method.body:
            self._analyze_block(method.body)
        
        self.symbol_table.exit_scope()
        self.current_method = None
        self.current_return_type = None
    
    def _analyze_function(self, func: FunctionDeclaration):
        """Analyze a function declaration"""
        return_type = self._resolve_type(func.return_type)
        if not return_type:
            self._error(f"Unknown return type '{func.return_type}'", func.line, func.column)
            return_type = self.type_registry.get("void")
        
        # Analyze parameters
        param_types = []
        param_names = []
        for param in func.parameters:
            param_type = self._resolve_type(param.type_name)
            if not param_type:
                self._error(f"Unknown parameter type '{param.type_name}'", param.line, param.column)
                param_type = self.type_registry.get("int")
            param_types.append(param_type)
            param_names.append(param.name)
        
        # Register function
        func_type = FunctionType(return_type, param_types)
        self.symbol_table.define(
            func.name, SymbolKind.FUNCTION, func_type,
            llvm_name=f"@{func.name}"
        )
        
        # Analyze function body
        self.current_return_type = return_type
        self.symbol_table.enter_scope(f"function_{func.name}")
        
        # Add parameters to scope
        for name, ptype in zip(param_names, param_types):
            self.symbol_table.define(name, SymbolKind.PARAMETER, ptype)
        
        # Analyze body
        if func.body:
            self._analyze_block(func.body)
        
        self.symbol_table.exit_scope()
        self.current_return_type = None
    
    def _analyze_block(self, block: Block):
        """Analyze a block of statements"""
        for stmt in block.statements:
            self._analyze_statement(stmt)
    
    def _analyze_statement(self, stmt: Statement):
        """Analyze a statement"""
        if isinstance(stmt, VariableDeclaration):
            self._analyze_var_declaration(stmt)
        elif isinstance(stmt, ReturnStatement):
            self._analyze_return(stmt)
        elif isinstance(stmt, IfStatement):
            self._analyze_if(stmt)
        elif isinstance(stmt, WhileStatement):
            self._analyze_while(stmt)
        elif isinstance(stmt, ForStatement):
            self._analyze_for(stmt)
        elif isinstance(stmt, ForEachStatement):
            self._analyze_foreach(stmt)
        elif isinstance(stmt, BreakStatement):
            pass  # Valid in loops
        elif isinstance(stmt, ContinueStatement):
            pass  # Valid in loops
        elif isinstance(stmt, PrintStatement):
            for arg in stmt.arguments:
                self._analyze_expression(arg)
        elif isinstance(stmt, ExpressionStatement):
            self._analyze_expression(stmt.expression)
        elif isinstance(stmt, AssignmentStatement):
            self._analyze_assignment(stmt)
    
    def _analyze_for(self, stmt: ForStatement):
        """Analyze a for statement"""
        self.symbol_table.enter_scope("for_body")
        
        if stmt.init:
            self._analyze_statement(stmt.init)
        
        if stmt.condition:
            cond_type = self._analyze_expression(stmt.condition)
            if cond_type and cond_type.name != "boolean":
                self._error("For condition must be boolean", 0, 0)
        
        if stmt.update:
            self._analyze_expression(stmt.update)
        
        self._analyze_block(stmt.body)
        self.symbol_table.exit_scope()
    
    def _analyze_foreach(self, stmt: ForEachStatement):
        """Analyze a for-each statement"""
        self.symbol_table.enter_scope("foreach_body")
        
        # Analyze collection
        coll_type = self._analyze_expression(stmt.collection)
        
        # Add loop variable to scope
        var_type = self._resolve_type(stmt.var_type)
        if var_type:
            self.symbol_table.define(stmt.var_name, SymbolKind.VARIABLE, var_type)
        
        self._analyze_block(stmt.body)
        self.symbol_table.exit_scope()
    
    def _analyze_var_declaration(self, stmt: VariableDeclaration):
        """Analyze a variable declaration"""
        var_type = self._resolve_type(stmt.type_name)
        if not var_type:
            self._error(f"Unknown type '{stmt.type_name}'", 0, 0)
            var_type = self.type_registry.get("int")
        
        # Check if it's a pointer type
        is_pointer = var_type.is_pointer()
        
        symbol = self.symbol_table.define(stmt.name, SymbolKind.VARIABLE, var_type)
        symbol.is_pointer_allocated = is_pointer
        
        if stmt.initial_value:
            init_type = self._analyze_expression(stmt.initial_value)
            if init_type and not self._types_compatible(var_type, init_type):
                self._error(f"Type mismatch in variable declaration", 0, 0)
            symbol.is_initialized = True
    
    def _analyze_return(self, stmt: ReturnStatement):
        """Analyze a return statement"""
        if stmt.value:
            return_type = self._analyze_expression(stmt.value)
            if return_type and self.current_return_type:
                if not self._types_compatible(self.current_return_type, return_type):
                    self._error(
                        f"Return type mismatch: expected {self.current_return_type.name}, got {return_type.name}",
                        0, 0
                    )
        elif self.current_return_type and self.current_return_type.name != "void":
            self._error("Non-void function must return a value", 0, 0)
    
    def _analyze_if(self, stmt: IfStatement):
        """Analyze an if statement"""
        cond_type = self._analyze_expression(stmt.condition)
        if cond_type and cond_type.name != "boolean":
            self._error("Condition must be boolean", 0, 0)
        
        self.symbol_table.enter_scope("if_then")
        self._analyze_block(stmt.then_block)
        self.symbol_table.exit_scope()
        
        if stmt.else_block:
            self.symbol_table.enter_scope("if_else")
            self._analyze_block(stmt.else_block)
            self.symbol_table.exit_scope()
    
    def _analyze_while(self, stmt: WhileStatement):
        """Analyze a while statement"""
        cond_type = self._analyze_expression(stmt.condition)
        if cond_type and cond_type.name != "boolean":
            self._error("Condition must be boolean", 0, 0)
        
        self.symbol_table.enter_scope("while_body")
        self._analyze_block(stmt.body)
        self.symbol_table.exit_scope()
    
    def _analyze_assignment(self, stmt: AssignmentStatement):
        """Analyze an assignment statement"""
        target_type = self._analyze_expression(stmt.target)
        value_type = self._analyze_expression(stmt.value)
        
        if target_type and value_type:
            if not self._types_compatible(target_type, value_type):
                self._error(
                    f"Type mismatch in assignment: {target_type.name} vs {value_type.name}",
                    0, 0
                )
    
    def _analyze_expression(self, expr: Expression) -> Optional[SinterType]:
        """Analyze an expression and return its type"""
        if isinstance(expr, Literal):
            return self._analyze_literal(expr)
        elif isinstance(expr, Identifier):
            return self._analyze_identifier(expr)
        elif isinstance(expr, BinaryExpression):
            return self._analyze_binary(expr)
        elif isinstance(expr, UnaryExpression):
            return self._analyze_unary(expr)
        elif isinstance(expr, MemberAccess):
            return self._analyze_member_access(expr)
        elif isinstance(expr, MethodCall):
            return self._analyze_method_call(expr)
        elif isinstance(expr, NewExpression):
            return self._analyze_new(expr)
        elif isinstance(expr, PointerExpression):
            return self._analyze_pointer_expr(expr)
        elif isinstance(expr, AssignmentStatement):
            # Assignment used as expression
            self._analyze_assignment(expr)
            return self._analyze_expression(expr.target)
        return None
    
    def _analyze_literal(self, lit: Literal) -> SinterType:
        """Analyze a literal and return its type"""
        type_map = {
            "int": "int",
            "float": "float",
            "double": "double",
            "boolean": "boolean",
            "str": "str",
            "d_str": "d_str",
            "null": "null",
        }
        type_name = type_map.get(lit.literal_type, "int")
        return self.type_registry.get(type_name)
    
    def _analyze_identifier(self, ident: Identifier) -> Optional[SinterType]:
        """Analyze an identifier and return its type"""
        symbol = self.symbol_table.resolve(ident.name)
        if not symbol:
            # Check if it's a class field (implicit this)
            if self.current_class:
                field = self.current_class.get_field(ident.name)
                if field:
                    return field.field_type
            self._error(f"Undefined identifier '{ident.name}'", ident.line, ident.column)
            return None
        return symbol.symbol_type
    
    def _analyze_binary(self, expr: BinaryExpression) -> Optional[SinterType]:
        """Analyze a binary expression"""
        left_type = self._analyze_expression(expr.left)
        right_type = self._analyze_expression(expr.right)
        
        if not left_type or not right_type:
            return None
        
        # Comparison operators return boolean
        if expr.operator in ["==", "!=", "<", ">", "<=", ">="]:
            return self.type_registry.get("boolean")
        
        # Logical operators return boolean
        if expr.operator in ["&&", "||"]:
            return self.type_registry.get("boolean")
        
        # Arithmetic operators return the wider type
        if expr.operator in ["+", "-", "*", "/", "%"]:
            return self._wider_type(left_type, right_type)
        
        return left_type
    
    def _analyze_unary(self, expr: UnaryExpression) -> Optional[SinterType]:
        """Analyze a unary expression"""
        operand_type = self._analyze_expression(expr.operand)
        if not operand_type:
            return None
        
        if expr.operator == "!":
            return self.type_registry.get("boolean")
        elif expr.operator == "-":
            return operand_type
        elif expr.operator == "*":  # Dereference
            if operand_type.is_pointer():
                return operand_type.pointee_type
            self._error("Cannot dereference non-pointer type", 0, 0)
            return None
        elif expr.operator == "&":  # Address-of
            return self.type_registry.get_or_create_pointer(operand_type)
        elif expr.operator in ["++", "--"]:
            return operand_type
        
        return operand_type
    
    def _analyze_member_access(self, expr: MemberAccess) -> Optional[SinterType]:
        """Analyze member access (obj.member)"""
        # Special case: Class.new() constructor call
        if expr.member == "new" and isinstance(expr.object_expr, Identifier):
            class_type = self.type_registry.get(expr.object_expr.name)
            if isinstance(class_type, ClassType):
                # Return a function type that returns pointer to class
                ptr_type = self.type_registry.get_or_create_pointer(class_type)
                return FunctionType(ptr_type, [])
        
        obj_type = self._analyze_expression(expr.object_expr)
        if not obj_type:
            return None
        
        # Handle pointer types
        actual_type = obj_type
        if obj_type.is_pointer() and isinstance(obj_type, PointerType):
            actual_type = obj_type.pointee_type
        
        if not actual_type.is_class():
            self._error(f"Cannot access member of non-class type '{actual_type.name}'", 0, 0)
            return None
        
        # Look up field or method
        if isinstance(actual_type, ClassType):
            field = actual_type.get_field(expr.member)
            if field:
                return field.field_type
            
            method = actual_type.get_method(expr.member)
            if method:
                return FunctionType(method.return_type, method.param_types)
        
        self._error(f"Unknown member '{expr.member}' in class '{actual_type.name}'", 0, 0)
        return None
    
    def _analyze_method_call(self, expr: MethodCall) -> Optional[SinterType]:
        """Analyze a method call"""
        callee_type = self._analyze_expression(expr.callee)
        if not callee_type:
            return None
        
        # Analyze arguments
        arg_types = []
        for arg in expr.arguments:
            arg_type = self._analyze_expression(arg)
            if arg_type:
                arg_types.append(arg_type)
        
        # Check if callee is a function type
        if isinstance(callee_type, FunctionType):
            # Type check arguments
            if len(arg_types) != len(callee_type.param_types):
                self._error(
                    f"Wrong number of arguments: expected {len(callee_type.param_types)}, got {len(arg_types)}",
                    0, 0
                )
            else:
                for i, (expected, actual) in enumerate(zip(callee_type.param_types, arg_types)):
                    if not self._types_compatible(expected, actual):
                        self._error(f"Argument {i+1} type mismatch", 0, 0)
            return callee_type.return_type
        
        # Could be a constructor call (Class.new())
        if isinstance(expr.callee, MemberAccess) and expr.callee.member == "new":
            return callee_type
        
        return None
    
    def _analyze_new(self, expr: NewExpression) -> Optional[SinterType]:
        """Analyze a 'new' expression"""
        class_type = self.type_registry.get(expr.class_name)
        if not class_type:
            self._error(f"Unknown class '{expr.class_name}'", 0, 0)
            return None
        
        return self.type_registry.get_or_create_pointer(class_type)
    
    def _analyze_pointer_expr(self, expr: PointerExpression) -> Optional[SinterType]:
        """Analyze a pointer expression (* or &)"""
        operand_type = self._analyze_expression(expr.operand)
        if not operand_type:
            return None
        
        if expr.operator == "*":  # Dereference
            if operand_type.is_pointer():
                return operand_type.pointee_type
            self._error("Cannot dereference non-pointer type", 0, 0)
        elif expr.operator == "&":  # Address-of
            return self.type_registry.get_or_create_pointer(operand_type)
        
        return None
    
    def _resolve_type(self, type_name: str) -> Optional[SinterType]:
        """Resolve a type name to a SinterType"""
        # Check for pointer type
        if type_name.endswith("*"):
            base_name = type_name[:-1].strip()
            base_type = self._resolve_type(base_name)
            if base_type:
                return self.type_registry.get_or_create_pointer(base_type)
            return None
        
        return self.type_registry.get(type_name)
    
    def _types_compatible(self, target: SinterType, source: SinterType) -> bool:
        """Check if source type can be assigned to target type"""
        if target == source:
            return True
        
        # Null can be assigned to any pointer
        if source.name == "null" and target.is_pointer():
            return True
        
        # D-strings are compatible with strings (they produce string values)
        if target.name == "str" and source.name == "d_str":
            return True
        
        # Numeric promotions
        numeric_types = {"byte", "short", "int", "long", "float", "double"}
        if target.name in numeric_types and source.name in numeric_types:
            # Allow implicit widening
            return True
        
        # Class inheritance
        if target.is_class() and source.is_class():
            # Check if source is subclass of target
            if isinstance(source, ClassType):
                parent = source.parent_class
                while parent:
                    if parent == target:
                        return True
                    parent = parent.parent_class
        
        return False
    
    def _wider_type(self, t1: SinterType, t2: SinterType) -> SinterType:
        """Return the wider of two numeric types"""
        type_order = ["byte", "short", "int", "long", "float", "double"]
        try:
            idx1 = type_order.index(t1.name)
            idx2 = type_order.index(t2.name)
            return t1 if idx1 >= idx2 else t2
        except ValueError:
            return t1
    
    def _error(self, message: str, line: int, column: int):
        """Record an error"""
        loc = f" at line {line}, column {column}" if line > 0 else ""
        self.errors.append(f"Error{loc}: {message}")
    
    def _warning(self, message: str, line: int, column: int):
        """Record a warning"""
        loc = f" at line {line}, column {column}" if line > 0 else ""
        self.warnings.append(f"Warning{loc}: {message}")
