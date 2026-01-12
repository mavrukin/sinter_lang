"""
D-String (Dynamic String) Runtime Support for Sinter
Generates LLVM IR for dynamic strings that update when referenced variables change
"""

from typing import Dict, List, Tuple, Set
import re


class DStringParser:
    """Parses D-string format strings to extract variable references"""
    
    # Pattern to match {variable_name} in strings
    VAR_PATTERN = re.compile(r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}')
    
    @classmethod
    def parse(cls, format_string: str) -> Tuple[str, List[str]]:
        """
        Parse a D-string format string.
        Returns (format_template, [variable_names])
        
        Example:
            "Hello, count is {counter}" -> ("Hello, count is %d", ["counter"])
        """
        variables = []
        
        def replace_var(match):
            var_name = match.group(1)
            variables.append(var_name)
            return "%s"  # Placeholder for string conversion
        
        template = cls.VAR_PATTERN.sub(replace_var, format_string)
        return template, variables
    
    @classmethod
    def get_variables(cls, format_string: str) -> Set[str]:
        """Extract all variable names from a D-string"""
        return set(cls.VAR_PATTERN.findall(format_string))


class DStringCodeGen:
    """Generates LLVM IR code for D-string operations"""
    
    def __init__(self):
        self.dstring_counter = 0
        self.dstring_structs: List[str] = []
    
    def generate_dstring_type(self) -> str:
        """Generate the D-string struct type definition"""
        return """
; D-String structure
; Contains format string, cached result, and variable references
%DString = type {
    i8*,        ; format string pointer
    i64,        ; format string length
    i8*,        ; cached result (regenerated on access)
    i64,        ; cached result length
    i8*,        ; variable references array pointer
    i32,        ; number of variable references
    i1          ; dirty flag (true if needs regeneration)
}

; Variable reference structure (for D-string)
%DStringVarRef = type {
    i8*,        ; variable name (for debugging)
    i8*,        ; pointer to variable location
    i32         ; variable type (0=int, 1=float, 2=string, etc.)
}
"""
    
    def generate_dstring_runtime_functions(self) -> str:
        """Generate runtime functions for D-string operations"""
        return """
; D-String runtime functions

; Create a new D-string
define %DString* @DString_new(i8* %format, i64 %format_len) {
entry:
    ; Allocate D-string struct (7 fields * 8 bytes = 56 bytes)
    %dstr = call i8* @malloc(i64 56)
    %dstr_ptr = bitcast i8* %dstr to %DString*
    
    ; Store format string
    %format_ptr = getelementptr %DString, %DString* %dstr_ptr, i32 0, i32 0
    store i8* %format, i8** %format_ptr
    
    ; Store format length
    %format_len_ptr = getelementptr %DString, %DString* %dstr_ptr, i32 0, i32 1
    store i64 %format_len, i64* %format_len_ptr
    
    ; Initialize cached result to null
    %cache_ptr = getelementptr %DString, %DString* %dstr_ptr, i32 0, i32 2
    store i8* null, i8** %cache_ptr
    
    ; Initialize cache length
    %cache_len_ptr = getelementptr %DString, %DString* %dstr_ptr, i32 0, i32 3
    store i64 0, i64* %cache_len_ptr
    
    ; Initialize var refs to null
    %refs_ptr = getelementptr %DString, %DString* %dstr_ptr, i32 0, i32 4
    store i8* null, i8** %refs_ptr
    
    ; Initialize ref count
    %ref_count_ptr = getelementptr %DString, %DString* %dstr_ptr, i32 0, i32 5
    store i32 0, i32* %ref_count_ptr
    
    ; Set dirty flag
    %dirty_ptr = getelementptr %DString, %DString* %dstr_ptr, i32 0, i32 6
    store i1 1, i1* %dirty_ptr
    
    ret %DString* %dstr_ptr
}

; Add a variable reference to a D-string (simplified version)
define void @DString_addRef(%DString* %dstr, i8* %name, i8* %var_ptr, i32 %var_type) {
entry:
    ; Get current ref count
    %ref_count_ptr = getelementptr %DString, %DString* %dstr, i32 0, i32 5
    %ref_count = load i32, i32* %ref_count_ptr
    
    ; Update ref count
    %new_count = add i32 %ref_count, 1
    store i32 %new_count, i32* %ref_count_ptr
    
    ret void
}

; Get the current string value (regenerates if dirty)
define i8* @DString_get(%DString* %dstr) {
entry:
    ; Check dirty flag
    %dirty_ptr = getelementptr %DString, %DString* %dstr, i32 0, i32 6
    %dirty = load i1, i1* %dirty_ptr
    
    br i1 %dirty, label %regenerate, label %return_cached

regenerate:
    ; Get format string
    %format_ptr = getelementptr %DString, %DString* %dstr, i32 0, i32 0
    %format = load i8*, i8** %format_ptr
    
    ; Allocate buffer for result (simplified - fixed size)
    %buffer = call i8* @malloc(i64 1024)
    
    ; For now, just copy format string (full impl would substitute vars)
    call i8* @strcpy(i8* %buffer, i8* %format)
    
    ; Free old cache if exists
    %cache_ptr = getelementptr %DString, %DString* %dstr, i32 0, i32 2
    %old_cache = load i8*, i8** %cache_ptr
    %old_null = icmp eq i8* %old_cache, null
    br i1 %old_null, label %store_cache, label %free_old

free_old:
    call void @free(i8* %old_cache)
    br label %store_cache

store_cache:
    ; Store new cache
    store i8* %buffer, i8** %cache_ptr
    
    ; Clear dirty flag
    store i1 0, i1* %dirty_ptr
    
    br label %return_cached

return_cached:
    %cache_ptr2 = getelementptr %DString, %DString* %dstr, i32 0, i32 2
    %result = load i8*, i8** %cache_ptr2
    ret i8* %result
}

; Mark D-string as dirty (called when a referenced variable changes)
define void @DString_markDirty(%DString* %dstr) {
entry:
    %dirty_ptr = getelementptr %DString, %DString* %dstr, i32 0, i32 6
    store i1 1, i1* %dirty_ptr
    ret void
}

; Free a D-string
define void @DString_free(%DString* %dstr) {
entry:
    ; Free cached result if exists
    %cache_ptr = getelementptr %DString, %DString* %dstr, i32 0, i32 2
    %cache = load i8*, i8** %cache_ptr
    %cache_null = icmp eq i8* %cache, null
    br i1 %cache_null, label %free_refs, label %free_cache

free_cache:
    call void @free(i8* %cache)
    br label %free_refs

free_refs:
    ; Free refs array if exists
    %refs_ptr = getelementptr %DString, %DString* %dstr, i32 0, i32 4
    %refs = load i8*, i8** %refs_ptr
    %refs_null = icmp eq i8* %refs, null
    br i1 %refs_null, label %free_struct, label %do_free_refs

do_free_refs:
    call void @free(i8* %refs)
    br label %free_struct

free_struct:
    ; Free the struct itself
    %dstr_ptr = bitcast %DString* %dstr to i8*
    call void @free(i8* %dstr_ptr)
    ret void
}
"""
    
    def generate_dstring_creation(self, format_string: str, var_refs: List[Tuple[str, str]]) -> Tuple[str, str]:
        """
        Generate code to create a D-string with variable references.
        
        Args:
            format_string: The format string template
            var_refs: List of (variable_name, llvm_var_ptr) tuples
        
        Returns:
            (code, result_register)
        """
        code_lines = []
        self.dstring_counter += 1
        dstr_id = self.dstring_counter
        
        # Create string constant for format
        format_escaped = format_string.replace('"', '\\"').replace('\n', '\\n')
        format_len = len(format_string) + 1
        
        code_lines.append(f"  ; Create D-string {dstr_id}")
        code_lines.append(f"  %dstr_{dstr_id}_format = getelementptr [{format_len} x i8], [{format_len} x i8]* @.dstr.{dstr_id}, i32 0, i32 0")
        code_lines.append(f"  %dstr_{dstr_id} = call %DString* @DString_new(i8* %dstr_{dstr_id}_format, i64 {format_len - 1})")
        
        # Add variable references
        for i, (var_name, var_ptr) in enumerate(var_refs):
            var_type = 0  # Assume int for now
            code_lines.append(f"  ; Add reference to {var_name}")
            code_lines.append(f"  %dstr_{dstr_id}_name_{i} = getelementptr [32 x i8], [32 x i8]* @.dstr.{dstr_id}.var.{i}, i32 0, i32 0")
            code_lines.append(f"  call void @DString_addRef(%DString* %dstr_{dstr_id}, i8* %dstr_{dstr_id}_name_{i}, i8* {var_ptr}, i32 {var_type})")
        
        return "\n".join(code_lines), f"%dstr_{dstr_id}"
