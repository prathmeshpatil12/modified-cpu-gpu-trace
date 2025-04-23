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
#include <signal.h> // Needed for kill()
#include <assert.h>
#include <czmq.h> // Include czmq's zclock functions
#include <nvml.h>
#include <time.h>

#define PAGE_SIZE 4096

// libdw initialization
static Dwfl_Callbacks callbacks = {
    .find_elf = dwfl_linux_proc_find_elf,
    .find_debuginfo = dwfl_standard_find_debuginfo
};

Dwfl* init_dwfl(pid_t pid) {
    Dwfl* dwfl = dwfl_begin(&callbacks);
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

void print_mmap_page(struct perf_event_mmap_page* header) {
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

void print_header(struct perf_event_header* header) {
    printf("struct perf_event_header\n");
    printf("\ttype: %u\n", header->type);
    printf("\tmisc: %hu\n", header->misc);
    printf("\tsize: %hu\n", header->size);

    printf("\n");
}

void print_sample(struct sample* sample, Dwfl* dwfl) {
    print_header(&sample->header);
    printf("struct sample\n");
    printf("\tnr: %lu\n", sample->nr);
    for (u64 i = 0; i < sample->nr; i++) {
        uintptr_t ip = sample->ips[i]; // get ip
        Dwfl_Module* mod = dwfl_addrmodule(dwfl, ip); // get module of this ip
        const char* symbol = NULL; // instantiate symbol
        if (mod) symbol = dwfl_module_addrname(mod, ip);
        printf("\t\tips[%lu]: 0x%lx %s\n", i, ip, symbol ? symbol : "unknown");
    }
    printf("\n\n");
}

struct strbuffer {
    char* buffer;
    size_t buffsize;
    size_t currsize;
};

struct strbuffer* strnew(size_t size)
{
    if (size == 0)
        return NULL;

    struct strbuffer* strbuffer = malloc(sizeof(struct strbuffer));
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

void strapp(struct strbuffer* strbuffer, const char* to_append)
{
    size_t append_len = strlen(to_append);

    size_t new_size = strbuffer->buffsize;
    while (new_size <= strbuffer->currsize + append_len)
        new_size *= 2;

    // Resize if needed
    if (new_size > strbuffer->buffsize) {
        char* new_buff = realloc(strbuffer->buffer, new_size);
        if (!new_buff)
            return; // for error checking, verify strbuffer->currsize changed

        strbuffer->buffer = new_buff;
        strbuffer->buffsize = new_size;
    }

    strncpy(strbuffer->buffer + strbuffer->currsize, to_append, append_len + 1);
    strbuffer->currsize += append_len;
}

char* strfreewrap(struct strbuffer* strbuffer)
{
    char* buffer = strbuffer->buffer;
    free(strbuffer);
    return buffer;
}

void append_symbols_from_sample(struct strbuffer* callchains, struct sample* sample, Dwfl* dwfl)
{
    if (sample->nr > 100) {
        fprintf(stderr, "ERROR: sample at loc %p reported nr %lu\n", (void*)sample, sample->nr);
        return;
    }

    // Create a stack buffer of size = 20 bytes per ip.
    char ip_buffer[20];

    if (dwfl) {
        for (uint64_t i = 0; i < sample->nr; i++) {
            Dwfl_Module* mod = dwfl_addrmodule(dwfl, sample->ips[i]);
            const char* symbol = NULL;
            if (mod)
                symbol = dwfl_module_addrname(mod, sample->ips[i]);
            if (symbol) {
                strapp(callchains, symbol);
                strapp(callchains, ";");
            }
            else {
                snprintf(ip_buffer, sizeof(ip_buffer), "0x%lx;", sample->ips[i]);
                strapp(callchains, ip_buffer);
            }
        }
    }
    else {
        for (uint64_t i = 0; i < sample->nr; i++) {
            snprintf(ip_buffer, sizeof(ip_buffer), "0x%lx;", sample->ips[i]);
            strapp(callchains, ip_buffer);
        }
    }
    strapp(callchains, "|");
}

char* get_callchains(struct perf_event_mmap_page* buffer, Dwfl* dwfl)
{
    uint64_t head = buffer->data_head;
    __sync_synchronize();

    if (head == buffer->data_tail)
        return NULL;

    void* buffer_start = (void*)buffer + buffer->data_offset;
    struct strbuffer* callchains = strnew(1024);
    if (!callchains) {
        fprintf(stderr, "ERROR: Memory allocation failed in perf.c:get_callchains\n");
        return NULL;
    }

    struct perf_event_header header;
    while (buffer->data_tail < head) {
        uint64_t relative_loc = buffer->data_tail % buffer->data_size;
        size_t bytes_remaining = buffer->data_size - relative_loc;
        size_t header_bytes_remaining = bytes_remaining > sizeof(struct perf_event_header) ?
            sizeof(struct perf_event_header) : bytes_remaining;

        memcpy(&header, buffer_start + relative_loc, header_bytes_remaining);
        memcpy((void*)&header + header_bytes_remaining, buffer_start, sizeof(struct perf_event_header) - header_bytes_remaining);

        struct sample* sample = buffer_start + relative_loc;
        int used_malloc = 0;
        if (bytes_remaining < header.size) {
            sample = malloc(header.size);
            used_malloc = 1;
            memcpy(sample, buffer_start + relative_loc, bytes_remaining);
            memcpy((void*)sample + bytes_remaining, buffer_start, header.size - bytes_remaining);
        }
        append_symbols_from_sample(callchains, sample, dwfl);
        if (used_malloc)
            free(sample);

        buffer->data_tail += header.size;
    }

    __sync_synchronize();
    return strfreewrap(callchains);
}

long long get_energy() {
    FILE* fp;
    char energy_buffer[256];
    fp = fopen("/sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj", "r");
    if (fp == NULL) {
        perror("fopen");
        exit(EXIT_FAILURE);
    }
    if (!fgets(energy_buffer, sizeof(energy_buffer), fp)) {
        perror("fgets");
        exit(EXIT_FAILURE);
    }
    fclose(fp);
    return atoll(energy_buffer);
}

long get_process_time(pid_t pid) {
    char path[256];
    FILE* fp;
    char line[1024];
    long utime = 0, stime = 0;

    snprintf(path, sizeof(path), "/proc/%d/stat", pid);
    if ((fp = fopen(path, "r")) == NULL) return -1;

    if (fgets(line, sizeof(line), fp) == NULL) {
        fclose(fp);
        return -1;
    }
    fclose(fp);

    char* start = strchr(line, '(');
    char* end = strrchr(line, ')');
    if (!start || !end) return -1;

    char* p = end + 1;
    int field = 2;
    while (*p && field < 14) {
        if (*p == ' ') {
            field++;
            while (*++p == ' ');
        }
        else
            p++;
    }
    sscanf(p, "%ld %ld", &utime, &stime);
    return utime + stime;
}

long get_total_cpu_time() {
    FILE* fp;
    char line[1024];
    long user, nice, system, idle, iowait, irq, softirq;

    if ((fp = fopen("/proc/stat", "r")) == NULL) return -1;
    fgets(line, sizeof(line), fp);
    fclose(fp);

    if (sscanf(line, "cpu  %ld %ld %ld %ld %ld %ld %ld",
        &user, &nice, &system, &idle, &iowait, &irq, &softirq) != 7)
        return -1;

    return user + nice + system + irq + softirq;
}

// double get_gpu_power(unsigned int gpu_count) {
//     for (unsigned int i = 0; i < gpu_count; i++) {
//         nvmlDevice_t device;
//         nvmlReturn_t result = nvmlDeviceGetHandleByIndex(i, &device);
//         if (result != NVML_SUCCESS) {
//             fprintf(stderr, "Failed to get device handle\n");
//             continue;
//         }

//         unsigned int power;
//         result = nvmlDeviceGetPowerUsage(device, &power);
//         if (result != NVML_SUCCESS) {
//             fprintf(stderr, "Failed to get power usage for device %u\n", i);
//             continue;
//         }

//         return (double)power / 1000.0; // Convert to watts
//     }
//     return 0;
// }

void get_utc_timestamp(char *buffer, size_t buffer_size) {
    struct timespec ts;
    clock_gettime(CLOCK_REALTIME, &ts);
    struct tm tm_utc;
    gmtime_r(&ts.tv_sec, &tm_utc);
    
    // Format base time (YYYY-MM-DDTHH:MM:SS)
    strftime(buffer, buffer_size, "%Y-%m-%dT%H:%M:%S", &tm_utc);
    
    // Append microseconds (6 digits) and 'Z'
    int microsec = ts.tv_nsec / 1000; // Convert nanoseconds to microseconds
    snprintf(buffer + strlen(buffer), buffer_size - strlen(buffer), 
            ".%06dZ", microsec);
}

int main(int argc, char** argv) {
    // Default values for optional arguments.
    unsigned int callchains_per_report = 20;
    unsigned int report_sleep_ms = 5;

    if (argc < 2) {
        fprintf(stderr, "Usage: %s <pid> [callchains_per_report] [report_sleep_ms]\n", *argv);
        exit(EXIT_FAILURE);
    }

    pid_t pid = atoi(argv[1]);
    fprintf(stderr, "Got pid %i\n", pid);

    // Check if optional arguments are provided.
    if (argc > 2) {
        callchains_per_report = atoi(argv[2]);
    }
    if (argc > 3) {
        report_sleep_ms = atoi(argv[3]);
    }

    // Initialize NVML
    // nvmlReturn_t nvmlRet = nvmlInit();
    // if (nvmlRet != NVML_SUCCESS) {
    //     fprintf(stderr, "Failed to initialize NVML\n");
    // }

    // Get the number of devices
    // unsigned int gpuCount;
    // nvmlRet = nvmlDeviceGetCount(&gpuCount);
    // if (nvmlRet != NVML_SUCCESS) {
    //     fprintf(stderr, "Failed to get device count\n");
    //     nvmlShutdown();
    // }

    struct perf_event_attr attr = { 0 };
    attr.size = sizeof(struct perf_event_attr);
    attr.type = PERF_TYPE_HARDWARE;
    attr.config = PERF_COUNT_HW_INSTRUCTIONS;
    attr.sample_type = PERF_SAMPLE_CALLCHAIN;
    attr.sample_freq = callchains_per_report * report_sleep_ms;
    attr.mmap = 1;
    attr.freq = 1;
    attr.ksymbol = 0;
    attr.disabled = 1;

    int fd = syscall(SYS_perf_event_open, &attr, pid, -1, -1, 0);
    if (fd == -1) {
        perror("perf_event_open");
        exit(EXIT_FAILURE);
    }

    void* buffer = mmap(NULL, 2 * PAGE_SIZE, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    if (buffer == MAP_FAILED) {
        perror("mmap");
        close(fd);
        exit(EXIT_FAILURE);
    }

    ioctl(fd, PERF_EVENT_IOC_RESET, 0);
    ioctl(fd, PERF_EVENT_IOC_ENABLE, 0);

    struct perf_event_mmap_page* buffer_info = buffer;
    Dwfl* dwfl = init_dwfl(pid);

    // Use zclock to get the start time in milliseconds.
    // long start_ms = zclock_mono();
    printf("timestamp, callchains, power, resource_usage, gpu_power\n");
    struct timespec prev_ts;
    clock_gettime(CLOCK_MONOTONIC, &prev_ts);

    long long prevEnergy = get_energy();
    // long prev_time_ms = start_ms;

    long prev_process_time = get_process_time(pid);
    long prev_total_time = get_total_cpu_time();
    if (prev_process_time == -1 || prev_total_time == -1) {
        fprintf(stderr, "Error reading initial CPU time values\n");
        exit(EXIT_FAILURE);
    }

    while (1) {
        // Sleep for the report interval (converted to milliseconds)
        zclock_sleep(report_sleep_ms);  // Sleep for the specified interval

        if (kill(pid, 0) == -1) {
            if (errno == ESRCH) {
                fprintf(stderr, "Process %d has exited. Exiting program.\n", pid);
                break;
            }
        }

        // long now_ms = zclock_mono();
        // double overall_elapsed = (now_ms - start_ms) / 1000.0;
        long long currentEnergy = get_energy();
        long long deltaEnergy = currentEnergy - prevEnergy;
        prevEnergy = currentEnergy;

        // double interval_seconds = (now_ms - prev_time_ms) / 1000.0;
        // prev_time_ms = now_ms;
        struct timespec curr_ts;
        clock_gettime(CLOCK_MONOTONIC, &curr_ts);
        double interval_seconds = (curr_ts.tv_sec - prev_ts.tv_sec) + 
                                (curr_ts.tv_nsec - prev_ts.tv_nsec) / 1e9;
        prev_ts = curr_ts;
        double power = (deltaEnergy / 1e6) / interval_seconds;
        double gpu_power = 0; //get_gpu_power(gpuCount);

        long curr_process_time = get_process_time(pid);
        long curr_total_time = get_total_cpu_time();
        double usage = 0.0;
        if (curr_process_time == -1 || curr_total_time == -1) {
            fprintf(stderr, "Error reading CPU time values\n");
        }
        else {
            long delta_process = curr_process_time - prev_process_time;
            long delta_total = curr_total_time - prev_total_time;
            if (delta_total > 0)
                usage = 100.0 * delta_process / delta_total;
            else
                fprintf(stderr, "No CPU time elapsed\n");

            prev_process_time = curr_process_time;
            prev_total_time = curr_total_time;
        }

        char* callchains = get_callchains(buffer_info, dwfl);
        char timestamp[32];
        get_utc_timestamp(timestamp, sizeof(timestamp));
        if (callchains)
            printf("%s, %s, %.6f, %.2f, %.6f\n", timestamp, callchains, power, usage, gpu_power);
        else
            printf("%s, , %.6f, %.2f, %.6f\n", timestamp, power, usage, gpu_power);

        free(callchains);
    }

    ioctl(fd, PERF_EVENT_IOC_DISABLE, 0);
    munmap(buffer, 2 * PAGE_SIZE);
    close(fd);
    dwfl_end(dwfl);
    // nvmlRet = nvmlShutdown();
    // if (nvmlRet != NVML_SUCCESS) {
    //     fprintf(stderr, "Failed to shutdown NVML\n");
    // }
    return EXIT_SUCCESS;
}
