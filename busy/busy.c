#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

void f21() {
    int n = 0;
    while (n < 10) {/* Busy wait */
        n++;
        sleep(1); // Wait for 1 second
    }
    printf("Hello\n"); // Print "Hello"
}

void f20() {
    int n = 0;
    while (n < 10) {/* Busy wait */
        n++;
        sleep(1); // Wait for 1 second
    }
    printf("Hello\n"); // Print "Hello"
    f21();
}

void f19() { f20(); }
void f18() { f19(); }
void f17() { f18(); }
void f16() { f17(); }
void f15() { f16(); }
void f14() { f15(); }
void f13() { f14(); }
void f12() { f13(); }
void f11() { f12(); }
void f10() { f11(); }
void f9() { f10(); }
void f8() { f9(); }
void f7() { f8(); }
void f6() { f7(); }
void f5() { f6(); }
void f4() { f5(); }
void f3() { f4(); }
void f2() { f3(); }
void f1() { f2(); }

int main() {
    f1();
    return 0;
}
