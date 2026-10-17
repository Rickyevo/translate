//! One hidden window on its own thread for what Windows delivers to a window:
//!  - global shortcuts (RegisterHotKey → WM_HOTKEY), registered and unregistered on request;
//!  - single instance: a second Translate.exe finds this window and asks it to open Settings;
//!  - theme changes (WM_SETTINGCHANGE "ImmersiveColorSet").
//! Its class name includes a hash of the user-data folder, so test runs with an isolated profile run side by side
//! with your own copy, as with the Electron builds.

use std::collections::HashMap;
use std::sync::{Mutex, OnceLock};
use windows_sys::Win32::Foundation::{GetLastError, HWND, LPARAM, LRESULT, WPARAM};
use windows_sys::Win32::System::LibraryLoader::GetModuleHandleW;
use windows_sys::Win32::System::Threading::CreateMutexW;
use windows_sys::Win32::UI::Input::KeyboardAndMouse::{RegisterHotKey, UnregisterHotKey};
use windows_sys::Win32::UI::WindowsAndMessaging::*;

pub enum SysEvent {
    Hotkey(String),
    /// The shortcuts that could not be registered (another app holds them), whenever that set changes.
    HotkeysUnavailable(Vec<String>),
    OpenSettings,
    ThemeChanged,
}

const WM_APP_OPEN: u32 = WM_APP + 1;
const WM_APP_HOTKEYS: u32 = WM_APP + 2;
const RETRY_TIMER: usize = 7;

struct Shared {
    tx: Box<dyn Fn(SysEvent) + Send>,
    wanted: Vec<String>,
    registered: HashMap<i32, String>,
    retries: u32,
    unavailable: Vec<String>,
}
static SHARED: OnceLock<Mutex<Shared>> = OnceLock::new();
static HWND_CELL: OnceLock<isize> = OnceLock::new();

fn wide(s: &str) -> Vec<u16> {
    s.encode_utf16().chain(std::iter::once(0)).collect()
}

pub fn fnv(s: &str) -> u32 {
    s.to_lowercase().bytes().fold(0x811c9dc5u32, |h, b| (h ^ b as u32).wrapping_mul(0x01000193))
}

fn class_name(profile: &str) -> String {
    format!("TranslateHost-{:08x}", fnv(profile))
}

/// True when another Translate with this profile is already running; it has been asked to open Settings.
pub fn already_running(profile: &str) -> bool {
    let name = wide(&format!("Local\\Translate-{:08x}", fnv(profile)));
    unsafe {
        let m = CreateMutexW(std::ptr::null(), 1, name.as_ptr());
        if !m.is_null() && GetLastError() == 183 {
            // ERROR_ALREADY_EXISTS: hand off to the running instance (it may still be creating its window).
            let cls = wide(&class_name(profile));
            for _ in 0..50 {
                let h = FindWindowW(cls.as_ptr(), std::ptr::null());
                if !h.is_null() {
                    PostMessageW(h, WM_APP_OPEN, 0, 0);
                    break;
                }
                std::thread::sleep(std::time::Duration::from_millis(100));
            }
            return true;
        }
        // Keep the mutex for the life of the process (never closed).
        false
    }
}

/// Parse "Ctrl+Alt+P", "Alt+`", "Alt+Shift+3", "Alt+PageDown" … into (modifiers, virtual key).
pub fn parse_accel(acc: &str) -> Option<(u32, u32)> {
    let mut mods = 0x4000u32; // MOD_NOREPEAT
    let mut vk = None;
    for part in acc.split('+') {
        match part.trim().to_ascii_lowercase().as_str() {
            "alt" | "option" => mods |= 0x1,
            "ctrl" | "control" | "cmdorctrl" | "commandorcontrol" => mods |= 0x2,
            "shift" => mods |= 0x4,
            "win" | "super" | "meta" => mods |= 0x8,
            "`" => vk = Some(0xC0),
            "up" => vk = Some(0x26),
            "down" => vk = Some(0x28),
            "left" => vk = Some(0x25),
            "right" => vk = Some(0x27),
            "pageup" => vk = Some(0x21),
            "pagedown" => vk = Some(0x22),
            "space" => vk = Some(0x20),
            k if k.len() == 1 && k.as_bytes()[0].is_ascii_alphanumeric() => vk = Some(k.to_ascii_uppercase().as_bytes()[0] as u32),
            k if k.starts_with('f') && k[1..].parse::<u32>().map(|n| (1..=24).contains(&n)).unwrap_or(false) => vk = Some(0x6F + k[1..].parse::<u32>().unwrap()),
            _ => return None,
        }
    }
    vk.map(|v| (mods, v))
}

