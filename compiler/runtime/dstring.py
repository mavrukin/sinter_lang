"""
D-String (Dynamic String) Runtime Support for Sinter
Generates LLVM IR for dynamic strings that update when referenced variables change

D-strings are a novel feature that automatically regenerate their content when
any referenced variable changes value. Example:

    var count: int = 0;
    var msg: str = D"Count is {count}";
    println(msg);  // "Count is 0"
    count = 5;
    println(msg);  // "Count is 5" (auto-updated!)
"""

from typing import Dict, List, Tuple, Set, Optional
import re


class DStringVarType:
    """Variable type codes for D-string substitution"""
    INT = 0
    FLOAT = 1
    DOUBLE = 2
    BOOLEAN = 3
    STRING = 4
    POINTER = 5


class DStringParser:
    """Parses D-string format strings to extract variable references"""
    
    # Pattern to match {variable_name} in strings
    VAR_PATTERN = re.compile(r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}')
    
    @classmethod
    def parse(cls, format_string: str) -> Tuple[str, List[str]]:
        """
        Parse a D-string format string.
        Returns (format_template_with_placeholders, [variable_names])
        
        Example:
            "Hello, count is {counter}" -> ("Hello, count is %s", ["counter"])
        """
        variables = []
        
        def replace_var(match):
            var_name = match.group(1)
            variables.append(var_name)
            return "%s"  # Use %s as universal placeholder
        
        template = cls.VAR_PATTERN.sub(replace_var, format_string)
        return template, variables
    
    @classmethod
    def get_variables(cls, format_string: str) -> List[str]:
        """Extract all variable names from a D-string in order"""
        return cls.VAR_PATTERN.findall(format_string)
    
    @classmethod
    def get_unique_variables(cls, format_string: str) -> Set[str]:
        """Extract unique variable names from a D-string"""
        return set(cls.VAR_PATTERN.findall(format_string))


class DStringRegistry:
    """
    Tracks D-strings and their variable dependencies.
    Used by the code generator to inject dirty-flag updates.
    """
    
    def __init__(self):
        # Map: variable_name -> list of (dstring_id, dstring_llvm_ptr)
        self.var_to_dstrings: Dict[str, List[Tuple[int, str]]] = {}
        # Map: dstring_id -> list of variable names
        self.dstring_vars: Dict[int, List[str]] = {}
        self.next_id = 0
    
    def register_dstring(self, dstring_id: int, dstring_ptr: str, variables: List[str]):
        """Register a D-string and its variable dependencies"""
        self.dstring_vars[dstring_id] = variables
        for var in variables:
            if var not in self.var_to_dstrings:
                self.var_to_dstrings[var] = []
            self.var_to_dstrings[var].append((dstring_id, dstring_ptr))
    
    def get_dstrings_for_var(self, var_name: str) -> List[Tuple[int, str]]:
        """Get all D-strings that reference a variable"""
        return self.var_to_dstrings.get(var_name, [])
    
    def allocate_id(self) -> int:
        """Allocate a new D-string ID"""
        id = self.next_id
        self.next_id += 1
        return id


