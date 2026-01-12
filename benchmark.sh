#!/bin/bash
# Sinter vs C++ Benchmark Script

set -e

LLVM_BIN="/opt/homebrew/Cellar/llvm/21.1.8/bin"
SINTER_DIR="/Users/avrukin/sinter_lang"

echo "========================================"
echo "Sinter vs C++ Benchmark"
echo "========================================"
echo ""

# Function to compile Sinter
compile_sinter() {
    local src=$1
    local name=$(basename "$src" .sinter)
    echo "Compiling Sinter: $name.sinter"
    
    cd "$SINTER_DIR"
    python3 compiler/main.py "examples/${name}.sinter" --emit-llvm -o "examples/${name}.ll"
    "$LLVM_BIN/llc" -O3 -filetype=obj "examples/${name}.ll" -o "examples/${name}_sinter.o"
    clang -O3 "examples/${name}_sinter.o" -o "examples/${name}_sinter"
    echo "  -> examples/${name}_sinter"
}

# Function to compile C++
compile_cpp() {
    local src=$1
    local name=$(basename "$src" .cpp)
    echo "Compiling C++: $name.cpp"
    
    clang++ -O3 "$src" -o "examples/${name}_cpp"
    echo "  -> examples/${name}_cpp"
}

# Function to run benchmark
run_benchmark() {
    local name=$1
    local iterations=${2:-1}
    
    echo ""
    echo "--- Benchmark: $name ---"
    
    # Run Sinter version
    echo "Sinter:"
    time -p ./examples/${name}_sinter 2>&1 | head -3
    
    echo ""
    
    # Run C++ version  
    echo "C++:"
    time -p ./examples/${name}_cpp 2>&1 | head -3
}

# Compile all benchmarks
echo "=== Compiling Benchmarks ==="
echo ""

compile_sinter "examples/fibonacci.sinter"
compile_cpp "examples/fibonacci.cpp"

compile_sinter "examples/counter.sinter"
compile_cpp "examples/counter.cpp"

# Run benchmarks
echo ""
echo "=== Running Benchmarks ==="

run_benchmark "fibonacci"
run_benchmark "counter"

echo ""
echo "========================================"
echo "Benchmark Complete"
echo "========================================"
