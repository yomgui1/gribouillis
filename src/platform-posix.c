/******************************************************************************
Copyright (c) 2009-2013 Guillaume Roguez

<license to provide>

******************************************************************************/

#include "common.h"

#include <pthread.h>

RWLock *rwlock_create(void)
{
    pthread_rwlock_t *lock = malloc(sizeof(*lock));

    if (NULL != lock)
        pthread_rwlock_init(lock, NULL);

    return (RWLock *)lock;
}

int rwlock_destroy(RWLock *lock)
{
    pthread_rwlock_destroy((pthread_rwlock_t *)lock);
    free(lock);

    return 1;
}

int rwlock_lock_read(RWLock *lock, int wait)
{
    if (wait)
    {
        pthread_rwlock_rdlock((pthread_rwlock_t *)lock);
        return 1;
    }

    return pthread_rwlock_tryrdlock((pthread_rwlock_t *)lock) ? 0 : 1;
}

int rwlock_lock_write(RWLock *lock, int wait)
{
    if (wait)
    {
        pthread_rwlock_wrlock((pthread_rwlock_t *)lock);
        return 1;
    }

    return pthread_rwlock_tryrdlock((pthread_rwlock_t *)lock);
}

void rwlock_unlock(RWLock *lock)
{
    pthread_rwlock_unlock((pthread_rwlock_t *)lock);
}

/* EOF */