class DStringCodeGen:
    """Generates LLVM IR code for D-string operations"""
    
    def __init__(self):
        self.dstring_counter = 0
        self.format_strings: Dict[int, Tuple[str, int]] = {}  # id -> (format, length)
        self.registry = DStringRegistry()
    
    def get_registry(self) -> DStringRegistry:
        """Get the D-string registry for variable tracking"""
        return self.registry
    
    def generate_dstring_type(self) -> str:
        """Generate the D-string struct type definition"""
        return """; D-String structure - Dynamic strings that auto-update
%DString = type {
    i8*,        ; 0: format string pointer (with %s placeholders)
    i64,        ; 1: format string length
    i8*,        ; 2: cached result string
    i64,        ; 3: cached result length
    i8**,       ; 4: array of pointers to referenced variables
    i32*,       ; 5: array of variable types (DStringVarType)
    i32,        ; 6: number of variable references
    i1          ; 7: dirty flag (true = needs regeneration)
}
"""
    
    def generate_dstring_runtime_functions(self) -> str:
        """Generate runtime functions for D-string operations"""
        return """
; ===========================================================================
; D-String Runtime Functions
; ===========================================================================

; Create a new D-string with format and variable count
define %DString* @DString_create(i8* %format, i64 %format_len, i32 %var_count) {
entry:
    ; Allocate D-string struct
    %dstr_mem = call i8* @malloc(i64 64)
    %dstr = bitcast i8* %dstr_mem to %DString*
    
    ; Copy format string (we own it)
    %format_buf = call i8* @malloc(i64 %format_len)
    call i8* @strcpy(i8* %format_buf, i8* %format)
    
    ; Store format string
    %fmt_ptr = getelementptr %DString, %DString* %dstr, i32 0, i32 0
    store i8* %format_buf, i8** %fmt_ptr
    
    ; Store format length
    %fmt_len_ptr = getelementptr %DString, %DString* %dstr, i32 0, i32 1
    store i64 %format_len, i64* %fmt_len_ptr
    
    ; Initialize cached result to null
    %cache_ptr = getelementptr %DString, %DString* %dstr, i32 0, i32 2
    store i8* null, i8** %cache_ptr
    
    ; Initialize cache length to 0
    %cache_len_ptr = getelementptr %DString, %DString* %dstr, i32 0, i32 3
    store i64 0, i64* %cache_len_ptr
    
    ; Allocate variable pointer array
    %var_count_64 = sext i32 %var_count to i64
    %ptrs_size = mul i64 %var_count_64, 8
    %var_ptrs_mem = call i8* @malloc(i64 %ptrs_size)
    %var_ptrs = bitcast i8* %var_ptrs_mem to i8**
    %var_ptrs_ptr = getelementptr %DString, %DString* %dstr, i32 0, i32 4
    store i8** %var_ptrs, i8*** %var_ptrs_ptr
    
    ; Allocate variable type array
    %types_size = mul i64 %var_count_64, 4
    %var_types_mem = call i8* @malloc(i64 %types_size)
    %var_types = bitcast i8* %var_types_mem to i32*
    %var_types_ptr = getelementptr %DString, %DString* %dstr, i32 0, i32 5
    store i32* %var_types, i32** %var_types_ptr
    
    ; Store variable count
    %count_ptr = getelementptr %DString, %DString* %dstr, i32 0, i32 6
    store i32 %var_count, i32* %count_ptr
    
    ; Set dirty flag (needs initial generation)
    %dirty_ptr = getelementptr %DString, %DString* %dstr, i32 0, i32 7
    store i1 1, i1* %dirty_ptr
    
    ret %DString* %dstr
}

; Set a variable reference at index
define void @DString_setVar(%DString* %dstr, i32 %index, i8* %var_ptr, i32 %var_type) {
entry:
    ; Get var pointers array
    %var_ptrs_ptr = getelementptr %DString, %DString* %dstr, i32 0, i32 4
    %var_ptrs = load i8**, i8*** %var_ptrs_ptr
    
    ; Store variable pointer at index
    %ptr_slot = getelementptr i8*, i8** %var_ptrs, i32 %index
    store i8* %var_ptr, i8** %ptr_slot
    
    ; Get var types array
    %var_types_ptr = getelementptr %DString, %DString* %dstr, i32 0, i32 5
    %var_types = load i32*, i32** %var_types_ptr
    
    ; Store variable type at index
    %type_slot = getelementptr i32, i32* %var_types, i32 %index
    store i32 %var_type, i32* %type_slot
    
    ret void
}

; Mark D-string as dirty (called when a referenced variable changes)
define void @DString_markDirty(%DString* %dstr) {
entry:
    %dirty_ptr = getelementptr %DString, %DString* %dstr, i32 0, i32 7
    store i1 1, i1* %dirty_ptr
    ret void
}

; Convert an integer to string (helper)
define i8* @DString_itoa(i32 %val) {
entry:
    %buf = call i8* @malloc(i64 32)
    call i32 (i8*, i8*, ...) @sprintf(i8* %buf, i8* getelementptr ([3 x i8], [3 x i8]* @.dstr.fmt.int, i32 0, i32 0), i32 %val)
    ret i8* %buf
}

; Convert a float to string (helper)
define i8* @DString_ftoa(float %val) {
entry:
    %buf = call i8* @malloc(i64 64)
    %val_d = fpext float %val to double
    call i32 (i8*, i8*, ...) @sprintf(i8* %buf, i8* getelementptr ([3 x i8], [3 x i8]* @.dstr.fmt.float, i32 0, i32 0), double %val_d)
    ret i8* %buf
}

; Convert a double to string (helper)
define i8* @DString_dtoa(double %val) {
entry:
    %buf = call i8* @malloc(i64 64)
    call i32 (i8*, i8*, ...) @sprintf(i8* %buf, i8* getelementptr ([4 x i8], [4 x i8]* @.dstr.fmt.double, i32 0, i32 0), double %val)
    ret i8* %buf
}

; Convert a boolean to string (helper)
define i8* @DString_btoa(i1 %val) {
entry:
    br i1 %val, label %true_case, label %false_case
true_case:
    ret i8* getelementptr ([5 x i8], [5 x i8]* @.dstr.true, i32 0, i32 0)
false_case:
    ret i8* getelementptr ([6 x i8], [6 x i8]* @.dstr.false, i32 0, i32 0)
}

; Get the current string value (regenerates if dirty)
; This is the core D-string magic!
define i8* @DString_get(%DString* %dstr) {
entry:
    ; Check dirty flag
    %dirty_ptr = getelementptr %DString, %DString* %dstr, i32 0, i32 7
    %dirty = load i1, i1* %dirty_ptr
    br i1 %dirty, label %regenerate, label %return_cached

regenerate:
    ; Free old cache if exists
    %cache_ptr = getelementptr %DString, %DString* %dstr, i32 0, i32 2
    %old_cache = load i8*, i8** %cache_ptr
    %old_null = icmp eq i8* %old_cache, null
    br i1 %old_null, label %do_regen, label %free_old

free_old:
    call void @free(i8* %old_cache)
    br label %do_regen

do_regen:
    ; Get format string
    %fmt_ptr = getelementptr %DString, %DString* %dstr, i32 0, i32 0
    %format = load i8*, i8** %fmt_ptr
    
    ; Get variable count
    %count_ptr = getelementptr %DString, %DString* %dstr, i32 0, i32 6
    %var_count = load i32, i32* %count_ptr
    
    ; Allocate result buffer (generous size)
    %result_buf = call i8* @malloc(i64 4096)
    
    ; If no variables, just copy format string
    %has_vars = icmp sgt i32 %var_count, 0
    br i1 %has_vars, label %substitute_vars, label %copy_format

copy_format:
    call i8* @strcpy(i8* %result_buf, i8* %format)
    br label %store_result

substitute_vars:
    ; Get arrays
    %var_ptrs_ptr = getelementptr %DString, %DString* %dstr, i32 0, i32 4
    %var_ptrs = load i8**, i8*** %var_ptrs_ptr
    %var_types_ptr = getelementptr %DString, %DString* %dstr, i32 0, i32 5
    %var_types = load i32*, i32** %var_types_ptr
    
    ; We'll build the result by calling a helper that does sprintf-style substitution
    ; For simplicity, we handle up to 8 variables
    call void @DString_substitute(%DString* %dstr, i8* %result_buf)
    br label %store_result

store_result:
    ; Store new cache
    store i8* %result_buf, i8** %cache_ptr
    
    ; Update cache length
    %result_len = call i64 @strlen(i8* %result_buf)
    %cache_len_ptr = getelementptr %DString, %DString* %dstr, i32 0, i32 3
    store i64 %result_len, i64* %cache_len_ptr
    
    ; Clear dirty flag
    store i1 0, i1* %dirty_ptr
    
    br label %return_cached

return_cached:
    %final_cache_ptr = getelementptr %DString, %DString* %dstr, i32 0, i32 2
    %result = load i8*, i8** %final_cache_ptr
    ret i8* %result
}

; Substitute variables into format string
; This handles the actual {var} -> value replacement
define void @DString_substitute(%DString* %dstr, i8* %output) {
entry:
    ; Get format
    %fmt_ptr = getelementptr %DString, %DString* %dstr, i32 0, i32 0
    %format = load i8*, i8** %fmt_ptr
    
    ; Get var count
    %count_ptr = getelementptr %DString, %DString* %dstr, i32 0, i32 6
    %var_count = load i32, i32* %count_ptr
    
    ; Get arrays
    %var_ptrs_ptr = getelementptr %DString, %DString* %dstr, i32 0, i32 4
    %var_ptrs = load i8**, i8*** %var_ptrs_ptr
    %var_types_ptr = getelementptr %DString, %DString* %dstr, i32 0, i32 5
    %var_types = load i32*, i32** %var_types_ptr
    
    ; Initialize output position
    %out_pos = alloca i64
    store i64 0, i64* %out_pos
    
    ; Variable index for substitution
    %var_idx = alloca i32
    store i32 0, i32* %var_idx
    
    ; Scan through format string
    %fmt_len = call i64 @strlen(i8* %format)
    %i = alloca i64
    store i64 0, i64* %i
    br label %loop_start

loop_start:
    %curr_i = load i64, i64* %i
    %done = icmp sge i64 %curr_i, %fmt_len
    br i1 %done, label %loop_end, label %loop_body

loop_body:
    ; Get current char
    %char_ptr = getelementptr i8, i8* %format, i64 %curr_i
    %char = load i8, i8* %char_ptr
    
    ; Check for %s (our placeholder)
    %is_percent = icmp eq i8 %char, 37  ; '%'
    br i1 %is_percent, label %check_s, label %copy_char

check_s:
    ; Check next char is 's'
    %next_i = add i64 %curr_i, 1
    %next_done = icmp sge i64 %next_i, %fmt_len
    br i1 %next_done, label %copy_char, label %check_s_char

check_s_char:
    %next_ptr = getelementptr i8, i8* %format, i64 %next_i
    %next_char = load i8, i8* %next_ptr
    %is_s = icmp eq i8 %next_char, 115  ; 's'
    br i1 %is_s, label %do_substitute, label %copy_char

do_substitute:
    ; Get current variable index
    %curr_var_idx = load i32, i32* %var_idx
    %var_in_range = icmp slt i32 %curr_var_idx, %var_count
    br i1 %var_in_range, label %substitute_var, label %skip_percent_s

substitute_var:
    ; Get variable pointer
    %var_ptr_slot = getelementptr i8*, i8** %var_ptrs, i32 %curr_var_idx
    %var_ptr = load i8*, i8** %var_ptr_slot
    
    ; Get variable type
    %type_slot = getelementptr i32, i32* %var_types, i32 %curr_var_idx
    %var_type = load i32, i32* %type_slot
    
    ; Convert to string based on type
    %str_val = call i8* @DString_varToString(i8* %var_ptr, i32 %var_type)
    
    ; Copy string value to output
    %curr_out_pos = load i64, i64* %out_pos
    %out_ptr = getelementptr i8, i8* %output, i64 %curr_out_pos
    call i8* @strcpy(i8* %out_ptr, i8* %str_val)
    
    ; Update output position
    %str_len = call i64 @strlen(i8* %str_val)
    %new_out_pos = add i64 %curr_out_pos, %str_len
    store i64 %new_out_pos, i64* %out_pos
    
    ; Free temp string if it was allocated (not for booleans)
    %is_bool = icmp eq i32 %var_type, 3
    br i1 %is_bool, label %skip_free, label %maybe_free

maybe_free:
    %is_str = icmp eq i32 %var_type, 4
    br i1 %is_str, label %skip_free, label %do_free

do_free:
    call void @free(i8* %str_val)
    br label %skip_free

skip_free:
    ; Increment variable index
    %new_var_idx = add i32 %curr_var_idx, 1
    store i32 %new_var_idx, i32* %var_idx
    
    ; Skip the %s in format
    %skip_i = add i64 %curr_i, 2
    store i64 %skip_i, i64* %i
    br label %loop_start

skip_percent_s:
    ; No more variables, copy %s literally
    br label %copy_char

copy_char:
    ; Copy single character
    %curr_out_pos2 = load i64, i64* %out_pos
    %out_char_ptr = getelementptr i8, i8* %output, i64 %curr_out_pos2
    store i8 %char, i8* %out_char_ptr
    
    ; Increment output position
    %new_out_pos2 = add i64 %curr_out_pos2, 1
    store i64 %new_out_pos2, i64* %out_pos
    
    ; Increment input position
    %new_i = add i64 %curr_i, 1
    store i64 %new_i, i64* %i
    br label %loop_start

loop_end:
    ; Null terminate
    %final_out_pos = load i64, i64* %out_pos
    %null_ptr = getelementptr i8, i8* %output, i64 %final_out_pos
    store i8 0, i8* %null_ptr
    ret void
}

; Convert variable to string based on type
define i8* @DString_varToString(i8* %var_ptr, i32 %var_type) {
entry:
    switch i32 %var_type, label %default [
        i32 0, label %type_int
        i32 1, label %type_float
        i32 2, label %type_double
        i32 3, label %type_bool
        i32 4, label %type_string
    ]

type_int:
    %int_ptr = bitcast i8* %var_ptr to i32*
    %int_val = load i32, i32* %int_ptr
    %int_str = call i8* @DString_itoa(i32 %int_val)
    ret i8* %int_str

type_float:
    %float_ptr = bitcast i8* %var_ptr to float*
    %float_val = load float, float* %float_ptr
    %float_str = call i8* @DString_ftoa(float %float_val)
    ret i8* %float_str

type_double:
    %double_ptr = bitcast i8* %var_ptr to double*
    %double_val = load double, double* %double_ptr
    %double_str = call i8* @DString_dtoa(double %double_val)
    ret i8* %double_str

type_bool:
    %bool_ptr = bitcast i8* %var_ptr to i1*
    %bool_val = load i1, i1* %bool_ptr
    %bool_str = call i8* @DString_btoa(i1 %bool_val)
    ret i8* %bool_str

type_string:
    ; String is already a char*, just load the pointer
    %str_ptr_ptr = bitcast i8* %var_ptr to i8**
    %str_val = load i8*, i8** %str_ptr_ptr
    ret i8* %str_val

default:
    ; Unknown type, return empty string
    ret i8* getelementptr ([1 x i8], [1 x i8]* @.dstr.empty, i32 0, i32 0)
}

; Free a D-string and all its resources
define void @DString_free(%DString* %dstr) {
entry:
    ; Free format string
    %fmt_ptr = getelementptr %DString, %DString* %dstr, i32 0, i32 0
    %format = load i8*, i8** %fmt_ptr
    call void @free(i8* %format)
    
    ; Free cached result if exists
    %cache_ptr = getelementptr %DString, %DString* %dstr, i32 0, i32 2
    %cache = load i8*, i8** %cache_ptr
    %cache_null = icmp eq i8* %cache, null
    br i1 %cache_null, label %free_arrays, label %free_cache

free_cache:
    call void @free(i8* %cache)
    br label %free_arrays

free_arrays:
    ; Free var pointers array
    %var_ptrs_ptr = getelementptr %DString, %DString* %dstr, i32 0, i32 4
    %var_ptrs = load i8**, i8*** %var_ptrs_ptr
    %var_ptrs_i8 = bitcast i8** %var_ptrs to i8*
    call void @free(i8* %var_ptrs_i8)
    
    ; Free var types array
    %var_types_ptr = getelementptr %DString, %DString* %dstr, i32 0, i32 5
    %var_types = load i32*, i32** %var_types_ptr
    %var_types_i8 = bitcast i32* %var_types to i8*
    call void @free(i8* %var_types_i8)
    
    ; Free struct
    %dstr_i8 = bitcast %DString* %dstr to i8*
    call void @free(i8* %dstr_i8)
    ret void
}
"""

    def generate_format_constants(self) -> str:
        """Generate string constants used by D-string runtime"""
        return """; D-String format constants
@.dstr.fmt.int = private unnamed_addr constant [3 x i8] c"%d\\00"
@.dstr.fmt.float = private unnamed_addr constant [3 x i8] c"%f\\00"
@.dstr.fmt.double = private unnamed_addr constant [4 x i8] c"%lf\\00"
@.dstr.true = private unnamed_addr constant [5 x i8] c"true\\00"
@.dstr.false = private unnamed_addr constant [6 x i8] c"false\\00"
@.dstr.empty = private unnamed_addr constant [1 x i8] c"\\00"
"""

    def get_var_type_code(self, type_name: str) -> int:
        """Get the DString variable type code for a Sinter type"""
        type_map = {
            "int": DStringVarType.INT,
            "float": DStringVarType.FLOAT,
            "double": DStringVarType.DOUBLE,
            "boolean": DStringVarType.BOOLEAN,
            "str": DStringVarType.STRING,
        }
        return type_map.get(type_name, DStringVarType.INT)

    def generate_dstring_creation(self, dstring_id: int, format_template: str, 
                                   var_infos: List[Tuple[str, str, int]]) -> Tuple[str, str]:
        """
        Generate code to create a D-string.
        
        Args:
            dstring_id: Unique ID for this D-string
            format_template: Format string with %s placeholders
            var_infos: List of (var_name, llvm_var_ptr, var_type_code)
        
        Returns:
            (code, result_register)
        """
        lines = []
        var_count = len(var_infos)
        format_len = len(format_template) + 1  # +1 for null terminator
        
        # Create format string constant name
        const_name = f"@.dstr.fmt.{dstring_id}"
        
        lines.append(f"  ; Create D-string {dstring_id} with {var_count} variables")
        lines.append(f"  %dstr_{dstring_id}_fmt_ptr = getelementptr [{format_len} x i8], [{format_len} x i8]* {const_name}, i32 0, i32 0")
        lines.append(f"  %dstr_{dstring_id} = call %DString* @DString_create(i8* %dstr_{dstring_id}_fmt_ptr, i64 {format_len}, i32 {var_count})")
        
        # Set each variable reference
        for idx, (var_name, var_ptr, var_type) in enumerate(var_infos):
            lines.append(f"  ; Set variable {idx}: {var_name}")
            lines.append(f"  %dstr_{dstring_id}_var_{idx}_ptr = bitcast i8* {var_ptr} to i8*")
            lines.append(f"  call void @DString_setVar(%DString* %dstr_{dstring_id}, i32 {idx}, i8* %dstr_{dstring_id}_var_{idx}_ptr, i32 {var_type})")
        
        return "\n".join(lines), f"%dstr_{dstring_id}"

    def generate_format_string_constant(self, dstring_id: int, format_template: str) -> str:
        """Generate the format string constant for a D-string"""
        # Escape the format string for LLVM
        escaped = format_template.replace("\\", "\\\\").replace('"', '\\"')
        length = len(format_template) + 1  # +1 for null terminator
        
        # Convert to LLVM string constant format
        const_name = f"@.dstr.fmt.{dstring_id}"
        return f'{const_name} = private unnamed_addr constant [{length} x i8] c"{escaped}\\00"'

    def generate_dirty_mark(self, dstring_ptr: str) -> str:
        """Generate code to mark a D-string as dirty"""
        return f"  call void @DString_markDirty(%DString* {dstring_ptr})"

    def generate_dstring_get(self, dstring_ptr: str, result_reg: str) -> str:
        """Generate code to get the current value of a D-string"""
        return f"  {result_reg} = call i8* @DString_get(%DString* {dstring_ptr})"
