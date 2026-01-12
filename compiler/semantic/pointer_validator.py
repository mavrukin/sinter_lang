"""
Pointer Cleanup Validator for Sinter Programming Language
Ensures all allocated pointers are cleaned up before scope exit
"""

from typing import Dict, List, Set, Optional, Tuple
from compiler.sinter_ast.nodes import (
    ASTNode, Program, ClassDeclaration, MethodDeclaration, FunctionDeclaration,
    Block, Statement, ExpressionStatement, ReturnStatement, VariableDeclaration,
    IfStatement, WhileStatement, AssignmentStatement, Expression, Identifier,
    MemberAccess, MethodCall, NewExpression, BinaryExpression, UnaryExpression
)
from compiler.sinter_types.types import SinterType, PointerType, ClassType


class PointerState:
    """Tracks the state of a pointer variable"""
    ALLOCATED = "allocated"
    RELEASED = "released"
    CLEANED = "cleaned"
    UNKNOWN = "unknown"


class PointerTracker:
    """Tracks pointer allocations and cleanups in a scope"""
    
    def __init__(self, parent: Optional['PointerTracker'] = None):
        self.parent = parent
        self.pointers: Dict[str, str] = {}  # name -> state
        self.allocations: List[Tuple[str, int, int]] = []  # (name, line, col)
    
    def allocate(self, name: str, line: int = 0, col: int = 0):
        """Record a pointer allocation"""
        self.pointers[name] = PointerState.ALLOCATED
        self.allocations.append((name, line, col))
    
    def release(self, name: str):
        """Mark a pointer as released (still exists in another scope)"""
        if name in self.pointers:
            self.pointers[name] = PointerState.RELEASED
        elif self.parent:
            self.parent.release(name)
    
    def clean(self, name: str):
        """Mark a pointer as cleaned (memory freed)"""
        if name in self.pointers:
            self.pointers[name] = PointerState.CLEANED
        elif self.parent:
            self.parent.clean(name)
    
    def get_state(self, name: str) -> Optional[str]:
        """Get the state of a pointer"""
        if name in self.pointers:
            return self.pointers[name]
        if self.parent:
            return self.parent.get_state(name)
        return None
    
    def get_unclean_pointers(self) -> List[Tuple[str, int, int]]:
        """Get all pointers that haven't been cleaned or released"""
        unclean = []
        for name, line, col in self.allocations:
            state = self.pointers.get(name)
            if state == PointerState.ALLOCATED:
                unclean.append((name, line, col))
        return unclean


