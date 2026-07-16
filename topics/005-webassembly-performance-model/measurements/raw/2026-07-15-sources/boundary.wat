(module
  (type $step_type (func (param i64) (result i64)))
  (import "host" "step" (func $host_step (type $step_type)))

  ;; The multiply-add is dependency chained. WebAssembly i64 arithmetic wraps
  ;; modulo 2^64, matching uint64_t in the C callback.
  (func $guest_step (type $step_type) (param $x i64) (result i64)
    local.get $x
    i64.const 6364136223846793005
    i64.mul
    i64.const 1442695040888963407
    i64.add)

  ;; One host-to-Wasm call performs n steps entirely in guest code.
  (func $guest_loop (export "guest_loop")
    (param $n i64) (param $x i64) (result i64)
    (local $i i64)
    block $done
      loop $loop
        local.get $i
        local.get $n
        i64.ge_u
        br_if $done
        local.get $x
        call $guest_step
        local.set $x
        local.get $i
        i64.const 1
        i64.add
        local.set $i
        br $loop
      end
    end
    local.get $x)

  ;; One host-to-Wasm call performs n guest-to-host callbacks.
  (func $host_loop (export "host_loop")
    (param $n i64) (param $x i64) (result i64)
    (local $i i64)
    block $done
      loop $loop
        local.get $i
        local.get $n
        i64.ge_u
        br_if $done
        local.get $x
        call $host_step
        local.set $x
        local.get $i
        i64.const 1
        i64.add
        local.set $i
        br $loop
      end
    end
    local.get $x))
