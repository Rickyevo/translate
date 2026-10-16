//! The host's core: everything Electron's main.ts did, on one thread that owns all state. Events arrive on a channel
//! (engine messages, page IPC, shortcuts, window events, test control) and timers are deadlines in the loop, so no
//! state is shared between threads. Window operations go through Tauri (thread-safe) and Win32 (physical pixels).
//!
//! Resident footprint: no window exists at startup; the panel is created on the first candidate list and released
//! after 3 min without typing; Settings is created on demand and destroyed on close; no tray icon, no polling.

use crate::backend::{Backend, BackendEvent, Spec};
use crate::layout::{self, Dir, Kind, PanelInput, PreviewInput, Rect};
use crate::system::{self, SysEvent};
use crate::{config, log, win};
use serde_json::{json, Map, Value};
use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::mpsc::{Receiver, Sender};
use std::time::{Duration, Instant};
use tauri::{AppHandle, Manager, WebviewUrl, WebviewWindow, WebviewWindowBuilder};

pub const BRIDGE: &str = include_str!("bridge.js");
const M: f64 = 16.0; // transparent margin (CSS px) around panel/preview content
const STALE_MS: u64 = 600;
const INSERT_NOTICE: &[(&str, &str)] = &[("unavailable", "unavailable"), ("ime", "notice.imeBusy"), ("modifiers", "notice.releaseKeys"), ("denied", "notice.denied")];

pub enum Ev {
    Backend(BackendEvent),
    Ipc { label: String, ch: String, args: Vec<Value>, reply: Option<Sender<Value>> },
    Sys(SysEvent),
    Test { path: String, body: Value, reply: Sender<(u16, Value)> },
    Destroyed(String),
    Rescaled(String),
    PreviewCreated(String),
}
impl From<BackendEvent> for Ev {
    fn from(e: BackendEvent) -> Self {
        Ev::Backend(e)
    }
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum Timer {
    Push,
    Stale(i64),
    Release,
    RestartBackend,
}

pub struct Options {
    pub test_port: u16,
    pub observe_port: u16,
    pub test_source: String,
    pub translator_live: bool,
    pub keep_panel: bool,
    pub release_ms: u64,
    pub push_ms: u64,
    pub user_data: PathBuf,
    pub webview_data: PathBuf,
    pub browser_args: String,
    pub exe: PathBuf,
    pub login_items: bool,
    pub python: PathBuf,
    pub backend_dir: PathBuf,
}

type Done = Box<dyn FnOnce(&mut Host, Value) + Send>;

pub struct Host {
    app: AppHandle,
    tx: Sender<Ev>,
    o: Options,
    backend: Backend,
    restarts: Vec<Instant>,
    stopping: bool,
    next_id: u64,
    pending: HashMap<u64, (Instant, Done)>,
    timers: Vec<(Instant, Timer)>,

    settings: Map<String, Value>,
    draft: Option<Map<String, Value>>,
    legacy_key: Option<(String, String)>,
    paused: bool,
    hidden: bool,
    list: Option<Value>, // CandidateList as the UI expects it: { gen, pinyin, items, banner }
    composition: i64,
    bar: Option<Rect>,
    canvas: Option<Rect>,
    caret: Option<Rect>,
    measured: bool,
    dir: Dir,
    band: Option<Rect>,
    panel: Option<WebviewWindow>,
    panel_hwnd: isize,
    preview: Option<WebviewWindow>,
    preview_hwnd: isize,
    settings_win: Option<WebviewWindow>,
    settings_show_inactive: bool,
    settings_size: (f64, f64),
    settings_fits: u32,
    content: (f64, f64, f64, f64), // CSS px: w, h, extent w, extent h
    rows: Value,
    preview_need: Value,
    placement_kind: Option<Kind>,
    last_place_key: String,
    shortcuts_on: bool,
    translation_mode: String,
    ime_state: String,
    ime_name: String,
    service_state: String,
    last_insert: Value,
    panel_created: u64,
    panel_hides: u64,
    window_resizes: u64,
    panel_seq: u64,
}

fn obj(v: Value) -> Map<String, Value> {
    v.as_object().cloned().unwrap_or_default()
}

fn rect_of(v: &Value) -> Option<Rect> {
    Some(Rect::new(v.get("x")?.as_f64()?, v.get("y")?.as_f64()?, v.get("w")?.as_f64()?, v.get("h")?.as_f64()?))
}

fn rjson(r: &Rect) -> Value {
    json!({ "x": r.x.round(), "y": r.y.round(), "w": r.w.round(), "h": r.h.round() })
}

impl Host {
    pub fn new(app: AppHandle, tx: Sender<Ev>, o: Options) -> Self {
        let loaded = config::load(&o.user_data);
        let mut args: Vec<String> = ["-E", "-s", "-B", "-m", "translate_backend"].iter().map(|s| s.to_string()).collect();
        if o.test_port != 0 {
            args.push("--test".into());
            if !o.test_source.is_empty() {
                args.push(format!("--source={}", o.test_source));
            }
            if o.translator_live {
                args.push("--translator=live".into());
            }
        }
        let backend = Backend::new(Spec { python: o.python.clone(), args, cwd: o.backend_dir.clone() });
        Host {
            app,
            tx,
            backend,
            restarts: vec![],
            stopping: false,
            next_id: 1,
            pending: HashMap::new(),
            timers: vec![],
            settings: loaded.settings,
            draft: None,
            legacy_key: loaded.legacy_key,
            paused: false,
            hidden: false,
            list: None,
            composition: 0,
            bar: None,
            canvas: None,
            caret: None,
            measured: true,
            dir: Dir::Below,
            band: None,
            panel: None,
            panel_hwnd: 0,
            preview: None,
            preview_hwnd: 0,
            settings_win: None,
            settings_show_inactive: false,
            settings_size: (860.0, 620.0),
            settings_fits: 0,
            content: (0.0, 0.0, 0.0, 0.0),
            rows: json!([]),
            preview_need: json!({ "wanted": false, "requested": false, "w": 360, "h": 0 }),
            placement_kind: None,
            last_place_key: String::new(),
            shortcuts_on: false,
            translation_mode: "fixture".into(),
            ime_state: "starting".into(),
            ime_name: String::new(),
            service_state: String::new(),
            last_insert: Value::Null,
            panel_created: 0,
            panel_hides: 0,
            window_resizes: 0,
            panel_seq: 0,
            o,
        }
    }

    // ------------------------------------------------------------------------------------------- run loop

    pub fn run(mut self, rx: Receiver<Ev>) {
        self.start_backend();
        self.update_hotkeys();
        self.sync_login_item();
        log::info(format!("started v{} host=tauri webview2", env!("CARGO_PKG_VERSION")));
        loop {
            let now = Instant::now();
            let next = self.timers.iter().map(|t| t.0).chain(self.pending.values().map(|p| p.0)).min();
            let ev = match next {
                Some(t) if t <= now => None,
                Some(t) => match rx.recv_timeout(t - now) {
                    Ok(e) => Some(e),
                    Err(std::sync::mpsc::RecvTimeoutError::Timeout) => None,
                    Err(_) => return,
                },
                None => match rx.recv() {
                    Ok(e) => Some(e),
                    Err(_) => return,
                },
            };
            if let Some(e) = ev {
                self.handle(e);
            }
            self.fire_due();
            if self.stopping && !self.backend.running() && self.pending.is_empty() {
                // quit() already asked the engine to stop
            }
        }
    }

