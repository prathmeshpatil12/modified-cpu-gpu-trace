#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <linux/perf_event.h>
#include <linux/hw_breakpoint.h>
#include <sys/syscall.h>
#include <sys/mman.h>
#include <sys/ioctl.h>
#include <unistd.h>
#include <errno.h>
#include <elfutils/libdwfl.h>
#include <elfutils/libdw.h>
#include <libelf.h>
#include <assert.h>

#define PAGE_SIZE 4096

// libdw initialization
static Dwfl_Callbacks callbacks = {
    .find_elf = dwfl_linux_proc_find_elf,
    .find_debuginfo = dwfl_standard_find_debuginfo
};

Dwfl *init_dwfl(pid_t pid) {
    Dwfl *dwfl = dwfl_begin(&callbacks);
    if (!dwfl) {
        fprintf(stderr, "dwfl_begin error: %s\n", dwfl_errmsg(-1));
        exit(EXIT_FAILURE);
    }

    if (dwfl_linux_proc_report(dwfl, pid)) {
        fprintf(stderr, "dwfl_linux_proc_report error: %s\n", dwfl_errmsg(-1));
        dwfl_end(dwfl);
        exit(EXIT_FAILURE);
    }

    if (dwfl_report_end(dwfl, NULL, NULL) != 0) {
        fprintf(stderr, "dwfl_report_end error: %s\n", dwfl_errmsg(-1));
        dwfl_end(dwfl);
        exit(EXIT_FAILURE);
    }

    return dwfl;
}


typedef unsigned long u64;

struct read_format {
    u64 value;
    u64 time_enabled;
    u64 time_running;
    u64 id;
    u64 lost;
};

struct sample {
    struct perf_event_header header;
    u64 nr;
    u64 ips[];
};

void print_mmap_page(struct perf_event_mmap_page *header) {
    printf("struct perf_event_mmap_page\n");
    printf("\tversion: %u\n", header->version);
    printf("\tcompat_version: %u\n", header->compat_version);
    printf("\tlock: %u\n", header->lock);

    printf("\tindex: %u\n", header->index);
    printf("\toffset: %lli\n", header->offset);
    printf("\ttime_enabled: %llu\n", header->time_enabled);
    printf("\ttime_running: %llu\n", header->time_running);
    printf("\tcapabilities: %llu\n", header->capabilities);

    printf("\tpmc_width: %hu\n", header->pmc_width);
    printf("\ttime_shift: %hu\n", header->time_shift);
    printf("\ttime_mult: %u\n", header->time_mult);
    printf("\ttime_offset: %llu\n", header->time_offset);

    printf("\tdata_head: %llu\n", header->data_head);
    printf("\tdata_tail: %llu\n", header->data_tail);
    printf("\tdata_offset: %llu\n", header->data_offset);
    printf("\tdata_size: %llu\n", header->data_size);

    printf("\taux_head: %llu\n", header->aux_head);
    printf("\taux_tail: %llu\n", header->aux_tail);
    printf("\taux_offset: %llu\n", header->aux_offset);
    printf("\taux_size: %llu\n", header->aux_size);

    printf("\n");
}

void print_header(struct perf_event_header *header) {
    printf("struct perf_event_header\n");
    printf("\ttype: %u\n", header->type);
    printf("\tmisc: %hu\n", header->misc);
    printf("\tsize: %hu\n", header->size);

    printf("\n");
}

void print_sample(struct sample *sample, Dwfl *dwfl) {
    print_header(&sample->header);
    printf("struct sample\n");
    printf("\tnr: %lu\n", sample->nr);
    for (u64 i = 0; i < sample->nr; i++) {
        uintptr_t ip = sample->ips[i]; // get ip
        Dwfl_Module *mod = dwfl_addrmodule(dwfl, ip); // get module of this ip
        const char *symbol = NULL; // instantiate symbol
        if (mod) symbol = dwfl_module_addrname(mod, ip);
        printf("\t\tips[%lu]: 0x%lx %s\n", i, ip, symbol ? symbol : "unknown");
    }
    printf("\n\n");
}

