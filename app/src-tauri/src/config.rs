//! Settings (config.json) in the user-data folder (%APPDATA%\Translate, the same place the Electron builds used, so
//! settings and cache carry over). Settings stay JSON objects: the UI owns
//! their shape (prototype/src/model.ts); defaults come from the same file via defaults.json.

use serde_json::{json, Map, Value};
use std::fs;
use std::path::Path;

pub const DEFAULTS: &str = include_str!("../defaults.json");

pub fn defaults() -> Map<String, Value> {
    serde_json::from_str::<Value>(DEFAULTS).ok().and_then(|v| v.as_object().cloned()).unwrap_or_default()
}

pub struct Loaded {
    pub settings: Map<String, Value>,
    /// A key found in an older plaintext config.json; moved to Windows Credential Manager once the engine is up.
    pub legacy_key: Option<(String, String)>,
}

pub fn load(dir: &Path) -> Loaded {
    let mut s = defaults();
    let mut legacy_key = None;
    if let Some(mut raw) = fs::read_to_string(dir.join("config.json")).ok().and_then(|t| serde_json::from_str::<Value>(&t).ok()).and_then(|v| v.as_object().cloned()) {
        if let Some(k) = raw.get("apiKey").and_then(Value::as_str).filter(|k| !k.is_empty()) {
            let provider = raw.get("provider").and_then(Value::as_str).unwrap_or("openai").to_string();
            legacy_key = Some((provider, k.to_string()));
        }
        raw.remove("endpoint"); // stage ≤ 4 fields, replaced by provider/services
        raw.remove("model");
        // ≤ 0.1.0 defaulted to 97 % (and allowed 70 %): other apps' text showed through the panel. Opaque by default
        // now, at least 90 % when chosen.
        if let Some(o) = raw.get("opacity").and_then(Value::as_f64) {
            let o = if (o - 0.97).abs() < 1e-9 { 1.0 } else { o.clamp(0.9, 1.0) };
            raw.insert("opacity".into(), json!(o));
        }
        let shortcuts = merge(s.get("shortcuts").cloned().unwrap_or(json!({})), raw.remove("shortcuts").unwrap_or(json!({})));
        for (k, v) in raw {
            s.insert(k, v);
        }
        s.insert("shortcuts".into(), shortcuts);
        if !s.get("services").map(Value::is_object).unwrap_or(false) {
            s.insert("services".into(), json!({}));
        }
    }
    s.insert("apiKey".into(), json!(""));
    Loaded { settings: s, legacy_key }
}

fn merge(base: Value, over: Value) -> Value {
    match (base, over) {
        (Value::Object(mut b), Value::Object(o)) => {
            for (k, v) in o {
                b.insert(k, v);
            }
            Value::Object(b)
        }
        (b, _) => b,
    }
}

/// config.json never holds a key: keys live in Windows Credential Manager (written by the engine).
pub fn save(dir: &Path, s: &Map<String, Value>) {
    let mut s = s.clone();
    s.remove("apiKey");
    let _ = fs::create_dir_all(dir);
    if let Ok(text) = serde_json::to_string_pretty(&s) {
        let _ = fs::write(dir.join("config.json"), text);
    }
}

pub fn get_f(s: &Map<String, Value>, k: &str, d: f64) -> f64 {
    s.get(k).and_then(Value::as_f64).unwrap_or(d)
}
pub fn get_s<'a>(s: &'a Map<String, Value>, k: &str, d: &'a str) -> &'a str {
    s.get(k).and_then(Value::as_str).unwrap_or(d)
}
pub fn get_b(s: &Map<String, Value>, k: &str, d: bool) -> bool {
    s.get(k).and_then(Value::as_bool).unwrap_or(d)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    fn dir(name: &str) -> PathBuf {
        let d = std::env::temp_dir().join(format!("translate-config-test-{name}-{}", std::process::id()));
        let _ = fs::remove_dir_all(&d);
        fs::create_dir_all(&d).unwrap();
        d
    }

    #[test]
    fn defaults_and_migration() {
        let d = dir("mig");
        assert_eq!(get_f(&load(&d).settings, "opacity", 0.0), 1.0);
        for (saved, want) in [(0.97, 1.0), (0.7, 0.9), (0.95, 0.95)] {
            fs::write(d.join("config.json"), format!(r#"{{"opacity":{saved},"shortcuts":{{"pause":"Ctrl+Alt+K"}},"apiKey":"secret","provider":"claude"}}"#)).unwrap();
            let l = load(&d);
            assert_eq!(get_f(&l.settings, "opacity", 0.0), want);
            assert_eq!(l.settings["shortcuts"]["pause"], "Ctrl+Alt+K");
            assert_eq!(l.settings["shortcuts"]["settings"], "Ctrl+Alt+O", "default shortcuts kept");
            assert_eq!(l.settings["apiKey"], "", "never kept in memory settings");
            assert_eq!(l.legacy_key, Some(("claude".into(), "secret".into())));
            save(&d, &l.settings);
            assert!(!fs::read_to_string(d.join("config.json")).unwrap().contains("apiKey"));
        }
        let _ = fs::remove_dir_all(&d);
    }
}
