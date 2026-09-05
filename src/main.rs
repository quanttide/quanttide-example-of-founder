#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use eframe::egui;

fn main() -> eframe::Result {
    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_inner_size([960.0, 640.0])
            .with_title("量潮创始人实验室"),
        ..Default::default()
    };
    eframe::run_native(
        "laboratory",
        options,
        Box::new(|_cc| Ok(Box::new(LabApp::default()))),
    )
}

#[derive(Default, Clone, Copy, PartialEq)]
enum Tool {
    #[default]
    Health,
    Cogni,
    SpecReview,
}

impl Tool {
    fn label(&self) -> &'static str {
        match self {
            Tool::Health => "Health",
            Tool::Cogni => "Cogni",
            Tool::SpecReview => "SpecReview",
        }
    }

    fn placeholder(&self) -> &'static str {
        match self {
            Tool::Health => "健康检查 — 待实现",
            Tool::Cogni => "知识抽取（knowl）— 待实现，模型约束见 data/knowl/",
            Tool::SpecReview => "规格清晰度评估 — 规格见 .agents/skills/docs-clarity-review/",
        }
    }
}

struct LabApp {
    selected: Tool,
}

impl Default for LabApp {
    fn default() -> Self {
        Self { selected: Tool::default() }
    }
}

impl eframe::App for LabApp {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        egui::SidePanel::left("tools").show(ctx, |ui| {
            ui.heading("工具");
            ui.separator();
            for tool in [Tool::Health, Tool::Cogni, Tool::SpecReview] {
                ui.selectable_value(&mut self.selected, tool, tool.label());
            }
        });

        egui::CentralPanel::default().show(ctx, |ui| {
            ui.heading(self.selected.label());
            ui.separator();
            ui.label(self.selected.placeholder());
        });
    }
}