struct strbuffer {
    char *buffer;
    size_t buffsize;
    size_t currsize;
};

struct strbuffer *strnew(size_t size)
{
    if (size == 0)
        return NULL;

    struct strbuffer *strbuffer = malloc(sizeof(struct strbuffer));
    if (!strbuffer)
        return NULL;

    strbuffer->buffer = malloc(size);
    if (!strbuffer->buffer) {
        free(strbuffer);
        return NULL;
    }

    strbuffer->buffsize = size;
    strbuffer->currsize = 0;

    return strbuffer;
}

void strapp(struct strbuffer *strbuffer, const char *to_append)
{
    size_t append_len = strlen(to_append);

    size_t new_size = strbuffer->buffsize;
    while (new_size <= strbuffer->currsize + append_len)
        new_size *= 2;

    // Resize if needed
    if (new_size > strbuffer->buffsize) {
        char *new_buff = realloc(strbuffer->buffer, new_size);
        if (!new_buff)
            return; // for error checking, verify strbuffer->currsize changed

        strbuffer->buffer = new_buff;
        strbuffer->buffsize = new_size;
    }

    strncpy(strbuffer->buffer + strbuffer->currsize, to_append, append_len+1);
    strbuffer->currsize += append_len;
}

char *strfreewrap(struct strbuffer *strbuffer)
{
    char *buffer = strbuffer->buffer;
    free(strbuffer);
    return buffer;
}

void append_symbols_from_sample(struct strbuffer *callchains, struct sample *sample, Dwfl *dwfl)
{
    if (sample->nr > 100) {
        fprintf(stderr, "ERROR: sample at loc %p reported nr %lu\n", (void*)sample, sample->nr);
        return;
    }

    // Create a stack buffer of size = 19[2(0x) + 16(length of hex string) + 1(;) + 1(\0)]
    char ip_buffer[20];

    // Perform symbolization
    if (dwfl) {
        for (uint64_t i = 0; i < sample->nr; i++) {
            Dwfl_Module *mod = dwfl_addrmodule(dwfl, sample->ips[i]);
            const char *symbol = NULL;
            if (mod)
                symbol = dwfl_module_addrname(mod, sample->ips[i]);
            if (symbol) {
                strapp(callchains, symbol);
                strapp(callchains, ";");
            } else {
                snprintf(ip_buffer, sizeof(ip_buffer), "0x%lx;", sample->ips[i]);
                strapp(callchains, ip_buffer);
            }
        }
    } else {
        for (uint64_t i = 0; i < sample->nr; i++) {
            snprintf(ip_buffer, sizeof(ip_buffer), "0x%lx;", sample->ips[i]);
            strapp(callchains, ip_buffer);
        }
    }
    strapp(callchains, "|");
}

char *get_callchains(struct perf_event_mmap_page *buffer, Dwfl *dwfl)
{
    uint64_t head = buffer->data_head;
    __sync_synchronize();

    // Check if there's a new sample to be read
    if (head == buffer->data_tail)
        return NULL;

    // Create helpers
    void *buffer_start = (void*)buffer + buffer->data_offset;
    struct strbuffer *callchains = strnew(1024);
    if (!callchains) {
        fprintf(stderr, "ERROR: Memory allocation failed in perf.c:get_callchains\n");
        return NULL;
    }
    
    // Get pointers to struct samples.
    struct perf_event_header header;
    while (buffer->data_tail < head) {
        // Get relative offset
        uint64_t relative_loc = buffer->data_tail % buffer->data_size; // Number of bytes into buffer we are.
        size_t bytes_remaining = buffer->data_size - relative_loc; // How many bytes till we hit the buffer wrap.
        size_t header_bytes_remaining = bytes_remaining > sizeof(struct perf_event_header) ? sizeof(struct perf_event_header) : bytes_remaining;

        // Copy header to our stack
        memcpy(&header, buffer_start + relative_loc, header_bytes_remaining); // Copy part at end of buffer.
        memcpy((void*)&header + header_bytes_remaining, buffer_start, sizeof(struct perf_event_header) - header_bytes_remaining); // Copy part at start of buffer.

        // Find struct sample location
        struct sample *sample = buffer_start + relative_loc;
        int used_malloc = 0;
        if (bytes_remaining < header.size) {
            sample = malloc(header.size);
            used_malloc = 1;
            memcpy(sample, buffer_start + relative_loc, bytes_remaining);
            memcpy((void*)sample + bytes_remaining, buffer_start, header.size - bytes_remaining);
        }

        // Do symbolization
        append_symbols_from_sample(callchains, sample, dwfl);

        if (used_malloc)
            free(sample);

        buffer->data_tail += header.size;
    }

    // __sync_synchronize();
    
    return strfreewrap(callchains);
}

