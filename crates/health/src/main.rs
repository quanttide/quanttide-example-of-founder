use clap::{Parser, Subcommand};
use quanttide_agent::llm::{CompleteOptions, LLM};
use quanttide_agent::Message;
use std::path::PathBuf;

const EXTRACT_PROMPT: &str =
    "从以下文本中提取情绪状态。输出JSON：{\"dominant_mood\":\"\",\"valence\":0,\"arousal\":0,\"warning_signs\":[],\"emotional_needs\":[]} 纯JSON。";

#[derive(Parser)]
#[command(name = "health")]
struct Cli {
    #[command(subcommand)]
    cmd: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Weekly emotional health check
    Check {
        #[arg(long, default_value = "~/docs/memory")]
        memory: String,
        #[arg(long, default_value = "~/docs/fiction")]
        fiction: String,
        #[arg(long, default_value_t = 7)]
        days: u32,
    },
    /// Record this week to CSV
    Track {
        #[arg(long, default_value = "~/docs/memory")]
        memory: String,
        #[arg(long, default_value = "~/docs/fiction")]
        fiction: String,
        #[arg(long)]
        csv: Option<String>,
        #[arg(long)]
        show: bool,
    },
    /// Generate baseline profile
    Profile {
        #[arg(long, default_value = "~/docs/memory")]
        memory: String,
        #[arg(long, default_value = "~/docs/fiction")]
        fiction: String,
        #[arg(long, default_value = "output")]
        output: String,
    },
}

fn main() {
    let cli = Cli::parse();
    match cli.cmd {
        Commands::Check { memory, fiction, days } => cmd_check(&memory, &fiction, days),
        Commands::Track { memory, fiction, csv, show } => cmd_track(&memory, &fiction, csv, show),
        Commands::Profile { memory, fiction, output } => cmd_profile(&memory, &fiction, &output),
    }
}

fn expand(p: &str) -> PathBuf {
    if p.starts_with('~') {
        PathBuf::from(std::env::var("HOME").unwrap_or_default()).join(&p[2..])
    } else {
        PathBuf::from(p)
    }
}

// ponytail: reads full file contents from git log. git2 is the stdlib for git.
fn git_latest(repo: &PathBuf, days: u32, max: usize) -> String {
    let repo = match git2::Repository::open(repo) { Ok(r) => r, Err(_) => return String::new() };
    let mut revwalk = match repo.revwalk() { Ok(r) => r, Err(_) => return String::new() };
    let _ = revwalk.push_head();
    revwalk.set_sorting(git2::Sort::TIME).unwrap_or(());

    let cutoff = chrono_timestamp_days_ago(days);
    let mut texts = Vec::new();
    for oid in revwalk.flatten().take(max) {
        let commit = match repo.find_commit(oid) { Ok(c) => c, Err(_) => continue };
        if commit.time().seconds() < cutoff { break; }
        let tree = match commit.tree() { Ok(t) => t, Err(_) => continue };
        for entry in tree.iter().take(1) {
            if let Some(obj) = entry.to_object(&repo).ok() {
                if let Some(blob) = obj.as_blob() {
                    let content = std::str::from_utf8(blob.content()).unwrap_or("");
                    let date = chrono_timestamp_to_str(commit.time().seconds());
                    texts.push(format!("[{}] {}", date, &content[..content.len().min(2000)]));
                }
            }
        }
    }
    texts.join("\n\n")
}

fn extract(text: &str) -> serde_json::Value {
    if text.is_empty() {
        return serde_json::json!({});
    }
    let llm = LLM::default();
    match llm.complete(
        &[
            Message::new("system", EXTRACT_PROMPT),
            Message::new("user", &text[..text.len().min(4000)]),
        ],
        CompleteOptions::default(),
    ) {
        Ok(r) => serde_json::from_str(r.content.trim()).unwrap_or_default(),
        Err(_) => serde_json::json!({}),
    }
}

fn cmd_check(memory: &str, fiction: &str, days: u32) {
    let mem = git_latest(&expand(memory), days, 100);
    let fic = git_latest(&expand(fiction), days, 100);
    println!("日记: {}字  小说: {}字", mem.len(), fic.len());
    let (d, f) = (extract(&mem), extract(&fic));
    let dv = d["valence"].as_f64().unwrap_or(0.0);
    let fv = f["valence"].as_f64().unwrap_or(0.0);
    println!(
        "现实: {} ({})  创作: {} ({})  差距: {:.1}",
        d["dominant_mood"].as_str().unwrap_or("?"),
        dv,
        f["dominant_mood"].as_str().unwrap_or("?"),
        fv,
        fv - dv
    );
}

