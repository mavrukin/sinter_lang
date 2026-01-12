# Sinter Programming Language

**A modern, strongly-typed language with built-in safety and serialization.**

<p align="center">
  <strong>Write Safe, Ship Fast</strong>
</p>

---

## Features

- **Object-Oriented** — Classes, inheritance, interfaces, polymorphism
- **Strongly Typed** — Compile-time type checking
- **Memory Safe** — Compiler-enforced pointer cleanup
- **Built-in Serialization** — Every class supports JSON/XML out of the box
- **D-Strings** — Dynamic strings that auto-update when variables change
- **Clean Syntax** — Python-style string interpolation, C++-style scope blocks

## Quick Example

```sinter
class Counter {
  private:
    var count: int = 0
  
  public:
    method increment() -> void {
      count = count + 1;
    }
    
    method getCount() -> int {
      return count;
    }
    
    method clean() -> void { }
}

function main() -> int {
  var c: Counter* = Counter.new();
  
  c.increment();
  c.increment();
  c.increment();
  
  var value: int = c.getCount();
  println(value);  // Output: 3
  
  c.clean();  // Memory cleanup required!
  return 0;
}
```

## Documentation

📖 **[Language Guide](docs/LANGUAGE_GUIDE.md)** — Complete documentation with tutorials  
📋 **[Quick Reference](docs/QUICK_REFERENCE.md)** — Syntax cheat sheet

## Installation & Compilation

### Requirements

- Python 3.13+ [[memory:8371484]]
- LLVM 21+ (provides `llc`)
- Clang (for linking)

### Compile a Sinter Program

```bash
# Step 1: Generate LLVM IR
python3 compiler/main.py myprogram.sinter --emit-llvm -o myprogram.ll

# Step 2: Compile to object file
llc -filetype=obj myprogram.ll -o myprogram.o

# Step 3: Link to executable
clang myprogram.o -o myprogram

# Step 4: Run!
./myprogram
```

## Examples

The `/examples` directory contains working programs:

| File | Description |
|------|-------------|
| `hospital.sinter` | Hospital management with business logic |
| `showcase.sinter` | Comprehensive feature demonstration |
| `features_demo.sinter` | Loops, classes, break/continue |
| `field_init_test.sinter` | Field initialization with defaults |
| `counter.sinter` | Simple counter benchmark |
| `fibonacci.sinter` | Fibonacci calculation |

## Language Highlights

### Scope Blocks (C++ Style)

```sinter
class MyClass {
  private:
    var secret: int = 42
  
  protected:
    var inherited: int = 0
  
  public:
    method getSecret() -> int {
      return secret;
    }
}
```

### Methods vs Functions

```sinter
// Functions are static - no instance state
function add(a: int, b: int) -> int {
  return a + b;
}

// Methods have instance context - no 'this' needed!
class Calculator {
  private:
    var result: int = 0
  
  public:
    method add(value: int) -> void {
      result = result + value;  // Direct field access
    }
}
```

### Control Flow

```sinter
// For loops
for (var i: int = 0; i < 10; i = i + 1) {
  if (i == 5) {
    break;
  }
  if (i % 2 == 0) {
    continue;
  }
  println(i);
}

// While loops
while (condition) {
  // ...
}
```

### Interfaces

```sinter
interface Drawable {
  method draw() -> void;
  method getArea() -> double;
}
```

### Field Annotations

```sinter
class Config {
  public:
    @attribute(serializable=true)
    var apiKey: str
    
    @attribute(read_only=true)
    var version: str
    
    @attribute(derived=true)
    var status: str
}
```

## Project Structure

```
sinter_lang/
├── compiler/
│   ├── lexer/       # Tokenization
│   ├── parser/      # AST construction  
│   ├── sinter_ast/  # AST node definitions
│   ├── semantic/    # Type checking & validation
│   ├── codegen/     # LLVM IR generation
│   ├── sinter_types/ # Type system
│   └── runtime/     # Runtime support (D-strings, serialization)
├── docs/
│   ├── LANGUAGE_GUIDE.md  # Full documentation
│   └── QUICK_REFERENCE.md # Cheat sheet
├── examples/        # Sample programs
├── BUILD            # Bazel build file
└── MODULE.bazel     # Bazel module configuration
```

## Implementation Status

| Component | Status |
|-----------|--------|
| Lexer | ✅ Complete |
| Parser | ✅ Complete |
| AST | ✅ Complete |
| Semantic Analyzer | ✅ Complete |
| LLVM Code Generation | ✅ Complete |
| For/While Loops | ✅ Complete |
| Break/Continue | ✅ Complete |
| Print/Println | ✅ Complete |
| Interfaces | ✅ Complete |
| Field Initialization | ✅ Complete |
| Memory Cleanup | ✅ Complete |
| D-Strings | 🚧 In Progress |
| JSON/XML Serialization | 🚧 In Progress |
| Pointer Cleanup Validation | 🚧 In Progress |

## Building with Bazel [[memory:8369097]]

```bash
# Build the compiler
bazel build //:sinterc

# Run the compiler
bazel run //:sinterc -- input.sinter -o output.ll
```

## License

MIT License - See LICENSE file for details.

---

*Sinter — Write Safe, Ship Fast*
