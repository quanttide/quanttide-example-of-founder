use clap::{Parser, Subcommand, ValueEnum};
use quanttide_agent::llm::{CompleteOptions, LLM};
use quanttide_agent::Message;
use std::io::{self, Write};
use std::path::PathBuf;

#[derive(Parser)]
#[command(version, name = "product-blueprint")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    Init {
        #[arg(long, default_value = ".")]
        path: PathBuf,
        #[arg(long)]
        force: bool,
    },
    Generate { perspective: Perspective },
    /// Check filled-in blueprint files. LLM required — reads files, sends to LLM, reports quality.
    Check {
        perspective: Option<Perspective>,
    },
}

#[derive(Clone, ValueEnum)]
enum Perspective {
    Product,
    Design,
    DesignLanguage,
    Architecture,
    All,
}

fn main() {
    let cli = Cli::parse();
    match cli.command {
        Commands::Init { path, force } => cmd_init(path.as_path(), force),
        Commands::Generate { perspective } => cmd_generate(&perspective),
        Commands::Check { perspective } => cmd_check(perspective.as_ref()),
    }
}

const TEMPLATE_PRODUCT: &str = include_str!("../skills/product-blueprint/product.md");
const TEMPLATE_DESIGN: &str = include_str!("../skills/product-blueprint/design.md");
const TEMPLATE_DESIGN_LANGUAGE: &str = include_str!("../skills/product-blueprint/design-language.md");
const TEMPLATE_ARCHITECTURE: &str = include_str!("../skills/product-blueprint/architecture.md");

