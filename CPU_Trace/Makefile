CC = gcc
CFLAGS = -Wall -Wextra -g
LDFLAGS = -lczmq -ldw -lelf

dw-pid: dw-pid.c
	$(CC) $(CFLAGS) -o dw-pid dw-pid.c $(LDFLAGS)

dw: dw.c
	$(CC) $(CFLAGS) -o dw dw.c $(LDFLAGS)

clean:
	rm -f dw

.PHONY: clean
