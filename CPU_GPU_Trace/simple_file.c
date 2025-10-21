#include <cuda.h>
#include <cuda_runtime.h>
#include <cupti.h>
#include <iostream>

int main() {
    // Initialize CUDA first
    CUresult cuResult = cuInit(0);
    std::cout << "cuInit result: " << cuResult << std::endl;
    
    // Then initialize CUPTI
    CUptiResult cuptiErr = cuptiInit(0);
    std::cout << "cuptiInit result: " << cuptiErr << std::endl;
    
    return 0;
}