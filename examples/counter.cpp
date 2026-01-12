// Counter benchmark in C++ - loop performance test
#include <iostream>

class Counter {
private:
    int count = 0;
    int limit = 0;

public:
    void setLimit(int value) {
        limit = value;
    }
    
    int run() {
        for (int i = 0; i < limit; i++) {
            count++;
        }
        return count;
    }
    
    int getCount() const {
        return count;
    }
};

int main() {
    Counter* counter = new Counter();
    counter->setLimit(100000000);
    int result = counter->run();
    delete counter;
    return 0;
}