unsafe extern "system" fn wndproc(h: HWND, msg: u32, wp: WPARAM, lp: LPARAM) -> LRESULT {
    match msg {
        WM_HOTKEY => {
            if let Some(s) = SHARED.get() {
                let g = s.lock().unwrap();
                if let Some(name) = g.registered.get(&(wp as i32)) {
                    (g.tx)(SysEvent::Hotkey(name.clone()));
                }
            }
            0
        }
        WM_APP_OPEN => {
            if let Some(s) = SHARED.get() {
                (s.lock().unwrap().tx)(SysEvent::OpenSettings);
            }
            0
        }
        WM_TIMER if wp == RETRY_TIMER => {
            KillTimer(h, RETRY_TIMER);
            PostMessageW(h, WM_APP_HOTKEYS, 1, 0);
            0
        }
        WM_APP_HOTKEYS => {
            let mut failed = false;
            let mut missing: Vec<String> = vec![];
            if let Some(s) = SHARED.get() {
                let mut g = s.lock().unwrap();
                if wp == 0 {
                    g.retries = 0; // a new request, not a retry
                }
                let want = g.wanted.clone();
                let keep: Vec<i32> = g.registered.iter().filter(|(_, n)| want.contains(n)).map(|(id, _)| *id).collect();
                let drop: Vec<i32> = g.registered.keys().filter(|id| !keep.contains(id)).copied().collect();
                for id in drop {
                    UnregisterHotKey(h, id);
                    g.registered.remove(&id);
                }
                for name in want {
                    if g.registered.values().any(|n| *n == name) {
                        continue;
                    }
                    if let Some((mods, vk)) = parse_accel(&name) {
                        let id = (1..0xBFFF).find(|i| !g.registered.contains_key(i)).unwrap();
                        if RegisterHotKey(h, id, mods, vk) != 0 {
                            g.registered.insert(id, name);
                        } else {
                            // Another app holds it — often a Translate that is still exiting. Try again for a minute.
                            failed = true;
                            missing.push(name.clone());
                            if g.retries == 0 {
                                crate::log::warn(format!("shortcut unavailable: {name} (retrying)"));
                            }
                        }
                    }
                }
                if failed && g.retries < 30 {
                    g.retries += 1;
                    SetTimer(h, RETRY_TIMER, 2000, None);
                } else if !failed && g.retries > 0 {
                    crate::log::info("shortcuts registered after retrying");
                    g.retries = 0;
                }
                if missing != g.unavailable {
                    g.unavailable = missing.clone();
                    (g.tx)(SysEvent::HotkeysUnavailable(missing));
                }
            }
            0
        }
        WM_SETTINGCHANGE => {
            if lp != 0 {
                let p = lp as *const u16;
                let len = (0..256).take_while(|&i| *p.add(i) != 0).count();
                let s = String::from_utf16_lossy(std::slice::from_raw_parts(p, len));
                if s == "ImmersiveColorSet" {
                    if let Some(sh) = SHARED.get() {
                        (sh.lock().unwrap().tx)(SysEvent::ThemeChanged);
                    }
                }
            }
            DefWindowProcW(h, msg, wp, lp)
        }
        _ => DefWindowProcW(h, msg, wp, lp),
    }
}

pub fn start(profile: &str, tx: impl Fn(SysEvent) + Send + 'static) {
    let _ = SHARED.set(Mutex::new(Shared { tx: Box::new(tx), wanted: vec![], registered: HashMap::new(), retries: 0, unavailable: vec![] }));
    let cls = class_name(profile);
    let (ready_tx, ready_rx) = std::sync::mpsc::channel::<()>();
    std::thread::spawn(move || unsafe {
        let name = wide(&cls);
        let inst = GetModuleHandleW(std::ptr::null());
        let wc = WNDCLASSW { lpfnWndProc: Some(wndproc), hInstance: inst, lpszClassName: name.as_ptr(), ..std::mem::zeroed() };
        RegisterClassW(&wc);
        // A hidden top-level popup (not message-only: those don't receive WM_SETTINGCHANGE broadcasts).
        let h = CreateWindowExW(WS_EX_TOOLWINDOW, name.as_ptr(), name.as_ptr(), WS_POPUP, 0, 0, 0, 0, std::ptr::null_mut(), std::ptr::null_mut(), inst, std::ptr::null());
        let _ = HWND_CELL.set(h as isize);
        let _ = ready_tx.send(());
        let mut msg: MSG = std::mem::zeroed();
        while GetMessageW(&mut msg, std::ptr::null_mut(), 0, 0) > 0 {
            TranslateMessage(&msg);
            DispatchMessageW(&msg);
        }
    });
    let _ = ready_rx.recv_timeout(std::time::Duration::from_secs(2));
}

/// Replace the set of registered global shortcuts.
pub fn set_hotkeys(names: Vec<String>) {
    if let (Some(s), Some(h)) = (SHARED.get(), HWND_CELL.get()) {
        s.lock().unwrap().wanted = names;
        unsafe {
            PostMessageW(*h as HWND, WM_APP_HOTKEYS, 0, 0);
        }
    }
}

/// Whether Windows would give us this shortcut now: true when it is free or already ours. Registers it for a moment
/// on the calling thread (no window), then lets it go.
pub fn hotkey_available(name: &str) -> bool {
    let Some((mods, vk)) = parse_accel(name) else { return false };
    if let Some(s) = SHARED.get() {
        if s.lock().unwrap().registered.values().any(|n| n.eq_ignore_ascii_case(name)) {
            return true;
        }
    }
    unsafe {
        if RegisterHotKey(std::ptr::null_mut(), 0xBFF0, mods, vk) == 0 {
            return false;
        }
        UnregisterHotKey(std::ptr::null_mut(), 0xBFF0);
    }
    true
}

#[cfg(test)]
mod tests {
    use super::parse_accel;
    #[test]
    fn accelerators() {
        assert_eq!(parse_accel("Alt+1"), Some((0x4001, 0x31)));
        assert_eq!(parse_accel("Alt+Shift+9"), Some((0x4005, 0x39)));
        assert_eq!(parse_accel("Ctrl+Alt+P"), Some((0x4003, 0x50)));
        assert_eq!(parse_accel("Alt+`"), Some((0x4001, 0xC0)));
        assert_eq!(parse_accel("Alt+PageDown"), Some((0x4001, 0x22)));
        assert_eq!(parse_accel("Alt+Bogus"), None);
    }
    #[test]
    fn availability_probe_leaves_shortcut_free() {
        for _ in 0..3 {
            assert!(super::hotkey_available("Ctrl+Alt+Shift+F9"), "err {}", unsafe { windows_sys::Win32::Foundation::GetLastError() });
        }
    }
}
