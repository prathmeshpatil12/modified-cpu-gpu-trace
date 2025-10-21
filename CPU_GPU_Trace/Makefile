CC := g++
CFLAGS := -g -O2 -Wall -Wextra -fPIC
CUDA_PATH := /usr/local/cuda-12.8
INCLUDES := -I$(CUDA_PATH)/include -I/usr/include
LIBS := -L$(CUDA_PATH)/lib64 -lcuda -lcudart -lcupti -ldl -lstdc++

dw-pid: dw-pid.c
	$(CC) $(CFLAGS) $(INCLUDES) dw-pid.c -o dw-pid -ldw -lelf -lczmq -lnvidia-ml $(LIBS)

simple: simple_file.c
	$(CC) $(CFLAGS) $(INCLUDES) simple_file.c -o simple $(LIBS)

libdwcupti.so: cupti_inject.cpp
	$(CC) $(CFLAGS) $(INCLUDES) -shared cupti_inject.cpp -o libdwcupti.so $(LIBS)

clean:
	rm -f dw-pid simple libdwcupti.so

debug:
	@echo "INCLUDES: $(INCLUDES)"; echo "LIBS: $(LIBS)"