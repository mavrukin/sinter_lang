"""
JSON/XML Serialization Code Generation for Sinter
Generates LLVM IR for built-in serialization methods
"""

from typing import Dict, List, Optional, Tuple
from compiler.sinter_types.types import (
    SinterType, PrimitiveType, StringType, ClassType, PointerType,
    FieldInfo, TypeRegistry
)


class SerializationCodeGen:
    """Generates serialization code for Sinter classes"""
    
    def __init__(self, type_registry: TypeRegistry):
        self.type_registry = type_registry
        self.json_buffer_size = 4096
        self.xml_buffer_size = 8192
    
    def generate_runtime_declarations(self) -> str:
        """Generate runtime function declarations for serialization"""
        return """
; Serialization runtime declarations

; JSON serialization helpers
@.json.obj_start = private unnamed_addr constant [2 x i8] c"{\\00"
@.json.obj_end = private unnamed_addr constant [2 x i8] c"}\\00"
@.json.arr_start = private unnamed_addr constant [2 x i8] c"[\\00"
@.json.arr_end = private unnamed_addr constant [2 x i8] c"]\\00"
@.json.quote = private unnamed_addr constant [2 x i8] c"\\22\\00"
@.json.colon = private unnamed_addr constant [3 x i8] c": \\00"
@.json.comma = private unnamed_addr constant [3 x i8] c", \\00"
@.json.null = private unnamed_addr constant [5 x i8] c"null\\00"
@.json.true = private unnamed_addr constant [5 x i8] c"true\\00"
@.json.false = private unnamed_addr constant [6 x i8] c"false\\00"
@.json.int_fmt = private unnamed_addr constant [3 x i8] c"%d\\00"
@.json.float_fmt = private unnamed_addr constant [3 x i8] c"%f\\00"
@.json.str_fmt = private unnamed_addr constant [5 x i8] c"\\22%s\\22\\00"

; XML serialization helpers
@.xml.lt = private unnamed_addr constant [2 x i8] c"<\\00"
@.xml.gt = private unnamed_addr constant [2 x i8] c">\\00"
@.xml.lt_slash = private unnamed_addr constant [3 x i8] c"</\\00"
@.xml.newline = private unnamed_addr constant [2 x i8] c"\\0A\\00"
"""
    
    def generate_json_serializer(self, class_type: ClassType) -> str:
        """Generate as_json() method for a class"""
        class_name = class_type.name
        
        # Get serializable fields
        serializable_fields = [
            (name, field) for name, field in class_type.fields.items()
            if field.visibility == "public" and 
               field.is_serializable and 
               not field.is_derived
        ]
        
        code = f"""
; JSON serializer for {class_name}
define i8* @{class_name}_as_json(%class.{class_name}* %this) {{
entry:
    ; Allocate buffer
    %buffer = call i8* @malloc(i64 {self.json_buffer_size})
    %pos = alloca i64
    store i64 0, i64* %pos
    
    ; Start object
    %start = getelementptr [2 x i8], [2 x i8]* @.json.obj_start, i32 0, i32 0
    call i8* @strcpy(i8* %buffer, i8* %start)
    %len1 = call i64 @strlen(i8* %buffer)
    store i64 %len1, i64* %pos
"""
        
        # Add each serializable field
        for i, (field_name, field) in enumerate(serializable_fields):
            field_idx = list(class_type.fields.keys()).index(field_name) + 1
            llvm_type = self._get_llvm_type(field.field_type)
            
            # Generate field name string constant
            code += f"""
    ; Field: {field_name}
    %field_{i}_name_ptr = getelementptr [64 x i8], [64 x i8]* @.json.{class_name}.{field_name}, i32 0, i32 0
"""
            
            # Get field value
            code += f"""
    %field_{i}_ptr = getelementptr %class.{class_name}, %class.{class_name}* %this, i32 0, i32 {field_idx}
    %field_{i}_val = load {llvm_type}, {llvm_type}* %field_{i}_ptr
"""
            
            # Format based on type
            if field.field_type.name == "int":
                code += f"""
    %pos_{i} = load i64, i64* %pos
    %buf_{i} = getelementptr i8, i8* %buffer, i64 %pos_{i}
    %fmt_{i} = getelementptr [3 x i8], [3 x i8]* @.json.int_fmt, i32 0, i32 0
    %written_{i} = call i32 (i8*, i64, i8*, ...) @snprintf(i8* %buf_{i}, i64 256, i8* %fmt_{i}, {llvm_type} %field_{i}_val)
    %written_{i}_64 = sext i32 %written_{i} to i64
    %newpos_{i} = add i64 %pos_{i}, %written_{i}_64
    store i64 %newpos_{i}, i64* %pos
"""
            elif field.field_type.name == "boolean":
                code += f"""
    %pos_{i} = load i64, i64* %pos
    %buf_{i} = getelementptr i8, i8* %buffer, i64 %pos_{i}
    br i1 %field_{i}_val, label %true_{i}, label %false_{i}
true_{i}:
    %true_str_{i} = getelementptr [5 x i8], [5 x i8]* @.json.true, i32 0, i32 0
    call i8* @strcpy(i8* %buf_{i}, i8* %true_str_{i})
    br label %cont_{i}
false_{i}:
    %false_str_{i} = getelementptr [6 x i8], [6 x i8]* @.json.false, i32 0, i32 0
    call i8* @strcpy(i8* %buf_{i}, i8* %false_str_{i})
    br label %cont_{i}
cont_{i}:
    %len_{i} = call i64 @strlen(i8* %buf_{i})
    %newpos_{i} = add i64 %pos_{i}, %len_{i}
    store i64 %newpos_{i}, i64* %pos
"""
            
            # Add comma if not last field
            if i < len(serializable_fields) - 1:
                code += f"""
    ; Add comma
    %comma_pos_{i} = load i64, i64* %pos
    %comma_buf_{i} = getelementptr i8, i8* %buffer, i64 %comma_pos_{i}
    %comma_str_{i} = getelementptr [3 x i8], [3 x i8]* @.json.comma, i32 0, i32 0
    call i8* @strcpy(i8* %comma_buf_{i}, i8* %comma_str_{i})
    %comma_len_{i} = call i64 @strlen(i8* %comma_buf_{i})
    %comma_newpos_{i} = add i64 %comma_pos_{i}, %comma_len_{i}
    store i64 %comma_newpos_{i}, i64* %pos
"""
        
        # End object
        code += """
    ; End object
    %end_pos = load i64, i64* %pos
    %end_buf = getelementptr i8, i8* %buffer, i64 %end_pos
    %end_str = getelementptr [2 x i8], [2 x i8]* @.json.obj_end, i32 0, i32 0
    call i8* @strcpy(i8* %end_buf, i8* %end_str)
    
    ret i8* %buffer
}
"""
        return code
    
    def generate_xml_serializer(self, class_type: ClassType) -> str:
        """Generate as_xml() method for a class"""
        class_name = class_type.name
        
        # Get serializable fields
        serializable_fields = [
            (name, field) for name, field in class_type.fields.items()
            if field.visibility == "public" and 
               field.is_serializable and 
               not field.is_derived
        ]
        
        code = f"""
; XML serializer for {class_name}
define i8* @{class_name}_as_xml(%class.{class_name}* %this) {{
entry:
    ; Allocate buffer
    %buffer = call i8* @malloc(i64 {self.xml_buffer_size})
    %pos = alloca i64
    store i64 0, i64* %pos
    
    ; Start root element
    %lt = getelementptr [2 x i8], [2 x i8]* @.xml.lt, i32 0, i32 0
    call i8* @strcpy(i8* %buffer, i8* %lt)
    %class_name = getelementptr [32 x i8], [32 x i8]* @.xml.{class_name}.name, i32 0, i32 0
    call i8* @strcat(i8* %buffer, i8* %class_name)
    %gt = getelementptr [2 x i8], [2 x i8]* @.xml.gt, i32 0, i32 0
    call i8* @strcat(i8* %buffer, i8* %gt)
    %nl = getelementptr [2 x i8], [2 x i8]* @.xml.newline, i32 0, i32 0
    call i8* @strcat(i8* %buffer, i8* %nl)
    %len1 = call i64 @strlen(i8* %buffer)
    store i64 %len1, i64* %pos
"""
        
        # Add each serializable field
        for i, (field_name, field) in enumerate(serializable_fields):
            field_idx = list(class_type.fields.keys()).index(field_name) + 1
            llvm_type = self._get_llvm_type(field.field_type)
            
            code += f"""
    ; Field: {field_name}
    %fpos_{i} = load i64, i64* %pos
    %fbuf_{i} = getelementptr i8, i8* %buffer, i64 %fpos_{i}
    
    ; Open tag
    call i8* @strcpy(i8* %fbuf_{i}, i8* %lt)
    %ftag_{i} = getelementptr [32 x i8], [32 x i8]* @.xml.{class_name}.{field_name}, i32 0, i32 0
    call i8* @strcat(i8* %fbuf_{i}, i8* %ftag_{i})
    call i8* @strcat(i8* %fbuf_{i}, i8* %gt)
    
    ; Get field value
    %fptr_{i} = getelementptr %class.{class_name}, %class.{class_name}* %this, i32 0, i32 {field_idx}
    %fval_{i} = load {llvm_type}, {llvm_type}* %fptr_{i}
"""
            
            # Format value based on type
            if field.field_type.name == "int":
                code += f"""
    %vlen_{i} = call i64 @strlen(i8* %fbuf_{i})
    %vbuf_{i} = getelementptr i8, i8* %fbuf_{i}, i64 %vlen_{i}
    %vfmt_{i} = getelementptr [3 x i8], [3 x i8]* @.json.int_fmt, i32 0, i32 0
    call i32 (i8*, i64, i8*, ...) @snprintf(i8* %vbuf_{i}, i64 64, i8* %vfmt_{i}, {llvm_type} %fval_{i})
"""
            
            code += f"""
    ; Close tag
    %lt_slash = getelementptr [3 x i8], [3 x i8]* @.xml.lt_slash, i32 0, i32 0
    call i8* @strcat(i8* %fbuf_{i}, i8* %lt_slash)
    call i8* @strcat(i8* %fbuf_{i}, i8* %ftag_{i})
    call i8* @strcat(i8* %fbuf_{i}, i8* %gt)
    call i8* @strcat(i8* %fbuf_{i}, i8* %nl)
    
    %fnewlen_{i} = call i64 @strlen(i8* %buffer)
    store i64 %fnewlen_{i}, i64* %pos
"""
        
        # End root element
        code += f"""
    ; End root element
    %epos = load i64, i64* %pos
    %ebuf = getelementptr i8, i8* %buffer, i64 %epos
    call i8* @strcpy(i8* %ebuf, i8* %lt_slash)
    call i8* @strcat(i8* %ebuf, i8* %class_name)
    call i8* @strcat(i8* %ebuf, i8* %gt)
    
    ret i8* %buffer
}}
"""
        return code
    
    def generate_json_deserializer(self, class_type: ClassType) -> str:
        """Generate from_json() method stub for a class"""
        class_name = class_type.name
        
        # This is a simplified stub - full implementation would need JSON parsing
        code = f"""
; JSON deserializer for {class_name} (stub)
define %class.{class_name}* @{class_name}_from_json(i8* %json_str) {{
entry:
    ; Create new instance
    %obj = call %class.{class_name}* @{class_name}_new()
    
    ; TODO: Parse JSON and populate fields
    ; For now, just return the default instance
    
    ret %class.{class_name}* %obj
}}
"""
        return code
    
    def generate_xml_deserializer(self, class_type: ClassType) -> str:
        """Generate from_xml() method stub for a class"""
        class_name = class_type.name
        
        # This is a simplified stub - full implementation would need XML parsing
        code = f"""
; XML deserializer for {class_name} (stub)
define %class.{class_name}* @{class_name}_from_xml(i8* %xml_str) {{
entry:
    ; Create new instance
    %obj = call %class.{class_name}* @{class_name}_new()
    
    ; TODO: Parse XML and populate fields
    ; For now, just return the default instance
    
    ret %class.{class_name}* %obj
}}
"""
        return code
    
    def generate_string_constants(self, class_type: ClassType) -> str:
        """Generate string constants needed for serialization"""
        class_name = class_type.name
        
        code = f"""
; Serialization string constants for {class_name}
@.xml.{class_name}.name = private unnamed_addr constant [{len(class_name) + 1} x i8] c"{class_name}\\00"
"""
        
        for field_name in class_type.fields.keys():
            code += f'@.xml.{class_name}.{field_name} = private unnamed_addr constant [{len(field_name) + 1} x i8] c"{field_name}\\00"\n'
            code += f'@.json.{class_name}.{field_name} = private unnamed_addr constant [64 x i8] c"\\"{field_name}\\":\\00"\n'
        
        return code
    
    def generate_all_serializers(self, class_type: ClassType) -> str:
        """Generate all serialization methods for a class"""
        code = ""
        code += self.generate_string_constants(class_type)
        code += self.generate_json_serializer(class_type)
        code += self.generate_xml_serializer(class_type)
        code += self.generate_json_deserializer(class_type)
        code += self.generate_xml_deserializer(class_type)
        return code
    
    def _get_llvm_type(self, sinter_type: SinterType) -> str:
        """Convert Sinter type to LLVM type"""
        type_map = {
            "int": "i32",
            "float": "float",
            "double": "double",
            "boolean": "i1",
            "byte": "i8",
            "short": "i16",
            "long": "i64",
            "str": "i8*",
        }
        return type_map.get(sinter_type.name, "i32")
