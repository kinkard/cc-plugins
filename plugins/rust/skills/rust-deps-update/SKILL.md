---
name: rust-deps-update
description: Update a Rust project's dependencies thoroughly - `cargo update`, semver-major bumps with changelog and source reading, adopting new APIs, MSRV / edition / Docker toolchain bumps from Rust release notes, feature trimming and fewer duplicate crates, and a release bump for libraries. Use whenever the user says "update dependencies", "update deps", "bump crates", "cargo update", "bump MSRV", "update rust version", "new edition", "why do we have two versions of X", "Cargo.lock duplicates" or "binary is too big", even if they name only one crate.
context: fork
model: sonnet
---

# Rust dependency update

Scope: $ARGUMENTS (paths or crate names); if empty, the current repo.

Goal: the newest deps that make sense, fewer crates and duplicates, and code on the newest idioms they allow. Leave changes uncommitted (`chore: Update dependencies`). Scratch copies go in your scratchpad, with `[workspace]` appended to `Cargo.toml` and `CARGO_TARGET_DIR=<repo>/target`.

## 1. Baseline

- **Library or binary?** A published `[lib]` is a library; anything else is a binary. Every `Cargo.lock` from `git ls-files` is a workspace to repeat the steps in.
- **Read** `Cargo.toml`, the CI workflows and the Dockerfiles for `rust-version`, `RUST_VERSION`/`LLVM_VERSION`, apt packages, `deny.toml`, and what CI runs.
- **Record** the numbers below. The "before" lockfile is `git show HEAD:Cargo.lock`.
  ```sh
  cargo tree -d -e normal --depth 0 2>/dev/null | awk '/ v/{print $1, $2}' | sort -u   # duplicates; no normal deps -> drop -e normal
  cargo tree -e normal --prefix none | sort -u | wc -l                                 # host crates
  cargo build --release --locked && ls -l target/release/<bin>                        # binaries
  ```

## 2. MSRV first, so the update resolves against it

- **Binary:** the latest stable (`rustc +stable -V`, e.g. `1.99`) in the Docker `RUST_VERSION` and CI images. Don't add `rust-version`: the resolver already uses the toolchain it runs on, and nothing builds the binary with an older one.
- **Library:** latest stable minus 5 minors (1.99 -> 1.94); raise older floors to it. Go higher only for a named win in library code, such as an API that simplifies or speeds it up, or an LTO toolchain constraint. Dev-deps don't count.
- **Toolchains:** use installed ones, or install one deliberately. `cargo +<v>` auto-installs, so never probe below the floor.

## 3. Compatible update

Run `cargo update --verbose`, then sort each `Unchanged x vA (available: vB[, requires Rust R])` line:
- **Newer major:** step 4. Prereleases aren't listed; skip them.
- **`requires Rust R`:** it needs more than the floor. Hold it; a library may raise the floor if the crate is worth it. R is exact: `1.94` does not satisfy `1.94.1`.
- **Same major:** `cargo update -p x --precise <B> --dry-run` names the `=` pin holding it. Move our own pins, keeping pairs like `cxx`/`cxx-build` together. Ignore other crates' pins.

Write specs at major granularity (`"4"`, `"0.7"`); use `=` only with a comment saying why. A long run of minors, such as an SDK, gets step 4's reading too.

## 4. Semver-major bumps

Save `Cargo.lock`, trial-bump (`cargo update -p x`), then:
- **Read the changelog and the source diff.**
  - Changelog: the registry `CHANGELOG.md`; if there's none, raw GitHub `CHANGELOG.md`, `api.github.com/repos/<o>/<r>/releases`, or `git log` in a local clone.
  - Source: diff the modules we call; both versions are in `~/.cargo/registry/src/`. Read the old implementation too, since semantics can change under an unchanged signature.
  - Adopt new APIs that are simpler, faster or safer.
  - No migration notes and a big diff? A subagent walks the commits between the two tags for the APIs we use and reports each signature and behaviour change, with how to adapt.
- **A/B** the HEAD build against the new one on data that exercises the changed path. The dep's own repo may have test data. For network crates, try a real endpoint and a known-bad one.
- **Features:** `cargo info x@<new>` shows the feature map and `license`. Renamed defaults can switch the TLS/crypto stack, or add runtime needs such as an OS CA bundle.
- **Cost:** recount duplicates and crates. If dependents still pull the old major, hold the bump ("wait for <crate>"). A dev-dep may cost crates if it improves what it's there for.

## 5. Idioms and toolchain

`python3 ${CLAUDE_SKILL_DIR}/scripts/rust_releases.py <old floor> <new floor|latest>` prints each release's Language, Libraries, Stabilized APIs and Cargo sections (`--compat` adds breaking changes). Grep our code for what they replace:
- nested `if let` -> let chains
- `chunks_exact` + `try_into` -> `as_chunks`
- same-width `as` -> `cast_signed`/`cast_unsigned`
- `% n == 0` -> `is_multiple_of` (unsigned only)
- `assert!(matches!(..))` -> `assert_matches!` (needs `use std::assert_matches;`)

A new edition means `cargo fix --edition`.

For cross-language LTO, clang/lld must match rustc's LLVM major (`rustc +<v> -vV`). Check that apt.llvm.org has `clang-N` for the distro and arch, then bump `LLVM_VERSION` together with `RUST_VERSION`.

## 6. Features and duplicates

Audit every direct dep's default features against what we use; `cargo tree -e normal,features -i <dep>` shows who enables what. Turn defaults off only for a measurable win:
- a `-sys` or build-script crate
- a second TLS or crypto stack
- serde/syn heavy crates if that codegen is unused
- binary size

Keep features users see, such as clap's `color` and `suggestions`; a few small pure-Rust crates are not worth a hand-kept feature list.

For a duplicate, `cargo tree -i x@<ver> -e normal --target all` shows who pulls it. Then do one of these:
- align our dep (a downgrade is fine)
- trim features
- use one TLS stack (rustls on `ring`)
- replace it with std

List upstream lag, proc-macro duplicates (`syn` 2/3) and other-target duplicates, but leave them.

Remove Dockerfile apt packages whose `-sys` crate left the lock. To attribute binary growth: `cargo update -p x@<new> --precise <old>`, rebuild, restore.

## 7. Library release

If users get something new (`rust-version`, normal deps, code), make a compatible bump: 0.4.1 -> 0.4.2, never 0.5. The MSRV-aware resolver protects users on old toolchains. Then run `cargo update -w`, and update the README only if it pins finer than major.minor. Skip this when only dev-deps changed.

## 8. Verify and report

Run `cargo fmt --check && cargo clippy --all-targets -- -Dwarnings && cargo test`, plus:
- CI's own commands
- `cargo bench --no-run`, if bench deps changed
- `cargo deny check`, if `deny.toml` exists
- `cargo build --release`, for binaries
- a Docker build, if a Dockerfile changed (say so if the daemon is down)

Report:
- majors bumped, each with its reason or new API
- what was held back, and why
- MSRV and crate version, old -> new
- idioms adopted
- duplicates, crate count and binary size, before -> after
- anything unverified