    fn fire_due(&mut self) {
        let now = Instant::now();
        let due: Vec<Timer> = self.timers.iter().filter(|t| t.0 <= now).map(|t| t.1).collect();
        self.timers.retain(|t| t.0 > now);
        for t in due {
            match t {
                Timer::Push => self.send_state(None),
                Timer::Stale(gen) => self.clear_stale(gen),
                Timer::Release => {
                    if self.list.is_none() {
                        self.destroy_panel();
                    }
                }
                Timer::RestartBackend => {
                    if !self.stopping {
                        self.start_backend();
                    }
                }
            }
        }
        let expired: Vec<u64> = self.pending.iter().filter(|(_, p)| p.0 <= now).map(|(id, _)| *id).collect();
        for id in expired {
            if let Some((_, done)) = self.pending.remove(&id) {
                done(self, json!({ "v": 1, "type": "error", "code": "timeout", "message": "The translation engine did not answer" }));
            }
        }
    }

    fn timer(&mut self, after_ms: u64, t: Timer) {
        self.timers.retain(|x| x.1 != t);
        self.timers.push((Instant::now() + Duration::from_millis(after_ms), t));
    }
    fn has_timer(&self, t: Timer) -> bool {
        self.timers.iter().any(|x| x.1 == t)
    }
    fn cancel(&mut self, t: Timer) {
        self.timers.retain(|x| x.1 != t);
    }

    // ------------------------------------------------------------------------------------------- engine

    fn start_backend(&mut self) {
        match self.backend.start(self.tx.clone()) {
            Ok(()) => log::info(format!("backend started pid={}", self.backend.pid)),
            Err(e) => log::error(format!("backend spawn failed: {e}")),
        }
    }

    fn send(&self, t: &str, fields: Value) {
        self.backend.send(t, obj(fields));
    }

    fn request(&mut self, t: &str, fields: Value, timeout_ms: u64, done: Done) {
        let id = self.next_id;
        self.next_id += 1;
        let mut f = obj(fields);
        f.insert("id".into(), json!(id));
        self.pending.insert(id, (Instant::now() + Duration::from_millis(timeout_ms), done));
        self.backend.send(t, f);
    }

    fn backend_config(&self) -> Value {
        let s = &self.settings;
        json!({
            "target": s.get("target"), "count": s.get("count"), "denylist": s.get("denylist"), "localOnly": s.get("localOnly"),
            "localDict": s.get("localDict"), "provider": s.get("provider"), "services": s.get("services"),
            "timeout": s.get("timeout"), "jsonMode": s.get("jsonMode"), "ime": s.get("ime"),
            "dataDir": self.o.user_data.to_string_lossy(), // the encrypted translation cache lives here
        })
    }

    fn on_backend(&mut self, e: BackendEvent) {
        match e {
            BackendEvent::Exited(epoch, code) => {
                if epoch != self.backend.epoch {
                    return;
                }
                log::info(format!("backend exited code={code:?}"));
                let pend: Vec<u64> = self.pending.keys().copied().collect();
                for id in pend {
                    if let Some((_, done)) = self.pending.remove(&id) {
                        done(self, json!({ "v": 1, "type": "error", "code": "backend_exit", "message": "The translation engine stopped" }));
                    }
                }
                if self.stopping {
                    return;
                }
                // Restart with backoff; give up after 5 crashes within a minute.
                let now = Instant::now();
                self.restarts.retain(|t| now.duration_since(*t) < Duration::from_secs(60));
                self.restarts.push(now);
                if self.restarts.len() > 5 {
                    log::error("the translation engine keeps stopping");
                    return;
                }
                let delay = (250u64 << (self.restarts.len() - 1)).min(8000);
                self.timer(delay, Timer::RestartBackend);
            }
            BackendEvent::Message(epoch, m) => {
                if epoch != self.backend.epoch {
                    return;
                }
                if let Some(id) = m.get("id").and_then(Value::as_u64) {
                    if let Some((_, done)) = self.pending.remove(&id) {
                        done(self, m.clone());
                    }
                }
                self.on_message(m);
            }
        }
    }

    fn banner(&self) -> Value {
        if self.translation_mode == "simulated" {
            return json!("simulated");
        }
        match self.service_state.as_str() {
            s @ ("localOnly" | "offline" | "auth" | "failed" | "noService") => json!(s),
            _ => Value::Null,
        }
    }

    fn on_message(&mut self, m: Value) {
        match m.get("type").and_then(Value::as_str).unwrap_or("") {
            "ready" => {
                log::info(format!("backend status {{\"state\":\"ready\",\"info\":{m}}}"));
                self.translation_mode = m.get("translationMode").and_then(Value::as_str).unwrap_or("fixture").to_string();
                if self.list.is_some() {
                    self.end_composition(); // a restarted engine numbers its lists from 1 again
                }
                self.send("config.set", json!({ "config": self.backend_config() }));
                if self.paused {
                    self.send("pause", json!({}));
                }
                if let Some((provider, key)) = self.legacy_key.take() {
                    self.request("secret.set", json!({ "provider": provider, "key": key }), 5000, Box::new(|h: &mut Host, _| config::save(&h.o.user_data, &h.settings)));
                }
            }
            "status" => {
                if let Some(st) = m.get("ime").and_then(|i| i.get("state")).and_then(Value::as_str) {
                    self.ime_state = st.into();
                    if let Some(n) = m["ime"].get("name").and_then(Value::as_str) {
                        if n != self.ime_name {
                            log::info(format!("input method {n}"));
                        }
                        self.ime_name = n.into();
                    }
                    let code = m["ime"].get("code").and_then(Value::as_str).map(|c| format!(" {c}")).unwrap_or_default();
                    log::info(format!("ime {st}{code}"));
                }
                if let Some(st) = m.get("service").and_then(|i| i.get("state")).and_then(Value::as_str) {
                    self.service_state = st.into();
                    log::info(format!("service {st}"));
                    let b = self.banner();
                    if let Some(l) = self.list.as_mut() {
                        if l["banner"] != b {
                            l["banner"] = b;
                            self.push_state();
                        }
                    }
                }
            }
            "candidates" => self.on_candidates(&m),
            "translation" => {
                let gen = m["gen"].as_i64().unwrap_or(-1);
                let n = m["n"].as_i64().unwrap_or(0);
                let Some(l) = self.list.as_mut() else { return };
                if l["gen"].as_i64() != Some(gen) {
                    return; // stale generation
                }
                if let Some(items) = l["items"].as_array_mut() {
                    for it in items.iter_mut() {
                        if it["n"].as_i64() == Some(n) {
                            let prev = it.get("prev").cloned();
                            let mut x = json!({ "n": n, "text": it["text"], "state": m["state"] });
                            for k in ["translation", "source", "reason"] {
                                let key = if k == "translation" { "text" } else { k };
                                if let Some(v) = m.get(key).filter(|v| !v.is_null()) {
                                    x[k] = v.clone();
                                }
                            }
                            if m["state"] == "loading" {
                                if let Some(p) = prev {
                                    x["prev"] = p;
                                }
                            }
                            *it = x;
                        }
                    }
                }
                self.push_state();
            }
            "composition.end" => {
                if self.list.as_ref().and_then(|l| l["gen"].as_i64()) == m["gen"].as_i64() {
                    self.end_composition();
                }
            }
            "insert.result" => {
                self.last_insert = json!({ "ok": m["ok"].as_bool().unwrap_or(false), "error": m["error"], "gen": m["gen"], "n": m["n"] });
                // A stale list is replaced a few ms later anyway; saying so would only be noise.
                let err = m["error"].as_str().unwrap_or("");
                if !m["ok"].as_bool().unwrap_or(false) && err != "stale" {
                    let key = INSERT_NOTICE.iter().find(|(e, _)| *e == err).map(|(_, k)| *k).unwrap_or("notice.notInserted");
                    self.send_state(Some(json!({ "key": key })));
                }
            }
            _ => {}
        }
    }