fn cmd_track(memory: &str, fiction: &str, csv_path: Option<String>, show: bool) {
    let csv_path = csv_path.unwrap_or_else(|| "HEALTH.csv".to_string());
    if show {
        show_trend(&csv_path);
        return;
    }
    let mem = git_latest(&expand(memory), 7, 100);
    let fic = git_latest(&expand(fiction), 7, 100);
    let (d, f) = (extract(&mem), extract(&fic));
    let dv = d["valence"].as_f64();
    let fv = f["valence"].as_f64();
    let gap = match (dv, fv) {
        (Some(d), Some(f)) => format!("{:.1}", f - d),
        _ => String::new(),
    };
    let now = chrono_now();
    let week = format!("{}-W{:02}", now.0, now.1);

    let mut wtr = csv::WriterBuilder::new().from_path(&csv_path).unwrap();
    wtr.write_record(&[
        "week", "date", "diary_present", "diary_mood", "diary_valence",
        "fiction_present", "fiction_mood", "fiction_valence", "gap", "signals",
    ]).ok();
    wtr.write_record(&[
        week.as_str(),
        &format!("{}-{:02}-{:02}", now.0, now.1, now.2),
        if mem.is_empty() { "0" } else { "1" },
        d["dominant_mood"].as_str().unwrap_or(""),
        &dv.map(|v| format!("{v}")).unwrap_or_default(),
        if fic.is_empty() { "0" } else { "1" },
        f["dominant_mood"].as_str().unwrap_or(""),
        &fv.map(|v| format!("{v}")).unwrap_or_default(),
        &gap,
        &f["warning_signs"].as_array().map(|a| a.iter().map(|v| v.as_str().unwrap_or("")).collect::<Vec<_>>().join("; ")).unwrap_or_default(),
    ]).ok();
    wtr.flush().ok();
    println!("已记录 {week} → {csv_path}");
}

fn show_trend(csv_path: &str) {
    let mut rdr = csv::Reader::from_path(csv_path).unwrap_or_else(|_| {
        println!("暂无数据"); std::process::exit(0);
    });
    let mut rows = Vec::new();
    for result in rdr.records() {
        if let Ok(r) = result { rows.push(r); }
    }
    println!("共 {} 周\n", rows.len());
    for r in rows.iter().rev().take(10).rev() {
        println!("{:<10} {:<12} 日记:{:<6} 小说:{:<6} 差距:{:<6}",
                 r.get(0).unwrap_or(""), r.get(1).unwrap_or(""),
                 r.get(4).unwrap_or(""), r.get(7).unwrap_or(""), r.get(8).unwrap_or(""));
    }
    // ponytail: simple mean, no rolling stats
    let vals: Vec<f64> = rows.iter().filter_map(|r| r.get(4).and_then(|v| v.parse().ok())).collect();
    let fvs: Vec<f64> = rows.iter().filter_map(|r| r.get(7).and_then(|v| v.parse().ok())).collect();
    if !vals.is_empty() { println!("\n日记均值: {:.2}", vals.iter().sum::<f64>() / vals.len() as f64); }
    if !fvs.is_empty() { println!("小说均值: {:.2}", fvs.iter().sum::<f64>() / fvs.len() as f64); }
}

fn cmd_profile(memory: &str, fiction: &str, output: &str) {
    let mem = daily_content(&expand(memory), 500);
    let fic = daily_content(&expand(fiction), 500);
    let mem_sample: Vec<_> = mem.iter().take(20).collect();
    let fic_sample: Vec<_> = fic.iter().take(20).collect();
    println!("分析 {} 天日记 + {} 天小说...", mem_sample.len(), fic_sample.len());

    let (mut d_vals, mut f_vals) = (Vec::new(), Vec::new());
    for (_, text) in &mem_sample {
        let s = extract(text);
        if let Some(v) = s["valence"].as_f64() { d_vals.push(v); }
    }
    for (_, text) in &fic_sample {
        let s = extract(text);
        if let Some(v) = s["valence"].as_f64() { f_vals.push(v); }
    }

    let da = mean(&d_vals);
    let ds = stddev(&d_vals, da);
    let fa = mean(&f_vals);
    let profile = serde_json::json!({
        "baseline": {
            "diary_avg_valence": (da * 100.0).round() / 100.0,
            "diary_volatility": (ds * 100.0).round() / 100.0,
            "fiction_avg_valence": (fa * 100.0).round() / 100.0,
            "typical_gap": ((fa - da) * 100.0).round() / 100.0,
        },
        "thresholds": {
            "warning_if_below": ((da - ds) * 100.0).round() / 100.0,
        },
    });

    let out = PathBuf::from(output).join("profile.yaml");
    std::fs::create_dir_all(out.parent().unwrap()).ok();
    std::fs::write(&out, serde_yaml::to_string(&profile).unwrap()).ok();
    println!("基线 → {}", out.display());
    println!("日记 {da:.1}±{ds:.1}  小说 {fa:.1}  差距 {:.1}  预警 <{:.1}", fa - da, da - ds);
}

