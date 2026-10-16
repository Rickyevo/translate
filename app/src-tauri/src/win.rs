//! Thin Win32 helpers (physical pixels throughout).

use crate::layout::Rect;
use std::ffi::c_void;
use windows_sys::Win32::Foundation::{HWND, POINT, RECT};
use windows_sys::Win32::Graphics::Gdi::{
    CombineRgn, CreateRectRgn, DeleteObject, GetMonitorInfoW, MonitorFromPoint, MonitorFromRect, SetWindowRgn, MONITORINFO, MONITOR_DEFAULTTONEAREST, RGN_OR,
};
use windows_sys::Win32::UI::HiDpi::{GetDpiForMonitor, MDT_EFFECTIVE_DPI};
use windows_sys::Win32::UI::WindowsAndMessaging::*;

pub fn hwnd(h: isize) -> HWND {
    h as HWND
}

/// Tool window that never takes activation (clicks don't move focus away from the app being typed in).
pub fn make_overlay(h: isize) {
    unsafe {
        let w = hwnd(h);
        let ex = GetWindowLongPtrW(w, GWL_EXSTYLE);
        SetWindowLongPtrW(w, GWL_EXSTYLE, ex | (WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TOPMOST) as isize);
    }
}

pub fn show_noactivate(h: isize) {
    unsafe {
        let w = hwnd(h);
        SetWindowPos(w, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW);
    }
}

pub fn hide(h: isize) {
    unsafe {
        ShowWindow(hwnd(h), SW_HIDE);
    }
}

pub fn is_visible(h: isize) -> bool {
    unsafe { IsWindowVisible(hwnd(h)) != 0 }
}

pub fn window_rect(h: isize) -> Option<Rect> {
    let mut r = RECT { left: 0, top: 0, right: 0, bottom: 0 };
    if unsafe { GetWindowRect(hwnd(h), &mut r) } == 0 {
        return None;
    }
    Some(Rect::new(r.left as f64, r.top as f64, (r.right - r.left) as f64, (r.bottom - r.top) as f64))
}

/// Move/size without activation, kept topmost. Returns whether the size changed.
pub fn set_bounds(h: isize, r: (i32, i32, i32, i32)) -> bool {
    let cur = window_rect(h);
    let size_changed = cur.map(|c| c.w as i32 != r.2 || c.h as i32 != r.3).unwrap_or(true);
    let moved = cur.map(|c| c.x as i32 != r.0 || c.y as i32 != r.1).unwrap_or(true);
    if size_changed || moved {
        unsafe {
            SetWindowPos(hwnd(h), HWND_TOPMOST, r.0, r.1, r.2, r.3, SWP_NOACTIVATE);
        }
    }
    size_changed
}

/// Resize a normal window around its centre (no activation change).
pub fn resize_keep_center(h: isize, r: &Rect, w: i32, hh: i32) {
    let (x, y) = ((r.x + (r.w - w as f64) / 2.0).round() as i32, (r.y + (r.h - hh as f64) / 2.0).round() as i32);
    unsafe {
        SetWindowPos(hwnd(h), std::ptr::null_mut(), x, y, w, hh, SWP_NOZORDER | SWP_NOACTIVATE);
    }
}

/// Only these rectangles (window coordinates) are part of the window: clicks elsewhere go to the window below.
pub fn set_region(h: isize, rects: &[(i32, i32, i32, i32)]) {
    unsafe {
        let rgn = CreateRectRgn(0, 0, 0, 0);
        for &(x, y, w, hh) in rects {
            let r = CreateRectRgn(x, y, x + w, y + hh);
            CombineRgn(rgn, rgn, r, RGN_OR);
            DeleteObject(r as _);
        }
        SetWindowRgn(hwnd(h), rgn, 1); // the system owns rgn now
    }
}

pub struct Monitor {
    pub work: Rect,
    pub scale: f64,
}

fn monitor_info(hm: windows_sys::Win32::Graphics::Gdi::HMONITOR) -> Monitor {
    let mut mi: MONITORINFO = unsafe { std::mem::zeroed() };
    mi.cbSize = std::mem::size_of::<MONITORINFO>() as u32;
    unsafe { GetMonitorInfoW(hm, &mut mi) };
    let (mut dx, mut dy) = (96u32, 96u32);
    unsafe { GetDpiForMonitor(hm, MDT_EFFECTIVE_DPI, &mut dx, &mut dy) };
    let w = mi.rcWork;
    Monitor { work: Rect::new(w.left as f64, w.top as f64, (w.right - w.left) as f64, (w.bottom - w.top) as f64), scale: dx.max(96) as f64 / 96.0 }
}

/// The monitor a rectangle is (mostly) on: its work area (without the taskbar) and scale factor.
pub fn monitor_for(r: &Rect) -> Monitor {
    let rc = RECT { left: r.x as i32, top: r.y as i32, right: r.r() as i32, bottom: r.b() as i32 };
    monitor_info(unsafe { MonitorFromRect(&rc, MONITOR_DEFAULTTONEAREST) })
}

