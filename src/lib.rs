//! 实验室核心逻辑层。
//!
//! GUI（lab-gui）与 CLI（lab）均为薄壳，领域逻辑统一在这里实现，
//! 以 `docs/` 为规格、以 `data/` 为数据。

pub mod revision;

use quanttide_agent::{LLM, Settings};

/// 默认供应商：GLM（智谱开放平台）
const DEFAULT_PROVIDER: &str = "glm";
/// 默认模型：可被环境变量 GLM_MODEL 覆盖
const GLM_DEFAULT_MODEL: &str = "glm-5.3-flash";

fn provider() -> String {
    std::env::var("LAB_LLM_PROVIDER")
        .unwrap_or_else(|_| DEFAULT_PROVIDER.to_string())
        .to_lowercase()
}

/// 按供应商构造 LLM 客户端。默认 GLM + glm-5.3-flash，
/// 可用 `LAB_LLM_PROVIDER`（glm / llm / mimo）与 `GLM_MODEL` 覆盖。
pub fn llm_from_env() -> LLM {
    let settings = Settings::from_env();
    match provider().as_str() {
        "llm" => LLM::new(&settings.llm_model, &settings.llm_base_url, &settings.llm_api_key),
        "mimo" => LLM::new(&settings.mimo_model, &settings.mimo_base_url, &settings.mimo_api_key),
        _ => LLM::new(
            &std::env::var("GLM_MODEL").unwrap_or_else(|_| GLM_DEFAULT_MODEL.to_string()),
            &settings.glm_base_url,
            &settings.glm_api_key,
        ),
    }
}

/// 当前供应商的 API key 是否缺失
pub fn api_key_missing() -> bool {
    let settings = Settings::from_env();
    match provider().as_str() {
        "llm" => settings.llm_api_key.is_empty(),
        "mimo" => settings.mimo_api_key.is_empty(),
        _ => settings.glm_api_key.is_empty(),
    }
}
