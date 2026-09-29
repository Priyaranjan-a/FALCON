//! FALCON desktop: the discovery engine and the console in a native window.
//!
//! A small splash window shows while the engine starts; the console then opens
//! in the main window, served by the engine on the loopback address. Native
//! folder and file pickers are available to the console through the dialog
//! plugin (see `capabilities/console.json`); nothing else is exposed to it.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod engine;

use engine::{Engine, Status};
use tauri::webview::PageLoadEvent;
use tauri::{AppHandle, Manager, RunEvent, State, WebviewUrl, WebviewWindowBuilder};

const MAIN: &str = "main";
const SPLASH: &str = "splash";

/// Opens the console once the engine answers, and retires the splash when the page has loaded.
pub fn open_console(app: &AppHandle, url: &str) -> tauri::Result<()> {
    if let Some(window) = app.get_webview_window(MAIN) {
        window.show()?;
        return window.set_focus();
    }
    let (width, height) = window_size(app);
    let url = url.parse().map_err(|_| tauri::Error::InvalidWebviewUrl("engine address"))?;
    WebviewWindowBuilder::new(app, MAIN, WebviewUrl::External(url))
        .title("FALCON")
        .inner_size(width, height)
        .min_inner_size(1024.0, 680.0)
        .center()
        .visible(false)
        .on_page_load(|window, payload| {
            if payload.event() == PageLoadEvent::Finished && !window.is_visible().unwrap_or(true) {
                let _ = window.show();
                let _ = window.set_focus();
                if let Some(splash) = window.app_handle().get_webview_window(SPLASH) {
                    let _ = splash.close();
                }
            }
        })
        .build()?;
    Ok(())
}

/// Generous but never larger than the screen it opens on.
fn window_size(app: &AppHandle) -> (f64, f64) {
    let (mut width, mut height) = (1440.0, 920.0);
    if let Ok(Some(monitor)) = app.primary_monitor() {
        let size = monitor.size().to_logical::<f64>(monitor.scale_factor());
        width = f64::min(width, size.width * 0.92);
        height = f64::min(height, size.height * 0.9);
    }
    (width, height)
}

#[tauri::command]
fn engine_status(engine: State<'_, Engine>) -> Status {
    engine.status()
}

#[tauri::command]
fn retry(app: AppHandle, engine: State<'_, Engine>) {
    engine.stop();
    engine::launch(app);
}

#[tauri::command]
fn open_logs(app: AppHandle) {
    if let Ok(data) = engine::data_dir(&app) {
        let logs = data.join("logs");
        let _ = std::fs::create_dir_all(&logs);
        let opener = if cfg!(windows) { "explorer" } else if cfg!(target_os = "macos") { "open" } else { "xdg-open" };
        let _ = std::process::Command::new(opener).arg(logs).spawn();
    }
}

#[tauri::command]
fn quit(app: AppHandle) {
    app.exit(0);
}

fn main() {
    let app = tauri::Builder::default()
        // One FALCON per user: a second launch focuses the running one instead of starting another engine.
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            if let Some(window) = app.get_webview_window(MAIN).or_else(|| app.get_webview_window(SPLASH)) {
                let _ = window.unminimize();
                let _ = window.show();
                let _ = window.set_focus();
            }
        }))
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![engine_status, retry, open_logs, quit])
        .setup(|app| {
            app.manage(Engine::new(app.package_info().version.to_string()));
            engine::launch(app.handle().clone());
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("FALCON could not start");

    app.run(|app, event| {
        if let RunEvent::Exit = event {
            // The engine notices this process has gone and shuts itself down gracefully,
            // finishing its database writes; nothing to force here.
            let _ = app;
        }
    });
}
