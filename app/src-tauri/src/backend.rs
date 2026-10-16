//! The Python engine process: spawn, JSON Lines framing, stderr → log. Requests, timeouts and restarts are handled
//! by the host's core loop (host.rs), which receives everything here as events. stdout = protocol only.

use crate::log;
use serde_json::{json, Map, Value};
use std::io::{BufRead, BufReader, Read, Write};
use std::os::windows::process::CommandExt;
use std::path::PathBuf;
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::mpsc::Sender;
use std::sync::{Arc, Mutex};

const CREATE_NO_WINDOW: u32 = 0x0800_0000;
const MAX_LINE: usize = 1 << 20; // 1 MiB: anything longer is a framing error, not a message

pub enum BackendEvent {
    Message(u64, Value),
    Exited(u64, Option<i32>),
}

pub struct Spec {
    pub python: PathBuf,
    pub args: Vec<String>,
    pub cwd: PathBuf,
}

pub struct Backend {
    spec: Spec,
    stdin: Arc<Mutex<Option<ChildStdin>>>,
    child: Arc<Mutex<Option<Child>>>,
    pub pid: u32,
    pub epoch: u64,
}

impl Backend {
    pub fn new(spec: Spec) -> Self {
        Backend { spec, stdin: Arc::new(Mutex::new(None)), child: Arc::new(Mutex::new(None)), pid: 0, epoch: 0 }
    }

    pub fn start<E: From<BackendEvent> + Send + 'static>(&mut self, tx: Sender<E>) -> Result<(), String> {
        self.epoch += 1;
        let epoch = self.epoch;
        let mut child = Command::new(&self.spec.python)
            .args(&self.spec.args)
            .current_dir(&self.spec.cwd)
            .env("PYTHONUTF8", "1")
            .env("PYTHONDONTWRITEBYTECODE", "1")
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .creation_flags(CREATE_NO_WINDOW)
            .spawn()
            .map_err(|e| e.to_string())?;
        self.pid = child.id();
        let stdout = child.stdout.take().unwrap();
        let stderr = child.stderr.take().unwrap();
        *self.stdin.lock().unwrap() = child.stdin.take();
        *self.child.lock().unwrap() = Some(child);

        let out_tx = tx.clone();
        std::thread::spawn(move || {
            let mut r = BufReader::new(stdout);
            let mut line = Vec::new();
            loop {
                line.clear();
                // Bounded read of one line.
                let mut limited = (&mut r).take(MAX_LINE as u64 + 1);
                match limited.read_until(b'\n', &mut line) {
                    Ok(0) => break,
                    Ok(_) => {}
                    Err(_) => break,
                }
                if line.len() > MAX_LINE && !line.ends_with(b"\n") {
                    log::error("backend line too long; dropping it");
                    // Skip to the end of this line.
                    let mut rest = Vec::new();
                    if r.read_until(b'\n', &mut rest).unwrap_or(0) == 0 {
                        break;
                    }
                    continue;
                }
                let text = String::from_utf8_lossy(&line);
                let text = text.trim();
                if text.is_empty() {
                    continue;
                }
                match serde_json::from_str::<Value>(text) {
                    Ok(v) => {
                        if out_tx.send(E::from(BackendEvent::Message(epoch, v))).is_err() {
                            break;
                        }
                    }
                    Err(_) => log::error(format!("unparseable backend line ({} chars)", text.len())),
                }
            }
        });
        std::thread::spawn(move || {
            for l in BufReader::new(stderr).lines().map_while(Result::ok) {
                if !l.trim().is_empty() {
                    log::info(format!("[py] {l}"));
                }
            }
        });
        let child = self.child.clone();
        std::thread::spawn(move || {
            // Wait for exit without holding the lock while blocked.
            let code = loop {
                std::thread::sleep(std::time::Duration::from_millis(200));
                let mut g = child.lock().unwrap();
                match g.as_mut().map(|c| c.try_wait()) {
                    Some(Ok(Some(st))) => {
                        *g = None;
                        break st.code();
                    }
                    Some(Ok(None)) => continue,
                    Some(Err(_)) | None => break None,
                }
            };
            let _ = tx.send(E::from(BackendEvent::Exited(epoch, code)));
        });
        Ok(())
    }

    pub fn send(&self, msg_type: &str, fields: Map<String, Value>) {
        let mut m = fields;
        m.insert("v".into(), json!(1));
        m.insert("type".into(), json!(msg_type));
        let mut line = serde_json::to_string(&Value::Object(m)).unwrap_or_default();
        line.push('\n');
        if let Some(s) = self.stdin.lock().unwrap().as_mut() {
            let _ = s.write_all(line.as_bytes()).and_then(|_| s.flush());
        }
    }

    pub fn running(&self) -> bool {
        self.child.lock().map(|c| c.is_some()).unwrap_or(false)
    }

    /// Ask the engine to shut down; kill it if it hasn't exited after `wait_ms`.
    pub fn stop(&self, wait_ms: u64) {
        self.send("shutdown", Map::from_iter([("id".to_string(), json!(0))]));
        *self.stdin.lock().unwrap() = None; // close stdin
        let deadline = std::time::Instant::now() + std::time::Duration::from_millis(wait_ms);
        while std::time::Instant::now() < deadline {
            if !self.running() {
                return;
            }
            std::thread::sleep(std::time::Duration::from_millis(50));
        }
        if let Some(c) = self.child.lock().unwrap().as_mut() {
            let _ = c.kill();
        }
    }
}
