//! Fresh-process correctness probe for the Topic 32 mechanism model.
//!
//! `--self-check` prints the model's stable receipt and exits successfully only
//! after every invariant check passes. Any other invocation prints the usage
//! contract to standard error and exits unsuccessfully.

use mvcc_hot_vacuum::self_check_receipt;
use std::ffi::{OsStr, OsString};
use std::process::ExitCode;

fn main() -> ExitCode {
    match run(std::env::args_os().skip(1)) {
        Ok(receipt) => {
            print!("{receipt}");
            ExitCode::SUCCESS
        }
        Err(error) => {
            eprintln!("{error}");
            ExitCode::FAILURE
        }
    }
}

fn run(arguments: impl IntoIterator<Item = OsString>) -> Result<String, String> {
    let mut arguments = arguments.into_iter();
    match (arguments.next().as_deref(), arguments.next()) {
        (Some(argument), None) if argument == OsStr::new("--self-check") => self_check_receipt(),
        _ => Err("usage: mvcc-hot-vacuum-probe --self-check".to_owned()),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn exact_self_check_argument_runs_the_model() {
        let receipt = run([OsString::from("--self-check")]).expect("valid command must pass");
        assert!(receipt.ends_with("CHECK=PASS\n"));
    }

    #[test]
    fn extra_argument_returns_usage() {
        assert_eq!(
            run([OsString::from("--self-check"), OsString::from("extra")]),
            Err("usage: mvcc-hot-vacuum-probe --self-check".to_owned())
        );
    }

    #[cfg(unix)]
    #[test]
    fn non_unicode_argument_returns_usage() {
        use std::os::unix::ffi::OsStringExt;

        assert_eq!(
            run([OsString::from_vec(vec![0xff])]),
            Err("usage: mvcc-hot-vacuum-probe --self-check".to_owned())
        );
    }
}
