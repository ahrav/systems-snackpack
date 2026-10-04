//! Build the native C comparison object without cross-language LTO.
use std::{env, path::PathBuf, process::Command};
fn main() {
    println!("cargo:rerun-if-changed=c/kernel.c");
    for key in ["CC", "AR", "TOPIC67_NATIVE"] {
        println!("cargo:rerun-if-env-changed={key}");
    }
    assert_eq!(
        env::var("HOST").unwrap(),
        env::var("TARGET").unwrap(),
        "native builds only"
    );
    let out = PathBuf::from(env::var_os("OUT_DIR").unwrap());
    let mut cc = Command::new(env::var("CC").unwrap_or_else(|_| "cc".into()));
    cc.args(["-std=c11", "-O3", "-fno-lto", "-Wall", "-Wextra", "-Werror"]);
    if env::var_os("TOPIC67_NATIVE").is_some() {
        cc.arg(if env::var("CARGO_CFG_TARGET_ARCH").unwrap() == "aarch64" {
            "-mcpu=native"
        } else {
            "-march=native"
        });
    }
    assert!(
        cc.arg("-c")
            .arg("c/kernel.c")
            .arg("-o")
            .arg(out.join("kernel.o"))
            .status()
            .unwrap()
            .success()
    );
    assert!(
        Command::new(env::var("AR").unwrap_or_else(|_| "ar".into()))
            .arg("crs")
            .arg(out.join("libtopic67.a"))
            .arg(out.join("kernel.o"))
            .status()
            .unwrap()
            .success()
    );
    println!("cargo:rustc-link-search=native={}", out.display());
    println!("cargo:rustc-link-lib=static=topic67");
}