int main(int argc, char** argv) {
    unsigned int samp_freq = 1000;
    unsigned int report_sleep = 1000000;

    if (argc < 2) {
        fprintf(stderr, "Usage: %s <path-to-program>\n", *argv);
        exit(EXIT_FAILURE);
    }

    // Fork
    char *exe_path = argv[1];
    pid_t pid = fork();
    if (pid == -1) {
        perror("fork");
        exit(EXIT_FAILURE);
    }
    if (pid == 0) {
        // Child process - start the specified executable
        if (strstr(exe_path, ".py"))
            execlp("python3", "python3", exe_path, (char*)NULL);
        else
            execlp(exe_path, exe_path, (char*)NULL);
        perror("execlp");
        exit(EXIT_FAILURE);
    }

    // Parent process - monitor the given pid
    sleep(1);
    fprintf(stderr, "Got child pid %i\n", pid);

    // Create struct perf_event_attr
    struct perf_event_attr attr = {0};
    // Fields
    attr.size = sizeof(struct perf_event_attr);
    attr.type = PERF_TYPE_HARDWARE;
    attr.config = PERF_COUNT_HW_INSTRUCTIONS;
    attr.sample_type = PERF_SAMPLE_CALLCHAIN;
    attr.sample_freq = samp_freq;
    // Flags
    attr.mmap = 1;
    attr.freq = 1;
    attr.ksymbol = 0;
    // Require an enable call to start recording
    attr.disabled = 1;

    // Invoke the perf recorder
    int fd = syscall(SYS_perf_event_open, &attr, pid, -1, -1, 0);
    if (fd == -1) {
        perror("perf_event_open");
        exit(EXIT_FAILURE);
    }

    // Set up memory map to collect results
    void *buffer = mmap(NULL, 2*PAGE_SIZE, PROT_READ|PROT_WRITE, MAP_SHARED, fd, 0);
    if (buffer == MAP_FAILED) {
        perror("mmap");
        close(fd);
        exit(EXIT_FAILURE);
    }

    // Enable sampling
    ioctl(fd, PERF_EVENT_IOC_RESET, 0);
    ioctl(fd, PERF_EVENT_IOC_ENABLE, 0);

    // Save a pointer to the info struct
    struct perf_event_mmap_page *buffer_info = buffer;

    // Init dwfl
    Dwfl *dwfl = init_dwfl(pid);

    // Continuously read samples and print using print_sample()
    while (1) {
        print_mmap_page(buffer_info);
        char *callchains = get_callchains(buffer_info, dwfl);
        if (callchains)
            fprintf(stdout, "%s\n", callchains);
        free(callchains);
        usleep(report_sleep);
    }

    dwfl_end(dwfl);
}

// For reading standard metrics (reported from fd)
/*
// Set up buffer to read results
struct read_format results[100] = {0};
// Read 1 result into buffer for testing
read(fd, results, sizeof(struct read_format));
printf("Value: %lu\nTime Enabled:%lu\nTime Running: %lu\nID:%lu\n",
results[0].value, results[0].time_enabled, results[0].time_running, results[0].id);
*/

