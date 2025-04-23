#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <time.h>

int main() {
    FILE* fp;
    char buffer[1024];
    struct timespec start, end;
    double elapsed_seconds;

    // Get the start time
    clock_gettime(CLOCK_MONOTONIC, &start);

    // Open the energy file for reading
    fp = fopen("/sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj", "r");
    if (fp == NULL) {
        perror("fopen");
        return 1;
    }

    // Read the initial energy value
    fgets(buffer, sizeof(buffer), fp);
    long long initialEnergy = atoll(buffer);
    fclose(fp);

    // Your workload here...

    usleep(1000000); // Simulate workload with a sleep


    // Open and read the final energy value
    fp = fopen("/sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj", "r");
    if (fp == NULL) {
        perror("fopen");
        return 1;
    }

    fgets(buffer, sizeof(buffer), fp);
    long long finalEnergy = atoll(buffer);
    fclose(fp);

    // Get the end time
    clock_gettime(CLOCK_MONOTONIC, &end);

    // Calculate elapsed time in seconds
    elapsed_seconds = (end.tv_sec - start.tv_sec) +
        (end.tv_nsec - start.tv_nsec) / 1000000000.0;

    // Calculate the energy consumed during the workload
    long long consumedEnergy = finalEnergy - initialEnergy;

    // Calculate power in watts (joules per second)
    // Convert microjoules to joules by dividing by 1,000,000
    double power = (consumedEnergy / 1000000.0) / elapsed_seconds;

    printf("Energy consumed: %lld microjoules\n", consumedEnergy);
    printf("Time elapsed: %.6f seconds\n", elapsed_seconds);
    printf("Average power: %.6f watts\n", power);

    return 0;
}
