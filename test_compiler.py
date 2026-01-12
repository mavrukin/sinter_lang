#!/usr/bin/env python3
"""
Test script to demonstrate Sinter compiler capabilities
"""

import sys
sys.path.insert(0, '/Users/avrukin/sinter_lang')

from compiler.lexer.lexer import Lexer
from compiler.parser.parser import Parser
from compiler.semantic.analyzer import SemanticAnalyzer, SemanticError
from compiler.codegen.codegen import CodeGenerator

# Test program in Sinter
sinter_code = """
class Hospital {
  private:
    const numRooms: int = 100
    var numRoomsOccupied: int = 35

  public:
    method canAcceptMorePatients() -> boolean { 
      return numRoomsOccupied < numRooms;
    }
    
    method admitPatient() -> void {
      numRoomsOccupied = numRoomsOccupied + 1;
    }
    
    method getOccupancy() -> int {
      return numRoomsOccupied;
    }
}

function main() -> int {
  var hospital: Hospital* = Hospital.new();
  if (hospital.canAcceptMorePatients()) {
    hospital.admitPatient();
  }
  return 0;
}
"""

print("=" * 70)
print("SINTER COMPILER - Full Pipeline Test")
print("=" * 70)

# Lexer test
print("\n[1] LEXER")
print("-" * 50)
lexer = Lexer(sinter_code)
tokens = lexer.tokenize()
print(f"  ✓ Tokenized {len(tokens)} tokens")

# Parser test
print("\n[2] PARSER")
print("-" * 50)
lexer = Lexer(sinter_code)
tokens = lexer.tokenize()
parser = Parser(tokens)
try:
    ast = parser.parse()
    print(f"  ✓ Parsed {len(ast.declarations)} declarations:")
    for decl in ast.declarations:
        print(f"    - {decl}")
except Exception as e:
    print(f"  ✗ Parse error: {e}")
    sys.exit(1)

# Semantic analysis
print("\n[3] SEMANTIC ANALYSIS")
print("-" * 50)
try:
    analyzer = SemanticAnalyzer()
    type_registry, symbol_table = analyzer.analyze(ast)
    print(f"  ✓ Type checking passed")
    print(f"  ✓ Registered {len(type_registry.types)} types")
    if analyzer.warnings:
        for w in analyzer.warnings:
            print(f"  ⚠ {w}")
except SemanticError as e:
    print(f"  ✗ Semantic error:\n{e}")
    sys.exit(1)

# Code generation
print("\n[4] CODE GENERATION")
print("-" * 50)
try:
    codegen = CodeGenerator(type_registry, symbol_table)
    llvm_ir = codegen.generate(ast)
    lines = llvm_ir.split('\n')
    print(f"  ✓ Generated {len(lines)} lines of LLVM IR")
except Exception as e:
    print(f"  ✗ Code generation error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Write output
output_file = "/Users/avrukin/sinter_lang/examples/hospital.ll"
with open(output_file, "w") as f:
    f.write(llvm_ir)
print(f"  ✓ Written to {output_file}")

# Show generated LLVM IR
print("\n[5] GENERATED LLVM IR (first 80 lines)")
print("-" * 50)
for i, line in enumerate(lines[:80]):
    print(f"  {line}")
if len(lines) > 80:
    print(f"  ... ({len(lines) - 80} more lines)")

print("\n" + "=" * 70)
print("COMPILATION SUCCESSFUL")
print("=" * 70)
print("\nTo compile to native code:")
print(f"  llc -filetype=obj {output_file} -o examples/hospital.o")
print(f"  clang examples/hospital.o -o examples/hospital")
print("\nOr use the compiler directly:")
print(f"  python3 compiler/main.py examples/hospital.sinter")
