// Translate — Tauri 2 / WebView2 host (replaces the Electron main process; the UI and the Python engine are unchanged).
#![windows_subsystem = "windows"]

mod backend;
mod config;
mod host;
mod layout;
mod log;
mod system;
mod win;

use host::{Ev, Host, Options};
use serde_json::Value;
use std::path::{Path, PathBuf};
use std::sync::mpsc::{channel, Sender};
use std::sync::Mutex;

struct CoreTx(Mutex<Sender<Ev>>);

/// The one IPC entry point for our pages (bridge.js). Channels that answer get the core's reply; the rest are
/// fire-and-forget.
#[tauri::command]
async fn ipc(ch: String, args: Vec<Value>, webview: tauri::Webview, core: tauri::State<'_, CoreTx>) -> Result<Value, String> {
    const ANSWERS: &[&str] = &["settings:get", "settings:save", "svc:test", "svc:models", "svc:keys", "cache:stats", "cache:clear", "status:get"];
    let label = webview.label().to_string();
    let tx = core.0.lock().unwrap().clone();
    if !ANSWERS.contains(&ch.as_str()) {
        let _ = tx.send(Ev::Ipc { label, ch, args, reply: None });
        return Ok(Value::Null);
    }
    let (rtx, rrx) = channel();
    let _ = tx.send(Ev::Ipc { label, ch, args, reply: Some(rtx) });
    tauri::async_runtime::spawn_blocking(move || rrx.recv_timeout(std::time::Duration::from_secs(90)).unwrap_or(Value::Null)).await.map_err(|e| e.to_string())
}

fn arg(name: &str) -> Option<String> {
    let p = format!("--{name}=");
    std::env::args().find_map(|a| a.strip_prefix(&p).map(str::to_owned))
}
fn flag(name: &str) -> bool {
    std::env::args().any(|a| a == format!("--{name}"))
}

/// The repository's backend/ when running a development build from app/src-tauri/target/….
fn find_up(start: &Path, rel: &str) -> Option<PathBuf> {
    start.ancestors().map(|a| a.join(rel)).find(|p| p.exists())
}

fn start_test_control(port: u16, tx: Sender<Ev>) {
    std::thread::spawn(move || {
        let Ok(server) = tiny_http::Server::http(("127.0.0.1", port)) else {
            log::error(format!("test control: port {port} unavailable"));
            return;
        };
        for mut req in server.incoming_requests() {
            let mut body = String::new();
            let _ = req.as_reader().read_to_string(&mut body);
            let q: Value = if body.trim().is_empty() { Value::Object(Default::default()) } else { serde_json::from_str(&body).unwrap_or(Value::Null) };
            let path = req.url().to_string();
            let tx = tx.clone();
            // One thread per request: replies may wait for the engine.
            std::thread::spawn(move || {
                let (rtx, rrx) = channel();
                let _ = tx.send(Ev::Test { path, body: q, reply: rtx });
                let (code, v) = rrx.recv_timeout(std::time::Duration::from_secs(90)).unwrap_or((504, Value::Null));
                let resp = tiny_http::Response::from_string(v.to_string()).with_status_code(code).with_header("content-type: application/json".parse::<tiny_http::Header>().unwrap());
                let _ = req.respond(resp);
            });
        }
    });
    log::info(format!("test control on 127.0.0.1:{port}"));
}

use std::io::Read;

