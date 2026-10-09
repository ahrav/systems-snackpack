//! Compare complete file preparation plus one verified overwrite pass.
use std::fs::{File, OpenOptions};
use std::io::{self, Read, Seek, SeekFrom, Write};
use std::path::Path;
use std::time::Instant;
use topic_072_storage_layout::{BLOCK, Pattern, expected_byte, offsets};

#[cfg(all(target_os = "linux", target_pointer_width = "64"))]
fn reserve(file: &File, len: u64) -> io::Result<()> {
    use std::os::fd::AsRawFd;
    unsafe extern "C" {
        fn fallocate(fd: i32, mode: i32, offset: i64, len: i64) -> i32;
    }
    if len == 0 {
        return Ok(());
    }
    let len = i64::try_from(len).map_err(|_| io::Error::other("length exceeds off_t"))?;
    // SAFETY: a live writable file descriptor, mode 0, and nonnegative i64 range.
    let result = unsafe { fallocate(file.as_raw_fd(), 0, 0, len) };
    if result == 0 {
        Ok(())
    } else {
        Err(io::Error::last_os_error())
    }
}
#[cfg(not(all(target_os = "linux", target_pointer_width = "64")))]
fn reserve(_: &File, _: u64) -> io::Result<()> {
    Err(io::Error::new(
        io::ErrorKind::Unsupported,
        "Linux fallocate required",
    ))
}
fn blocks(file: &File) -> io::Result<u64> {
    #[cfg(unix)]
    {
        use std::os::unix::fs::MetadataExt;
        Ok(file.metadata()?.blocks())
    }
    #[cfg(not(unix))]
    {
        let _ = file;
        Ok(0)
    }
}
fn patch(file: &mut File, len: u64, writes: &[u64], buf: &[u8]) -> io::Result<()> {
    for &off in writes {
        file.seek(SeekFrom::Start(off))?;
        file.write_all(&buf[..(len - off).min(BLOCK) as usize])?;
    }
    Ok(())
}
fn verify(path: &Path, len: u64, pattern: Pattern, value: u8) -> io::Result<()> {
    let mut file = File::open(path)?;
    assert_eq!(file.metadata()?.len(), len);
    let mut buf = [0; 65536];
    let mut pos = 0;
    loop {
        let n = file.read(&mut buf)?;
        if n == 0 {
            break;
        }
        for &byte in &buf[..n] {
            assert_eq!(byte, expected_byte(pos, len, pattern, value), "byte {pos}");
            pos += 1;
        }
    }
    assert_eq!(pos, len);
    Ok(())
}
fn main() -> io::Result<()> {
    let args: Vec<_> = std::env::args().collect();
    if !(args.len() == 5 || (args.len() == 6 && args[5] == "keep")) {
        return Err(io::Error::other(
            "usage: layout DIR dense|sparse|prealloc BYTES empty|dense|scattered|clustered [keep]",
        ));
    }
    let candidate = &args[2];
    if !["dense", "sparse", "prealloc"].contains(&candidate.as_str()) {
        return Err(io::Error::other("unknown candidate"));
    }
    let len: u64 = args[3].parse().map_err(io::Error::other)?;
    if len > 64 * 1024 * 1024 {
        return Err(io::Error::other("maximum 64 MiB"));
    }
    let pattern = Pattern::parse(&args[4]).ok_or_else(|| io::Error::other("unknown pattern"))?;
    let writes = offsets(len, pattern);
    let zeros = [0u8; 65536];
    let first = [0x59u8; BLOCK as usize];
    let second = [0xa6u8; BLOCK as usize];
    let path = Path::new(&args[1]).join(format!("probe-{}.dat", std::process::id()));
    let start = Instant::now();
    let mut file = OpenOptions::new()
        .read(true)
        .write(true)
        .create_new(true)
        .open(&path)?;
    match candidate.as_str() {
        "sparse" => file.set_len(len)?,
        "prealloc" => reserve(&file, len)?,
        _ => {
            let mut remaining = len;
            while remaining > 0 {
                let n = remaining.min(zeros.len() as u64) as usize;
                file.write_all(&zeros[..n])?;
                remaining -= n as u64;
            }
        }
    }
    patch(&mut file, len, &writes, &first)?;
    file.sync_all()?;
    let ready_ns = start.elapsed().as_nanos();
    let allocated = blocks(&file)?;
    verify(&path, len, pattern, 0x59)?;
    let rewrite = Instant::now();
    patch(&mut file, len, &writes, &second)?;
    file.sync_all()?;
    let rewrite_ns = rewrite.elapsed().as_nanos();
    verify(&path, len, pattern, 0xa6)?;
    let cleanup = Instant::now();
    drop(file);
    if args.len() == 5 {
        std::fs::remove_file(&path)?;
    }
    let cleanup_ns = cleanup.elapsed().as_nanos();
    println!(
        "{{\"candidate\":\"{candidate}\",\"len\":{len},\"pattern\":\"{}\",\"writes\":{},\"blocks_512\":{allocated},\"ready_ns\":{ready_ns},\"rewrite_ns\":{rewrite_ns},\"cleanup_ns\":{cleanup_ns}}}",
        args[4],
        writes.len()
    );
    Ok(())
}