    fn on_candidates(&mut self, m: &Value) {
        if self.paused {
            return;
        }
        let gen = m["gen"].as_i64().unwrap_or(0);
        let cur = self.list.as_ref().and_then(|l| l["gen"].as_i64());
        if cur.map(|c| gen < c).unwrap_or(false) {
            return; // out of order: never go back to an older list
        }
        let is_new = cur != Some(gen);
        if is_new {
            // Within a composition, a row still translating keeps showing (dimmed) what it showed for the previous
            // keystroke for ≤ STALE_MS, instead of flashing to a placeholder on every keystroke.
            let before = self.list.clone();
            let mut any_prev = false;
            let items: Vec<Value> = m["items"]
                .as_array()
                .cloned()
                .unwrap_or_default()
                .into_iter()
                .map(|i| {
                    let n = i["n"].as_i64().unwrap_or(0);
                    let mut x = json!({ "n": n, "text": i["text"], "state": i["state"] });
                    if i["state"] == "loading" {
                        if let Some(old) = before.as_ref().and_then(|b| b["items"].get((n - 1) as usize)) {
                            let p = if old["state"] == "done" { old.get("translation").cloned() } else { old.get("prev").cloned() };
                            if let Some(p) = p.filter(|p| p.is_string()) {
                                x["prev"] = p;
                                any_prev = true;
                            }
                        }
                    }
                    x
                })
                .collect();
            if any_prev {
                self.timer(STALE_MS, Timer::Stale(gen));
            }
            if self.list.is_none() {
                self.composition += 1;
            }
            self.list = Some(json!({ "gen": gen, "pinyin": m["pinyin"], "items": items, "banner": self.banner() }));
        } // same gen: the IME window moved; keep the items (and translations) we already have
        let a = &m["anchor"];
        self.bar = rect_of(a);
        self.canvas = a.get("canvas").and_then(rect_of);
        self.caret = a.get("caret").and_then(rect_of);
        self.measured = a.get("measured").and_then(Value::as_bool).unwrap_or(true);
        self.ensure_panel();
        self.set_shortcuts(true);
        if is_new {
            self.push_now(); // a keystroke: render at once; repositions need layout only
        }
        self.layout_panel();
    }

    fn clear_stale(&mut self, gen: i64) {
        let Some(l) = self.list.as_mut() else { return };
        if l["gen"].as_i64() != Some(gen) {
            return;
        }
        let mut changed = false;
        if let Some(items) = l["items"].as_array_mut() {
            for it in items.iter_mut() {
                if let Some(o) = it.as_object_mut() {
                    changed |= o.remove("prev").is_some();
                }
            }
        }
        if changed {
            self.push_state();
        }
    }

    fn end_composition(&mut self) {
        self.list = None;
        self.composition += 1;
        if let Some(o) = self.preview_need.as_object_mut() {
            o.insert("wanted".into(), json!(false));
        }
        self.hide_panel();
        self.set_shortcuts(false);
        self.push_state();
    }

    // ------------------------------------------------------------------------------------------- settings

    fn eff(&self) -> Map<String, Value> {
        let mut s = self.settings.clone();
        if let Some(d) = &self.draft {
            for k in ["theme", "textSize", "density", "opacity", "offsetX", "offsetY", "showOriginal", "leadMode", "uiLang"] {
                if let Some(v) = d.get(k) {
                    s.insert(k.into(), v.clone());
                }
            }
        }
        s
    }

    fn theme(&self) -> &'static str {
        match config::get_s(&self.eff(), "theme", "system") {
            "dark" => "dark",
            "light" => "light",
            _ => {
                if win::system_dark() {
                    "dark"
                } else {
                    "light"
                }
            }
        }
    }

    fn save_settings(&mut self, s: Map<String, Value>, done: Box<dyn FnOnce(&mut Host) + Send>) {
        // A newly typed key goes to the engine, which stores it in Windows Credential Manager; it is not kept here.
        let key = s.get("apiKey").and_then(Value::as_str).map(str::trim).unwrap_or("").to_string();
        let finish = move |h: &mut Host, s: Map<String, Value>| {
            let mut s = s;
            s.insert("apiKey".into(), json!(""));
            h.settings = s;
            h.draft = None;
            config::save(&h.o.user_data, &h.settings);
            h.sync_login_item();
            h.send("config.set", json!({ "config": h.backend_config() }));
            h.update_hotkeys();
            h.push_state();
            h.layout_panel();
            done(h);
        };
        if key.is_empty() {
            finish(self, s);
        } else {
            let provider = s.get("provider").cloned().unwrap_or(json!("openai"));
            self.request("secret.set", json!({ "provider": provider, "key": key }), 10_000, Box::new(move |h: &mut Host, _| finish(h, s)));
        }
    }

    /// Start with Windows: the per-user Run entry for this exe. Synced at every start and on Save, so a moved portable
    /// copy re-registers its new path. Test and verification runs (isolated profile) never touch it, except the
    /// autostart test itself (TRANSLATE_LOGIN_ITEM_TEST).
    fn sync_login_item(&self) {
        if !self.o.login_items {
            return;
        }
        let want = config::get_b(&self.settings, "autostart", true);
        if win::set_run_entry(want, &self.o.exe.to_string_lossy()) {
            log::info(format!("start with Windows: {}", if want { "on" } else { "off" }));
        } else {
            log::warn("start with Windows: registry write failed");
        }
    }

    // ------------------------------------------------------------------------------------------- render scheduling

    /// A new list (a keystroke) is pushed at once; everything else (translations arriving one by one) is coalesced to
    /// one push per 33 ms. Notices are sent immediately.
    fn push_now(&mut self) {
        self.cancel(Timer::Push);
        self.send_state(None);
    }
    fn push_state(&mut self) {
        if !self.has_timer(Timer::Push) {
            self.timer(self.o.push_ms, Timer::Push);
        }
    }
    fn panel_state(&self, notice: Option<Value>) -> Value {
        let mut st = json!({ "list": self.list, "settings": self.eff(), "theme": self.theme(), "paused": self.paused, "hidden": self.hidden, "composition": self.composition });
        if let Some(n) = notice {
            st["notice"] = n;
        }
        st
    }
    fn send_state(&mut self, notice: Option<Value>) {
        let st = self.panel_state(notice);
        if let Some(p) = &self.panel {
            emit(p, "state", &st);
        }
    }

