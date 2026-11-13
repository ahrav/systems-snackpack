// LD_PRELOAD shim for test_check.py. UFFD_SHIM selects one kernel answer:
//   no_wp              UFFDIO_API as Linux 6.12 built without userfaultfd WP: a WP
//                      request gets EINVAL and a zeroed struct; other requests
//                      succeed and report a feature mask without WP.
//   no_user_mode_only  userfaultfd(2) as Linux 5.7 through 5.10: EINVAL for the
//                      UFFD_USER_MODE_ONLY flag.
//   api_eio            UFFDIO_API fails with EIO.
// Every other call reaches the kernel unchanged.
#define _GNU_SOURCE  // glibc feature-test macro: declares RTLD_NEXT
#include <dlfcn.h>
#include <errno.h>
#include <linux/userfaultfd.h>
#include <stdarg.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/syscall.h>

static int selected(const char *answer) {
    const char *mode = getenv("UFFD_SHIM");
    return mode && !strcmp(mode, answer);
}
int ioctl(int fd, unsigned long request, ...) {
    static int (*next)(int, unsigned long, ...);
    if (!next) next = (int (*)(int, unsigned long, ...))dlsym(RTLD_NEXT, "ioctl");
    va_list ap;
    va_start(ap, request);
    void *arg = va_arg(ap, void *);
    va_end(ap);
    if (request != UFFDIO_API) return next(fd, request, arg);
    struct uffdio_api *api = arg;
    if (selected("api_eio")) { errno = EIO; return -1; }
    if (!selected("no_wp")) return next(fd, request, arg);
    if (api->features & UFFD_FEATURE_PAGEFAULT_FLAG_WP) {
        memset(api, 0, sizeof(*api));
        errno = EINVAL;
        return -1;
    }
    int rc = next(fd, request, arg);
    if (!rc) api->features &= ~(__u64)UFFD_FEATURE_PAGEFAULT_FLAG_WP;
    return rc;
}
long syscall(long number, ...) {
    static long (*next)(long, ...);
    if (!next) next = (long (*)(long, ...))dlsym(RTLD_NEXT, "syscall");
    va_list ap;
    va_start(ap, number);
    // glibc's syscall() loads six argument slots for every call; forward the same six.
    long a[6];
    for (int i = 0; i < 6; ++i) a[i] = va_arg(ap, long);
    va_end(ap);
    if (number == SYS_userfaultfd && ((int)a[0] & UFFD_USER_MODE_ONLY) && selected("no_user_mode_only")) {
        errno = EINVAL;
        return -1;
    }
    return next(number, a[0], a[1], a[2], a[3], a[4], a[5]);
}
