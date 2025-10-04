CC = g++
CFLAGS = -Wall -Wextra -g -I/usr/local/cuda/include 
LDFLAGS = -L/usr/local/cuda/lib64  -lczmq -ldw -lelf -lnvidia-ml -lcupti

dw-pid: dw-pid.c
	$(CC) $(CFLAGS) -o dw-pid dw-pid.c $(LDFLAGS)

dw: dw.c
	$(CC) $(CFLAGS) -o dw dw.c $(LDFLAGS)

clean:
	rm -f dw-pid dw

.PHONY: clean
