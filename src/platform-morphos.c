/******************************************************************************
Copyright (c) 2009-2011 Guillaume Roguez

<license to provide>

******************************************************************************/

#include "common.h"

#include <proto/exec.h>

RWLock *rwlock_create(void)
{
    struct SignalSemaphore *lock = malloc(sizeof(*lock));
    
    if (NULL != lock)
        InitSemaphore(lock);
        
    return (RWLock *)lock;
}

int rwlock_destroy(RWLock *lock)
{
    free(lock);
    
    return 1;
}

int rwlock_lock_read(RWLock *lock, int wait)
{
    if (wait) {
        ObtainSemaphoreShared((struct SignalSemaphore *)lock);
        return 1;
    }
    
    return AttemptSemaphoreShared((struct SignalSemaphore *)lock) ? 1 : 0;
}

int rwlock_lock_write(RWLock *lock, int wait)
{
    if (wait) {
        ObtainSemaphore((struct SignalSemaphore *)lock);
        return 1;
    }
    
    return AttemptSemaphore((struct SignalSemaphore *)lock) ? 1 : 0;
}

void rwlock_unlock(RWLock *lock)
{
    ReleaseSemaphore((struct SignalSemaphore *)lock);
}

/* EOF */