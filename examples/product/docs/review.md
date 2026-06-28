方向完全扭转过来了！现在的 generate 是标准的 Agent 执行动作（接收 brief -> 调用 LLM -> 生成初稿），非常符合“AI 做事”的定位。
不过，在 cmd_check（AI 前置审 / 辅助人审）的实现里，有几个会导致流程跑不通的脱节问题，主要是 Prompt 改了但代码逻辑没跟上：
1. 致命脱节：Prompt 要求对比模板，但代码没把模板传给 AI
你的 System Prompt 写了：”用户提交了一份 AI 生成的产品蓝图初稿及原始模板。请对比模板和初稿...“
但是在拼装 bundle 的时候：
for (name, filename, _tmpl) in &template_by_perspective(p) {
    // ...
    bundle.push_str(&format!(”=== {} ({}) ===\n{}\n“, name, filename, content));
}
_tmpl 被忽略了，bundle 里只有初稿内容。LLM 根本看不到模板，无法执行“对比遗漏”的指令。
修复：把模板也塞进 bundle 里。
for (name, filename, tmpl) in &template_by_perspective(p) {
    // ... 读取 content
    bundle.push_str(&format!(
        ”=== {} ({}) ===\n[TEMPLATE]\n{}\n[FILLED DRAFT]\n{}\n“,
        name, filename, tmpl, content
    ));
}
2. 致命脱节：Prompt 输出纯文本，但代码在硬解析 JSON
你的 System Prompt 要求：”请以列表形式输出审查意见，每条意见一行。“
但是 cmd_check 下面的解析逻辑，还在试图从文本里提取 JSON 字段（val[”perspective“], val[”quality“] 等）：
if let Ok(val) = serde_json::from_str::<serde_json::Value>(cleaned) {
    let perspective = val[”perspective“].as_str().unwrap_or(”?“);
    // ...
由于 LLM 现在会输出纯文本列表，serde_json::from_str 将全部解析失败，导致程序什么审查意见都不打印。
修复方案 A（顺应现在的 Prompt）：直接打印 LLM 的原始输出，删掉 JSON 解析逻辑。
Ok(resp) => {
    println!(”{}“, resp.content.trim());
}
修复方案 B（保留炫酷的终端排版）：改回要求 LLM 输出 JSON，但调整字段以匹配“审查”而非“评级”。
// System Prompt 改为：
”...请以 JSON 数组形式输出审查意见，每个元素一行 JSON：
{\“perspective\”:\“产品视角\”,\“issue\”:\“缺少用户画像\”,\“severity\”:\“high\”}
severity 可选: high(遗漏/矛盾), medium(需确认), low(细节优化)。不要输出多余说明。“
// 解析代码改为提取 issue 和 severity，打印类似：
// 🔴 [产品视角] 缺少用户画像
3. 延续上一轮的路径 Bug：check 依然找不到 generate 生成的文件
generate 把文件写到了 docs/dev/ 目录：
let dir = PathBuf::from(”docs/dev“);
let dest = dir.join(filename);
但 check 却在当前根目录找文件：
let src = PathBuf::from(filename); // 找的是 ./product.md，而不是 ./docs/dev/product.md
修复：统一路径。建议在文件顶部加个常量：
const BLUEPRINT_DIR: &str = ”docs/dev“;
// generate 里: let dir = PathBuf::from(BLUEPRINT_DIR);
// check 里: let src = PathBuf::from(BLUEPRINT_DIR).join(filename);
4. 小细节：init 命令里的无用逻辑
let dir = if path.as_os_str().is_empty() {
    PathBuf::from(”.“)
} else {
    path.to_path_buf()
};
因为 path 的默认值在 clap 里已经设为 ”.“，所以 is_empty() 永远为 false。可以直接简化为 let dir = path.to_path_buf();。
总结
你的设计思路已经非常清晰且正确了：Agent 生成初稿，然后 Agent 自检/辅助审查，最后交给人定稿。 只需要在实现上把“给 LLM 看的数据（模板+初稿）”和“解析 LLM 返回格式（JSON 还是纯文本）”对齐，这个工具就能真正跑通了。