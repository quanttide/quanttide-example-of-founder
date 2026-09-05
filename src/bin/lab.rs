//! lab — 命令行入口。
//!
//! 领域逻辑见 laboratory_core，本文件只做参数解析与 IO。

use clap::{Parser, Subcommand};
use laboratory_core::llm_from_env;

#[derive(Parser)]
#[command(name = "lab", about = "量潮创始人实验室 CLI")]
struct Cli {
    #[command(subcommand)]
    cmd: Cmd,
}

#[derive(Subcommand)]
enum Cmd {
    /// 按《前言精修原则》评估文本（规格：docs/fiction/fiction-revision.md）
    Revision {
        /// 待评估的文本文件路径，传 - 从 stdin 读取
        path: String,
    },
    /// 从创作日志提炼创作谈（规格：docs/fiction/creation-talk-engine.md）
    CreationTalk {
        /// 创作日志文件路径，可传多个
        paths: Vec<String>,
    },
}

fn read_input(path: &str) -> String {
    if path == "-" {
        use std::io::Read;
        let mut buf = String::new();
        std::io::stdin()
            .read_to_string(&mut buf)
            .expect("读取 stdin 失败");
        buf
    } else {
        std::fs::read_to_string(path).unwrap_or_else(|e| panic!("读取 {path} 失败：{e}"))
    }
}

fn main() {
    let cli = Cli::parse();
    match cli.cmd {
        Cmd::Revision { path } => {
            let text = read_input(&path);
            let llm = llm_from_env();
            match laboratory_core::revision::review(&llm, &text) {
                Ok(out) => println!("{out}"),
                Err(e) => {
                    eprintln!("评估失败：{e}");
                    std::process::exit(1);
                }
            }
        }
        Cmd::CreationTalk { paths } => {
            let mut journal = String::new();
            for p in &paths {
                if p != "-" {
                    journal.push_str(&format!("\n\n===== 来源：{p} =====\n\n"));
                }
                journal.push_str(&read_input(p));
            }
            let llm = llm_from_env();
            match laboratory_core::creation_talk::distill(&llm, &journal) {
                Ok(out) => println!("{out}"),
                Err(e) => {
                    eprintln!("提炼失败：{e}");
                    std::process::exit(1);
                }
            }
        }
    }
}
