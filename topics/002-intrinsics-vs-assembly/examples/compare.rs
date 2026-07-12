//! Confirms that the Topic 2 public paths produce the same fold.

use systems_snackpack_topic_002::{fold_inline_asm, fold_intrinsic, fold_reference};

fn main() {
    let words = [1_u64, 2, 3, 4, 5, 6, 7];
    let reference = fold_reference(&words);
    let intrinsic = fold_intrinsic(&words);
    let assembly = fold_inline_asm(&words);

    assert_eq!(reference, intrinsic);
    assert_eq!(reference, assembly);
    println!("fold={reference:#010x}");
}
