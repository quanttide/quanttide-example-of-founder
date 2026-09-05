//! 实验室核心逻辑层。
//!
//! GUI（lab-gui）与 CLI（lab）均为薄壳，领域逻辑统一在这里实现，
//! 以 `docs/` 为规格、以 `data/` 为数据。

pub mod revision;