    // ------------------------------------------------------------------------------------------- windows

    fn ensure_panel(&mut self) {
        self.cancel(Timer::Release);
        if self.panel.is_some() {
            return;
        }
        self.panel_seq += 1;
        let label = format!("panel-{}", self.panel_seq);
        let q = if self.o.test_port != 0 || self.o.observe_port != 0 { "?test=1" } else { "" };
        let app = self.app.clone();
        let tx = self.tx.clone();
        let (args, data) = (self.o.browser_args.clone(), self.o.webview_data.clone());
        let preview_seq = std::sync::Arc::new(std::sync::atomic::AtomicU64::new(0));
        let b = overlay_builder(&self.app, &self.o, &label, WebviewUrl::App(format!("panel.html{q}").into()))
            .initialization_script(BRIDGE)
            // Only the lead preview may be opened from the panel (window.open('about:blank', 'translate-preview')):
            // a window in the same WebView2 environment, so it shares this page's renderer and React tree.
            .on_new_window(move |url, features| {
                if url.as_str() != "about:blank" {
                    return tauri::webview::NewWindowResponse::Deny;
                }
                let n = preview_seq.fetch_add(1, std::sync::atomic::Ordering::SeqCst) + 1;
                let label = format!("preview-{}-{n}", std::process::id());
                let built = WebviewWindowBuilder::new(&app, &label, WebviewUrl::External("about:blank".parse().unwrap()))
                    .window_features(features)
                    .title("Translate preview")
                    .transparent(true)
                    .decorations(false)
                    .shadow(false)
                    .resizable(false)
                    .skip_taskbar(true)
                    .always_on_top(true)
                    .focused(false)
                    .focusable(false)
                    .visible(false)
                    .inner_size(400.0, 200.0)
                    .data_directory(data.clone())
                    .additional_browser_args(&args)
                    .build();
                match built {
                    Ok(w) => {
                        if let Ok(h) = w.hwnd() {
                            win::make_overlay(h.0 as isize);
                        }
                        let tx2 = tx.clone();
                        let l2 = label.clone();
                        w.on_window_event(move |e| {
                            if let tauri::WindowEvent::Destroyed = e {
                                let _ = tx2.send(Ev::Destroyed(l2.clone()));
                            }
                        });
                        let _ = tx.send(Ev::PreviewCreated(label));
                        tauri::webview::NewWindowResponse::Create { window: w }
                    }
                    Err(e) => {
                        log::error(format!("[panel] preview window failed: {e}"));
                        tauri::webview::NewWindowResponse::Deny
                    }
                }
            });
        match b.build() {
            Ok(w) => {
                let h = w.hwnd().map(|h| h.0 as isize).unwrap_or(0);
                win::make_overlay(h);
                win::set_region(h, &[]); // nothing takes the mouse until laid out
                self.watch(&w);
                self.panel_hwnd = h;
                self.panel = Some(w);
                self.panel_created += 1;
            }
            Err(e) => log::error(format!("[panel] window failed: {e}")),
        }
    }

    fn watch(&self, w: &WebviewWindow) {
        let tx = self.tx.clone();
        let label = w.label().to_string();
        w.on_window_event(move |e| match e {
            tauri::WindowEvent::Destroyed => {
                let _ = tx.send(Ev::Destroyed(label.clone()));
            }
            tauri::WindowEvent::ScaleFactorChanged { .. } => {
                let _ = tx.send(Ev::Rescaled(label.clone()));
            }
            _ => {}
        });
    }

    fn destroy_panel(&mut self) {
        if let Some(p) = self.preview.take() {
            let _ = p.destroy();
        }
        if let Some(p) = self.panel.take() {
            let _ = p.destroy();
        }
        self.panel_hwnd = 0;
        self.preview_hwnd = 0;
        self.content = (0.0, 0.0, 0.0, 0.0);
        self.last_place_key.clear();
    }

    fn hide_panel(&mut self) {
        if self.panel_hwnd != 0 && win::is_visible(self.panel_hwnd) {
            self.panel_hides += 1;
            win::hide(self.panel_hwnd);
        }
        if self.preview_hwnd != 0 && win::is_visible(self.preview_hwnd) {
            win::hide(self.preview_hwnd);
        }
        self.placement_kind = None;
        if !self.o.keep_panel && self.panel.is_some() {
            // Release the panel renderer after a pause in typing; it is recreated on the next list.
            self.timer(self.o.release_ms, Timer::Release);
        }
    }

    /// Largest the panel can be with the current settings (CSS px): Panel.tsx metrics — max width 24.6 × text size; rows
    /// of round(text size × 2.15 | 1.85 compact), 1 px gaps, 4 px padding top and bottom, a 1 px rule, the 24 px footer.
    fn capacity(&self) -> (f64, f64) {
        let s = self.eff();
        let ts = config::get_f(&s, "textSize", 13.0);
        let row = (ts * if config::get_s(&s, "density", "comfortable") == "compact" { 1.85 } else { 2.15 }).round();
        let n = config::get_f(&s, "count", 5.0).clamp(1.0, 9.0);
        ((ts * 24.6).round() + 2.0, 8.0 + n * row + (n - 1.0) + 1.0 + 24.0 + 2.0)
    }

    fn layout_panel(&mut self) {
        let (Some(bar), Some(_)) = (self.bar, self.list.as_ref()) else { return };
        if self.panel_hwnd == 0 || self.hidden || self.content.0 == 0.0 {
            return;
        }
        let s = self.eff();
        let mon = win::monitor_for(&bar);
        let k = mon.scale;
        let (w, h) = ((self.content.0 * k).ceil(), (self.content.1 * k).ceil());
        let p = layout::place_panel(&PanelInput {
            work: mon.work,
            bar,
            canvas: self.canvas,
            caret: self.caret,
            clickable: config::get_b(&s, "clickable", false),
            w,
            h,
            offset_x: (config::get_f(&s, "offsetX", 0.0) * k).round(),
            offset_y: (config::get_f(&s, "offsetY", 4.0) * k).round(),
            scale: k,
        });
        self.dir = p.dir;
        self.band = Some(p.band);
        // The window is sized to the panel's capacity, not to the current content: rows appearing or translations
        // getting longer between keystrokes change only what is drawn inside a stable window (no resize flicker).
        // It still grows for an open menu or larger text.
        let cap = self.capacity();
        let m = (M * k).round();
        let ww = (self.content.2.max(cap.0) * k).ceil() + 2.0 * m;
        let wh = (self.content.3.max(cap.1) * k).ceil() + 2.0 * m;
        if win::set_bounds(self.panel_hwnd, ((p.x - m) as i32, (p.y - m) as i32, ww as i32, wh as i32)) {
            self.window_resizes += 1;
        }
        // Only the drawn panel (+ its 1 px border ring and any open menu) takes the mouse; the margin passes clicks.
        let ring = (2.0 * k).ceil();
        let (rw, rh) = ((self.content.2.max(self.content.0) * k).ceil(), (self.content.3.max(self.content.1) * k).ceil());
        win::set_region(self.panel_hwnd, &[((m - ring) as i32, (m - ring) as i32, (rw + 2.0 * ring) as i32, (rh + 2.0 * ring) as i32)]);
        if !win::is_visible(self.panel_hwnd) {
            win::show_noactivate(self.panel_hwnd);
        }
        self.layout_preview();
    }