fn templates() -> [(&'static str, &'static str, &'static str); 4] {
    [
        ("product", "product.md", TEMPLATE_PRODUCT),
        ("design", "design.md", TEMPLATE_DESIGN),
        ("design-language", "design-language.md", TEMPLATE_DESIGN_LANGUAGE),
        ("architecture", "architecture.md", TEMPLATE_ARCHITECTURE),
    ]
}

fn template_by_perspective(p: &Perspective) -> Vec<(&'static str, &'static str, &'static str)> {
    match p {
        Perspective::All => templates().to_vec(),
        Perspective::Product => vec![templates()[0]],
        Perspective::Design => vec![templates()[1]],
        Perspective::DesignLanguage => vec![templates()[2]],
        Perspective::Architecture => vec![templates()[3]],
    }
}

// ── init ──

fn cmd_init(path: &std::path::Path, force: bool) {
    let dir = if path.as_os_str().is_empty() {
        PathBuf::from(".")
    } else {
        path.to_path_buf()
    };
    if !dir.exists() {
        eprintln!("error: directory does not exist: {}", dir.display());
        std::process::exit(1);
    }
    for (_, filename, content) in templates() {
        let dest = dir.join(filename);
        if dest.exists() && !force {
            eprint!("{} already exists. Overwrite? [y/N] ", filename);
            io::stdout().flush().unwrap();
            let mut input = String::new();
            io::stdin().read_line(&mut input).unwrap();
            if input.trim().to_lowercase() != "y" {
                println!("skipped: {}", filename);
                continue;
            }
        }
        std::fs::write(&dest, content).unwrap_or_else(|e| {
            eprintln!("error: failed to write {}: {}", dest.display(), e);
            std::process::exit(1);
        });
        println!("created: {}", dest.display());
    }
}

// ── generate ──

fn skeleton_from(content: &str) -> String {
    let mut out = String::new();
    let mut in_fence = false;
    for line in content.lines() {
        if line.trim_start().starts_with("```") {
            in_fence = !in_fence;
            continue;
        }
        if in_fence {
            continue;
        }
        if line.trim().is_empty()
            || line.starts_with('#')
            || line.starts_with("---")
            || line.starts_with('>')
            || line.trim_start().starts_with('-')
            || line.trim_start().starts_with('*')
        {
            out.push_str(line);
            out.push('\n');
        }
    }
    out
}

fn cmd_generate(perspective: &Perspective) {
    let dir = PathBuf::from("docs/dev");
    std::fs::create_dir_all(&dir).unwrap();
    for (name, filename, content) in &template_by_perspective(perspective) {
        let dest = dir.join(filename);
        let skeleton = skeleton_from(content);
        if dest.exists() {
            eprint!("{} already exists. Overwrite? [y/N] ", dest.display());
            io::stdout().flush().unwrap();
            let mut input = String::new();
            io::stdin().read_line(&mut input).unwrap();
            if input.trim().to_lowercase() != "y" {
                println!("skipped: {}", dest.display());
                continue;
            }
        }
        std::fs::write(&dest, &skeleton).unwrap_or_else(|e| {
            eprintln!("error: failed to write {}: {}", dest.display(), e);
            std::process::exit(1);
        });
        println!("generated: {} ({})", dest.display(), name);
    }
}

// ── check (LLM gateway) ──

fn cmd_check(perspective: Option<&Perspective>) {
    let p = perspective.unwrap_or(&Perspective::All);

    // 1. Read files — only send filled content + section headings as context
    let mut bundle = String::new();
    let mut has_file = false;
    for (name, filename, _tmpl) in &template_by_perspective(p) {
        let src = PathBuf::from(filename);
        if !src.exists() {
            bundle.push_str(&format!("[{}] {} — FILE NOT FOUND\n", name, filename));
            continue;
        }
        has_file = true;
        let content = std::fs::read_to_string(&src).unwrap();
        bundle.push_str(&format!("=== {} ({}) ===\n{}\n", name, filename, content));
    }

    if !has_file {
        eprintln!("error: no blueprint files found. Run `product-blueprint init` first.");
        std::process::exit(1);
    }

    // 2. LLM call
    let llm = LLM::default();
    let sys = "你是一个产品分析文档质量评审员。用户提交了产品蓝图填写内容。\n\
        规则：模板中的问题提示（如\"用一句话说清楚\"）不是用户填写的内容。\n\
        忽略引导问题，只判断用户实际添加的内容。\n\
        对填写内容的每个 section 输出一行JSON：\n\
        {\"perspective\":\"产品视角\",\"section\":\"## 1. 产品定位\",\"quality\":\"adequate\",\"issues\":\"缺少用户画像\"}\n\
        quality可选：empty(完全未填或只复制了模板) poor(写了但内容少) adequate(有要点但缺细节) good(完整)。\n\
        一行一个section，不要列表包裹，不要markdown代码块。";

    match llm.complete(
        &[
            Message::new("system", sys),
            Message::new("user", &format!("模板定义和填写内容如下：\n{}", bundle)),
        ],
        CompleteOptions::default(),
    ) {
        Ok(resp) => {
            let text = resp.content.trim();
            // ponytail: parse each line as JSON, print nicely
            for line in text.lines() {
                let line = line.trim();
                if line.is_empty() || line.starts_with("```") {
                    continue;
                }
                // ponytail: peel surrounding brackets if LLM wraps in array
                let cleaned = line
                    .trim_start_matches('[')
                    .trim_end_matches(']')
                    .trim_end_matches(',');
                if let Ok(val) = serde_json::from_str::<serde_json::Value>(cleaned) {
                    let perspective = val["perspective"].as_str().unwrap_or("?");
                    let section = val["section"].as_str().unwrap_or("?");
                    let quality = val["quality"].as_str().unwrap_or("?");
                    let issues = val["issues"].as_str().unwrap_or("");
                    let icon = match quality {
                        "empty" => "⬜",
                        "poor" => "🟡",
                        "adequate" => "🟢",
                        "good" => "✅",
                        _ => "❓",
                    };
                    let iss = if issues.is_empty() {
                        String::new()
                    } else {
                        format!(" — {}", issues)
                    };
                    println!("{} [{:>12}] {}{}", icon, perspective, section, iss);
                }
            }
        }
        Err(e) => {
            eprintln!("error: LLM call failed: {}", e);
        }
    }
}
