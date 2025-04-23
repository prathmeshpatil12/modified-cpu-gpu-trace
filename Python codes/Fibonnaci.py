import random
import time

def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

def main():
    for _ in range(100):
        n = random.randint(20, 30)
        # n = 10
        fibonacci(n)
        time.sleep(0.05)
    print('Done')

if __name__ == "__main__":
    main()
