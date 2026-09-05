//! lab-gui — 图形界面入口。
//!
//! 领域逻辑见 laboratory_core，本文件只做界面呈现。

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use eframe::egui;
use laboratory_core::{api_key_missing, llm_from_env};
use std::sync::mpsc::{self, Receiver, TryRecvError};
use std::thread;

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

struct LabApp {
    input: String,
    result: Option<Result<String, String>>,
    rx: Option<Receiver<Result<String, String>>>,
}

impl Default for LabApp {
    fn default() -> Self {
        Self {
            input: String::new(),
            result: None,
            rx: None,
        }
    }
}

impl LabApp {
    fn busy(&self) -> bool {
        self.rx.is_some()
    }

    fn start_review(&mut self) {
        let text = self.input.clone();
        let (tx, rx) = mpsc::channel();
        self.rx = Some(rx);
        thread::spawn(move || {
            let llm = llm_from_env();
            let res = laboratory_core::revision::review(&llm, &text).map_err(|e| e.to_string());
            let _ = tx.send(res);
        });
    }

    fn poll(&mut self) {
        if let Some(rx) = &self.rx {
            match rx.try_recv() {
                Ok(res) => {
                    self.result = Some(res);
                    self.rx = None;
                }
                Err(TryRecvError::Empty) => {}
                Err(TryRecvError::Disconnected) => {
                    self.rx = None;
                }
            }
        }
    }
}

impl eframe::App for LabApp {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        self.poll();

        egui::CentralPanel::default().show(ctx, |ui| {
            ui.heading("前言精修");
            ui.label("规格：docs/fiction/fiction-revision.md · 七条倾向性准则，仅提供建议，作者保留判断权");

            if api_key_missing() {
                ui.colored_label(
                    egui::Color32::YELLOW,
                    "未检测到 对应供应商的 API key（LAB_LLM_PROVIDER 选择 llm/glm/mimo），请求将会失败",
                );
            }

            ui.add_space(8.0);
            ui.add(
                egui::TextEdit::multiline(&mut self.input)
                    .hint_text("粘贴待精修的文本…")
                    .desired_rows(10),
            );

            ui.add_space(8.0);
            ui.horizontal(|ui| {
                if ui
                    .add_enabled(
                        !self.busy() && !self.input.trim().is_empty(),
                        egui::Button::new("评估"),
                    )
                    .clicked()
                {
                    self.start_review();
                }
                if self.busy() {
                    ui.spinner();
                    ui.label("评估中…");
                }
                if ui.button("清空").clicked() {
                    self.input.clear();
                    self.result = None;
                }
            });

            if let Some(res) = &self.result {
                ui.separator();
                egui::ScrollArea::vertical().show(ui, |ui| match res {
                    Ok(content) => {
                        ui.add(
                            egui::TextEdit::multiline(&mut content.as_str())
                                .desired_rows(8)
                                .code_editor(),
                        );
                    }
                    Err(err) => {
                        ui.colored_label(egui::Color32::RED, format!("评估失败：{err}"));
                    }
                });
            }
        });

        if self.busy() {
            ctx.request_repaint();
        }
    }
}
