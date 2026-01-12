#!/usr/bin/env python3
"""
Sinter Compiler - Main Entry Point
Compiles Sinter source code to native code via LLVM
"""

import argparse
import sys
import subprocess
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from compiler.lexer.lexer import Lexer
from compiler.parser.parser import Parser
from compiler.semantic.analyzer import SemanticAnalyzer, SemanticError, PointerCleanupError
from compiler.semantic.pointer_validator import PointerValidator
from compiler.codegen.codegen import CodeGenerator


def main():
    parser = argparse.ArgumentParser(
        description="Sinter Programming Language Compiler"
    )
    parser.add_argument(
        "source_file",
        type=str,
        help="Path to Sinter source file (.sinter)"
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="Output file path (default: input filename with appropriate extension)"
    )
    parser.add_argument(
        "--emit-llvm",
        action="store_true",
        help="Emit LLVM IR (.ll) instead of native object file"
    )
    parser.add_argument(
        "--emit-asm",
        action="store_true",
        help="Emit assembly (.s) instead of native object file"
    )
    parser.add_argument(
        "--compile-only", "-c",
        action="store_true",
        help="Compile to object file, don't link"
    )
    parser.add_argument(
        "--ast",
        action="store_true",
        help="Print AST and exit"
    )
    parser.add_argument(
        "--tokens",
        action="store_true",
        help="Print tokens and exit"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output"
    )

    args = parser.parse_args()

    source_path = Path(args.source_file)
    if not source_path.exists():
        print(f"Error: Source file '{args.source_file}' not found", file=sys.stderr)
        sys.exit(1)

    # Read source file
    with open(source_path, "r") as f:
        source_code = f.read()

    try:
        # === LEXICAL ANALYSIS ===
        if args.verbose:
            print("==> Lexical analysis...")
        
        lexer = Lexer(source_code)
        tokens = lexer.tokenize()

        if args.tokens:
            print("=== TOKENS ===")
            for token in tokens:
                print(f"  {token}")
            return 0

        # === PARSING ===
        if args.verbose:
            print("==> Parsing...")
        
        parser_obj = Parser(tokens)
        ast = parser_obj.parse()

        if args.ast:
            print("=== AST ===")
            print_ast(ast)
            return 0

        # === SEMANTIC ANALYSIS ===
        if args.verbose:
            print("==> Semantic analysis...")
        
        analyzer = SemanticAnalyzer()
        type_registry, symbol_table = analyzer.analyze(ast)
        
        if analyzer.warnings:
            for warning in analyzer.warnings:
                print(f"Warning: {warning}", file=sys.stderr)
        
        # === POINTER CLEANUP VALIDATION ===
        if args.verbose:
            print("==> Pointer cleanup validation...")
        
        pointer_validator = PointerValidator()
        ptr_errors, ptr_warnings = pointer_validator.validate(ast)
        
        for warning in ptr_warnings:
            print(f"Warning: {warning}", file=sys.stderr)
        
        if ptr_errors:
            for error in ptr_errors:
                print(f"Error: {error}", file=sys.stderr)
            raise PointerCleanupError("Pointer cleanup validation failed")

        # === CODE GENERATION ===
        if args.verbose:
            print("==> Code generation...")
        
        codegen = CodeGenerator(type_registry, symbol_table)
        llvm_ir = codegen.generate(ast)

        # === OUTPUT ===
        if args.emit_llvm:
            # Output LLVM IR
            if args.output:
                output_path = Path(args.output)
            else:
                output_path = source_path.with_suffix(".ll")
            
            with open(output_path, "w") as f:
                f.write(llvm_ir)
            
            print(f"LLVM IR written to: {output_path}")
            return 0

        # Write LLVM IR to temp file
        ll_path = source_path.with_suffix(".ll")
        with open(ll_path, "w") as f:
            f.write(llvm_ir)

        if args.emit_asm:
            # Compile to assembly
            if args.output:
                output_path = Path(args.output)
            else:
                output_path = source_path.with_suffix(".s")
            
            result = subprocess.run(
                ["llc", str(ll_path), "-o", str(output_path)],
                capture_output=True, text=True
            )
            if result.returncode != 0:
                print(f"Error compiling to assembly: {result.stderr}", file=sys.stderr)
                sys.exit(1)
            
            print(f"Assembly written to: {output_path}")
            return 0

        # Compile to object file
        obj_path = source_path.with_suffix(".o")
        result = subprocess.run(
            ["llc", "-filetype=obj", str(ll_path), "-o", str(obj_path)],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"Error compiling to object: {result.stderr}", file=sys.stderr)
            sys.exit(1)

        if args.compile_only:
            print(f"Object file written to: {obj_path}")
            return 0

        # Link to executable
        if args.output:
            output_path = Path(args.output)
        else:
            output_path = source_path.with_suffix("")
        
        result = subprocess.run(
            ["clang", str(obj_path), "-o", str(output_path)],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"Error linking: {result.stderr}", file=sys.stderr)
            sys.exit(1)

        print(f"Executable written to: {output_path}")
        return 0

    except SyntaxError as e:
        print(f"Syntax error: {e}", file=sys.stderr)
        sys.exit(1)
    except SemanticError as e:
        print(f"Semantic error:\n{e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


def print_ast(node, indent=0):
    """Pretty print the AST"""
    from compiler.sinter_ast.nodes import (
        Program, ClassDeclaration, MethodDeclaration, FunctionDeclaration,
        FieldDeclaration, Block, Statement, Expression
    )
    
    prefix = "  " * indent
    
    if isinstance(node, Program):
        print(f"{prefix}Program:")
        for decl in node.declarations:
            print_ast(decl, indent + 1)
    
    elif isinstance(node, ClassDeclaration):
        params = f"<{', '.join(node.type_parameters)}>" if node.type_parameters else ""
        extends = f" extends {node.extends}" if node.extends else ""
        impl = f" implements {', '.join(node.implements)}" if node.implements else ""
        print(f"{prefix}Class {node.name}{params}{extends}{impl}:")
        for member in node.members:
            print_ast(member, indent + 1)
    
    elif isinstance(node, FieldDeclaration):
        const = "const " if node.is_const else "var "
        print(f"{prefix}{const}{node.name}: {node.type_name}")
    
    elif isinstance(node, (MethodDeclaration, FunctionDeclaration)):
        kind = "function" if (isinstance(node, FunctionDeclaration) or 
                            (isinstance(node, MethodDeclaration) and node.is_static)) else "method"
        params = ", ".join(f"{p.name}: {p.type_name}" for p in node.parameters)
        print(f"{prefix}{kind} {node.name}({params}) -> {node.return_type}")
        if node.body:
            print_ast(node.body, indent + 1)
    
    elif isinstance(node, Block):
        print(f"{prefix}Block:")
        for stmt in node.statements:
            print_ast(stmt, indent + 1)
    
    else:
        print(f"{prefix}{node}")


if __name__ == "__main__":
    sys.exit(main())