fn main() {
    let exe = std::env::current_exe().unwrap_or_default();
    let exe_dir = exe.parent().map(Path::to_path_buf).unwrap_or_default();
    let override_profile = std::env::var_os("TRANSLATE_USER_DATA").map(PathBuf::from);
    let user_data = override_profile.clone().unwrap_or_else(|| PathBuf::from(std::env::var_os("APPDATA").unwrap_or_default()).join("Translate"));
    let _ = std::fs::create_dir_all(&user_data);
    log::init(user_data.clone());
    let profile_key = user_data.to_string_lossy().to_string();

    // Launching again = show Settings of the running instance.
    if system::already_running(&profile_key) {
        return;
    }
    if !win::webview2_installed() {
        log::error("WebView2 Runtime not found");
        if win::message_box("Translate", "Translate needs the Microsoft Edge WebView2 Runtime, which is part of Windows 11 and current Windows 10 but is missing on this PC.\n\nOpen the download page now?", true) {
            win::open_path("https://developer.microsoft.com/microsoft-edge/webview2/#download");
        }
        return;
    }

    let test_port: u16 = arg("test-control").and_then(|p| p.parse().ok()).unwrap_or(0);
    // Live verification: a read-only state endpoint (generations, counts, geometry; never candidate text).
    let observe_port: u16 = if test_port != 0 { 0 } else { arg("observe").and_then(|p| p.parse().ok()).unwrap_or(0) };
    let test_source = if test_port != 0 { arg("test-source").unwrap_or_default() } else { String::new() };
    // Lean WebView2: software rendering (as the Electron builds: the GPU process cost memory and CPU for a few small,
    // mostly static windows), and no extra browser services we don't use. --gpu opts back in.
    let mut browser_args = String::from("--disable-features=msWebOOUI,msPdfOOUI,msSmartScreenProtection,SpareRendererForSitePerProcess,CalculateNativeWinOcclusion,MediaSessionService,HardwareMediaKeyHandling");
    if !flag("gpu") {
        browser_args.push_str(" --disable-gpu --disable-gpu-compositing");
    }
    // DevTools access for the test harness only (never in normal runs).
    if let (Some(p), true) = (arg("remote-debugging-port"), test_port != 0) {
        browser_args.push_str(&format!(" --remote-debugging-port={p}"));
    }
    let webview_data = match &override_profile {
        Some(p) => p.join("WebView2"),
        None => PathBuf::from(std::env::var_os("LOCALAPPDATA").unwrap_or_default()).join("Translate").join("WebView2"),
    };
    // Release: the bundled, isolated Python runtime in resources\python; development: TRANSLATE_PYTHON or `python`.
    let bundled = exe_dir.join("resources").join("python").join("TranslateEngine.exe");
    let python = if bundled.exists() { bundled } else { std::env::var_os("TRANSLATE_PYTHON").map(PathBuf::from).unwrap_or_else(|| PathBuf::from("python")) };
    let backend_dir = [exe_dir.join("resources").join("backend")].into_iter().find(|p| p.exists()).or_else(|| std::env::var_os("TRANSLATE_BACKEND_DIR").map(PathBuf::from)).or_else(|| find_up(&exe_dir, "backend/translate_backend").and_then(|p| p.parent().map(Path::to_path_buf))).unwrap_or_else(|| exe_dir.join("backend"));
    let options = Options {
        test_port,
        observe_port,
        test_source,
        translator_live: test_port != 0 && std::env::args().any(|a| a == "--translator=live"),
        keep_panel: flag("keep-panel"),
        release_ms: arg("release-after-ms").and_then(|v| v.parse().ok()).unwrap_or(180_000),
        push_ms: arg("push-ms").and_then(|v| v.parse().ok()).unwrap_or(33),
        user_data,
        webview_data,
        browser_args,
        exe: exe.clone(),
        login_items: override_profile.is_none() || std::env::var_os("TRANSLATE_LOGIN_ITEM_TEST").is_some(),
        python,
        backend_dir,
    };

    let (tx, rx) = channel::<Ev>();
    let sys_tx = Mutex::new(tx.clone());
    system::start(&profile_key, move |e| {
        let _ = sys_tx.lock().unwrap().send(Ev::Sys(e));
    });

    let core_tx = tx.clone();
    let app = tauri::Builder::default()
        .manage(CoreTx(Mutex::new(tx.clone())))
        .invoke_handler(tauri::generate_handler![ipc])
        .setup(move |app| {
            let handle = app.handle().clone();
            let port = if options.test_port != 0 { options.test_port } else { options.observe_port };
            if port != 0 {
                start_test_control(port, core_tx.clone());
            }
            let host = Host::new(handle, core_tx.clone(), options);
            std::thread::Builder::new().name("core".into()).spawn(move || host.run(rx)).map_err(|e| e.to_string())?;
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("tauri build");
    app.run(|_app, e| {
        // Resident: closing windows never quits; only Quit (app.exit) does.
        if let tauri::RunEvent::ExitRequested { api, code: None, .. } = e {
            api.prevent_exit();
        }
    });
}
