// Fibonacci benchmark in C++
#include <iostream>

class Fibonacci {
private:
    int n = 0;
    int result = 0;

public:
    void setN(int value) {
        n = value;
    }
    
    int calculate() {
        if (n < 2) {
            result = n;
            return n;
        }
        
        int a = 0;
        int b = 1;
        
        for (int i = 2; i <= n; i++) {
            int temp = a + b;
            a = b;
            b = temp;
        }
        
        result = b;
        return b;
    }
    
    int getResult() const {
        return result;
    }
};

int main() {
    Fibonacci* fib = new Fibonacci();
    fib->setN(40);
    int result = fib->calculate();
    delete fib;
    return 0;
}
