# Sinter Quick Reference Card

## Variables

```sinter
var name: int = 42;       // Mutable
const PI: double = 3.14;  // Immutable
```

## Functions

```sinter
function add(a: int, b: int) -> int {
  return a + b;
}
```

## Classes

```sinter
class MyClass {
  private:
    var field: int = 0
  
  public:
    method getField() -> int {
      return field;
    }
    
    method clean() -> void { }
}
```

## Object Creation & Cleanup

```sinter
var obj: MyClass* = MyClass.new();
// ... use obj ...
obj.clean();  // REQUIRED!
```

## Control Flow

```sinter
// If/Else
if (condition) {
  // ...
} else {
  // ...
}

// While
while (condition) {
  // ...
}

// For
for (var i: int = 0; i < 10; i = i + 1) {
  // ...
}

// Break/Continue
break;     // Exit loop
continue;  // Next iteration
```

## Types

| Type | Description |
|------|-------------|
| `int` | 32-bit integer |
| `float` | 32-bit float |
| `double` | 64-bit float |
| `boolean` | true/false |
| `str` | String |
| `Type*` | Pointer |

## Operators

| Op | Meaning |
|----|---------|
| `+` `-` `*` `/` `%` | Arithmetic |
| `==` `!=` `<` `>` `<=` `>=` | Comparison |
| `&&` `||` `!` | Logical |
| `.` | Member access |
| `*` | Dereference |
| `&` | Address-of |

## Output

```sinter
print(value);    // No newline
println(value);  // With newline
```

## Annotations

```sinter
@attribute                    // Auto getter/setter
@attribute(read_only=true)    // Getter only
@attribute(write_only=true)   // Setter only
@attribute(derived=true)      // Computed value
@attribute(serializable=true) // Include in JSON/XML
```

## Compilation

```bash
python3 compiler/main.py file.sinter --emit-llvm -o file.ll
llc -filetype=obj file.ll -o file.o
clang file.o -o file
./file
```