    fn content_rect(&self) -> Option<Rect> {
        let r = win::window_rect(self.panel_hwnd)?;
        let k = self.bar.map(|b| win::monitor_for(&b).scale).unwrap_or(1.0);
        let m = (M * k).round();
        Some(Rect::new(r.x + m, r.y + m, (self.content.0 * k).ceil(), (self.content.1 * k).ceil()))
    }

    fn layout_preview(&mut self) {
        let Some(bar) = self.bar else { return };
        if self.panel_hwnd == 0 || self.preview_hwnd == 0 {
            return;
        }
        let wanted = self.preview_need["wanted"].as_bool().unwrap_or(false);
        if !wanted || self.list.is_none() || self.hidden {
            if win::is_visible(self.preview_hwnd) {
                win::hide(self.preview_hwnd);
            }
            self.placement_kind = None;
            return;
        }
        let Some(panel) = self.content_rect() else { return };
        let mon = win::monitor_for(&bar);
        let k = mon.scale;
        let s = self.eff();
        let line_h = ((config::get_f(&s, "textSize", 13.0) + 1.0) * 1.45).round();
        let mut avoid = vec![bar];
        if let Some(b) = self.band {
            avoid.push(b);
        }
        if config::get_b(&s, "clickable", false) {
            if let Some(c) = self.canvas {
                avoid.push(c);
            }
        }
        let pl = layout::place_preview(&PreviewInput {
            work: mon.work,
            panel,
            avoid,
            stack: self.dir,
            width: self.preview_need["w"].as_f64().unwrap_or(380.0) * k,
            need_h: self.preview_need["h"].as_f64().unwrap_or(0.0) * k,
            min_h: (30.0 + 2.0 * line_h + 16.0) * k,
            requested: self.preview_need["requested"].as_bool().unwrap_or(false),
            margin: (8.0 * k).round(),
            gap: (6.0 * k).round(),
        });
        self.placement_kind = Some(pl.kind);
        let msg = json!({ "kind": pl.kind, "h": (pl.rect.h / k).round(), "w": (pl.rect.w / k).round(), "scroll": pl.scroll });
        let key = msg.to_string();
        if key != self.last_place_key {
            self.last_place_key = key;
            if let Some(p) = &self.panel {
                emit(p, "preview:place", &msg);
            }
        }
        if pl.kind == Kind::None {
            if win::is_visible(self.preview_hwnd) {
                win::hide(self.preview_hwnd);
            }
            return;
        }
        let m = (M * k).round();
        let r = pl.rect;
        if win::set_bounds(self.preview_hwnd, ((r.x - m) as i32, (r.y - m) as i32, (r.w + 2.0 * m) as i32, (r.h + 2.0 * m) as i32)) {
            self.window_resizes += 1;
        }
        let ring = (2.0 * k).ceil();
        win::set_region(self.preview_hwnd, &[((m - ring) as i32, (m - ring) as i32, (r.w + 2.0 * ring) as i32, (r.h + 2.0 * ring) as i32)]);
        if !win::is_visible(self.preview_hwnd) {
            win::show_noactivate(self.preview_hwnd);
        }
    }

    fn open_settings(&mut self, page: Option<String>, inactive: bool) {
        if let Some(w) = &self.settings_win {
            let _ = w.unminimize();
            let _ = w.show();
            let _ = w.set_focus();
            return;
        }
        // 860 × 620 where it fits; on small or high-scaling screens it shrinks to the screen it opens on, and can be
        // resized — the pages scroll.
        let mon = win::monitor_at_cursor();
        let k = mon.scale;
        let (ww, wh) = ((860.0f64).min(mon.work.w / k - 24.0), (620.0f64).min(mon.work.h / k - 24.0));
        let dark = self.theme() == "dark";
        let q = page.map(|p| format!("?page={p}")).unwrap_or_default();
        let b = WebviewWindowBuilder::new(&self.app, "settings", WebviewUrl::App(format!("settings.html{q}").into()))
            .title("Translate")
            .decorations(false)
            .resizable(true)
            .maximizable(false)
            .inner_size(ww, wh)
            .min_inner_size(720f64.min(ww), 440f64.min(wh))
            .position((mon.work.x + (mon.work.w - ww * k) / 2.0) / k, (mon.work.y + (mon.work.h - wh * k) / 2.0) / k)
            .visible(false)
            .focused(!inactive)
            .background_color(if dark { tauri::window::Color(0x1d, 0x21, 0x27, 255) } else { tauri::window::Color(0xf4, 0xf6, 0xf8, 255) })
            .data_directory(self.o.webview_data.clone())
            .additional_browser_args(&self.o.browser_args)
            .initialization_script(BRIDGE)
            .on_navigation(|u| allowed_url(u));
        match b.build() {
            Ok(w) => {
                // Our own title bar (the page draws it): drop the native one, which the builder option alone left on
                // this resizable window.
                let _ = w.set_decorations(false);
                self.watch(&w);
                self.settings_show_inactive = inactive;
                self.settings_size = (ww, wh);
                self.settings_fits = 0;
                self.settings_win = Some(w);
            }
            Err(e) => log::error(format!("[settings] window failed: {e}")),
        }
    }

    /// Without a native frame, Tauri's size bookkeeping for a resizable window is off by the caption height on Windows,
    /// so the page reports its real viewport and the window is sized (Win32, physical px) to give exactly the intended
    /// one. Only while the window is new: later resizes are the user's.
    fn fit_settings(&mut self, vw: f64, vh: f64) {
        let Some(w) = &self.settings_win else { return };
        if self.settings_fits >= 3 || vw <= 0.0 || vh <= 0.0 {
            return;
        }
        let (tw, th) = self.settings_size;
        if (vw - tw).abs() <= 0.5 && (vh - th).abs() <= 0.5 {
            self.settings_fits = 3; // right: done
            return;
        }
        self.settings_fits += 1;
        let (Ok(h), Ok(k)) = (w.hwnd(), w.scale_factor()) else { return };
        let h = h.0 as isize;
        if let Some(r) = win::window_rect(h) {
            let (nw, nh) = (r.w + ((tw - vw) * k).round(), r.h + ((th - vh) * k).round());
            win::resize_keep_center(h, &r, nw as i32, nh as i32);
        }
    }

    // ------------------------------------------------------------------------------------------- shortcuts

    fn global_names(&self) -> Vec<String> {
        let sc = self.settings.get("shortcuts").cloned().unwrap_or(json!({}));
        vec![sc["pause"].as_str().unwrap_or("Ctrl+Alt+P").to_string(), sc["settings"].as_str().unwrap_or("Ctrl+Alt+O").to_string()]
    }