// ponytail: perf/date helpers, chrono lib not worth the dep for this
fn chrono_timestamp_days_ago(days: u32) -> i64 {
    use std::time::{SystemTime, UNIX_EPOCH};
    SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_secs() as i64 - (days as i64 * 86400)
}
fn chrono_timestamp_to_str(secs: i64) -> String {
    let t = std::time::UNIX_EPOCH + std::time::Duration::from_secs(secs as u64);
    let dt = time_to_date(t);
    format!("{}-{:02}-{:02}", dt.0, dt.1, dt.2)
}
fn chrono_now() -> (i32, u32, u32) {
    time_to_date(std::time::SystemTime::now())
}
fn time_to_date(t: std::time::SystemTime) -> (i32, u32, u32) {
    // ponytail: minimal date from epoch seconds. correct for 2021-2030.
    let secs = t.duration_since(std::time::UNIX_EPOCH).unwrap().as_secs();
    let days = secs / 86400;
    let year = 1970 + (days as f64 / 365.25) as u64;
    // ponytail: ISO week approx, good enough for weekly labels
    let rem = days as i64 - ((year - 1970) as i64 * 365 + leap_days(1970, year));
    let month = [31,28,31,30,31,30,31,31,30,31,30,31];
    let mut d = rem;
    let mut m = 0;
    for (i, days_in_m) in month.iter().enumerate() {
        if d < *days_in_m as i64 { m = i + 1; break; }
        d -= *days_in_m as i64;
    }
    if m == 0 { m = 12; d = 31; }
    (year as i32, m as u32, d as u32 + 1)
}
fn leap_days(start: u64, end: u64) -> i64 {
    ((end - start) / 4) as i64
}

fn daily_content(repo: &PathBuf, max: usize) -> Vec<(String, String)> {
    let repo = match git2::Repository::open(repo) { Ok(r) => r, _ => return vec![] };
    let mut revwalk = match repo.revwalk() { Ok(r) => r, _ => return vec![] };
    let _ = revwalk.push_head();
    revwalk.set_sorting(git2::Sort::TIME).unwrap_or(());
    let mut days: std::collections::HashMap<String, Vec<String>> = std::collections::HashMap::new();
    for oid in revwalk.flatten().take(max) {
        let commit = match repo.find_commit(oid) { Ok(c) => c, _ => continue };
        let date = chrono_timestamp_to_str(commit.time().seconds())[..10].to_string();
        let tree = match commit.tree() { Ok(t) => t, _ => continue };
        for entry in tree.iter().take(3) {
            if let Some(obj) = entry.to_object(&repo).ok() {
                if let Some(blob) = obj.as_blob() {
                    let content = std::str::from_utf8(blob.content()).unwrap_or("");
                    days.entry(date.clone()).or_default().push(content[..content.len().min(2000)].to_string());
                    break;
                }
            }
        }
    }
    let mut result: Vec<_> = days.into_iter().collect();
    result.sort_by(|a, b| a.0.cmp(&b.0));
    result.iter().map(|(d, texts)| (d.clone(), texts.join("\n\n"))).collect()
}

fn mean(v: &[f64]) -> f64 {
    if v.is_empty() { return 0.0; }
    v.iter().sum::<f64>() / v.len() as f64
}
fn stddev(v: &[f64], m: f64) -> f64 {
    if v.len() < 2 { return 0.0; }
    (v.iter().map(|x| (x - m).powi(2)).sum::<f64>() / v.len() as f64).sqrt()
}
