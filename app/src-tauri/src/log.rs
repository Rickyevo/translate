//! Size-capped diagnostic log in %APPDATA%\Translate\logs. No candidate text is ever written here.

use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::PathBuf;
use std::sync::{Mutex, OnceLock};
use std::time::{SystemTime, UNIX_EPOCH};

const MAX: u64 = 1024 * 1024; // 1 MiB per file, one rotation (≤ 2 MiB total)
static FILE: OnceLock<Mutex<PathBuf>> = OnceLock::new();

pub fn init(dir: PathBuf) {
    let logs = dir.join("logs");
    let _ = fs::create_dir_all(&logs);
    let _ = FILE.set(Mutex::new(logs.join("translate.log")));
}

fn stamp() -> String {
    let d = SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default();
    let (secs, ms) = (d.as_secs() as i64, d.subsec_millis());
    // UTC ISO-8601 without a date library (civil-from-days).
    let days = secs.div_euclid(86_400);
    let rem = secs.rem_euclid(86_400);
    let (h, m, s) = (rem / 3600, (rem % 3600) / 60, rem % 60);
    let z = days + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z - era * 146_097;
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let mo = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = if mo <= 2 { y + 1 } else { y };
    format!("{y:04}-{mo:02}-{d:02}T{h:02}:{m:02}:{s:02}.{ms:03}Z")
}

fn write(level: &str, msg: &str) {
    let Some(f) = FILE.get() else { return };
    let Ok(path) = f.lock() else { return };
    // Logging must never crash the app.
    if fs::metadata(&*path).map(|m| m.len() > MAX).unwrap_or(false) {
        let _ = fs::rename(&*path, path.with_extension("log.1"));
    }
    if let Ok(mut file) = OpenOptions::new().create(true).append(true).open(&*path) {
        let _ = writeln!(file, "{} {} {}", stamp(), level, msg);
    }
}

pub fn info(m: impl AsRef<str>) {
    write("I", m.as_ref())
}
pub fn warn(m: impl AsRef<str>) {
    write("W", m.as_ref())
}
pub fn error(m: impl AsRef<str>) {
    write("E", m.as_ref())
}