    fn update_hotkeys(&self) {
        let mut names = self.global_names();
        if self.shortcuts_on {
            for k in 1..=9 {
                names.push(format!("Alt+{k}"));
                names.push(format!("Alt+Shift+{k}"));
            }
            for n in ["Alt+0", "Alt+`", "Alt+Down", "Alt+Up", "Alt+PageDown", "Alt+PageUp"] {
                names.push(n.into());
            }
        }
        system::set_hotkeys(names);
    }

    fn set_shortcuts(&mut self, on: bool) {
        if on == self.shortcuts_on {
            return;
        }
        self.shortcuts_on = on;
        self.update_hotkeys();
    }

    fn on_hotkey(&mut self, name: &str) {
        let g = self.global_names();
        if name == g[0] {
            return self.set_paused(!self.paused);
        }
        if name == g[1] {
            return self.open_settings(None, false);
        }
        let gen = self.list.as_ref().and_then(|l| l["gen"].as_i64());
        if let Some(d) = name.strip_prefix("Alt+Shift+") {
            if let (Some(gen), Ok(n)) = (gen, d.parse::<i64>()) {
                self.copy(gen, n);
            }
            return;
        }
        let key = |a: Value| a;
        match name {
            "Alt+0" => self.toggle_hidden(),
            "Alt+`" => self.panel_key(key(json!({ "action": "togglePreview" }))),
            "Alt+Down" => self.panel_key(json!({ "action": "step", "d": 1 })),
            "Alt+Up" => self.panel_key(json!({ "action": "step", "d": -1 })),
            "Alt+PageDown" => self.panel_key(json!({ "action": "scroll", "d": 1 })),
            "Alt+PageUp" => self.panel_key(json!({ "action": "scroll", "d": -1 })),
            _ => {
                if let (Some(gen), Some(Ok(n))) = (gen, name.strip_prefix("Alt+").map(|d| d.parse::<i64>())) {
                    self.send("insert", json!({ "gen": gen, "n": n }));
                }
            }
        }
    }

    fn panel_key(&self, k: Value) {
        if let Some(p) = &self.panel {
            emit(p, "key", &k);
        }
    }

    fn toggle_hidden(&mut self) {
        self.hidden = !self.hidden;
        if self.hidden {
            self.hide_panel();
        }
        self.push_state();
        self.layout_panel();
    }

    fn set_paused(&mut self, p: bool) {
        self.paused = p;
        self.send(if p { "pause" } else { "resume" }, json!({}));
        if p {
            self.end_composition();
        }
        if let Some(w) = &self.settings_win {
            emit(w, "paused", &json!(p));
        }
    }

    fn copy(&mut self, gen: i64, n: i64) {
        let it = self.list.as_ref().filter(|l| l["gen"].as_i64() == Some(gen)).and_then(|l| l["items"].get((n - 1).max(0) as usize).cloned());
        match it {
            Some(it) if it["state"] == "done" && it["translation"].is_string() => {
                let text = it["translation"].as_str().unwrap().to_string();
                win::set_clipboard(&text);
                self.send_state(Some(json!({ "key": "notice.copiedText", "text": text })));
            }
            _ => self.send_state(Some(json!({ "key": "unavailable" }))),
        }
    }

    fn quit(&mut self) {
        self.stopping = true;
        system::set_hotkeys(vec![]);
        self.backend.stop(1500);
        self.app.exit(0);
    }

    // ------------------------------------------------------------------------------------------- events

    fn handle(&mut self, e: Ev) {
        match e {
            Ev::Backend(b) => self.on_backend(b),
            Ev::Ipc { label, ch, args, reply } => self.on_ipc(&label, &ch, args, reply),
            Ev::Sys(SysEvent::Hotkey(n)) => self.on_hotkey(&n),
            Ev::Sys(SysEvent::OpenSettings) => self.open_settings(None, false),
            Ev::Sys(SysEvent::ThemeChanged) => {
                self.push_state();
                if let Some(w) = &self.settings_win {
                    emit(w, "theme", &json!(self.theme()));
                }
            }
            Ev::Test { path, body, reply } => self.on_test(&path, body, reply),
            Ev::Destroyed(label) => {
                if self.panel.as_ref().map(|p| p.label() == label).unwrap_or(false) {
                    self.panel = None;
                    self.panel_hwnd = 0;
                    // A recreated renderer must report its own size before the window is shown (no blank frame).
                    self.content = (0.0, 0.0, 0.0, 0.0);
                    self.last_place_key.clear();
                    if let Some(p) = self.preview.take() {
                        let _ = p.destroy();
                    }
                    self.preview_hwnd = 0;
                } else if self.preview.as_ref().map(|p| p.label() == label).unwrap_or(false) {
                    self.preview = None;
                    self.preview_hwnd = 0;
                } else if label == "settings" {
                    self.settings_win = None;
                    // Closing without saving = Cancel: live-previewed values revert on the panel.
                    if self.draft.take().is_some() {
                        self.push_state();
                        self.layout_panel();
                    }
                }
            }
            Ev::Rescaled(label) => {
                // Moving to a monitor with another scale: Windows resizes the window; put back our own bounds.
                if self.panel.as_ref().map(|p| p.label() == label).unwrap_or(false) {
                    self.layout_panel();
                }
            }
            Ev::PreviewCreated(label) => {
                if let Some(w) = self.app.get_webview_window(&label) {
                    self.preview_hwnd = w.hwnd().map(|h| h.0 as isize).unwrap_or(0);
                    win::set_region(self.preview_hwnd, &[]);
                    self.preview = Some(w);
                    // The renderer asked for the preview before this window existed; place it now.
                    self.last_place_key.clear();
                    self.layout_preview();
                }
            }
        }
    }

    fn reply_with(reply: Option<Sender<Value>>, v: Value) {
        if let Some(r) = reply {
            let _ = r.send(v);
        }
    }