class PointerValidator:
    """Validates pointer cleanup at scope exit"""
    
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.current_tracker: Optional[PointerTracker] = None
        self.pointer_types: Dict[str, SinterType] = {}  # var name -> type
    
    def validate(self, ast: Program) -> Tuple[List[str], List[str]]:
        """Validate pointer cleanup in the entire program"""
        self.errors = []
        self.warnings = []
        
        for decl in ast.declarations:
            if isinstance(decl, ClassDeclaration):
                self._validate_class(decl)
            elif isinstance(decl, FunctionDeclaration):
                self._validate_function(decl)
        
        return self.errors, self.warnings
    
    def _validate_class(self, class_decl: ClassDeclaration):
        """Validate pointer cleanup in a class"""
        for member in class_decl.members:
            if isinstance(member, MethodDeclaration):
                self._validate_method(member, class_decl.name)
    
    def _validate_method(self, method: MethodDeclaration, class_name: str):
        """Validate pointer cleanup in a method"""
        self.current_tracker = PointerTracker()
        self.pointer_types = {}
        
        if method.body:
            self._validate_block(method.body)
        
        # Check for uncleaned pointers at method exit
        unclean = self.current_tracker.get_unclean_pointers()
        for name, line, col in unclean:
            self.errors.append(
                f"Pointer '{name}' allocated at line {line} is not cleaned up "
                f"before exit of method {class_name}.{method.name}(). "
                f"Use {name}.release() or {name}.clean() before returning."
            )
        
        self.current_tracker = None
    
    def _validate_function(self, func: FunctionDeclaration):
        """Validate pointer cleanup in a function"""
        self.current_tracker = PointerTracker()
        self.pointer_types = {}
        
        if func.body:
            self._validate_block(func.body)
        
        # Check for uncleaned pointers at function exit
        unclean = self.current_tracker.get_unclean_pointers()
        for name, line, col in unclean:
            self.errors.append(
                f"Pointer '{name}' allocated at line {line} is not cleaned up "
                f"before exit of function {func.name}(). "
                f"Use {name}.release() or {name}.clean() before returning."
            )
        
        self.current_tracker = None
    
    def _validate_block(self, block: Block):
        """Validate pointer cleanup in a block"""
        for stmt in block.statements:
            self._validate_statement(stmt)
    
    def _validate_statement(self, stmt: Statement):
        """Validate a statement for pointer operations"""
        if isinstance(stmt, VariableDeclaration):
            self._validate_var_declaration(stmt)
        elif isinstance(stmt, ExpressionStatement):
            self._validate_expression(stmt.expression)
        elif isinstance(stmt, ReturnStatement):
            # Check for uncleaned pointers before return
            if self.current_tracker:
                unclean = self.current_tracker.get_unclean_pointers()
                for name, line, col in unclean:
                    self.errors.append(
                        f"Pointer '{name}' allocated at line {line} is not cleaned up "
                        f"before return statement. "
                        f"Use {name}.release() or {name}.clean() before returning."
                    )
        elif isinstance(stmt, IfStatement):
            self._validate_if(stmt)
        elif isinstance(stmt, WhileStatement):
            self._validate_while(stmt)
        elif isinstance(stmt, AssignmentStatement):
            self._validate_assignment(stmt)
    
    def _validate_var_declaration(self, stmt: VariableDeclaration):
        """Check if a variable declaration involves pointer allocation"""
        if stmt.initial_value and self._is_allocation(stmt.initial_value):
            # This is a pointer allocation
            if self.current_tracker:
                line = getattr(stmt, 'line', 0)
                col = getattr(stmt, 'column', 0)
                self.current_tracker.allocate(stmt.name, line, col)
                self.pointer_types[stmt.name] = stmt.type_name
    
    def _validate_expression(self, expr: Expression):
        """Check expression for pointer operations"""
        if isinstance(expr, MethodCall):
            self._validate_method_call(expr)
    
    def _validate_method_call(self, call: MethodCall):
        """Check for release() or clean() calls"""
        if isinstance(call.callee, MemberAccess):
            method_name = call.callee.member
            
            # Get the object name
            obj_name = None
            if isinstance(call.callee.object_expr, Identifier):
                obj_name = call.callee.object_expr.name
            
            if obj_name and self.current_tracker:
                if method_name == "release":
                    self.current_tracker.release(obj_name)
                elif method_name == "clean":
                    self.current_tracker.clean(obj_name)
    
    def _validate_if(self, stmt: IfStatement):
        """Validate pointer cleanup in if statement"""
        # Create child trackers for branches
        parent_tracker = self.current_tracker
        
        # Validate then branch
        then_tracker = PointerTracker(parent_tracker)
        self.current_tracker = then_tracker
        self._validate_block(stmt.then_block)
        
        # Validate else branch if exists
        else_tracker = None
        if stmt.else_block:
            else_tracker = PointerTracker(parent_tracker)
            self.current_tracker = else_tracker
            self._validate_block(stmt.else_block)
        
        # Restore parent tracker
        self.current_tracker = parent_tracker
        
        # Warn if pointer cleanup differs between branches
        if else_tracker:
            then_unclean = set(n for n, _, _ in then_tracker.get_unclean_pointers())
            else_unclean = set(n for n, _, _ in else_tracker.get_unclean_pointers())
            
            diff = then_unclean.symmetric_difference(else_unclean)
            for name in diff:
                self.warnings.append(
                    f"Pointer '{name}' is cleaned in one branch but not the other. "
                    f"Consider cleaning in both branches or after the if statement."
                )
    
    def _validate_while(self, stmt: WhileStatement):
        """Validate pointer cleanup in while loop"""
        # Allocations inside a loop are problematic if not cleaned each iteration
        parent_tracker = self.current_tracker
        loop_tracker = PointerTracker(parent_tracker)
        self.current_tracker = loop_tracker
        
        self._validate_block(stmt.body)
        
        # Warn about allocations inside loops
        for name, line, col in loop_tracker.allocations:
            state = loop_tracker.pointers.get(name)
            if state == PointerState.ALLOCATED:
                self.warnings.append(
                    f"Pointer '{name}' allocated at line {line} inside a loop "
                    f"may cause memory leaks. Ensure cleanup happens each iteration."
                )
        
        self.current_tracker = parent_tracker
    
    def _validate_assignment(self, stmt: AssignmentStatement):
        """Check if assignment involves pointer allocation"""
        if self._is_allocation(stmt.value):
            if isinstance(stmt.target, Identifier):
                if self.current_tracker:
                    # Check if we're overwriting an existing pointer
                    existing_state = self.current_tracker.get_state(stmt.target.name)
                    if existing_state == PointerState.ALLOCATED:
                        self.warnings.append(
                            f"Pointer '{stmt.target.name}' is being overwritten without "
                            f"being cleaned. This may cause a memory leak."
                        )
                    
                    line = getattr(stmt, 'line', 0)
                    col = getattr(stmt, 'column', 0)
                    self.current_tracker.allocate(stmt.target.name, line, col)
    
    def _is_allocation(self, expr: Expression) -> bool:
        """Check if an expression is a pointer allocation"""
        if isinstance(expr, NewExpression):
            return True
        if isinstance(expr, MethodCall):
            if isinstance(expr.callee, MemberAccess):
                if expr.callee.member == "new":
                    return True
        return False
