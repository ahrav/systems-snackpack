#define _GNU_SOURCE

#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#define RECORD_SIZE 8192

struct record {
    char magic[8];
    unsigned char generation_le[8];
    unsigned char payload[RECORD_SIZE - 8 - 8 - 8];
    unsigned char checksum_le[8];
};

_Static_assert(sizeof(struct record) == RECORD_SIZE, "record size");

static void die(const char *operation) {
    perror(operation);
    exit(1);
}

static uint64_t fnv1a(const unsigned char *bytes, size_t length) {
    uint64_t hash = UINT64_C(14695981039346656037);
    for (size_t index = 0; index < length; ++index) {
        hash ^= bytes[index];
        hash *= UINT64_C(1099511628211);
    }
    return hash;
}

static void store_le64(unsigned char destination[8], uint64_t value) {
    for (size_t index = 0; index < 8; ++index) {
        destination[index] = (unsigned char)(value >> (index * 8));
    }
}

static uint64_t load_le64(const unsigned char source[8]) {
    uint64_t value = 0;
    for (size_t index = 0; index < 8; ++index) {
        value |= (uint64_t)source[index] << (index * 8);
    }
    return value;
}

static void make_record(struct record *record, uint64_t generation) {
    memset(record, generation == 41 ? 'O' : 'N', sizeof(*record));
    memcpy(record->magic, "COWCUT01", 8);
    store_le64(record->generation_le, generation);
    uint64_t checksum = fnv1a((const unsigned char *)record,
                              offsetof(struct record, checksum_le));
    store_le64(record->checksum_le, checksum);
}

static void write_full(int fd, const void *buffer, size_t length) {
    const unsigned char *cursor = buffer;
    size_t remaining = length;
    while (remaining != 0) {
        ssize_t written = write(fd, cursor, remaining);
        if (written < 0 && errno == EINTR) {
            continue;
        }
        if (written <= 0) {
            if (written == 0) {
                errno = EIO;
            }
            die("write");
        }
        cursor += (size_t)written;
        remaining -= (size_t)written;
    }
}

static void read_full(int fd, void *buffer, size_t length) {
    unsigned char *cursor = buffer;
    size_t remaining = length;
    while (remaining != 0) {
        ssize_t count = read(fd, cursor, remaining);
        if (count < 0 && errno == EINTR) {
            continue;
        }
        if (count < 0) {
            die("read");
        }
        if (count == 0) {
            fprintf(stderr, "short record: missing %zu bytes\n", remaining);
            exit(2);
        }
        cursor += (size_t)count;
        remaining -= (size_t)count;
    }

    unsigned char extra;
    ssize_t trailing;
    do {
        trailing = read(fd, &extra, 1);
    } while (trailing < 0 && errno == EINTR);
    if (trailing < 0) {
        die("read trailing byte");
    }
    if (trailing != 0) {
        fprintf(stderr, "long record\n");
        exit(2);
    }
}