    fn on_ipc(&mut self, label: &str, ch: &str, args: Vec<Value>, reply: Option<Sender<Value>>) {
        let a = |i: usize| args.get(i).cloned().unwrap_or(Value::Null);
        let from_panel = label.starts_with("panel-");
        match ch {
            "hello" => {
                if from_panel {
                    self.send_state(None);
                } else if label == "settings" {
                    self.fit_settings(a(0).as_f64().unwrap_or(0.0), a(1).as_f64().unwrap_or(0.0));
                    if let Some(w) = &self.settings_win {
                        if self.settings_show_inactive {
                            if let Ok(h) = w.hwnd() {
                                win::show_noactivate(h.0 as isize);
                            }
                        } else {
                            let _ = w.show();
                            let _ = w.set_focus();
                        }
                    }
                }
                Self::reply_with(reply, Value::Null)
            }
            "viewport" => {
                if label == "settings" {
                    self.fit_settings(a(0).as_f64().unwrap_or(0.0), a(1).as_f64().unwrap_or(0.0));
                }
                Self::reply_with(reply, Value::Null)
            }
            "panel:size" if from_panel => {
                let f = |i: usize| a(i).as_f64().unwrap_or(0.0).ceil();
                let (w, h) = (f(0), f(1));
                let next = (w, h, f(2).max(w), f(3).max(h));
                if next != self.content {
                    self.content = next;
                    self.layout_panel();
                }
                Self::reply_with(reply, Value::Null)
            }
            "panel:rows" => {
                self.rows = a(0);
                Self::reply_with(reply, Value::Null)
            }
            "mouse" => Self::reply_with(reply, Value::Null), // the window region decides what takes the mouse
            "panel:insert" => {
                self.send("insert", json!({ "gen": a(0), "n": a(1) }));
                Self::reply_with(reply, Value::Null)
            }
            "panel:copy" => {
                self.copy(a(0).as_i64().unwrap_or(-1), a(1).as_i64().unwrap_or(0));
                Self::reply_with(reply, Value::Null)
            }
            "panel:retry" => {
                self.send("retry", json!({ "gen": a(0), "n": a(1) }));
                Self::reply_with(reply, Value::Null)
            }
            "preview:need" => {
                self.preview_need = a(0);
                self.layout_preview();
                Self::reply_with(reply, Value::Null)
            }
            "settings:get" => {
                let mut saved = self.settings.clone();
                saved.insert("apiKey".into(), json!(""));
                Self::reply_with(reply, json!({ "saved": saved, "theme": self.theme(), "paused": self.paused, "version": env!("CARGO_PKG_VERSION") }))
            }
            "settings:save" => {
                let s = obj(a(0));
                self.save_settings(s, Box::new(move |_| Self::reply_with(reply, Value::Null)));
            }
            "settings:draft" => {
                self.draft = Some(obj(a(0)));
                self.push_state();
                self.layout_panel();
                Self::reply_with(reply, Value::Null)
            }
            "svc:test" | "svc:models" => {
                let t = if ch == "svc:test" { "service.test" } else { "service.models" };
                self.request(t, json!({ "service": a(0), "key": a(1) }), 60_000, Box::new(move |_, m| Self::reply_with(reply, m)));
            }
            "svc:keys" => self.request("secret.status", json!({}), 3000, Box::new(move |_, m| Self::reply_with(reply, m.get("keys").cloned().unwrap_or(json!({}))))),
            "cache:stats" => self.request("cache.stats", json!({}), 3000, Box::new(move |_, m| Self::reply_with(reply, m))),
            "cache:clear" => self.request("cache.clear", json!({}), 3000, Box::new(move |_, m| Self::reply_with(reply, m))),
            "status:get" => Self::reply_with(reply, json!({ "ime": self.ime_state, "service": self.service_state, "imeName": self.ime_name })),
            "logs:open" => {
                win::open_path(&self.o.user_data.join("logs").to_string_lossy());
                Self::reply_with(reply, Value::Null)
            }
            "paused" => {
                self.set_paused(a(0).as_bool().unwrap_or(false));
                Self::reply_with(reply, Value::Null)
            }
            "window" => {
                if let Some(w) = self.app.get_webview_window(label) {
                    match a(0).as_str().unwrap_or("") {
                        "close" => {
                            let _ = w.close();
                        }
                        "minimize" => {
                            let _ = w.minimize();
                        }
                        "drag" => {
                            let _ = w.start_dragging();
                        }
                        _ => {}
                    }
                }
                Self::reply_with(reply, Value::Null)
            }
            "quit" => {
                Self::reply_with(reply, Value::Null);
                self.quit();
            }
            "log" => {
                log::warn(format!("[{}] {}", label.split('-').next().unwrap_or(label), a(0).as_str().unwrap_or("")));
                Self::reply_with(reply, Value::Null)
            }
            _ => Self::reply_with(reply, Value::Null),
        }
    }

    // ------------------------------------------------------------------------------------------- test control

    fn state_json(&self) -> Value {
        let k = self.bar.map(|b| win::monitor_for(&b).scale).unwrap_or(1.0);
        let dip = |r: &Rect| json!({ "x": (r.x / k).round(), "y": (r.y / k).round(), "width": (r.w / k).round(), "height": (r.h / k).round() });
        let phys = |r: &Rect| json!({ "x": r.x.round(), "y": r.y.round(), "width": r.w.round(), "height": r.h.round() });
        let pb = if self.panel_hwnd != 0 { win::window_rect(self.panel_hwnd) } else { None };
        let rows: Vec<Value> = match (pb, self.rows.as_array()) {
            (Some(pb), Some(rows)) => rows
                .iter()
                .map(|r| {
                    let f = |n: &str| r[n].as_f64().unwrap_or(0.0) * k;
                    let rr = Rect::new(pb.x + f("x"), pb.y + f("y"), f("w"), f("h"));
                    json!({ "n": r["n"], "dip": dip(&rr), "phys": phys(&rr) })
                })
                .collect(),
            _ => vec![],
        };
        let content = self.content_rect().map(|c| json!({ "x": (c.x / k).round(), "y": (c.y / k).round(), "w": (c.w / k).round(), "h": (c.h / k).round() }));
        let prb = if self.preview_hwnd != 0 && win::is_visible(self.preview_hwnd) { win::window_rect(self.preview_hwnd) } else { None };
        let m = (M * k).round();
        let items = self.list.as_ref().and_then(|l| l["items"].as_array().cloned()).unwrap_or_default();
        let field = |f: &str| -> Value { if self.list.is_some() { json!(items.iter().map(|i| i.get(f).cloned().unwrap_or(Value::Null)).collect::<Vec<_>>()) } else { Value::Null } };
        json!({
            "panel": pb.map(|pb| json!({ "visible": win::is_visible(self.panel_hwnd), "bounds": dip(&pb), "content": content, "phys": phys(&pb) })),
            "rows": rows,
            "preview": prb.map(|p| json!({ "kind": self.placement_kind, "bounds": dip(&p), "phys": phys(&p), "contentPhys": phys(&Rect::new(p.x + m, p.y + m, p.w - 2.0 * m, p.h - 2.0 * m)) })),
            "settingsOpen": self.settings_win.is_some(),
            "list": self.list.as_ref().map(|l| json!({ "gen": l["gen"], "states": items.iter().map(|i| i["state"].clone()).collect::<Vec<_>>(), "count": items.len(), "banner": l["banner"], "sim": items.iter().map(|i| i["source"] == "sim").collect::<Vec<_>>() })),
            "composition": self.composition,
            "hidden": self.hidden,
            "panelExists": self.panel.is_some(),
            "panelCreated": self.panel_created,
            "panelHides": self.panel_hides,
            "windowResizes": self.window_resizes,
            "anchorDip": self.bar.map(|b| json!({ "x": (b.x / k).round(), "y": (b.y / k).round(), "w": (b.w / k).round(), "h": (b.h / k).round() })),
            "canvasDip": self.canvas.map(|c| json!({ "x": (c.x / k).round(), "y": (c.y / k).round(), "w": (c.w / k).round(), "h": (c.h / k).round() })),
            "anchorPhys": self.bar.map(|b| rjson(&b)),
            "caretPhys": self.caret.map(|c| rjson(&c)),
            "bandPhys": self.band.map(|c| rjson(&c)),
            "barMeasured": self.measured,
            "dir": if self.dir == Dir::Below { "below" } else { "above" },
            "scale": k,
            "imeState": self.ime_state,
            "imeName": self.ime_name,
            "translationMode": self.translation_mode,
            "lastInsert": self.last_insert,
            "serviceState": self.service_state,
            "mouseLog": [],
            "previewExists": self.preview.is_some(),
            "previewWanted": self.preview_need["wanted"],
            "hwnd": { "panel": self.panel_hwnd, "preview": self.preview_hwnd },
            "sources": field("source"),
            "reasons": field("reason"),
            "stale": if self.list.is_some() { json!(items.iter().map(|i| i["state"] == "loading" && i.get("prev").is_some()).collect::<Vec<_>>()) } else { Value::Null },
            "backendPid": self.backend.pid,
            "mainPid": std::process::id(),
            "paused": self.paused,
            "host": "tauri",
        })
    }

