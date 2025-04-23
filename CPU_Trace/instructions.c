#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>

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

    // Parse fields after the command name
    char* p = end + 1;
    int field = 2; // We're now at field 3 (0-based after comm)

    while (*p && field < 14) {
        if (*p == ' ') {
            field++;
            while (*++p == ' ');
        }
        else p++;
    }

    // Field 14 (utime) and 15 (stime)
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

int main(int argc, char* argv[]) {
    if (argc != 2) {
        fprintf(stderr, "Usage: %s <pid>\n", argv[0]);
        return 1;
    }

    pid_t pid = atoi(argv[1]);

    long t1_process = get_process_time(pid);
    long t1_total = get_total_cpu_time();

    if (t1_process == -1 || t1_total == -1) {
        fprintf(stderr, "Error reading initial values\n");
        return 1;
    }

    sleep(1);  // Measurement window

    long t2_process = get_process_time(pid);
    long t2_total = get_total_cpu_time();

    if (t2_process == -1 || t2_total == -1) {
        fprintf(stderr, "Error reading final values\n");
        return 1;
    }

    long delta_process = t2_process - t1_process;
    long delta_total = t2_total - t1_total;

    if (delta_total <= 0) {
        fprintf(stderr, "No CPU time elapsed\n");
        return 1;
    }

    double usage = 100.0 * delta_process / delta_total;
    printf("PID %d CPU usage: %.2f%%\n", pid, usage);

    return 0;
}
