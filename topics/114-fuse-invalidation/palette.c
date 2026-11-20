/* Read-only, single-file FUSE server for the invalidation experiment. */
#define FUSE_USE_VERSION 31
#include <fuse_lowlevel.h>
#include <errno.h>
#include <fcntl.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

enum { PALETTE = 12 };
static int backing_fd;

static void init(void *unused, struct fuse_conn_info *conn)
{
    (void)unused;
    /* Isolate explicit notifications from mtime-based page invalidation. */
    conn->want &= ~(FUSE_CAP_AUTO_INVAL_DATA | FUSE_CAP_WRITEBACK_CACHE);
}

static int attributes(fuse_ino_t ino, struct stat *st)
{
    if (ino == FUSE_ROOT_ID) {
        *st = (struct stat){.st_mode = S_IFDIR | 0555, .st_nlink = 2,
                            .st_ino = ino, .st_uid = getuid(), .st_gid = getgid()};
        return 0;
    }
    if (ino != PALETTE)
        return ENOENT;
    if (fstat(backing_fd, st) == -1)
        return errno;
    st->st_ino = ino;
    return 0;
}

static void lookup(fuse_req_t req, fuse_ino_t parent, const char *name)
{
    if (parent != FUSE_ROOT_ID || strcmp(name, "palette") != 0) {
        fuse_reply_err(req, ENOENT);
        return;
    }
    struct fuse_entry_param e = {.ino = PALETTE, .entry_timeout = 3600,
                                 .attr_timeout = 3600};
    int err = attributes(PALETTE, &e.attr);
    if (err)
        fuse_reply_err(req, err);
    else
        fuse_reply_entry(req, &e);
}

static void getattr_cb(fuse_req_t req, fuse_ino_t ino, struct fuse_file_info *fi)
{
    (void)fi;
    struct stat st;
    int err = attributes(ino, &st);
    if (err)
        fuse_reply_err(req, err);
    else
        fuse_reply_attr(req, &st, 3600);
}

static void open_cb(fuse_req_t req, fuse_ino_t ino, struct fuse_file_info *fi)
{
    if (ino != PALETTE || (fi->flags & O_ACCMODE) != O_RDONLY) {
        fuse_reply_err(req, EACCES);
        return;
    }
    fi->keep_cache = 1;
    fuse_reply_open(req, fi);
}

static void read_cb(fuse_req_t req, fuse_ino_t ino, size_t size, off_t off,
                    struct fuse_file_info *fi)
{
    (void)ino;
    (void)fi;
    char bytes[4]; /* The fixture is exactly four bytes. */
    ssize_t n = pread(backing_fd, bytes, size < sizeof bytes ? size : sizeof bytes, off);
    if (n < 0)
        fuse_reply_err(req, errno);
    else
        fuse_reply_buf(req, bytes, (size_t)n);
}

static void *control(void *session)
{
    int command;
    while ((command = getchar()) != EOF) {
        int result = -EINVAL;
        if (command == 'a' || command == 'p') {
            off_t start = command == 'a' ? -1 : 0;
            result = fuse_lowlevel_notify_inval_inode(session, PALETTE, start, 0);
        }
        printf("%d\n", result);
        fflush(stdout);
    }
    return NULL;
}

int main(int argc, char **argv)
{
    if (argc != 3) {
        fprintf(stderr, "usage: palette BACKING MOUNTPOINT\n");
        return 2;
    }
    backing_fd = open(argv[1], O_RDONLY);
    if (backing_fd < 0) {
        perror("open backing");
        return 1;
    }
    struct fuse_args args = FUSE_ARGS_INIT(1, argv);
    struct fuse_lowlevel_ops ops = {.init = init, .lookup = lookup, .getattr = getattr_cb,
                                    .open = open_cb, .read = read_cb};
    struct fuse_session *se = fuse_session_new(&args, &ops, sizeof ops, NULL);
    if (!se || fuse_session_mount(se, argv[2]) != 0)
        return 1;
    pthread_t worker;
    int result = pthread_create(&worker, NULL, control, se);
    if (result == 0) {
        puts("mounted");
        fflush(stdout);
        result = fuse_session_loop(se);
        pthread_join(worker, NULL); /* The driver closes stdin before unmount. */
    }
    fuse_session_unmount(se);
    fuse_session_destroy(se);
    fuse_opt_free_args(&args);
    close(backing_fd);
    return result != 0;
}
