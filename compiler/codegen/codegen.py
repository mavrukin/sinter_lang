"""
Code Generator for Sinter Programming Language
Generates LLVM IR from the AST
"""

from typing import Dict, List, Optional, Tuple, Any
from compiler.sinter_ast.nodes import (
    ASTNode, Program, ClassDeclaration, MethodDeclaration, FunctionDeclaration,
    FieldDeclaration, Parameter, Block, Expression, BinaryExpression,
    UnaryExpression, Literal, Identifier, MemberAccess, MethodCall,
    NewExpression, PointerExpression, Statement, ExpressionStatement,
    ReturnStatement, VariableDeclaration, IfStatement, WhileStatement,
    AssignmentStatement, ScopeBlock, ForStatement, ForEachStatement,
    BreakStatement, ContinueStatement, PrintStatement, ArrayLiteral, ArrayAccess
)
from compiler.sinter_types.types import (
    SinterType, PrimitiveType, VoidType, StringType, DStringType,
    PointerType, ClassType, FunctionType, TypeRegistry, FieldInfo, MethodInfo
)
from compiler.sinter_types.symbol_table import SymbolTable, Symbol, SymbolKind
from compiler.runtime.serialization import SerializationCodeGen
from compiler.runtime.dstring import DStringCodeGen, DStringParser