pub fn monitor_at_cursor() -> Monitor {
    let mut p = POINT { x: 0, y: 0 };
    unsafe { GetCursorPos(&mut p) };
    monitor_info(unsafe { MonitorFromPoint(p, MONITOR_DEFAULTTONEAREST) })
}

// --- clipboard ---------------------------------------------------------------------------------------
pub fn set_clipboard(text: &str) -> bool {
    use windows_sys::Win32::System::DataExchange::{CloseClipboard, EmptyClipboard, OpenClipboard, SetClipboardData};
    use windows_sys::Win32::System::Memory::{GlobalAlloc, GlobalLock, GlobalUnlock, GMEM_MOVEABLE};
    const CF_UNICODETEXT: u32 = 13;
    let wide: Vec<u16> = text.encode_utf16().chain(std::iter::once(0)).collect();
    unsafe {
        for _ in 0..10 {
            if OpenClipboard(std::ptr::null_mut()) != 0 {
                EmptyClipboard();
                let mem = GlobalAlloc(GMEM_MOVEABLE, wide.len() * 2);
                if mem.is_null() {
                    CloseClipboard();
                    return false;
                }
                let p = GlobalLock(mem) as *mut u16;
                std::ptr::copy_nonoverlapping(wide.as_ptr(), p, wide.len());
                GlobalUnlock(mem);
                let ok = !SetClipboardData(CF_UNICODETEXT, mem as _).is_null();
                CloseClipboard();
                return ok;
            }
            std::thread::sleep(std::time::Duration::from_millis(15));
        }
    }
    false
}

// --- registry -----------------------------------------------------------------------------------------
use windows_sys::Win32::System::Registry::*;

fn wide(s: &str) -> Vec<u16> {
    s.encode_utf16().chain(std::iter::once(0)).collect()
}

fn read_dword(root: HKEY, path: &str, name: &str) -> Option<u32> {
    let (p, n) = (wide(path), wide(name));
    let mut v: u32 = 0;
    let mut sz = 4u32;
    let r = unsafe { RegGetValueW(root, p.as_ptr(), n.as_ptr(), RRF_RT_REG_DWORD, std::ptr::null_mut(), &mut v as *mut u32 as *mut c_void, &mut sz) };
    (r == 0).then_some(v)
}

fn key_exists(root: HKEY, path: &str, name: &str) -> bool {
    let (p, n) = (wide(path), wide(name));
    let mut sz = 0u32;
    unsafe { RegGetValueW(root, p.as_ptr(), n.as_ptr(), RRF_RT_REG_SZ, std::ptr::null_mut(), std::ptr::null_mut(), &mut sz) == 0 && sz > 2 }
}

/// Windows "app mode": dark when AppsUseLightTheme is 0.
pub fn system_dark() -> bool {
    read_dword(HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", "AppsUseLightTheme") == Some(0)
}

const RUN: &str = r"Software\Microsoft\Windows\CurrentVersion\Run";

/// Start with Windows: the per-user Run entry "Translate" pointing at this exe (or removed).
pub fn set_run_entry(on: bool, exe: &str) -> bool {
    let (p, n) = (wide(RUN), wide("Translate"));
    unsafe {
        let mut key: HKEY = std::ptr::null_mut();
        if RegOpenKeyExW(HKEY_CURRENT_USER, p.as_ptr(), 0, KEY_SET_VALUE, &mut key) != 0 {
            return false;
        }
        let r = if on {
            let v = wide(&format!("\"{exe}\""));
            RegSetValueExW(key, n.as_ptr(), 0, REG_SZ, v.as_ptr() as *const u8, (v.len() * 2) as u32)
        } else {
            let r = RegDeleteValueW(key, n.as_ptr());
            if r == 2 { 0 } else { r } // ERROR_FILE_NOT_FOUND: already off
        };
        RegCloseKey(key);
        r == 0
    }
}

/// The WebView2 Runtime (Evergreen) is part of Windows 11 and current Windows 10, but can be missing on some systems.
pub fn webview2_installed() -> bool {
    const CLIENT: &str = r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}";
    const CLIENT64: &str = r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}";
    key_exists(HKEY_LOCAL_MACHINE, CLIENT, "pv") || key_exists(HKEY_LOCAL_MACHINE, CLIENT64, "pv") || key_exists(HKEY_CURRENT_USER, CLIENT64, "pv")
}

pub fn message_box(title: &str, text: &str, yes_no: bool) -> bool {
    let (t, m) = (wide(title), wide(text));
    let flags = if yes_no { MB_YESNO | MB_ICONINFORMATION } else { MB_OK | MB_ICONINFORMATION };
    unsafe { MessageBoxW(std::ptr::null_mut(), m.as_ptr(), t.as_ptr(), flags) == IDYES }
}

pub fn open_path(path: &str) {
    use windows_sys::Win32::UI::Shell::ShellExecuteW;
    let (op, p) = (wide("open"), wide(path));
    unsafe {
        ShellExecuteW(std::ptr::null_mut(), op.as_ptr(), p.as_ptr(), std::ptr::null(), std::ptr::null(), SW_SHOWNORMAL);
    }
}

pub fn foreground() -> isize {
    unsafe { GetForegroundWindow() as isize }
}
