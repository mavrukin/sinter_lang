"""
Type System for Sinter Programming Language
Defines all types and type operations
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from enum import Enum


class TypeKind(Enum):
    """Classification of types"""
    PRIMITIVE = "primitive"
    CLASS = "class"
    POINTER = "pointer"
    ARRAY = "array"
    FUNCTION = "function"
    VOID = "void"
    NULL = "null"
    STRING = "string"
    D_STRING = "d_string"


class SinterType(ABC):
    """Base class for all Sinter types"""
    
    def __init__(self, name: str, kind: TypeKind):
        self.name = name
        self.kind = kind
    
    @abstractmethod
    def llvm_type(self) -> str:
        """Return the LLVM IR type representation"""
        pass
    
    @abstractmethod
    def size_bytes(self) -> int:
        """Return the size in bytes"""
        pass
    
    def is_primitive(self) -> bool:
        return self.kind == TypeKind.PRIMITIVE
    
    def is_pointer(self) -> bool:
        return self.kind == TypeKind.POINTER
    
    def is_class(self) -> bool:
        return self.kind == TypeKind.CLASS
    
    def __eq__(self, other):
        if not isinstance(other, SinterType):
            return False
        return self.name == other.name and self.kind == other.kind
    
    def __hash__(self):
        return hash((self.name, self.kind))
    
    def __repr__(self):
        return f"{self.__class__.__name__}({self.name})"


class PrimitiveType(SinterType):
    """Primitive types: int, float, double, boolean"""
    
    LLVM_TYPES = {
        "int": "i32",
        "float": "float",
        "double": "double",
        "boolean": "i1",
        "byte": "i8",
        "short": "i16",
        "long": "i64",
    }
    
    SIZES = {
        "int": 4,
        "float": 4,
        "double": 8,
        "boolean": 1,
        "byte": 1,
        "short": 2,
        "long": 8,
    }
    
    def __init__(self, name: str):
        super().__init__(name, TypeKind.PRIMITIVE)
    
    def llvm_type(self) -> str:
        return self.LLVM_TYPES.get(self.name, "i32")
    
    def size_bytes(self) -> int:
        return self.SIZES.get(self.name, 4)


class VoidType(SinterType):
    """Void type for functions with no return value"""
    
    def __init__(self):
        super().__init__("void", TypeKind.VOID)
    
    def llvm_type(self) -> str:
        return "void"
    
    def size_bytes(self) -> int:
        return 0


class NullType(SinterType):
    """Null type"""
    
    def __init__(self):
        super().__init__("null", TypeKind.NULL)
    
    def llvm_type(self) -> str:
        return "i8*"
    
    def size_bytes(self) -> int:
        return 8  # pointer size


class StringType(SinterType):
    """String type (immutable, captured at creation)"""
    
    def __init__(self):
        super().__init__("str", TypeKind.STRING)
    
    def llvm_type(self) -> str:
        return "%String*"
    
    def size_bytes(self) -> int:
        return 8  # pointer to string struct


class DStringType(SinterType):
    """Dynamic string type (updates when referenced variables change)"""
    
    def __init__(self):
        super().__init__("d_str", TypeKind.D_STRING)
    
    def llvm_type(self) -> str:
        return "%DString*"
    
    def size_bytes(self) -> int:
        return 8  # pointer to d-string struct


class PointerType(SinterType):
    """Pointer to another type"""
    
    def __init__(self, pointee_type: SinterType):
        super().__init__(f"{pointee_type.name}*", TypeKind.POINTER)
        self.pointee_type = pointee_type
    
    def llvm_type(self) -> str:
        return f"{self.pointee_type.llvm_type()}*"
    
    def size_bytes(self) -> int:
        return 8  # 64-bit pointers


class ArrayType(SinterType):
    """Array type"""
    
    def __init__(self, element_type: SinterType, size: Optional[int] = None):
        name = f"{element_type.name}[]" if size is None else f"{element_type.name}[{size}]"
        super().__init__(name, TypeKind.ARRAY)
        self.element_type = element_type
        self.size = size
    
    def llvm_type(self) -> str:
        if self.size is not None:
            return f"[{self.size} x {self.element_type.llvm_type()}]"
        return f"{self.element_type.llvm_type()}*"  # Dynamic array as pointer
    
    def size_bytes(self) -> int:
        if self.size is not None:
            return self.size * self.element_type.size_bytes()
        return 8  # pointer for dynamic arrays


class FieldInfo:
    """Information about a class field"""
    
    def __init__(self, name: str, field_type: SinterType, offset: int, 
                 is_const: bool = False, visibility: str = "public",
                 is_serializable: bool = False, is_derived: bool = False,
                 is_read_only: bool = False, is_write_only: bool = False,
                 default_value: Any = None):
        self.name = name
        self.field_type = field_type
        self.offset = offset  # byte offset in struct
        self.is_const = is_const
        self.visibility = visibility
        self.is_serializable = is_serializable
        self.is_derived = is_derived
        self.is_read_only = is_read_only
        self.is_write_only = is_write_only
        self.default_value = default_value  # AST expression for initialization


class MethodInfo:
    """Information about a class method"""
    
    def __init__(self, name: str, return_type: SinterType,
                 param_types: List[SinterType], param_names: List[str],
                 is_static: bool = False, visibility: str = "public",
                 vtable_index: int = -1):
        self.name = name
        self.return_type = return_type
        self.param_types = param_types
        self.param_names = param_names
        self.is_static = is_static
        self.visibility = visibility
        self.vtable_index = vtable_index  # -1 if not virtual


class ClassType(SinterType):
    """Class type with fields and methods"""
    
    def __init__(self, name: str, type_params: List[str] = None):
        super().__init__(name, TypeKind.CLASS)
        self.type_params = type_params or []
        self.fields: Dict[str, FieldInfo] = {}
        self.methods: Dict[str, MethodInfo] = {}
        self.parent_class: Optional['ClassType'] = None
        self.interfaces: List[str] = []
        self.struct_size = 8  # Start with vtable pointer
        self.vtable: List[MethodInfo] = []
    
    def add_field(self, field_info: FieldInfo):
        """Add a field to the class"""
        self.fields[field_info.name] = field_info
        # Update struct size (simple alignment)
        field_size = field_info.field_type.size_bytes()
        # Align to field size (simplified)
        if self.struct_size % field_size != 0:
            self.struct_size += field_size - (self.struct_size % field_size)
        field_info.offset = self.struct_size
        self.struct_size += field_size
    
    def add_method(self, method_info: MethodInfo):
        """Add a method to the class"""
        self.methods[method_info.name] = method_info
        if not method_info.is_static:
            method_info.vtable_index = len(self.vtable)
            self.vtable.append(method_info)
    
    def get_field(self, name: str) -> Optional[FieldInfo]:
        """Get a field by name, checking parent classes"""
        if name in self.fields:
            return self.fields[name]
        if self.parent_class:
            return self.parent_class.get_field(name)
        return None
    
    def get_method(self, name: str) -> Optional[MethodInfo]:
        """Get a method by name, checking parent classes"""
        if name in self.methods:
            return self.methods[name]
        if self.parent_class:
            return self.parent_class.get_method(name)
        return None
    
    def llvm_type(self) -> str:
        return f"%class.{self.name}*"
    
    def llvm_struct_type(self) -> str:
        return f"%class.{self.name}"
    
    def size_bytes(self) -> int:
        return self.struct_size


class FunctionType(SinterType):
    """Function type for function pointers and signatures"""
    
    def __init__(self, return_type: SinterType, param_types: List[SinterType]):
        param_str = ", ".join(p.name for p in param_types)
        super().__init__(f"({param_str}) -> {return_type.name}", TypeKind.FUNCTION)
        self.return_type = return_type
        self.param_types = param_types
    
    def llvm_type(self) -> str:
        params = ", ".join(p.llvm_type() for p in self.param_types)
        return f"{self.return_type.llvm_type()} ({params})*"
    
    def size_bytes(self) -> int:
        return 8  # function pointer


class TypeRegistry:
    """Registry of all known types"""
    
    def __init__(self):
        self.types: Dict[str, SinterType] = {}
        self._register_builtin_types()
    
    def _register_builtin_types(self):
        """Register built-in primitive types"""
        for name in ["int", "float", "double", "boolean", "byte", "short", "long"]:
            self.types[name] = PrimitiveType(name)
        self.types["void"] = VoidType()
        self.types["null"] = NullType()
        self.types["str"] = StringType()
        self.types["d_str"] = DStringType()
    
    def register(self, sinter_type: SinterType):
        """Register a new type"""
        self.types[sinter_type.name] = sinter_type
    
    def get(self, name: str) -> Optional[SinterType]:
        """Get a type by name"""
        return self.types.get(name)
    
    def get_or_create_pointer(self, pointee_type: SinterType) -> PointerType:
        """Get or create a pointer type"""
        ptr_name = f"{pointee_type.name}*"
        if ptr_name not in self.types:
            self.types[ptr_name] = PointerType(pointee_type)
        return self.types[ptr_name]
    
    def get_or_create_array(self, element_type: SinterType, size: int = None) -> ArrayType:
        """Get or create an array type"""
        if size is not None:
            arr_name = f"{element_type.name}[{size}]"
        else:
            arr_name = f"{element_type.name}[]"
        if arr_name not in self.types:
            self.types[arr_name] = ArrayType(element_type, size)
        return self.types[arr_name]
