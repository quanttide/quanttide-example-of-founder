//! 实验室核心逻辑层。
//!
//! GUI（lab-gui）与 CLI（lab）均为薄壳，领域逻辑统一在这里实现，
//! 以 `docs/` 为规格、以 `data/` 为数据。

pub mod revision;

use quanttide_agent::{LLM, Settings};

/// 按 `LAB_LLM_PROVIDER` 选择供应商：`llm`（默认）/ `glm` / `mimo`
pub fn llm_from_env() -> LLM {
    let settings = Settings::from_env();
    match std::env::var("LAB_LLM_PROVIDER")
        .unwrap_or_default()
        .to_lowercase()
        .as_str()
    {
        "glm" => LLM::new(&settings.glm_model, &settings.glm_base_url, &settings.glm_api_key),
        "mimo" => LLM::new(&settings.mimo_model, &settings.mimo_base_url, &settings.mimo_api_key),
        _ => LLM::new(&settings.llm_model, &settings.llm_base_url, &settings.llm_api_key),
    }
}

/// 当前供应商的 API key 是否缺失
pub fn api_key_missing() -> bool {
    let settings = Settings::from_env();
    match std::env::var("LAB_LLM_PROVIDER")
        .unwrap_or_default()
        .to_lowercase()
        .as_str()
    {
        "glm" => settings.glm_api_key.is_empty(),
        "mimo" => settings.mimo_api_key.is_empty(),
        _ => settings.llm_api_key.is_empty(),
    }
}
