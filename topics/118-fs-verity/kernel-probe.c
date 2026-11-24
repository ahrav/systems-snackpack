// Probe one disposable read-only file containing a single zero byte.
#include <errno.h>
#include <fcntl.h>
#include <linux/fsverity.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

int main(int argc, char **argv) {
    if (argc != 2) return 1;
    const int fd = open(argv[1], O_RDONLY);
    if (fd < 0) { perror("open"); return 1; }
    struct fsverity_enable_arg args = {
        .version = 1, .hash_algorithm = FS_VERITY_HASH_ALG_SHA256, .block_size = 4096
    };
    if (ioctl(fd, FS_IOC_ENABLE_VERITY, &args) < 0) {
        int err = errno;
        fprintf(stderr, "FS_IOC_ENABLE_VERITY: %s (errno %d)\n", strerror(err), err);
        return err == ENOTTY || err == EOPNOTSUPP ? 77 : 1;
    }
    union {
        struct fsverity_digest header;
        unsigned char bytes[sizeof(struct fsverity_digest) + 32];
    } digest = { .header = { .digest_size = 32 } };
    if (ioctl(fd, FS_IOC_MEASURE_VERITY, &digest) < 0) { perror("measure"); return 1; }
    if (digest.header.digest_size != 32 || digest.header.digest_algorithm != 1) return 1;
    for (size_t i = 0; i < 32; ++i) printf("%02x", digest.bytes[sizeof(digest.header) + i]);
    puts("");
    char byte;
    return pread(fd, &byte, 1, 0) == 1 && byte == 0 ? 0 : 1;
}