class CodeGenerator:
    """Generates LLVM IR code from AST"""
    
    def __init__(self, type_registry: TypeRegistry, symbol_table: SymbolTable):
        self.type_registry = type_registry
        self.symbol_table = symbol_table
        self.output: List[str] = []
        self.temp_counter = 0
        self.label_counter = 0
        self.string_constants: Dict[str, Tuple[str, int]] = {}  # value -> (name, length)
        self.current_class: Optional[ClassType] = None
        self.current_function: Optional[str] = None
        self.local_vars: Dict[str, str] = {}  # var name -> llvm alloca name
        self.local_var_types: Dict[str, SinterType] = {}  # var name -> type
        self.has_returned = False
        self.serialization_codegen = SerializationCodeGen(type_registry)
        self.dstring_codegen = DStringCodeGen()
        self.generate_serialization = True  # Enable serialization code generation
        self.loop_stack: List[Tuple[str, str]] = []  # (continue_label, break_label)
        self.print_format_counter = 0
        # D-string tracking: maps variable name -> list of (dstring_id, dstring_ptr)
        self.dstring_var_refs: Dict[str, List[Tuple[int, str]]] = {}
        self.dstring_format_constants: List[str] = []  # Format string constants to emit
        self.dstring_counter = 0
        # Current scope's D-strings: maps dstring_id -> llvm ptr
        self.active_dstrings: Dict[int, str] = {}
        # Track which variables hold D-strings (var_name -> dstring_llvm_ptr)
        self.dstring_variables: Dict[str, str] = {}
    
    def generate(self, ast: Program) -> str:
        """Generate LLVM IR for the entire program"""
        self.output = []
        
        # Generate header
        self._emit("; Sinter Compiler - Generated LLVM IR")
        self._emit(f"target triple = \"arm64-apple-macosx14.0.0\"")
        self._emit("")
        
        # Generate runtime declarations
        self._generate_runtime_declarations()
        
        # Collect string constants first
        self._collect_strings(ast)
        
        # Generate string constants
        self._generate_string_constants()
        
        # Generate class struct definitions
        for decl in ast.declarations:
            if isinstance(decl, ClassDeclaration):
                self._generate_class_struct(decl)
        
        # Generate vtables
        for decl in ast.declarations:
            if isinstance(decl, ClassDeclaration):
                self._generate_vtable(decl)
        
        # Generate methods
        for decl in ast.declarations:
            if isinstance(decl, ClassDeclaration):
                self._generate_class_methods(decl)
        
        # Generate functions
        for decl in ast.declarations:
            if isinstance(decl, FunctionDeclaration):
                self._generate_function(decl)
        
        # Emit D-string format constants (generated during code generation)
        if self.dstring_format_constants:
            self._emit("")
            self._emit("; D-string format string constants")
            for const in self.dstring_format_constants:
                self._emit(const)
        
        return "\n".join(self.output)
    
    def _generate_runtime_declarations(self):
        """Generate runtime function declarations"""
        self._emit("; Runtime declarations")
        self._emit("declare i8* @malloc(i64)")
        self._emit("declare void @free(i8*)")
        self._emit("declare i32 @printf(i8*, ...)")
        self._emit("declare i32 @sprintf(i8*, i8*, ...)")
        self._emit("declare i32 @snprintf(i8*, i64, i8*, ...)")
        self._emit("declare i64 @strlen(i8*)")
        self._emit("declare i8* @strcpy(i8*, i8*)")
        self._emit("declare i8* @strcat(i8*, i8*)")
        self._emit("declare i32 @strcmp(i8*, i8*)")
        self._emit("")
        
        # String struct type
        self._emit("; String type")
        self._emit("%String = type { i8*, i64 }")  # data, length
        self._emit("")
        
        # D-String type and runtime
        self._emit(self.dstring_codegen.generate_dstring_type())
        self._emit(self.dstring_codegen.generate_format_constants())
        self._emit(self.dstring_codegen.generate_dstring_runtime_functions())
        
        # Serialization string constants
        if self.generate_serialization:
            self._emit(self.serialization_codegen.generate_runtime_declarations())
        
        # Print format strings
        self._emit("; Print format strings")
        self._emit('@.str.int_fmt = private unnamed_addr constant [3 x i8] c"%d\\00"')
        self._emit('@.str.float_fmt = private unnamed_addr constant [3 x i8] c"%f\\00"')
        self._emit('@.str.str_fmt = private unnamed_addr constant [3 x i8] c"%s\\00"')
        self._emit('@.str.ptr_fmt = private unnamed_addr constant [3 x i8] c"%p\\00"')
        self._emit('@.str.newline = private unnamed_addr constant [2 x i8] c"\\0A\\00"')
        self._emit('@.str.true = private unnamed_addr constant [5 x i8] c"true\\00"')
        self._emit('@.str.false = private unnamed_addr constant [6 x i8] c"false\\00"')
        self._emit("")
    
    def _collect_strings(self, ast: Program):
        """Collect all string constants from the AST"""
        def visit(node):
            if isinstance(node, Literal):
                # Only collect regular strings, not D-strings (handled separately)
                if node.literal_type == "str":
                    if node.value not in self.string_constants:
                        name = f"@.str.{len(self.string_constants)}"
                        self.string_constants[node.value] = (name, len(node.value) + 1)
            elif isinstance(node, Program):
                for decl in node.declarations:
                    visit(decl)
            elif isinstance(node, ClassDeclaration):
                for member in node.members:
                    visit(member)
            elif isinstance(node, (MethodDeclaration, FunctionDeclaration)):
                if node.body:
                    visit(node.body)
            elif isinstance(node, Block):
                for stmt in node.statements:
                    visit(stmt)
            elif isinstance(node, (IfStatement, WhileStatement)):
                visit(node.condition)
                visit(node.then_block if hasattr(node, 'then_block') else node.body)
                if hasattr(node, 'else_block') and node.else_block:
                    visit(node.else_block)
            elif isinstance(node, (ExpressionStatement, ReturnStatement)):
                if hasattr(node, 'expression') and node.expression:
                    visit(node.expression)
                if hasattr(node, 'value') and node.value:
                    visit(node.value)
            elif isinstance(node, VariableDeclaration):
                if node.initial_value:
                    visit(node.initial_value)
            elif isinstance(node, BinaryExpression):
                visit(node.left)
                visit(node.right)
            elif isinstance(node, UnaryExpression):
                visit(node.operand)
            elif isinstance(node, MethodCall):
                visit(node.callee)
                for arg in node.arguments:
                    visit(arg)
            elif isinstance(node, MemberAccess):
                visit(node.object_expr)
            elif isinstance(node, FieldDeclaration):
                if node.initial_value:
                    visit(node.initial_value)
        
        visit(ast)
    
    def _generate_string_constants(self):
        """Generate string constant definitions"""
        if self.string_constants:
            self._emit("; String constants")
            for value, (name, length) in self.string_constants.items():
                escaped = self._escape_string(value)
                self._emit(f"{name} = private unnamed_addr constant [{length} x i8] c\"{escaped}\\00\"")
            self._emit("")
    
    def _escape_string(self, s: str) -> str:
        """Escape a string for LLVM IR"""
        result = ""
        for c in s:
            if c == "\n":
                result += "\\0A"
            elif c == "\t":
                result += "\\09"
            elif c == "\r":
                result += "\\0D"
            elif c == '"':
                result += "\\22"
            elif c == "\\":
                result += "\\5C"
            elif ord(c) < 32 or ord(c) > 126:
                result += f"\\{ord(c):02X}"
            else:
                result += c
        return result
    
    def _generate_class_struct(self, decl: ClassDeclaration):
        """Generate LLVM struct type for a class"""
        class_type = self.type_registry.get(decl.name)
        if not isinstance(class_type, ClassType):
            return
        
        self._emit(f"; Class {decl.name}")
        
        # Generate struct fields
        fields = ["i8**"]  # vtable pointer
        for name, field in class_type.fields.items():
            llvm_type = self._get_llvm_type(field.field_type)
            fields.append(llvm_type)
        
        fields_str = ", ".join(fields)
        self._emit(f"%class.{decl.name} = type {{ {fields_str} }}")
        self._emit("")
    
    def _generate_vtable(self, decl: ClassDeclaration):
        """Generate vtable for a class"""
        class_type = self.type_registry.get(decl.name)
        if not isinstance(class_type, ClassType):
            return
        
        if not class_type.vtable:
            return
        
        self._emit(f"; VTable for {decl.name}")
        
        # Generate vtable type
        method_types = []
        for method in class_type.vtable:
            ret_type = self._get_llvm_type(method.return_type)
            param_types = [f"%class.{decl.name}*"]  # this pointer
            param_types.extend(self._get_llvm_type(p) for p in method.param_types)
            method_types.append(f"{ret_type} ({', '.join(param_types)})*")
        
        vtable_type = ", ".join(method_types)
        self._emit(f"%vtable.{decl.name} = type {{ {vtable_type} }}")
        
        # Generate vtable instance
        method_ptrs = []
        for method in class_type.vtable:
            ret_type = self._get_llvm_type(method.return_type)
            param_types = [f"%class.{decl.name}*"]
            param_types.extend(self._get_llvm_type(p) for p in method.param_types)
            func_type = f"{ret_type} ({', '.join(param_types)})*"
            method_ptrs.append(f"{func_type} @{decl.name}_{method.name}")
        
        vtable_init = ", ".join(method_ptrs) if method_ptrs else ""
        self._emit(f"@vtable.{decl.name} = global %vtable.{decl.name} {{ {vtable_init} }}")
        self._emit("")
    
    def _generate_class_methods(self, decl: ClassDeclaration):
        """Generate methods for a class"""
        class_type = self.type_registry.get(decl.name)
        if not isinstance(class_type, ClassType):
            return
        
        self.current_class = class_type
        
        # Generate constructor
        self._generate_constructor(decl, class_type)
        
        # Generate methods
        current_visibility = "public"
        for member in decl.members:
            if isinstance(member, ScopeBlock):
                current_visibility = member.visibility.value
                for sub_member in member.members:
                    if isinstance(sub_member, MethodDeclaration):
                        self._generate_method(sub_member, decl.name, class_type)
            elif isinstance(member, MethodDeclaration):
                self._generate_method(member, decl.name, class_type)
        
        self.current_class = None
    
    def _generate_constructor(self, decl: ClassDeclaration, class_type: ClassType):
        """Generate constructor (new) for a class"""
        self._emit(f"; Constructor for {decl.name}")
        self._emit(f"define %class.{decl.name}* @{decl.name}_new() {{")
        self._emit("entry:")
        
        # Calculate struct size
        struct_size = class_type.struct_size
        
        # Allocate memory
        self._emit(f"  %mem = call i8* @malloc(i64 {struct_size})")
        self._emit(f"  %this = bitcast i8* %mem to %class.{decl.name}*")
        
        # Initialize vtable pointer
        if class_type.vtable:
            self._emit(f"  %vtable_ptr = getelementptr %class.{decl.name}, %class.{decl.name}* %this, i32 0, i32 0")
            self._emit(f"  %vtable = bitcast %vtable.{decl.name}* @vtable.{decl.name} to i8**")
            self._emit(f"  store i8** %vtable, i8*** %vtable_ptr")
        
        # Initialize fields with default values
        field_idx = 1  # Start after vtable
        for name, field in class_type.fields.items():
            llvm_type = self._get_llvm_type(field.field_type)
            self._emit(f"  %field_{name}_ptr = getelementptr %class.{decl.name}, %class.{decl.name}* %this, i32 0, i32 {field_idx}")
            
            # Use the declared default value if available, otherwise type default
            if field.default_value is not None:
                init_val = self._generate_expression(field.default_value)
            else:
                init_val = self._get_default_value(field.field_type)
            self._emit(f"  store {llvm_type} {init_val}, {llvm_type}* %field_{name}_ptr")
            field_idx += 1
        
        self._emit(f"  ret %class.{decl.name}* %this")
        self._emit("}")
        self._emit("")
        
        # Generate destructor (clean) method that actually frees memory
        self._generate_destructor(decl, class_type)
    
    def _generate_destructor(self, decl: ClassDeclaration, class_type: ClassType):
        """Generate clean() method that actually frees memory"""
        self._emit(f"; Destructor (clean) for {decl.name}")
        self._emit(f"define void @{decl.name}_clean_impl(%class.{decl.name}* %this) {{")
        self._emit("entry:")
        
        # Free any pointer fields first (nested cleanup)
        field_idx = 1
        for name, field in class_type.fields.items():
            if field.field_type.is_pointer():
                llvm_type = self._get_llvm_type(field.field_type)
                self._emit(f"  ; Free field {name}")
                self._emit(f"  %field_{name}_ptr = getelementptr %class.{decl.name}, %class.{decl.name}* %this, i32 0, i32 {field_idx}")
                self._emit(f"  %field_{name}_val = load {llvm_type}, {llvm_type}* %field_{name}_ptr")
                self._emit(f"  %field_{name}_null = icmp eq {llvm_type} %field_{name}_val, null")
                self._emit(f"  br i1 %field_{name}_null, label %skip_free_{name}, label %do_free_{name}")
                self._emit(f"do_free_{name}:")
                self._emit(f"  %field_{name}_i8 = bitcast {llvm_type} %field_{name}_val to i8*")
                self._emit(f"  call void @free(i8* %field_{name}_i8)")
                self._emit(f"  br label %skip_free_{name}")
                self._emit(f"skip_free_{name}:")
            field_idx += 1
        
        # Free the object itself
        self._emit(f"  %this_i8 = bitcast %class.{decl.name}* %this to i8*")
        self._emit(f"  call void @free(i8* %this_i8)")
        self._emit("  ret void")
        self._emit("}")
        self._emit("")
    
    def _generate_method(self, method: MethodDeclaration, class_name: str, class_type: ClassType):
        """Generate a method"""
        self.local_vars = {}
        self.local_var_types = {}
        self.temp_counter = 0
        self.has_returned = False
        # Reset D-string tracking for this scope
        self.dstring_var_refs = {}
        self.active_dstrings = {}
        self.dstring_variables = {}
        
        ret_type = self._get_llvm_type(self._resolve_type(method.return_type))
        
        # Build parameter list
        params = []
        if not method.is_static:
            params.append(f"%class.{class_name}* %this")
        
        for param in method.parameters:
            param_type = self._get_llvm_type(self._resolve_type(param.type_name))
            params.append(f"{param_type} %{param.name}")
        
        params_str = ", ".join(params)
        self._emit(f"define {ret_type} @{class_name}_{method.name}({params_str}) {{")
        self._emit("entry:")
        
        self.current_function = f"{class_name}_{method.name}"
        
        # Allocate space for parameters
        if not method.is_static:
            self._emit(f"  %this.addr = alloca %class.{class_name}*")
            self._emit(f"  store %class.{class_name}* %this, %class.{class_name}** %this.addr")
            self.local_vars["this"] = "%this.addr"
            self.local_var_types["this"] = self.type_registry.get_or_create_pointer(class_type)
        
        for param in method.parameters:
            resolved_type = self._resolve_type(param.type_name)
            param_llvm_type = self._get_llvm_type(resolved_type)
            self._emit(f"  %{param.name}.addr = alloca {param_llvm_type}")
            self._emit(f"  store {param_llvm_type} %{param.name}, {param_llvm_type}* %{param.name}.addr")
            self.local_vars[param.name] = f"%{param.name}.addr"
            self.local_var_types[param.name] = resolved_type
        
        # Generate method body
        if method.body:
            self._generate_block(method.body)
        
        # Add default return if needed (only if no explicit return)
        if not self.has_returned:
            if ret_type == "void":
                self._emit("  ret void")
            else:
                default_val = self._get_default_value(self._resolve_type(method.return_type))
                self._emit(f"  ret {ret_type} {default_val}")
        
        self._emit("}")
        self._emit("")
        
        self.current_function = None
    
    def _generate_function(self, func: FunctionDeclaration):
        """Generate a standalone function"""
        self.local_vars = {}
        self.local_var_types = {}  # Track types of local variables
        self.temp_counter = 0
        self.has_returned = False
        # Reset D-string tracking for this scope
        self.dstring_var_refs = {}
        self.active_dstrings = {}
        self.dstring_variables = {}
        
        ret_type = self._get_llvm_type(self._resolve_type(func.return_type))
        
        # Build parameter list
        params = []
        for param in func.parameters:
            param_type = self._get_llvm_type(self._resolve_type(param.type_name))
            params.append(f"{param_type} %{param.name}")
        
        params_str = ", ".join(params)
        self._emit(f"define {ret_type} @{func.name}({params_str}) {{")
        self._emit("entry:")
        
        self.current_function = func.name
        
        # Allocate space for parameters
        for param in func.parameters:
            param_type = self._resolve_type(param.type_name)
            llvm_type = self._get_llvm_type(param_type)
            self._emit(f"  %{param.name}.addr = alloca {llvm_type}")
            self._emit(f"  store {llvm_type} %{param.name}, {llvm_type}* %{param.name}.addr")
            self.local_vars[param.name] = f"%{param.name}.addr"
            self.local_var_types[param.name] = param_type
        
        # Generate function body
        if func.body:
            self._generate_block(func.body)
        
        # Add default return if needed (only if no explicit return)
        if not self.has_returned:
            if ret_type == "void":
                self._emit("  ret void")
            else:
                default_val = self._get_default_value(self._resolve_type(func.return_type))
                self._emit(f"  ret {ret_type} {default_val}")
        
        self._emit("}")
        self._emit("")
        
        self.current_function = None
    
    def _generate_block(self, block: Block):
        """Generate code for a block"""
        for stmt in block.statements:
            self._generate_statement(stmt)
    
    def _generate_statement(self, stmt: Statement):
        """Generate code for a statement"""
        if isinstance(stmt, VariableDeclaration):
            self._generate_var_declaration(stmt)
        elif isinstance(stmt, ReturnStatement):
            self._generate_return(stmt)
        elif isinstance(stmt, IfStatement):
            self._generate_if(stmt)
        elif isinstance(stmt, WhileStatement):
            self._generate_while(stmt)
        elif isinstance(stmt, ForStatement):
            self._generate_for(stmt)
        elif isinstance(stmt, BreakStatement):
            self._generate_break()
        elif isinstance(stmt, ContinueStatement):
            self._generate_continue()
        elif isinstance(stmt, PrintStatement):
            self._generate_print(stmt)
        elif isinstance(stmt, ExpressionStatement):
            self._generate_expression(stmt.expression)
        elif isinstance(stmt, AssignmentStatement):
            self._generate_assignment(stmt)
    
    def _generate_var_declaration(self, stmt: VariableDeclaration):
        """Generate variable declaration"""
        var_type = self._resolve_type(stmt.type_name)
        llvm_type = self._get_llvm_type(var_type)
        
        # For class pointer types, we need the base type for storage
        storage_type = llvm_type
        
        # Allocate space
        alloca_name = f"%{stmt.name}.addr"
        self._emit(f"  {alloca_name} = alloca {storage_type}")
        self.local_vars[stmt.name] = alloca_name
        self.local_var_types[stmt.name] = var_type
        
        # Clear D-string tracking for this expression
        self._last_dstring_ptr = None
        self._last_dstring_id = None
        
        # Initialize if there's an initial value
        if stmt.initial_value:
            value = self._generate_expression(stmt.initial_value)
            self._emit(f"  store {storage_type} {value}, {storage_type}* {alloca_name}")
            
            # Check if this was a D-string literal
            if hasattr(self, '_last_dstring_ptr') and self._last_dstring_ptr:
                # Track this variable as holding a D-string
                self.dstring_variables[stmt.name] = (self._last_dstring_ptr, self._last_dstring_id)
                self._emit(f"  ; Variable '{stmt.name}' holds D-string {self._last_dstring_id}")
    
    def _generate_return(self, stmt: ReturnStatement):
        """Generate return statement"""
        self.has_returned = True
        if stmt.value:
            value = self._generate_expression(stmt.value)
            # Get return type from context
            ret_type = self._infer_type(stmt.value)
            llvm_type = self._get_llvm_type(ret_type) if ret_type else "i32"
            self._emit(f"  ret {llvm_type} {value}")
        else:
            self._emit("  ret void")
    
    def _generate_if(self, stmt: IfStatement):
        """Generate if statement"""
        cond = self._generate_expression(stmt.condition)
        
        then_label = self._new_label("then")
        else_label = self._new_label("else")
        end_label = self._new_label("endif")
        
        if stmt.else_block:
            self._emit(f"  br i1 {cond}, label %{then_label}, label %{else_label}")
        else:
            self._emit(f"  br i1 {cond}, label %{then_label}, label %{end_label}")
        
        # Then block
        self._emit(f"{then_label}:")
        self._generate_block(stmt.then_block)
        self._emit(f"  br label %{end_label}")
        
        # Else block
        if stmt.else_block:
            self._emit(f"{else_label}:")
            self._generate_block(stmt.else_block)
            self._emit(f"  br label %{end_label}")
        
        self._emit(f"{end_label}:")
    
    def _generate_while(self, stmt: WhileStatement):
        """Generate while statement"""
        cond_label = self._new_label("while_cond")
        body_label = self._new_label("while_body")
        end_label = self._new_label("while_end")
        
        # Push loop context for break/continue
        self.loop_stack.append((cond_label, end_label))
        
        self._emit(f"  br label %{cond_label}")
        
        # Condition
        self._emit(f"{cond_label}:")
        cond = self._generate_expression(stmt.condition)
        self._emit(f"  br i1 {cond}, label %{body_label}, label %{end_label}")
        
        # Body
        self._emit(f"{body_label}:")
        self._generate_block(stmt.body)
        self._emit(f"  br label %{cond_label}")
        
        self._emit(f"{end_label}:")
        
        # Pop loop context
        self.loop_stack.pop()
    
    def _generate_for(self, stmt: ForStatement):
        """Generate for statement"""
        init_label = self._new_label("for_init")
        cond_label = self._new_label("for_cond")
        body_label = self._new_label("for_body")
        update_label = self._new_label("for_update")
        end_label = self._new_label("for_end")
        
        # Push loop context (continue goes to update, break goes to end)
        self.loop_stack.append((update_label, end_label))
        
        # Init
        self._emit(f"  br label %{init_label}")
        self._emit(f"{init_label}:")
        if stmt.init:
            self._generate_statement(stmt.init)
        self._emit(f"  br label %{cond_label}")
        
        # Condition
        self._emit(f"{cond_label}:")
        if stmt.condition:
            cond = self._generate_expression(stmt.condition)
            self._emit(f"  br i1 {cond}, label %{body_label}, label %{end_label}")
        else:
            self._emit(f"  br label %{body_label}")
        
        # Body
        self._emit(f"{body_label}:")
        self._generate_block(stmt.body)
        self._emit(f"  br label %{update_label}")
        
        # Update
        self._emit(f"{update_label}:")
        if stmt.update:
            self._generate_expression(stmt.update)
        self._emit(f"  br label %{cond_label}")
        
        self._emit(f"{end_label}:")
        
        # Pop loop context
        self.loop_stack.pop()
    
    def _generate_break(self):
        """Generate break statement"""
        if self.loop_stack:
            _, break_label = self.loop_stack[-1]
            self._emit(f"  br label %{break_label}")
        else:
            self._emit("  ; ERROR: break outside of loop")
    
    def _generate_continue(self):
        """Generate continue statement"""
        if self.loop_stack:
            continue_label, _ = self.loop_stack[-1]
            self._emit(f"  br label %{continue_label}")
        else:
            self._emit("  ; ERROR: continue outside of loop")
    
    def _generate_print(self, stmt: PrintStatement):
        """Generate print/println statement"""
        if not stmt.arguments:
            if stmt.newline:
                self._emit('  call i32 (i8*, ...) @printf(i8* getelementptr ([2 x i8], [2 x i8]* @.str.newline, i32 0, i32 0))')
            return
        
        for arg in stmt.arguments:
            value = self._generate_expression(arg)
            arg_type = self._infer_type(arg)
            
            if arg_type:
                if arg_type.name == "int":
                    self._emit(f'  call i32 (i8*, ...) @printf(i8* getelementptr ([3 x i8], [3 x i8]* @.str.int_fmt, i32 0, i32 0), i32 {value})')
                elif arg_type.name in ["float", "double"]:
                    llvm_type = self._get_llvm_type(arg_type)
                    self._emit(f'  call i32 (i8*, ...) @printf(i8* getelementptr ([3 x i8], [3 x i8]* @.str.float_fmt, i32 0, i32 0), {llvm_type} {value})')
                elif arg_type.name == "boolean":
                    # Print "true" or "false"
                    temp = self._new_temp()
                    self._emit(f'  {temp} = select i1 {value}, i8* getelementptr ([5 x i8], [5 x i8]* @.str.true, i32 0, i32 0), i8* getelementptr ([6 x i8], [6 x i8]* @.str.false, i32 0, i32 0)')
                    self._emit(f'  call i32 (i8*, ...) @printf(i8* getelementptr ([3 x i8], [3 x i8]* @.str.str_fmt, i32 0, i32 0), i8* {temp})')
                elif arg_type.name == "str":
                    self._emit(f'  call i32 (i8*, ...) @printf(i8* getelementptr ([3 x i8], [3 x i8]* @.str.str_fmt, i32 0, i32 0), i8* {value})')
                else:
                    # Default: print as pointer
                    self._emit(f'  call i32 (i8*, ...) @printf(i8* getelementptr ([3 x i8], [3 x i8]* @.str.ptr_fmt, i32 0, i32 0), i8* {value})')
            else:
                # Assume int
                self._emit(f'  call i32 (i8*, ...) @printf(i8* getelementptr ([3 x i8], [3 x i8]* @.str.int_fmt, i32 0, i32 0), i32 {value})')
        
        if stmt.newline:
            self._emit('  call i32 (i8*, ...) @printf(i8* getelementptr ([2 x i8], [2 x i8]* @.str.newline, i32 0, i32 0))')
    
    def _generate_assignment(self, stmt: AssignmentStatement):
        """Generate assignment statement"""
        value = self._generate_expression(stmt.value)
        
        if isinstance(stmt.target, Identifier):
            var_name = stmt.target.name
            if var_name in self.local_vars:
                ptr = self.local_vars[var_name]
                var_type = self._infer_type(stmt.target)
                llvm_type = self._get_llvm_type(var_type) if var_type else "i32"
                self._emit(f"  store {llvm_type} {value}, {llvm_type}* {ptr}")
                
                # Mark any D-strings that reference this variable as dirty
                self._mark_dstrings_dirty_for_var(var_name)
            elif self.current_class:
                # Field access
                field = self.current_class.get_field(var_name)
                if field:
                    self._generate_field_store(var_name, value, field)
        elif isinstance(stmt.target, MemberAccess):
            self._generate_member_store(stmt.target, value)
    
    def _mark_dstrings_dirty_for_var(self, var_name: str):
        """Mark all D-strings that reference this variable as dirty"""
        if var_name in self.dstring_var_refs:
            refs = self.dstring_var_refs[var_name]
            for dstring_id, dstring_ptr in refs:
                if dstring_id in self.active_dstrings:
                    self._emit(f"  ; Mark D-string {dstring_id} dirty (var {var_name} changed)")
                    self._emit(f"  call void @DString_markDirty(%DString* {self.active_dstrings[dstring_id]})")
    
    def _generate_expression(self, expr: Expression) -> str:
        """Generate code for an expression, return the result register"""
        if isinstance(expr, Literal):
            return self._generate_literal(expr)
        elif isinstance(expr, Identifier):
            return self._generate_identifier(expr)
        elif isinstance(expr, BinaryExpression):
            return self._generate_binary(expr)
        elif isinstance(expr, UnaryExpression):
            return self._generate_unary(expr)
        elif isinstance(expr, MemberAccess):
            return self._generate_member_access(expr)
        elif isinstance(expr, MethodCall):
            return self._generate_method_call(expr)
        elif isinstance(expr, NewExpression):
            return self._generate_new(expr)
        elif isinstance(expr, AssignmentStatement):
            self._generate_assignment(expr)
            return self._generate_expression(expr.target)
        return "0"
    
    def _generate_literal(self, lit: Literal) -> str:
        """Generate code for a literal"""
        if lit.literal_type == "int":
            return str(lit.value)
        elif lit.literal_type == "float":
            return f"{float(lit.value):.6e}"
        elif lit.literal_type == "double":
            return f"{float(lit.value):.15e}"
        elif lit.literal_type == "boolean":
            return "1" if lit.value else "0"
        elif lit.literal_type == "d_str":
            # D-string: create dynamic string with variable references
            return self._generate_dstring_literal(lit.value)
        elif lit.literal_type == "str":
            if lit.value in self.string_constants:
                name, length = self.string_constants[lit.value]
                temp = self._new_temp()
                self._emit(f"  {temp} = getelementptr [{length} x i8], [{length} x i8]* {name}, i32 0, i32 0")
                return temp
            return "null"
        elif lit.literal_type == "null":
            return "null"
        return "0"
    
    def _generate_dstring_literal(self, format_string: str) -> str:
        """Generate code for a D-string literal with variable substitution"""
        # Parse the format string to find variables
        template, variables = DStringParser.parse(format_string)
        
        # Allocate a D-string ID
        dstring_id = self.dstring_counter
        self.dstring_counter += 1
        
        # Generate format string constant
        format_len = len(template) + 1
        escaped_template = template.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\0A')
        const_name = f"@.dstr.fmt.{dstring_id}"
        self.dstring_format_constants.append(
            f'{const_name} = private unnamed_addr constant [{format_len} x i8] c"{escaped_template}\\00"'
        )
        
        # Build variable info list
        var_infos = []  # (var_name, llvm_ptr, type_code)
        for var_name in variables:
            if var_name in self.local_vars:
                var_ptr = self.local_vars[var_name]
                var_type = self.local_var_types.get(var_name)
                type_code = self._get_dstring_type_code(var_type)
                var_infos.append((var_name, var_ptr, type_code))
                
                # Register this D-string as depending on this variable
                if var_name not in self.dstring_var_refs:
                    self.dstring_var_refs[var_name] = []
        
        # Generate D-string creation code
        self._emit(f"  ; Create D-string {dstring_id}: {format_string[:30]}...")
        self._emit(f"  %dstr_{dstring_id}_fmt = getelementptr [{format_len} x i8], [{format_len} x i8]* {const_name}, i32 0, i32 0")
        self._emit(f"  %dstr_{dstring_id} = call %DString* @DString_create(i8* %dstr_{dstring_id}_fmt, i64 {format_len}, i32 {len(var_infos)})")
        
        # Set each variable reference
        for idx, (var_name, var_ptr, type_code) in enumerate(var_infos):
            self._emit(f"  ; D-string var {idx}: {var_name}")
            # Cast the alloca pointer to i8*
            self._emit(f"  %dstr_{dstring_id}_vptr_{idx} = bitcast i8* {var_ptr} to i8*")
            self._emit(f"  call void @DString_setVar(%DString* %dstr_{dstring_id}, i32 {idx}, i8* %dstr_{dstring_id}_vptr_{idx}, i32 {type_code})")
            
            # Track this dependency
            self.dstring_var_refs[var_name].append((dstring_id, f"%dstr_{dstring_id}"))
        
        # Store in active D-strings
        self.active_dstrings[dstring_id] = f"%dstr_{dstring_id}"
        
        # Store the D-string pointer for later retrieval
        # We'll allocate storage and track this as a D-string variable
        dstr_alloca = f"%dstr_{dstring_id}_ptr"
        self._emit(f"  {dstr_alloca} = alloca %DString*")
        self._emit(f"  store %DString* %dstr_{dstring_id}, %DString** {dstr_alloca}")
        
        # Mark that a D-string was just created (will be picked up by var declaration)
        self._last_dstring_ptr = dstr_alloca
        self._last_dstring_id = dstring_id
        
        # Return current string value (for immediate use)
        result = self._new_temp()
        self._emit(f"  {result} = call i8* @DString_get(%DString* %dstr_{dstring_id})")
        return result
    
    def _get_dstring_type_code(self, sinter_type: Optional[SinterType]) -> int:
        """Get the D-string variable type code for a Sinter type"""
        if not sinter_type:
            return 0  # INT by default
        
        type_map = {
            "int": 0,      # DStringVarType.INT
            "float": 1,    # DStringVarType.FLOAT
            "double": 2,   # DStringVarType.DOUBLE
            "boolean": 3,  # DStringVarType.BOOLEAN
            "str": 4,      # DStringVarType.STRING
        }
        return type_map.get(sinter_type.name, 0)
    
    def _generate_identifier(self, ident: Identifier) -> str:
        """Generate code for an identifier"""
        if ident.name in self.local_vars:
            # Check if this is a D-string variable - need to call DString_get
            if ident.name in self.dstring_variables:
                dstr_ptr_alloca, dstring_id = self.dstring_variables[ident.name]
                self._emit(f"  ; Load D-string variable '{ident.name}' (D-string {dstring_id})")
                dstr_ptr = self._new_temp()
                self._emit(f"  {dstr_ptr} = load %DString*, %DString** {dstr_ptr_alloca}")
                result = self._new_temp()
                self._emit(f"  {result} = call i8* @DString_get(%DString* {dstr_ptr})")
                return result
            
            ptr = self.local_vars[ident.name]
            # Get type from local_var_types if available
            if hasattr(self, 'local_var_types') and ident.name in self.local_var_types:
                var_type = self.local_var_types[ident.name]
            else:
                var_type = self._infer_type(ident)
            llvm_type = self._get_llvm_type(var_type) if var_type else "i32"
            temp = self._new_temp()
            self._emit(f"  {temp} = load {llvm_type}, {llvm_type}* {ptr}")
            return temp
        elif self.current_class:
            # Check if it's a field
            field = self.current_class.get_field(ident.name)
            if field:
                return self._generate_field_load(ident.name, field)
        
        return "0"
    
    def _generate_field_load(self, name: str, field: FieldInfo) -> str:
        """Generate code to load a field value"""
        llvm_type = self._get_llvm_type(field.field_type)
        
        # Load this pointer
        this_ptr = self.local_vars.get("this", "%this.addr")
        temp1 = self._new_temp()
        self._emit(f"  {temp1} = load %class.{self.current_class.name}*, %class.{self.current_class.name}** {this_ptr}")
        
        # Get field index
        field_idx = list(self.current_class.fields.keys()).index(name) + 1  # +1 for vtable
        
        # Get field pointer
        temp2 = self._new_temp()
        self._emit(f"  {temp2} = getelementptr %class.{self.current_class.name}, %class.{self.current_class.name}* {temp1}, i32 0, i32 {field_idx}")
        
        # Load value
        temp3 = self._new_temp()
        self._emit(f"  {temp3} = load {llvm_type}, {llvm_type}* {temp2}")
        
        return temp3
    
    def _generate_field_store(self, name: str, value: str, field: FieldInfo):
        """Generate code to store a field value"""
        llvm_type = self._get_llvm_type(field.field_type)
        
        # Load this pointer
        this_ptr = self.local_vars.get("this", "%this.addr")
        temp1 = self._new_temp()
        self._emit(f"  {temp1} = load %class.{self.current_class.name}*, %class.{self.current_class.name}** {this_ptr}")
        
        # Get field index
        field_idx = list(self.current_class.fields.keys()).index(name) + 1
        
        # Get field pointer
        temp2 = self._new_temp()
        self._emit(f"  {temp2} = getelementptr %class.{self.current_class.name}, %class.{self.current_class.name}* {temp1}, i32 0, i32 {field_idx}")
        
        # Store value
        self._emit(f"  store {llvm_type} {value}, {llvm_type}* {temp2}")
    
    def _generate_binary(self, expr: BinaryExpression) -> str:
        """Generate code for a binary expression"""
        left_type = self._infer_type(expr.left)
        
        # Handle string concatenation
        if left_type and left_type.name == "str" and expr.operator == "+":
            return self._generate_string_concat(expr.left, expr.right)
        
        left = self._generate_expression(expr.left)
        right = self._generate_expression(expr.right)
        
        llvm_type = self._get_llvm_type(left_type) if left_type else "i32"
        
        temp = self._new_temp()
        
        # Determine operation based on type and operator
        is_float = llvm_type in ["float", "double"]
        
        op_map = {
            "+": "fadd" if is_float else "add",
            "-": "fsub" if is_float else "sub",
            "*": "fmul" if is_float else "mul",
            "/": "fdiv" if is_float else "sdiv",
            "%": "srem",  # No fmod in LLVM IR directly
            "==": "fcmp oeq" if is_float else "icmp eq",
            "!=": "fcmp one" if is_float else "icmp ne",
            "<": "fcmp olt" if is_float else "icmp slt",
            ">": "fcmp ogt" if is_float else "icmp sgt",
            "<=": "fcmp ole" if is_float else "icmp sle",
            ">=": "fcmp oge" if is_float else "icmp sge",
            "&&": "and",
            "||": "or",
            "&": "and",  # Bitwise and
            "|": "or",   # Bitwise or
            "^": "xor",  # Bitwise xor
        }
        
        op = op_map.get(expr.operator, "add")
        
        if expr.operator in ["==", "!=", "<", ">", "<=", ">="]:
            self._emit(f"  {temp} = {op} {llvm_type} {left}, {right}")
        elif expr.operator in ["&&", "||"]:
            self._emit(f"  {temp} = {op} i1 {left}, {right}")
        else:
            self._emit(f"  {temp} = {op} {llvm_type} {left}, {right}")
        
        return temp
    
    def _generate_string_concat(self, left_expr: Expression, right_expr: Expression) -> str:
        """Generate string concatenation using runtime functions"""
        left = self._generate_expression(left_expr)
        right = self._generate_expression(right_expr)
        
        # Get string lengths
        len1 = self._new_temp()
        len2 = self._new_temp()
        self._emit(f"  {len1} = call i64 @strlen(i8* {left})")
        self._emit(f"  {len2} = call i64 @strlen(i8* {right})")
        
        # Allocate new buffer (len1 + len2 + 1)
        total_len = self._new_temp()
        self._emit(f"  {total_len} = add i64 {len1}, {len2}")
        buf_size = self._new_temp()
        self._emit(f"  {buf_size} = add i64 {total_len}, 1")
        
        buf = self._new_temp()
        self._emit(f"  {buf} = call i8* @malloc(i64 {buf_size})")
        
        # Copy first string
        self._emit(f"  call i8* @strcpy(i8* {buf}, i8* {left})")
        # Concatenate second string
        self._emit(f"  call i8* @strcat(i8* {buf}, i8* {right})")
        
        return buf
    
    def _generate_unary(self, expr: UnaryExpression) -> str:
        """Generate code for a unary expression"""
        operand = self._generate_expression(expr.operand)
        operand_type = self._infer_type(expr.operand)
        llvm_type = self._get_llvm_type(operand_type) if operand_type else "i32"
        
        temp = self._new_temp()
        
        if expr.operator == "!":
            self._emit(f"  {temp} = xor i1 {operand}, 1")
        elif expr.operator == "-":
            if llvm_type in ["float", "double"]:
                self._emit(f"  {temp} = fneg {llvm_type} {operand}")
            else:
                self._emit(f"  {temp} = sub {llvm_type} 0, {operand}")
        elif expr.operator == "*":  # Dereference
            if operand_type and operand_type.is_pointer():
                pointee_type = self._get_llvm_type(operand_type.pointee_type)
                self._emit(f"  {temp} = load {pointee_type}, {pointee_type}* {operand}")
            else:
                return operand
        elif expr.operator == "&":  # Address-of
            # operand should already be an address
            return operand
        elif expr.operator == "++":
            self._emit(f"  {temp} = add {llvm_type} {operand}, 1")
            # Store back if it's a variable
            if isinstance(expr.operand, Identifier) and expr.operand.name in self.local_vars:
                ptr = self.local_vars[expr.operand.name]
                self._emit(f"  store {llvm_type} {temp}, {llvm_type}* {ptr}")
        elif expr.operator == "--":
            self._emit(f"  {temp} = sub {llvm_type} {operand}, 1")
            if isinstance(expr.operand, Identifier) and expr.operand.name in self.local_vars:
                ptr = self.local_vars[expr.operand.name]
                self._emit(f"  store {llvm_type} {temp}, {llvm_type}* {ptr}")
        else:
            return operand
        
        return temp
    
    def _generate_member_access(self, expr: MemberAccess) -> str:
        """Generate code for member access"""
        obj = self._generate_expression(expr.object_expr)
        obj_type = self._infer_type(expr.object_expr)
        
        if not obj_type:
            return "0"
        
        # Handle pointer types
        actual_type = obj_type
        if obj_type.is_pointer() and isinstance(obj_type, PointerType):
            actual_type = obj_type.pointee_type
        
        if isinstance(actual_type, ClassType):
            field = actual_type.get_field(expr.member)
            if field:
                llvm_type = self._get_llvm_type(field.field_type)
                field_idx = list(actual_type.fields.keys()).index(expr.member) + 1
                
                temp1 = self._new_temp()
                self._emit(f"  {temp1} = getelementptr %class.{actual_type.name}, %class.{actual_type.name}* {obj}, i32 0, i32 {field_idx}")
                
                temp2 = self._new_temp()
                self._emit(f"  {temp2} = load {llvm_type}, {llvm_type}* {temp1}")
                
                return temp2
        
        return "0"
    
    def _generate_member_store(self, expr: MemberAccess, value: str):
        """Generate code to store to a member"""
        obj = self._generate_expression(expr.object_expr)
        obj_type = self._infer_type(expr.object_expr)
        
        if not obj_type:
            return
        
        actual_type = obj_type
        if obj_type.is_pointer() and isinstance(obj_type, PointerType):
            actual_type = obj_type.pointee_type
        
        if isinstance(actual_type, ClassType):
            field = actual_type.get_field(expr.member)
            if field:
                llvm_type = self._get_llvm_type(field.field_type)
                field_idx = list(actual_type.fields.keys()).index(expr.member) + 1
                
                temp1 = self._new_temp()
                self._emit(f"  {temp1} = getelementptr %class.{actual_type.name}, %class.{actual_type.name}* {obj}, i32 0, i32 {field_idx}")
                
                self._emit(f"  store {llvm_type} {value}, {llvm_type}* {temp1}")
    
    def _generate_method_call(self, expr: MethodCall) -> str:
        """Generate code for a method call"""
        # Handle Class.new() constructor call
        if isinstance(expr.callee, MemberAccess) and expr.callee.member == "new":
            if isinstance(expr.callee.object_expr, Identifier):
                class_name = expr.callee.object_expr.name
                temp = self._new_temp()
                self._emit(f"  {temp} = call %class.{class_name}* @{class_name}_new()")
                return temp
        
        # Regular method call
        if isinstance(expr.callee, MemberAccess):
            obj = self._generate_expression(expr.callee.object_expr)
            obj_type = self._infer_type(expr.callee.object_expr)
            
            if obj_type:
                actual_type = obj_type
                if obj_type.is_pointer() and isinstance(obj_type, PointerType):
                    actual_type = obj_type.pointee_type
                
                if isinstance(actual_type, ClassType):
                    method = actual_type.get_method(expr.callee.member)
                    if method:
                        # Check if this is a clean() call - use the real destructor
                        if method.name == "clean":
                            self._emit(f"  call void @{actual_type.name}_clean_impl(%class.{actual_type.name}* {obj})")
                            return "0"
                        
                        # Generate arguments
                        args = [obj]  # this pointer
                        arg_types = [f"%class.{actual_type.name}*"]
                        
                        for arg_expr in expr.arguments:
                            arg = self._generate_expression(arg_expr)
                            arg_type = self._infer_type(arg_expr)
                            args.append(arg)
                            arg_types.append(self._get_llvm_type(arg_type) if arg_type else "i32")
                        
                        ret_type = self._get_llvm_type(method.return_type)
                        args_str = ", ".join(f"{t} {v}" for t, v in zip(arg_types, args))
                        
                        if ret_type == "void":
                            self._emit(f"  call void @{actual_type.name}_{method.name}({args_str})")
                            return "0"
                        else:
                            temp = self._new_temp()
                            self._emit(f"  {temp} = call {ret_type} @{actual_type.name}_{method.name}({args_str})")
                            return temp
        
        # Function call
        if isinstance(expr.callee, Identifier):
            func_name = expr.callee.name
            symbol = self.symbol_table.resolve(func_name)
            
            if symbol and isinstance(symbol.symbol_type, FunctionType):
                func_type = symbol.symbol_type
                
                # Generate arguments
                args = []
                arg_types = []
                for i, arg_expr in enumerate(expr.arguments):
                    arg = self._generate_expression(arg_expr)
                    if i < len(func_type.param_types):
                        arg_type = self._get_llvm_type(func_type.param_types[i])
                    else:
                        arg_type = "i32"
                    args.append(arg)
                    arg_types.append(arg_type)
                
                ret_type = self._get_llvm_type(func_type.return_type)
                args_str = ", ".join(f"{t} {v}" for t, v in zip(arg_types, args))
                
                if ret_type == "void":
                    self._emit(f"  call void @{func_name}({args_str})")
                    return "0"
                else:
                    temp = self._new_temp()
                    self._emit(f"  {temp} = call {ret_type} @{func_name}({args_str})")
                    return temp
        
        return "0"
    
    def _generate_new(self, expr: NewExpression) -> str:
        """Generate code for a new expression"""
        class_name = expr.class_name
        temp = self._new_temp()
        self._emit(f"  {temp} = call %class.{class_name}* @{class_name}_new()")
        return temp
    
    def _get_llvm_type(self, sinter_type: Optional[SinterType]) -> str:
        """Convert a Sinter type to LLVM type"""
        if not sinter_type:
            return "i32"
        
        type_map = {
            "int": "i32",
            "float": "float",
            "double": "double",
            "boolean": "i1",
            "byte": "i8",
            "short": "i16",
            "long": "i64",
            "void": "void",
            "str": "i8*",
            "d_str": "i8*",
            "null": "i8*",
        }
        
        if sinter_type.name in type_map:
            return type_map[sinter_type.name]
        
        if sinter_type.is_pointer() and isinstance(sinter_type, PointerType):
            pointee = sinter_type.pointee_type
            if isinstance(pointee, ClassType):
                # Class pointer: Hospital* -> %class.Hospital*
                return f"%class.{pointee.name}*"
            else:
                base = self._get_llvm_type(pointee)
                return f"{base}*"
        
        if sinter_type.is_class():
            # Non-pointer class type (shouldn't happen normally in Sinter)
            return f"%class.{sinter_type.name}"
        
        return "i32"
    
    def _get_default_value(self, sinter_type: Optional[SinterType]) -> str:
        """Get the default value for a type"""
        if not sinter_type:
            return "0"
        
        if sinter_type.name in ["int", "byte", "short", "long"]:
            return "0"
        elif sinter_type.name in ["float", "double"]:
            return "0.0"
        elif sinter_type.name == "boolean":
            return "0"
        elif sinter_type.is_pointer() or sinter_type.is_class():
            return "null"
        elif sinter_type.name in ["str", "d_str"]:
            return "null"
        
        return "0"
    
    def _resolve_type(self, type_name: str) -> Optional[SinterType]:
        """Resolve a type name"""
        if type_name.endswith("*"):
            base = self._resolve_type(type_name[:-1].strip())
            if base:
                return self.type_registry.get_or_create_pointer(base)
            return None
        return self.type_registry.get(type_name)
    
    def _infer_type(self, expr: Expression) -> Optional[SinterType]:
        """Infer the type of an expression"""
        if isinstance(expr, Literal):
            type_map = {
                "int": "int",
                "float": "float",
                "double": "double",
                "boolean": "boolean",
                "str": "str",
                "d_str": "d_str",
                "null": "null",
            }
            return self.type_registry.get(type_map.get(expr.literal_type, "int"))
        
        elif isinstance(expr, Identifier):
            # Check local var types first (our tracking)
            if hasattr(self, 'local_var_types') and expr.name in self.local_var_types:
                return self.local_var_types[expr.name]
            # Check symbol table
            symbol = self.symbol_table.resolve(expr.name)
            if symbol:
                return symbol.symbol_type
            # Check class fields
            if self.current_class:
                field = self.current_class.get_field(expr.name)
                if field:
                    return field.field_type
        
        elif isinstance(expr, BinaryExpression):
            if expr.operator in ["==", "!=", "<", ">", "<=", ">=", "&&", "||"]:
                return self.type_registry.get("boolean")
            return self._infer_type(expr.left)
        
        elif isinstance(expr, MemberAccess):
            obj_type = self._infer_type(expr.object_expr)
            if obj_type:
                actual = obj_type
                if obj_type.is_pointer() and isinstance(obj_type, PointerType):
                    actual = obj_type.pointee_type
                if isinstance(actual, ClassType):
                    field = actual.get_field(expr.member)
                    if field:
                        return field.field_type
                    method = actual.get_method(expr.member)
                    if method:
                        return FunctionType(method.return_type, method.param_types)
        
        elif isinstance(expr, NewExpression):
            class_type = self.type_registry.get(expr.class_name)
            if class_type:
                return self.type_registry.get_or_create_pointer(class_type)
        
        elif isinstance(expr, MethodCall):
            if isinstance(expr.callee, MemberAccess):
                if expr.callee.member == "new":
                    if isinstance(expr.callee.object_expr, Identifier):
                        class_type = self.type_registry.get(expr.callee.object_expr.name)
                        if class_type:
                            return self.type_registry.get_or_create_pointer(class_type)
                else:
                    # Regular method call
                    obj_type = self._infer_type(expr.callee.object_expr)
                    if obj_type:
                        actual = obj_type
                        if obj_type.is_pointer() and isinstance(obj_type, PointerType):
                            actual = obj_type.pointee_type
                        if isinstance(actual, ClassType):
                            method = actual.get_method(expr.callee.member)
                            if method:
                                return method.return_type
        
        return None
    
    def _new_temp(self) -> str:
        """Generate a new temporary name"""
        name = f"%t{self.temp_counter}"
        self.temp_counter += 1
        return name
    
    def _new_label(self, prefix: str = "label") -> str:
        """Generate a new label name"""
        name = f"{prefix}_{self.label_counter}"
        self.label_counter += 1
        return name
    
    def _emit(self, line: str):
        """Emit a line of LLVM IR"""
        self.output.append(line)
