---
name: rust-dev
description: Rust development workflow — cargo, testing, benchmarks, clippy, formatting, and unsafe code auditing
license: MIT
compatibility: opencode
metadata:
  audience: developers
  language: rust
---

## What I do

Full Rust development workflow with cargo, testing, benchmarks, and code quality tools.

## When to use me

- Writing Rust code
- Running tests and benchmarks
- Auditing unsafe code
- Performance optimization
- Dependency management

## Toolchain

```bash
# Check compilation
cargo check

# Build
cargo build
cargo build --release

# Run tests
cargo test
cargo test -- --nocapture  # Show println! output

# Run benchmarks
cargo bench

# Lint with clippy
cargo clippy -- -D warnings

# Format
cargo fmt --check
cargo fmt

# Generate docs
cargo doc --open

# Audit dependencies
cargo audit
cargo deny check
```

## Testing Patterns

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_basic_functionality() {
        let result = my_function(input);
        assert_eq!(result, expected);
    }

    #[test]
    #[should_panic(expected = "divide by zero")]
    fn test_panic_on_invalid_input() {
        my_function(invalid_input);
    }

    #[test]
    fn test_with_result() -> Result<(), Box<dyn std::error::Error>> {
        let result = my_function(input)?;
        assert_eq!(result, expected);
        Ok(())
    }
}
```

## Property-Based Testing

```rust
use proptest::prelude::*;

proptest! {
    #[test]
    fn test_my_function(x in 0..1000) {
        let result = my_function(x);
        prop_assert!(result >= 0);
    }
}
```

## Benchmarking

```rust
use criterion::{black_box, criterion_group, criterion_main, Criterion};

fn criterion_benchmark(c: &mut Criterion) {
    c.bench_function("my_function", |b| {
        b.iter(|| my_function(black_box(input)))
    });
}

criterion_group!(benches, criterion_benchmark);
criterion_main!(benches);
```

## Unsafe Code Audit

```bash
# Find unsafe blocks
grep -rn "unsafe" src/

# Use cargo-geiger for unsafe dependency analysis
cargo geiger
```

## Rules

- **Run clippy before commit** — no warnings allowed
- **Run cargo fmt** — consistent formatting
- **Write tests for all public functions**
- **Document unsafe code** — explain why it's safe
- **Use cargo audit** — check for vulnerabilities
- **Benchmark performance-critical code**
