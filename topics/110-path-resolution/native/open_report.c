#define _GNU_SOURCE
#include <fcntl.h>
#include <linux/openat2.h>
#include <stdio.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <unistd.h>

/* Exposed for the identity-oracle harness. Errors retain errno. */
int open_policy(int root, const char *path, unsigned long long resolve) {
    struct open_how how = {
        .flags = O_RDONLY | O_CLOEXEC | O_NONBLOCK | O_NOCTTY,
        .resolve = resolve
    };
    return syscall(SYS_openat2, root, path, &how, sizeof how);
}

#ifndef LIBRARY_ONLY
int main(int argc, char **argv) {
    if (argc != 3) {
        fprintf(stderr, "usage: %s ROOT RELATIVE_PATH\n", argv[0]);
        return 2;
    }
    /* ROOT comes from trusted configuration. */
    int root = open(argv[1], O_PATH | O_DIRECTORY | O_CLOEXEC);
    if (root < 0) { perror("root"); return 1; }
    int fd = open_policy(root, argv[2], RESOLVE_BENEATH | RESOLVE_NO_SYMLINKS);
    close(root);
    if (fd < 0) { perror("openat2"); return 1; }
    struct stat st;
    if (fstat(fd, &st) || !S_ISREG(st.st_mode)) {
        fprintf(stderr, "expected regular file\n");
        close(fd);
        return 1;
    }
    printf("opened regular file, size=%lld\n", (long long)st.st_size);
    close(fd);
    return 0;
}
#endif