    fn on_test(&mut self, path: &str, q: Value, reply: Sender<(u16, Value)>) {
        let read_only = self.o.test_port == 0;
        if read_only && !["/state", "/pids", "/quit"].contains(&path) {
            let _ = reply.send((403, Value::Null));
            return;
        }
        let ok = |v: Value| (200u16, v);
        let fwd = |reply: Sender<(u16, Value)>| -> Done { Box::new(move |_, m| { let _ = reply.send((200, m)); }) };
        let gen = || q.get("gen").cloned().filter(|v| !v.is_null());
        match path {
            "/state" => {
                let _ = reply.send(ok(self.state_json()));
            }
            "/pids" => {
                let _ = reply.send(ok(json!({ "main": std::process::id(), "backend": self.backend.pid, "panel": 0, "preview": 0, "settings": 0 })));
            }
            "/compose" => self.request("debug.compose", q.clone(), 3000, fwd(reply)),
            "/end" => self.request("debug.end", json!({}), 3000, fwd(reply)),
            "/foreground" => self.request("debug.foreground", json!({}), 3000, fwd(reply)),
            "/typing" => self.request("debug.typing", q.clone(), 3000, fwd(reply)),
            "/settings/open" => {
                self.open_settings(q.get("page").and_then(Value::as_str).map(String::from), q["inactive"].as_bool().unwrap_or(false));
                let _ = reply.send(ok(json!({ "ok": true })));
            }
            "/settings/close" => {
                if let Some(w) = &self.settings_win {
                    let _ = w.close();
                }
                let _ = reply.send(ok(json!({ "ok": true })));
            }
            "/key" => {
                self.panel_key(q.clone());
                let _ = reply.send(ok(json!({ "ok": true })));
            }
            "/quit" => {
                let _ = reply.send(ok(json!({ "ok": true })));
                self.quit();
            }
            "/wetype" => {
                let t = q["t"].as_str().unwrap_or("").to_string();
                self.request(&format!("debug.wetype.{t}"), q.get("f").cloned().unwrap_or(json!({})), 3000, fwd(reply));
            }
            "/mspy" => {
                let t = q["t"].as_str().unwrap_or("").to_string();
                self.request(&format!("debug.mspy.{t}"), q.get("f").cloned().unwrap_or(json!({})), 3000, fwd(reply));
            }
            "/input" => self.request("debug.input", q.clone(), 3000, fwd(reply)),
            "/insert" => {
                let g = gen().or_else(|| self.list.as_ref().map(|l| l["gen"].clone())).unwrap_or(Value::Null);
                self.request("insert", json!({ "gen": g, "n": q.get("n").cloned().unwrap_or(json!(1)) }), 3000, fwd(reply));
            }
            "/toggle-hidden" => {
                self.toggle_hidden();
                let _ = reply.send(ok(json!({ "ok": true, "hidden": self.hidden })));
            }
            "/pause" => {
                self.set_paused(q["paused"].as_bool().unwrap_or(false));
                let _ = reply.send(ok(json!({ "ok": true, "paused": self.paused })));
            }
            "/settings/save" => {
                // Same path as the settings window's Save (key → vault, config.json without it).
                let mut s = self.settings.clone();
                for (k, v) in obj(q.clone()) {
                    s.insert(k, v);
                }
                self.save_settings(s, Box::new(move |_| { let _ = reply.send((200, json!({ "ok": true }))); }));
            }
            "/settings/set" => {
                for (k, v) in obj(q.clone()) {
                    self.settings.insert(k, v);
                }
                config::save(&self.o.user_data, &self.settings);
                self.push_state();
                self.layout_panel();
                let _ = reply.send(ok(json!({ "ok": true })));
            }
            "/retry" => {
                let g = gen().or_else(|| self.list.as_ref().map(|l| l["gen"].clone())).unwrap_or(Value::Null);
                self.send("retry", json!({ "gen": g, "n": q.get("n").cloned().unwrap_or(json!(1)) }));
                let _ = reply.send(ok(json!({ "ok": true })));
            }
            "/svc-test" => self.request("service.test", q.clone(), 60_000, fwd(reply)),
            "/svc-models" => self.request("service.models", q.clone(), 60_000, fwd(reply)),
            "/cache" => {
                let t = if q["clear"].as_bool().unwrap_or(false) { "cache.clear" } else { "cache.stats" };
                self.request(t, json!({}), 3000, fwd(reply));
            }
            // Replay source only (synthetic candidates): translations, for scoring accuracy against a real service.
            "/translations" if self.o.test_source == "wetype-replay" => {
                let v = self.list.as_ref().map(|l| {
                    json!(l["items"].as_array().cloned().unwrap_or_default().iter().map(|i| json!({ "n": i["n"], "text": i["text"], "translation": i.get("translation").cloned().unwrap_or(Value::Null), "state": i["state"], "source": i.get("source").cloned().unwrap_or(Value::Null), "reason": i.get("reason").cloned().unwrap_or(Value::Null) })).collect::<Vec<_>>())
                });
                let _ = reply.send(ok(v.unwrap_or(Value::Null)));
            }
            _ => {
                let _ = reply.send((404, Value::Null));
            }
        }
    }
}

fn overlay_builder<'a>(app: &'a AppHandle, o: &Options, label: &str, url: WebviewUrl) -> WebviewWindowBuilder<'a, tauri::Wry, AppHandle> {
    WebviewWindowBuilder::new(app, label, url)
        .title("Translate")
        .transparent(true)
        .decorations(false)
        .shadow(false)
        .resizable(false)
        .maximizable(false)
        .minimizable(false)
        .skip_taskbar(true)
        .always_on_top(true)
        .focused(false)
        .focusable(false)
        .visible(false)
        .inner_size(300.0, 220.0)
        .data_directory(o.webview_data.clone())
        .additional_browser_args(&o.browser_args)
        .on_navigation(|u| allowed_url(u))
}

/// Host → page: window.__translateEmit(channel, payload) (see bridge.js).
fn emit(w: &WebviewWindow, ch: &str, payload: &Value) {
    let js = format!("window.__translateEmit && window.__translateEmit({}, {})", json!(ch), payload);
    let _ = w.eval(&js);
}

/// Our pages never navigate: only the app's own files (and the preview's about:blank).
fn allowed_url(u: &tauri::Url) -> bool {
    matches!(u.scheme(), "tauri" | "about") || (u.scheme() == "http" && u.host_str() == Some("tauri.localhost")) || (u.scheme() == "https" && u.host_str() == Some("tauri.localhost"))
}
