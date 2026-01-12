# Sinter Programming Language

## A Modern, Strongly-Typed Language with Built-in Safety and Serialization

---

## Table of Contents

1. [Introduction](#introduction)
2. [Getting Started](#getting-started)
3. [Core Concepts](#core-concepts)
4. [Language Features](#language-features)
5. [Tutorials](#tutorials)
6. [Reference](#reference)

---

## Introduction

**Sinter** is a modern, object-oriented programming language designed with three core principles:

1. **Safety First** — Compile-time pointer cleanup validation ensures no memory leaks
2. **Serialization Built-in** — Every class automatically supports JSON/XML serialization
3. **Expressive Syntax** — Clean, readable code with powerful features like D-strings (Dynamic Strings)

### What Makes Sinter Unique?

| Feature | Description |
|---------|-------------|
| **D-Strings** | Strings that automatically update when referenced variables change |
| **Scope Blocks** | C++-style `private:`, `protected:`, `public:` blocks for clean organization |
| **Methods vs Functions** | Clear distinction between instance methods and static functions |
| **Built-in Serialization** | Every class has `.as_json()`, `.as_xml()`, and custom serializers |
| **Pointer Safety** | Compiler enforces cleanup of all allocated pointers |
| **Attribute Annotations** | Mark fields as `@attribute(read_only=true)`, `@attribute(derived=true)`, etc. |

---

## Getting Started

### Your First Sinter Program

Create a file called `hello.sinter`:

```sinter
function main() -> int {
  println(42);
  return 0;
}
```

### Compile and Run

```bash
# Generate LLVM IR
python3 compiler/main.py hello.sinter --emit-llvm -o hello.ll

# Compile to object file
llc -filetype=obj hello.ll -o hello.o

# Link to executable
clang hello.o -o hello

# Run!
./hello
```

---

## Core Concepts

### Types

Sinter is **strongly typed**. Every variable must have a declared type.

#### Primitive Types

| Type | Description | Example |
|------|-------------|---------|
| `int` | 32-bit signed integer | `42`, `-17` |
| `float` | 32-bit floating point | `3.14` |
| `double` | 64-bit floating point | `3.14159265359` |
| `boolean` | True/false value | `true`, `false` |
| `str` | String (immutable) | `"Hello, World!"` |

#### Pointer Types

Append `*` to any type to create a pointer:

```sinter
var myObject: MyClass* = MyClass.new();
```

### Variables

Use `var` for mutable variables and `const` for constants:

```sinter
var counter: int = 0;        // Mutable
const MAX_SIZE: int = 100;   // Immutable
```

### Functions vs Methods

Sinter distinguishes between **functions** (static, standalone) and **methods** (instance, class-bound):

```sinter
// Function: Standalone, operates only on parameters
function add(a: int, b: int) -> int {
  return a + b;
}

class Calculator {
  private:
    var result: int = 0
  
  public:
    // Method: Has access to instance state (no 'this' keyword needed!)
    method accumulate(value: int) -> void {
      result = result + value;  // 'result' refers to instance field
    }
}
```

**Key Insight**: Inside a method, you can directly access fields without `this.` — Sinter assumes instance context automatically.

---

## Language Features

### 1. Classes and Objects

Classes use scope blocks for clean organization:

```sinter
class Person {
  private:
    var name: str
    var age: int = 0
  
  protected:
    var internalId: int = 0
  
  public:
    method getName() -> str {
      return name;
    }
    
    method setAge(newAge: int) -> void {
      age = newAge;
    }
    
    method release() -> void {
      // Release pointer in current scope
    }
    
    method clean() -> void {
      // Free memory (destructor)
    }
}
```

### 2. Object Creation and Memory Management

Objects are always allocated on the heap using `.new()`:

```sinter
var person: Person* = Person.new();

// Use the object
person.setAge(25);

// Clean up when done (REQUIRED!)
person.clean();
```

**Important**: Sinter requires explicit cleanup. The compiler will warn if pointers aren't cleaned before scope exit.

### 3. Control Flow

#### If/Else

```sinter
if (age >= 18) {
  println(1);  // Adult
} else {
  println(0);  // Minor
}
```

#### While Loop

```sinter
var i: int = 0;
while (i < 10) {
  println(i);
  i = i + 1;
}
```

#### For Loop

```sinter
for (var i: int = 0; i < 10; i = i + 1) {
  println(i);
}
```

#### Break and Continue

```sinter
for (var i: int = 0; i < 100; i = i + 1) {
  if (i == 50) {
    break;      // Exit loop
  }
  if (i % 2 == 0) {
    continue;   // Skip even numbers
  }
  println(i);
}
```

### 4. Interfaces

Define contracts that classes must implement:

```sinter
interface Drawable {
  method draw() -> void;
  method getArea() -> double;
}
```

### 5. Attribute Annotations

Control field behavior with annotations:

```sinter
class SensorReading {
  public:
    @attribute(serializable=true)
    var temperature: double = 0.0
    
    @attribute(read_only=true)
    var sensorId: str
    
    @attribute(derived=true)
    var status: str
    
    // Derived fields have auto-generated stub methods
    method status() -> str {
      if (temperature > 100.0) {
        return "HOT";
      }
      return "NORMAL";
    }
}
```

| Annotation | Effect |
|------------|--------|
| `@attribute` | Auto-generates getter/setter |
| `@attribute(read_only=true)` | Only generates getter |
| `@attribute(write_only=true)` | Only generates setter |
| `@attribute(derived=true)` | Value computed from other fields |
| `@attribute(serializable=true)` | Included in JSON/XML output |

### 6. Built-in Serialization

Every class automatically has serialization methods:

```sinter
var config: Config* = Config.new();

// Serialize to JSON
var json: str = config.as_json();

// Serialize to XML
var xml: str = config.as_xml();

// Deserialize
var restored: Config* = Config.from_json(jsonString);
```

### 7. D-Strings (Dynamic Strings)

D-strings are a unique Sinter feature — strings that automatically update when referenced variables change:

```sinter
var count: int = 0;

// D-string - the {count} is substituted with the variable's current value
var msg: str = D"The count is: {count}";

println(msg);  // Output: "The count is: 0"

count = 5;
println(msg);  // Output: "The count is: 5" (auto-updated!)

count = 42;
println(msg);  // Output: "The count is: 42" (auto-updated again!)
```

D-strings support multiple variables:

```sinter
var x: int = 10;
var y: int = 20;
var coords: str = D"Position: ({x}, {y})";

println(coords);  // "Position: (10, 20)"

x = 100;
y = 200;
println(coords);  // "Position: (100, 200)" - both values updated!
```

**How it works**: When you access a D-string variable, Sinter checks if any referenced variables have changed since the last access. If so, it regenerates the string with the new values. This happens automatically — no manual string formatting needed!

---

## Tutorials

### Tutorial 1: Building a Counter Class

Let's build a simple counter that demonstrates classes, methods, and memory management.

```sinter
class Counter {
  private:
    var count: int = 0
    var name: str
  
  public:
    method setName(n: str) -> void {
      name = n;
    }
    
    method increment() -> void {
      count = count + 1;
    }
    
    method decrement() -> void {
      count = count - 1;
    }
    
    method getCount() -> int {
      return count;
    }
    
    method reset() -> void {
      count = 0;
    }
    
    method release() -> void {
    }
    
    method clean() -> void {
    }
}

function main() -> int {
  // Create a counter
  var counter: Counter* = Counter.new();
  
  // Use it
  counter.increment();
  counter.increment();
  counter.increment();
  
  var value: int = counter.getCount();
  println(value);  // Output: 3
  
  counter.decrement();
  value = counter.getCount();
  println(value);  // Output: 2
  
  // Clean up!
  counter.clean();
  
  return 0;
}
```

**What you learned:**
- Creating classes with private/public sections
- Defining methods that modify state
- Object creation with `.new()`
- Memory cleanup with `.clean()`

---

### Tutorial 2: Working with Loops and Functions

This tutorial demonstrates for loops, while loops, and recursive functions.

```sinter
// Calculate factorial recursively
function factorial(n: int) -> int {
  if (n <= 1) {
    return 1;
  }
  return n * factorial(n - 1);
}

// Calculate fibonacci iteratively
function fibonacci(n: int) -> int {
  if (n <= 1) {
    return n;
  }
  
  var prev: int = 0;
  var curr: int = 1;
  
  for (var i: int = 2; i <= n; i = i + 1) {
    var next: int = prev + curr;
    prev = curr;
    curr = next;
  }
  
  return curr;
}

// Sum odd numbers using continue
function sumOddNumbers(limit: int) -> int {
  var sum: int = 0;
  
  for (var i: int = 1; i <= limit; i = i + 1) {
    if (i % 2 == 0) {
      continue;  // Skip even numbers
    }
    sum = sum + i;
  }
  
  return sum;
}

// Find first divisible using break
function findFirstDivisible(limit: int, divisor: int) -> int {
  for (var i: int = 1; i <= limit; i = i + 1) {
    if (i % divisor == 0) {
      return i;  // Early return
    }
  }
  return 0;
}

function main() -> int {
  // Test factorial
  var fact5: int = factorial(5);
  println(fact5);  // Output: 120
  
  // Test fibonacci
  var fib10: int = fibonacci(10);
  println(fib10);  // Output: 55
  
  // Test sum of odd numbers 1-10
  var oddSum: int = sumOddNumbers(10);
  println(oddSum);  // Output: 25 (1+3+5+7+9)
  
  // Find first number divisible by 7
  var first7: int = findFirstDivisible(20, 7);
  println(first7);  // Output: 7
  
  return 0;
}
```

**What you learned:**
- Recursive function calls
- For loop with initialization, condition, and update
- Using `break` to exit loops early
- Using `continue` to skip iterations

---

### Tutorial 3: Building a Hospital Management System

This tutorial demonstrates a more realistic application with multiple methods and business logic.

```sinter
class Hospital {
  private:
    const numRooms: int = 100
    var numRoomsOccupied: int = 0
  
  public:
    method canAcceptMorePatients() -> boolean {
      return numRoomsOccupied < numRooms;
    }
    
    method admitPatient() -> boolean {
      if (canAcceptMorePatients()) {
        numRoomsOccupied = numRoomsOccupied + 1;
        return true;
      }
      return false;
    }
    
    method dischargePatient() -> boolean {
      if (numRoomsOccupied > 0) {
        numRoomsOccupied = numRoomsOccupied - 1;
        return true;
      }
      return false;
    }
    
    method getOccupancy() -> int {
      return numRoomsOccupied;
    }
    
    method getAvailableRooms() -> int {
      return numRooms - numRoomsOccupied;
    }
    
    method getOccupancyPercentage() -> int {
      return (numRoomsOccupied * 100) / numRooms;
    }
    
    method release() -> void {
    }
    
    method clean() -> void {
    }
}

function simulateDay(hospital: Hospital*) -> void {
  // Morning: 10 patients arrive
  for (var i: int = 0; i < 10; i = i + 1) {
    hospital.admitPatient();
  }
  
  // Afternoon: 3 patients discharged
  for (var i: int = 0; i < 3; i = i + 1) {
    hospital.dischargePatient();
  }
}

function main() -> int {
  var hospital: Hospital* = Hospital.new();
  
  println(0);  // Initial state marker
  
  // Initial occupancy
  var initial: int = hospital.getOccupancy();
  println(initial);  // Output: 0
  
  // Simulate 5 days
  for (var day: int = 1; day <= 5; day = day + 1) {
    simulateDay(hospital);
    
    var occupancy: int = hospital.getOccupancy();
    println(occupancy);
  }
  
  // Final stats
  var available: int = hospital.getAvailableRooms();
  println(available);
  
  var percentage: int = hospital.getOccupancyPercentage();
  println(percentage);
  
  // Cleanup
  hospital.clean();
  
  return 0;
}
```

**What you learned:**
- Using `const` for immutable fields
- Business logic in methods
- Passing object pointers to functions
- Simulating real-world scenarios

---

### Tutorial 4: Geometric Shapes with Interfaces

This tutorial shows how to define interfaces and create polymorphic behavior.

```sinter
interface Shape {
  method getArea() -> int;
  method getPerimeter() -> int;
}

class Rectangle {
  private:
    var width: int = 10
    var height: int = 5
  
  public:
    method setSize(w: int, h: int) -> void {
      width = w;
      height = h;
    }
    
    method getArea() -> int {
      return width * height;
    }
    
    method getPerimeter() -> int {
      return (width + height) * 2;
    }
    
    method getWidth() -> int {
      return width;
    }
    
    method getHeight() -> int {
      return height;
    }
    
    method release() -> void {
    }
    
    method clean() -> void {
    }
}

class Square {
  private:
    var side: int = 10
  
  public:
    method setSide(s: int) -> void {
      side = s;
    }
    
    method getArea() -> int {
      return side * side;
    }
    
    method getPerimeter() -> int {
      return side * 4;
    }
    
    method release() -> void {
    }
    
    method clean() -> void {
    }
}

function main() -> int {
  // Create shapes
  var rect: Rectangle* = Rectangle.new();
  var square: Square* = Square.new();
  
  // Configure
  rect.setSize(8, 6);
  square.setSide(5);
  
  // Calculate areas
  var rectArea: int = rect.getArea();
  var squareArea: int = square.getArea();
  
  println(rectArea);   // Output: 48
  println(squareArea); // Output: 25
  
  // Calculate perimeters
  var rectPerim: int = rect.getPerimeter();
  var squarePerim: int = square.getPerimeter();
  
  println(rectPerim);   // Output: 28
  println(squarePerim); // Output: 20
  
  // Cleanup
  rect.clean();
  square.clean();
  
  return 0;
}
```

**What you learned:**
- Defining interfaces with method signatures
- Creating classes that implement interfaces
- Working with multiple object types

---

## Reference

### Keywords

| Keyword | Usage |
|---------|-------|
| `class` | Define a class |
| `interface` | Define an interface |
| `function` | Define a standalone function |
| `method` | Define an instance method |
| `var` | Declare a mutable variable |
| `const` | Declare an immutable constant |
| `if`, `else` | Conditional execution |
| `while` | While loop |
| `for` | For loop |
| `break` | Exit current loop |
| `continue` | Skip to next iteration |
| `return` | Return from function/method |
| `true`, `false` | Boolean literals |
| `null` | Null pointer |
| `private`, `protected`, `public` | Visibility modifiers |
| `extends` | Inherit from a class |
| `implements` | Implement an interface |
| `println`, `print` | Output to console |

### Operators

| Category | Operators |
|----------|-----------|
| Arithmetic | `+`, `-`, `*`, `/`, `%` |
| Comparison | `==`, `!=`, `<`, `>`, `<=`, `>=` |
| Logical | `&&`, `||`, `!` |
| Assignment | `=` |
| Member Access | `.` |
| Pointer | `*` (dereference), `&` (address-of) |

### Built-in Methods (All Classes)

| Method | Description |
|--------|-------------|
| `.new()` | Constructor, allocates and initializes |
| `.release()` | Release pointer in current scope |
| `.clean()` | Free memory (destructor) |
| `.as_json()` | Serialize to JSON string |
| `.as_xml()` | Serialize to XML string |
| `.from_json(str)` | Deserialize from JSON |
| `.from_xml(str)` | Deserialize from XML |

---

## Appendix: Complete Grammar (Simplified)

```ebnf
program        = (class_decl | function_decl | interface_decl)* ;

class_decl     = "class" IDENTIFIER type_params? extends? implements? "{" scope_block* "}" ;
scope_block    = ("private" | "protected" | "public") ":" member* ;
member         = field_decl | method_decl | function_decl ;

interface_decl = "interface" IDENTIFIER "{" method_sig* "}" ;
method_sig     = "method" IDENTIFIER "(" params? ")" "->" type ";" ;

function_decl  = "function" IDENTIFIER "(" params? ")" "->" type block ;
method_decl    = "method" IDENTIFIER "(" params? ")" "->" type block ;

field_decl     = annotation? ("var" | "const") IDENTIFIER ":" type ("=" expr)? ;
annotation     = "@attribute" ("(" attr_args ")")? ;

type           = primitive_type | IDENTIFIER type_args? | type "*" ;
primitive_type = "int" | "float" | "double" | "boolean" | "str" | "void" ;

statement      = var_decl | if_stmt | while_stmt | for_stmt | return_stmt 
               | break_stmt | continue_stmt | print_stmt | expr_stmt ;

expr           = assignment | logical_or ;
logical_or     = logical_and ("||" logical_and)* ;
logical_and    = equality ("&&" equality)* ;
equality       = comparison (("==" | "!=") comparison)* ;
comparison     = term (("<" | ">" | "<=" | ">=") term)* ;
term           = factor (("+" | "-") factor)* ;
factor         = unary (("*" | "/" | "%") unary)* ;
unary          = ("!" | "-" | "*" | "&") unary | postfix ;
postfix        = primary ("." IDENTIFIER | "(" args? ")" | "[" expr "]")* ;
primary        = INTEGER | FLOAT | STRING | "true" | "false" | "null" 
               | IDENTIFIER | "(" expr ")" | "[" expr_list? "]" ;
```

---

## Getting Help

- **Issues**: Report bugs on the project repository
- **Examples**: See the `/examples` directory for working code
- **Tests**: Run `python3 test_compiler.py` to verify your installation

---

*Sinter — Write Safe, Ship Fast*
