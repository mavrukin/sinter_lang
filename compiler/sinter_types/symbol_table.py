"""
Symbol Table for Sinter Programming Language
Manages variable and function scopes during compilation
"""

from typing import Dict, List, Optional, Any
from enum import Enum
from compiler.sinter_types.types import SinterType, ClassType, FunctionType


class SymbolKind(Enum):
    """Kind of symbol"""
    VARIABLE = "variable"
    PARAMETER = "parameter"
    FIELD = "field"
    METHOD = "method"
    FUNCTION = "function"
    CLASS = "class"
    TYPE = "type"


class Symbol:
    """Represents a symbol in the symbol table"""
    
    def __init__(self, name: str, kind: SymbolKind, symbol_type: SinterType,
                 is_const: bool = False, llvm_name: str = None):
        self.name = name
        self.kind = kind
        self.symbol_type = symbol_type
        self.is_const = is_const
        self.llvm_name = llvm_name or name  # Name used in LLVM IR
        self.is_initialized = False
        self.is_pointer_allocated = False  # Track if this is a pointer that needs cleanup
    
    def __repr__(self):
        return f"Symbol({self.name}: {self.symbol_type.name}, {self.kind.value})"


class Scope:
    """Represents a lexical scope"""
    
    def __init__(self, name: str, parent: Optional['Scope'] = None):
        self.name = name
        self.parent = parent
        self.symbols: Dict[str, Symbol] = {}
        self.children: List['Scope'] = []
        self.allocated_pointers: List[Symbol] = []  # Track pointers for cleanup
    
    def define(self, symbol: Symbol) -> bool:
        """Define a symbol in this scope. Returns False if already defined."""
        if symbol.name in self.symbols:
            return False
        self.symbols[symbol.name] = symbol
        if symbol.is_pointer_allocated:
            self.allocated_pointers.append(symbol)
        return True
    
    def lookup(self, name: str) -> Optional[Symbol]:
        """Look up a symbol in this scope only"""
        return self.symbols.get(name)
    
    def resolve(self, name: str) -> Optional[Symbol]:
        """Resolve a symbol, checking parent scopes"""
        if name in self.symbols:
            return self.symbols[name]
        if self.parent:
            return self.parent.resolve(name)
        return None
    
    def get_unclean_pointers(self) -> List[Symbol]:
        """Get pointers that haven't been cleaned up"""
        return [p for p in self.allocated_pointers if p.is_pointer_allocated]


class SymbolTable:
    """Manages all scopes and symbols during compilation"""
    
    def __init__(self):
        self.global_scope = Scope("global")
        self.current_scope = self.global_scope
        self.scope_stack: List[Scope] = [self.global_scope]
        self.temp_counter = 0
        self.label_counter = 0
        self.string_constants: Dict[str, str] = {}  # value -> llvm name
        self.string_counter = 0
    
    def enter_scope(self, name: str) -> Scope:
        """Enter a new scope"""
        new_scope = Scope(name, self.current_scope)
        self.current_scope.children.append(new_scope)
        self.current_scope = new_scope
        self.scope_stack.append(new_scope)
        return new_scope
    
    def exit_scope(self) -> Scope:
        """Exit the current scope, returning it"""
        exited_scope = self.current_scope
        self.scope_stack.pop()
        self.current_scope = self.scope_stack[-1] if self.scope_stack else self.global_scope
        return exited_scope
    
    def define(self, name: str, kind: SymbolKind, symbol_type: SinterType,
               is_const: bool = False, llvm_name: str = None) -> Symbol:
        """Define a new symbol in the current scope"""
        if llvm_name is None:
            llvm_name = self.generate_llvm_name(name)
        symbol = Symbol(name, kind, symbol_type, is_const, llvm_name)
        if not self.current_scope.define(symbol):
            raise NameError(f"Symbol '{name}' already defined in this scope")
        return symbol
    
    def resolve(self, name: str) -> Optional[Symbol]:
        """Resolve a symbol name to its Symbol"""
        return self.current_scope.resolve(name)
    
    def generate_llvm_name(self, base: str) -> str:
        """Generate a unique LLVM name"""
        return f"%{base}.{len(self.scope_stack)}"
    
    def new_temp(self) -> str:
        """Generate a new temporary variable name"""
        name = f"%t{self.temp_counter}"
        self.temp_counter += 1
        return name
    
    def new_label(self, prefix: str = "label") -> str:
        """Generate a new label name"""
        name = f"{prefix}_{self.label_counter}"
        self.label_counter += 1
        return name
    
    def add_string_constant(self, value: str) -> str:
        """Add a string constant and return its LLVM name"""
        if value in self.string_constants:
            return self.string_constants[value]
        name = f"@.str.{self.string_counter}"
        self.string_counter += 1
        self.string_constants[value] = name
        return name
    
    def get_current_function_scope(self) -> Optional[Scope]:
        """Get the nearest enclosing function scope"""
        for scope in reversed(self.scope_stack):
            if scope.name.startswith("function_") or scope.name.startswith("method_"):
                return scope
        return None
    
    def check_pointer_cleanup(self) -> List[str]:
        """Check for uncleaned pointers in current scope, return error messages"""
        errors = []
        unclean = self.current_scope.get_unclean_pointers()
        for ptr in unclean:
            errors.append(f"Pointer '{ptr.name}' not cleaned up before scope exit")
        return errors
