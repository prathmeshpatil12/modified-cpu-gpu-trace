#include <nvml.h>
#include <stdio.h>

int main() {
    // Initialize NVML
    nvmlReturn_t result = nvmlInit();
    if (result != NVML_SUCCESS) {
        printf("Failed to initialize NVML\n");
        return 1;
    }

    // Get the number of devices
    unsigned int deviceCount;
    result = nvmlDeviceGetCount(&deviceCount);
    if (result != NVML_SUCCESS) {
        printf("Failed to get device count\n");
        nvmlShutdown();
        return 1;
    }

    // Iterate over devices
    for (unsigned int i = 0; i < deviceCount; i++) {
        nvmlDevice_t device;
        result = nvmlDeviceGetHandleByIndex(i, &device);
        if (result != NVML_SUCCESS) {
            printf("Failed to get device handle\n");
            continue;
        }

        // Get power consumption
        unsigned int power;
        result = nvmlDeviceGetPowerUsage(device, &power);
        if (result != NVML_SUCCESS) {
            printf("Failed to get power usage for device %u\n", i);
            continue;
        }

        // Print power consumption in watts
        printf("Device %u power consumption: %.2f W\n", i, (float)power / 1000.0f);
    }

    // Shutdown NVML
    result = nvmlShutdown();
    if (result != NVML_SUCCESS) {
        printf("Failed to shutdown NVML\n");
    }

    return 0;
}