static int open_directory(const char *path) {
    int fd = open(path, O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    if (fd < 0) {
        die("open directory");
    }
    printf("syscall=open-directory result=%d\n", fd);
    return fd;
}

static void sync_fd(int fd, const char *name) {
    int status;
    do {
        status = fsync(fd);
    } while (status < 0 && errno == EINTR);
    if (status != 0) {
        die("fsync");
    }
    printf("syscall=fsync name=%s result=success\n", name);
}

static void write_initial_record(int dirfd) {
    struct record record;
    make_record(&record, 41);
    int fd = openat(dirfd, "current",
                    O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC,
                    S_IRUSR | S_IWUSR);
    if (fd < 0) {
        die("openat current");
    }
    printf("syscall=openat name=current result=%d\n", fd);
    write_full(fd, &record, sizeof(record));
    printf("syscall=write name=current bytes=%zu result=success\n",
           sizeof(record));
    sync_fd(fd, "current");
    if (close(fd) != 0) {
        die("close current");
    }
}

static void initialize(const char *path) {
    int dirfd = open_directory(path);
    write_initial_record(dirfd);
    sync_fd(dirfd, "directory");
    if (close(dirfd) != 0) {
        die("close directory");
    }
    puts("init=complete generation=OLD value=41");
}

static void cut_if_selected(const char *selected, const char *site, int code) {
    if (strcmp(selected, site) == 0) {
        printf("failpoint=%s action=_exit code=%d\n", site, code);
        if (fflush(stdout) != 0) {
            die("fflush before failpoint");
        }
        _exit(code);
    }
}

static void update(const char *path, const char *cut) {
    int dirfd = open_directory(path);
    struct record record;
    make_record(&record, 42);

    int fd = openat(dirfd, "next.tmp",
                    O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC,
                    S_IRUSR | S_IWUSR);
    if (fd < 0) {
        die("openat next.tmp");
    }
    printf("syscall=openat name=next.tmp result=%d\n", fd);
    write_full(fd, &record, sizeof(record));
    printf("syscall=write name=next.tmp bytes=%zu result=success\n",
           sizeof(record));
    cut_if_selected(cut, "after_write", 101);

    sync_fd(fd, "next.tmp");
    cut_if_selected(cut, "after_file_fsync", 102);

    if (renameat(dirfd, "next.tmp", dirfd, "current") != 0) {
        die("renameat");
    }
    puts("syscall=renameat from=next.tmp to=current result=success");
    cut_if_selected(cut, "after_rename", 103);

    sync_fd(dirfd, "directory");
    cut_if_selected(cut, "after_dir_fsync", 104);

    if (close(fd) != 0) {
        die("close next.tmp descriptor");
    }
    if (close(dirfd) != 0) {
        die("close directory");
    }
    puts("acknowledgement=success generation=NEW value=42");
}

static void verify(const char *path) {
    int dirfd = open_directory(path);
    int fd = openat(dirfd, "current", O_RDONLY | O_CLOEXEC);
    if (fd < 0) {
        die("openat current");
    }

    struct record record;
    read_full(fd, &record, sizeof(record));
    if (close(fd) != 0) {
        die("close current");
    }

    int magic_ok = memcmp(record.magic, "COWCUT01", 8) == 0;
    uint64_t generation = load_le64(record.generation_le);
    uint64_t expected = fnv1a((const unsigned char *)&record,
                              offsetof(struct record, checksum_le));
    int checksum_ok = expected == load_le64(record.checksum_le);
    const char *state = "INVALID";
    if (magic_ok && checksum_ok && generation == 41) {
        state = "OLD";
    } else if (magic_ok && checksum_ok && generation == 42) {
        state = "NEW";
    }

    struct stat metadata;
    int temp_status = fstatat(dirfd, "next.tmp", &metadata,
                              AT_SYMLINK_NOFOLLOW);
    const char *temp = "absent";
    if (temp_status == 0) {
        temp = "present";
    } else if (errno != ENOENT) {
        die("fstatat next.tmp");
    }

    printf("verify current=%s temp=%s magic=%s checksum=%s generation=%" PRIu64 "\n",
           state,
           temp,
           magic_ok ? "valid" : "invalid",
           checksum_ok ? "valid" : "invalid",
           generation);
    if (close(dirfd) != 0) {
        die("close directory");
    }
    if (strcmp(state, "INVALID") == 0) {
        exit(3);
    }
}

static void corrupt(const char *path) {
    int dirfd = open_directory(path);
    int fd = openat(dirfd, "current", O_RDWR | O_CLOEXEC);
    if (fd < 0) {
        die("openat current for corruption control");
    }
    unsigned char byte;
    if (pread(fd, &byte, 1, 128) != 1) {
        die("pread corruption byte");
    }
    byte ^= UINT8_C(0xff);
    if (pwrite(fd, &byte, 1, 128) != 1) {
        die("pwrite corruption byte");
    }
    sync_fd(fd, "corruption-control");
    if (close(fd) != 0 || close(dirfd) != 0) {
        die("close corruption control");
    }
    puts("corruption_control=applied offset=128");
}

static void print_model(void) {
    puts("model=allowed recovery states for a power-cut abstraction, not a live-kernel observation");
    puts("cut=after_write may_acknowledge=no current_allowed={OLD} temp_allowed={absent,present,partial}");
    puts("cut=after_file_fsync may_acknowledge=no current_allowed={OLD} temp_allowed={absent,present_valid_NEW}");
    puts("cut=after_rename may_acknowledge=no current_allowed={OLD,NEW} record_allowed={whole_OLD,whole_NEW}");
    puts("cut=after_dir_fsync may_acknowledge=yes current_allowed={NEW} temp_allowed={absent}");
    puts("exclusion=no controller-cache model, torn sectors, journal replay, delayed EIO, or filesystem bugs");
}

static void usage(const char *program) {
    fprintf(stderr,
            "usage: %s init DIR | update DIR CUT | verify DIR | corrupt DIR | model\n",
            program);
    exit(64);
}

int main(int argc, char **argv) {
    if (argc == 2 && strcmp(argv[1], "model") == 0) {
        print_model();
        return 0;
    }
    if (argc == 3 && strcmp(argv[1], "init") == 0) {
        initialize(argv[2]);
        return 0;
    }
    if (argc == 4 && strcmp(argv[1], "update") == 0) {
        update(argv[2], argv[3]);
        return 0;
    }
    if (argc == 3 && strcmp(argv[1], "verify") == 0) {
        verify(argv[2]);
        return 0;
    }
    if (argc == 3 && strcmp(argv[1], "corrupt") == 0) {
        corrupt(argv[2]);
        return 0;
    }
    usage(argv[0]);
}
