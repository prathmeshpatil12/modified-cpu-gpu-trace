#include <cupti.h>
#include <cuda.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <unistd.h>
#include <cupti_callbacks.h>

static FILE* logf = nullptr;

static void CUPTIAPI bufferRequested(uint8_t** buffer, size_t* size, size_t* maxNumRecords) {
    const size_t BUF_SZ = 64 * 1024;
    *size = BUF_SZ;
    *maxNumRecords = 0;
    *buffer = (uint8_t*) malloc(BUF_SZ);
}

static void CUPTIAPI bufferCompleted(CUcontext, uint32_t, uint8_t* buffer, size_t, size_t validSize) {
    CUpti_Activity* rec = nullptr;
    if (logf) {
        while (cuptiActivityGetNextRecord(buffer, validSize, &rec) == CUPTI_SUCCESS) {
            if (rec->kind == CUPTI_ACTIVITY_KIND_KERNEL || rec->kind == CUPTI_ACTIVITY_KIND_CONCURRENT_KERNEL) {
                auto* k = (CUpti_ActivityKernel4*)rec;
                fprintf(logf, "KERNEL,start_ns=%llu,end_ns=%llu,name=%s,corr=%u,dev=%u,ctx=%u,stream=%u,grid=(%u,%u,%u),block=(%u,%u,%u)\n",
                        (unsigned long long)k->start, (unsigned long long)k->end, k->name,
                        (unsigned)k->correlationId, (unsigned)k->deviceId, (unsigned)k->contextId, (unsigned)k->streamId,
                        k->gridX, k->gridY, k->gridZ, k->blockX, k->blockY, k->blockZ);
            } else if (rec->kind == CUPTI_ACTIVITY_KIND_MEMCPY) {
                auto* m = (CUpti_ActivityMemcpy*)rec;
                fprintf(logf, "MEMCPY,start_ns=%llu,end_ns=%llu,bytes=%llu,kind=%u,corr=%u\n",
                        (unsigned long long)m->start, (unsigned long long)m->end,
                        (unsigned long long)m->bytes, (unsigned)m->copyKind, (unsigned)m->correlationId);
            } else if (rec->kind == CUPTI_ACTIVITY_KIND_RUNTIME) {
                auto* r = (CUpti_ActivityAPI*)rec;
                const char* fname = nullptr;
                if (cuptiGetCallbackName(CUPTI_CB_DOMAIN_RUNTIME_API, r->cbid, &fname) != CUPTI_SUCCESS || !fname)
                    fname = "unknown_runtime";
                // contextId not present in your headers → remove it
                fprintf(logf, "RUNTIME,start_ns=%llu,end_ns=%llu,name=%s,cbid=%u,corr=%u,tid=%u\n",
                        (unsigned long long)r->start, (unsigned long long)r->end,
                        fname, (unsigned)r->cbid, (unsigned)r->correlationId,
                        (unsigned)r->threadId);
            } else if (rec->kind == CUPTI_ACTIVITY_KIND_DRIVER) {
                auto* d = (CUpti_ActivityAPI*)rec;
                const char* fname = nullptr;
                if (cuptiGetCallbackName(CUPTI_CB_DOMAIN_DRIVER_API, d->cbid, &fname) != CUPTI_SUCCESS || !fname)
                    fname = "unknown_driver";
                // contextId not present in your headers → remove it
                fprintf(logf, "DRIVER,start_ns=%llu,end_ns=%llu,name=%s,cbid=%u,corr=%u,tid=%u\n",
                        (unsigned long long)d->start, (unsigned long long)d->end,
                        fname, (unsigned)d->cbid, (unsigned)d->correlationId,
                        (unsigned)d->threadId);
            }
        }
        size_t dropped = 0;
        cuptiActivityGetNumDroppedRecords(nullptr, 0, &dropped);
        if (dropped) fprintf(logf, "DROPPED,%zu\n", dropped);
        fflush(logf);
    }
    free(buffer);
}

__attribute__((constructor))
static void init() {
    const char* path = getenv("DW_CUPTI_LOG");
    if (!path) path = "/tmp/dwcupti.log";
    logf = fopen(path, "a");
    if (!logf) return;

    cuInit(0);

    cuptiActivityRegisterCallbacks(bufferRequested, bufferCompleted);
    cuptiActivityEnable(CUPTI_ACTIVITY_KIND_KERNEL);
    cuptiActivityEnable(CUPTI_ACTIVITY_KIND_CONCURRENT_KERNEL);
    cuptiActivityEnable(CUPTI_ACTIVITY_KIND_MEMCPY);
    cuptiActivityEnable(CUPTI_ACTIVITY_KIND_RUNTIME);
    cuptiActivityEnable(CUPTI_ACTIVITY_KIND_DRIVER);

    // Adjust CUPTI buffers (CUPTI 12.x: 2nd arg is size_t*)
    size_t devSz = 64 * 1024;
    size_t devSzSize = sizeof(devSz);
    cuptiActivitySetAttribute(CUPTI_ACTIVITY_ATTR_DEVICE_BUFFER_SIZE, &devSzSize, &devSz);

    size_t poolLimit = 64 * 1024;
    size_t poolLimitSize = sizeof(poolLimit);
    cuptiActivitySetAttribute(CUPTI_ACTIVITY_ATTR_DEVICE_BUFFER_POOL_LIMIT, &poolLimitSize, &poolLimit);

    // Some headers don’t define PROFILING buffer attrs; guard them.
    #ifdef CUPTI_ACTIVITY_ATTR_PROFILING_BUFFER_SIZE
    size_t profSz = 4 * 1024 * 1024;
    size_t profSzSize = sizeof(profSz);
    cuptiActivitySetAttribute(CUPTI_ACTIVITY_ATTR_PROFILING_BUFFER_SIZE, &profSzSize, &profSz);
    #endif

    fprintf(logf, "CUPTI_INIT,pid=%d\n", getpid());
    fflush(logf);
}

__attribute__((destructor))
static void fini() {
    if (logf) {
        cuptiActivityFlushAll(CUPTI_ACTIVITY_FLAG_FLUSH_FORCED);
        fprintf(logf, "CUPTI_FINI\n");
        fclose(logf);
        logf = nullptr;
    }
}