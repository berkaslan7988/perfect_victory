// ZeusAI Desktop — Tauri v2 Main Entry Point
// ============================================
// Otomatik Python backend başlatma, WebView üzerinden bağlantı.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::Mutex;
use tauri::Manager;

/// Geliştirme modunda Python backend'i otomatik başlatmak için kullanılan
/// child process handle'ı. Uygulama kapandığında process öldürülür.
struct BackendProcess(Mutex<Option<Child>>);

#[tauri::command]
fn get_backend_port() -> u16 {
    8000
}

fn main() {
    // Proje kök dizini: CARGO_MANIFEST_DIR = .../ZeusAI/src-tauri, bir üst = .../ZeusAI
    let project_root: PathBuf = [env!("CARGO_MANIFEST_DIR"), ".."].iter().collect();

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(move |app| {
            let python_cmd = if cfg!(target_os = "windows") {
                "python"
            } else {
                "python3"
            };

            match Command::new(python_cmd)
                .current_dir(&project_root)
                .args([
                    "-m", "uvicorn",
                    "backend.server:app",
                    "--host", "127.0.0.1",
                    "--port", "8000",
                ])
                .spawn()
            {
                Ok(child) => {
                    println!("[ZeusAI] Backend başlatıldı (PID: {})", child.id());
                    app.manage(BackendProcess(Mutex::new(Some(child))));
                }
                Err(e) => {
                    eprintln!("[ZeusAI] Backend başlatılamadı: {e}");
                    app.manage(BackendProcess(Mutex::new(None)));
                }
            }

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![get_backend_port])
        .on_window_event(|window, event| {
            // Backend child process'i kapat
            if let tauri::WindowEvent::Destroyed = event {
                let handle = window.app_handle();
                if let Some(state) = handle.try_state::<BackendProcess>() {
                    if let Ok(mut guard) = state.0.lock() {
                        if let Some(ref mut child) = *guard {
                            let _ = child.kill();
                            println!("[ZeusAI] Backend process sonlandırıldı.");
                        }
                    }
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("ZeusAI failed to start");
}