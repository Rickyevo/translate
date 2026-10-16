//! Placement geometry, in physical pixels of one monitor. Pure functions (unit-tested below).
//!
//! The panel goes under WeType's bar, or above it when there is no room below — and never over the line being typed
//! on. Near the bottom of the screen WeType usually still draws its bar *below* the caret, so "directly above the bar"
//! is exactly the typing line (the 0.1.x bug). When the app reports its caret, that line is avoided precisely; when it
//! doesn't, a line's height above the bar is kept clear.

#[derive(Clone, Copy, Debug, PartialEq, Default, serde::Serialize, serde::Deserialize)]
pub struct Rect {
    pub x: f64,
    pub y: f64,
    pub w: f64,
    pub h: f64,
}

impl Rect {
    pub fn new(x: f64, y: f64, w: f64, h: f64) -> Self {
        Rect { x, y, w, h }
    }
    pub fn r(&self) -> f64 {
        self.x + self.w
    }
    pub fn b(&self) -> f64 {
        self.y + self.h
    }
    pub fn intersects(&self, o: &Rect) -> bool {
        self.x < o.r() && self.r() > o.x && self.y < o.b() && self.b() > o.y
    }
    pub fn union(&self, o: &Rect) -> Rect {
        let (x, y) = (self.x.min(o.x), self.y.min(o.y));
        Rect::new(x, y, self.r().max(o.r()) - x, self.b().max(o.b()) - y)
    }
    pub fn center_y(&self) -> f64 {
        self.y + self.h / 2.0
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Dir {
    Below,
    Above,
}

pub struct PanelInput {
    pub work: Rect,
    /// WeType's drawn bar (pinyin + candidates).
    pub bar: Rect,
    /// WeType's whole window (takes all mouse input over its area).
    pub canvas: Option<Rect>,
    /// The app's caret, when it reports one.
    pub caret: Option<Rect>,
    pub clickable: bool,
    /// Panel content size.
    pub w: f64,
    pub h: f64,
    pub offset_x: f64,
    pub offset_y: f64,
    pub scale: f64,
}

pub struct PanelPlacement {
    pub x: f64,
    pub y: f64,
    pub dir: Dir,
    /// The typing line as used for placement (known caret, or the assumed line above the bar).
    pub band: Rect,
    pub caret_known: bool,
}

/// A caret the app reports is only trusted next to the bar: some apps report a stale or unrelated caret.
pub fn usable_caret(bar: &Rect, caret: Option<Rect>, scale: f64) -> Option<Rect> {
    let c = caret?;
    if c.h <= 0.0 || c.h > 200.0 * scale {
        return None;
    }
    let near_y = (c.b() >= bar.y - 3.0 * bar.h.max(30.0 * scale)) && (c.y <= bar.b() + 3.0 * bar.h.max(30.0 * scale));
    let near_x = c.x >= bar.x - 400.0 * scale && c.x <= bar.r() + 400.0 * scale;
    if near_y && near_x {
        Some(c)
    } else {
        None
    }
}

pub fn place_panel(i: &PanelInput) -> PanelPlacement {
    let m = (8.0 * i.scale).round();
    let (top, bottom) = (i.work.y + m, i.work.b() - m);
    let caret = usable_caret(&i.bar, i.caret, i.scale);
    // The typing line: the caret's line across the bar's width, or — unknown — one line's height right above the
    // bar (where WeType's caret is, except when it flipped its bar above the caret near the bottom of the screen).
    let assumed_h = i.bar.h.max(24.0 * i.scale);
    let band = match caret {
        Some(c) => Rect::new(i.bar.x.min(c.x), c.y, (i.bar.r().max(c.r())) - i.bar.x.min(c.x), c.h),
        None => Rect::new(i.bar.x, i.bar.y - assumed_h, i.bar.w, assumed_h),
    };
    // What to keep clear, vertically. Below: bar and (known) caret. Above: bar and the typing line.
    let below_block = match caret {
        Some(_) => i.bar.union(&band),
        None => i.bar,
    };
    let above_block = i.bar.union(&band);
    let gap = i.offset_y.max(0.0);
    let fits_below = |blk: &Rect| blk.b() + gap + i.h <= bottom;
    let fits_above = |blk: &Rect| blk.y - gap - i.h >= top;

    let mut choice: Option<(f64, Dir)> = None;
    if i.clickable {
        if let Some(cv) = i.canvas {
            // Clear of WeType's whole window (it takes the mouse), when there's room on either side.
            let (bb, ab) = (cv.union(&below_block), cv.union(&above_block));
            if fits_below(&bb) {
                choice = Some((bb.b() + gap, Dir::Below));
            } else if fits_above(&ab) {
                choice = Some((ab.y - gap - i.h, Dir::Above));
            }
        }
    }
    if choice.is_none() {
        if fits_below(&below_block) {
            choice = Some((below_block.b() + gap, Dir::Below));
        } else if fits_above(&above_block) {
            choice = Some((above_block.y - gap - i.h, Dir::Above));
        } else {
            // No room either side (a very short screen or a very large panel): the side with more room, clamped
            // inside the work area. Overlap is then unavoidable; the bar itself is still kept clear where possible.
            let room_below = bottom - below_block.b();
            let room_above = above_block.y - top;
            if room_below >= room_above {
                choice = Some(((below_block.b() + gap).min(bottom - i.h).max(top), Dir::Below));
            } else {
                choice = Some(((above_block.y - gap - i.h).max(top).min(bottom - i.h), Dir::Above));
            }
        }
    }
    let (y, dir) = choice.unwrap();
    let x = (i.bar.x + i.offset_x).min(i.work.r() - m - i.w).max(i.work.x + m);
    PanelPlacement { x: x.round(), y: y.round(), dir, band, caret_known: caret.is_some() }
}

// ---------------------------------------------------------------------------------------------- lead preview

#[derive(Clone, Copy, Debug, PartialEq, Eq, serde::Serialize)]
#[serde(rename_all = "lowercase")]
pub enum Kind {
    Outer,
    Beside,
    Scroll,
    Overlay,
    None,
}

pub struct PreviewInput {
    pub work: Rect,
    pub panel: Rect,
    pub avoid: Vec<Rect>,
    pub stack: Dir,
    pub width: f64,
    pub need_h: f64,
    pub min_h: f64,
    pub requested: bool,
    pub margin: f64,
    pub gap: f64,
}

#[derive(Debug, Clone, Copy)]
pub struct Placement {
    pub kind: Kind,
    pub rect: Rect,
    pub scroll: bool,
}

fn free_intervals(x: f64, w: f64, top: f64, btm: f64, blockers: &[Rect], gap: f64) -> Vec<(f64, f64)> {
    let mut cuts: Vec<(f64, f64)> = blockers.iter().filter(|b| x < b.r() && x + w > b.x).map(|b| (b.y - gap, b.b() + gap)).collect();
    cuts.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap());
    let mut out = vec![];
    let mut cur = top;
    for (a, b) in cuts {
        if a > cur {
            out.push((cur, a.min(btm)));
        }
        cur = cur.max(b);
        if cur >= btm {
            break;
        }
    }
    if cur < btm {
        out.push((cur, btm));
    }
    out.into_iter().filter(|(a, b)| b - a > 0.0).collect()
}

struct Opt {
    kind: Kind,
    x: f64,
    avail: f64,
    y: Box<dyn Fn(f64) -> f64>,
}

/// Same order as prototype/src/layout/placePreview.ts: outer side → beside (more room) → best fit, scrolling →
/// overlay on our own rows (only when asked) → none. Never intersects `avoid` or the panel; inside the work area.
pub fn place_preview(i: &PreviewInput) -> Placement {
    let (m, gap) = (i.margin, i.gap);
    let (wl, wt, wr, wb) = (i.work.x + m, i.work.y + m, i.work.r() - m, i.work.b() - m);
    let w = i.width.min(wr - wl);
    let mut blockers = i.avoid.clone();
    blockers.push(i.panel);
    let mut opts: Vec<Opt> = vec![];
    {
        let x = (i.panel.x.min(wr - w)).max(wl);
        let iv = free_intervals(x, w, wt, wb, &blockers, gap);
        if i.stack == Dir::Below {
            let start = i.panel.b() + gap;
            if let Some(seg) = iv.iter().find(|(a, b)| *a <= start + 0.5 && *b > start) {
                opts.push(Opt { kind: Kind::Outer, x, avail: seg.1 - start, y: Box::new(move |_| start) });
            }
        } else {
            let end = i.panel.y - gap;
            if let Some(seg) = iv.iter().find(|(a, b)| *b >= end - 0.5 && *a < end) {
                opts.push(Opt { kind: Kind::Outer, x, avail: end - seg.0, y: Box::new(move |h| end - h) });
            }
        }
    }
    let mut beside: Vec<Opt> = vec![];
    for right in [true, false] {
        let x = if right { i.panel.r() + gap } else { i.panel.x - gap - w };
        if x < wl || x + w > wr {
            continue;
        }
        let mut iv = free_intervals(x, w, wt, wb, &blockers, gap);
        let anchor = i.panel.y;
        let seg = match iv.iter().find(|(a, b)| *a <= anchor && anchor <= *b) {
            Some(s) => Some(*s),
            None => {
                iv.sort_by(|p, q| ((p.0 + p.1) / 2.0 - anchor).abs().partial_cmp(&((q.0 + q.1) / 2.0 - anchor).abs()).unwrap());
                iv.first().copied()
            }
        };
        if let Some((a, b)) = seg {
            let py = i.panel.y;
            beside.push(Opt { kind: Kind::Beside, x, avail: b - a, y: Box::new(move |h| a.max(py.min(b - h))) });
        }
    }
    beside.sort_by(|p, q| q.avail.partial_cmp(&p.avail).unwrap());
    opts.extend(beside);
    for o in &opts {
        if o.avail >= i.need_h {
            return Placement { kind: o.kind, rect: Rect::new(o.x, (o.y)(i.need_h), w, i.need_h), scroll: false };
        }
    }
    if let Some(best) = opts.iter().max_by(|p, q| p.avail.partial_cmp(&q.avail).unwrap()) {
        if best.avail >= i.min_h {
            let h = best.avail.floor();
            return Placement { kind: Kind::Scroll, rect: Rect::new(best.x, (best.y)(h), w, h), scroll: true };
        }
    }
    if i.requested {
        let h = i.panel.h - 25.0;
        return Placement { kind: Kind::Overlay, rect: Rect::new(i.panel.x, i.panel.y, i.panel.w, h), scroll: i.need_h > h };
    }
    Placement { kind: Kind::None, rect: Rect::new(i.panel.x, i.panel.y, 0.0, 0.0), scroll: false }
}

// ---------------------------------------------------------------------------------------------- tests

#[cfg(test)]
mod tests {
    use super::*;

    /// WeType's bar inside its canvas at a given scale (3.0 layout: 27,136 574×43 in a 628×314 canvas at 96 dpi).
    fn wetype(canvas_x: f64, canvas_y: f64, s: f64, bar: (f64, f64, f64, f64)) -> (Rect, Rect) {
        let cv = Rect::new(canvas_x, canvas_y, (628.0 * s).round(), (314.0 * s).round());
        let b = Rect::new(canvas_x + (bar.0 * s).round(), canvas_y + (bar.1 * s).round(), (bar.2 * s).round(), (bar.3 * s).round());
        (cv, b)
    }

    fn panel(s: f64) -> (f64, f64) {
        ((219.0 * s).round(), (176.0 * s).round())
    }

    fn input(work: Rect, bar: Rect, canvas: Rect, caret: Option<Rect>, clickable: bool, s: f64) -> PanelInput {
        let (w, h) = panel(s);
        PanelInput { work, bar, canvas: Some(canvas), caret, clickable, w, h, offset_x: 0.0, offset_y: (4.0 * s).round(), scale: s }
    }

    /// Screens: (width, height, scale, taskbar height in physical px, origin x, origin y) — incl. a second monitor
    /// left of the primary (negative coordinates).
    const SCREENS: &[(f64, f64, f64, f64, f64, f64)] = &[
        (1366.0, 768.0, 1.0, 40.0, 0.0, 0.0),
        (1366.0, 768.0, 1.25, 48.0, 0.0, 0.0),
        (1920.0, 1080.0, 1.0, 48.0, 0.0, 0.0),
        (1920.0, 1080.0, 1.5, 72.0, 0.0, 0.0),
        (2560.0, 1440.0, 1.25, 60.0, 0.0, 0.0),
        (2560.0, 1600.0, 1.75, 84.0, 0.0, 0.0),
        (3840.0, 2160.0, 2.0, 96.0, 0.0, 0.0),
        (1920.0, 1080.0, 1.0, 0.0, -1920.0, 0.0),
        (2560.0, 1440.0, 1.5, 0.0, -2560.0, -360.0),
    ];

    const LAYOUTS: &[(f64, f64, f64, f64)] = &[
        (27.0, 136.0, 574.0, 43.0),  // 3.0, single line
        (20.0, 109.0, 588.0, 70.0),  // 2.1, pinyin line above
        (27.0, 262.0, 574.0, 43.0),  // drawn at the bottom of the canvas
        (27.0, 4.0, 574.0, 43.0),    // drawn at the top of the canvas
        (27.0, 136.0, 200.0, 43.0),  // short list
    ];

    /// Every screen × layout × vertical position (top … bottom edge) × horizontal position × caret case × mode.
    #[test]
    fn panel_never_covers_bar_or_typing_line_and_stays_on_screen() {
        let mut n = 0;
        for &(sw, sh, s, task, ox, oy) in SCREENS {
            let work = Rect::new(ox, oy, sw, sh - task);
            for layout in LAYOUTS {
                let ch = (314.0 * s).round();
                let cw = (628.0 * s).round();
                // Canvas positions from above the top edge to the bottom edge, and left/middle/right.
                let ys: Vec<f64> = (0..=12).map(|k| oy - ch / 2.0 + (sh - task) * k as f64 / 12.0).collect();
                let xs = [ox - cw / 4.0, ox + sw / 2.0 - cw / 2.0, ox + sw - cw * 0.75];
                for &cy in &ys {
                    for &cx in &xs {
                        let (canvas, bar) = wetype(cx, cy, s, *layout);
                        if bar.y < work.y || bar.b() > work.b() {
                            continue; // WeType keeps its bar on screen
                        }
                        let line = (22.0 * s).round();
                        // The real caret: above the bar (usual) or below it (WeType flipped its bar near the bottom),
                        // reported by the app or not.
                        let real = [
                            Rect::new(bar.x + 6.0 * s, bar.y - (4.0 * s).round() - line, 2.0, line),
                            Rect::new(bar.x + 6.0 * s, bar.b() + (4.0 * s).round(), 2.0, line),
                        ];
                        for (k, caret_real) in real.iter().enumerate() {
                            if caret_real.y < work.y || caret_real.b() > work.b() {
                                continue;
                            }
                            // WeType only flips when the bar doesn't fit below the caret.
                            let flipped = k == 1;
                            if flipped && caret_real.b() + (4.0 * s).round() + bar.h <= work.b() {
                                continue;
                            }
                            for reported in [true, false] {
                            let caret = if reported { Some(*caret_real) } else { None };
                            for clickable in [false, true] {
                                let i = input(work, bar, canvas, caret, clickable, s);
                                let p = place_panel(&i);
                                let r = Rect::new(p.x, p.y, i.w, i.h);
                                let ctx = format!("screen {sw}x{sh}@{s} at ({ox},{oy}) canvas {canvas:?} bar {bar:?} caret {caret_real:?} reported {reported} clickable {clickable} band {:?} -> {r:?}", p.band);
                                let m = (8.0 * s).round();
                                assert!(r.x >= work.x + m - 0.5 && r.r() <= work.r() - m + 0.5, "outside horizontally: {ctx}");
                                assert!(r.y >= work.y + m - 0.5 && r.b() <= work.b() - m + 0.5, "outside vertically: {ctx}");
                                assert!(!r.intersects(&bar), "covers the bar: {ctx}");
                                let typing = Rect::new(bar.x, caret_real.y, bar.w, caret_real.h);
                                assert!(!r.intersects(&typing), "covers the typing line: {ctx}");
                                if clickable {
                                    // Room clear of WeType's window, judged with what the panel knows: the reported caret, else the assumed line.
                                    let line_top = if reported { typing.y } else { p.band.y };
                                    let room = canvas.b() + i.offset_y + i.h <= work.b() - m || canvas.y.min(line_top) - i.offset_y - i.h >= work.y + m;
                                    if room {
                                        assert!(!r.intersects(&canvas), "clickable but under WeType's window: {ctx}");
                                    }
                                }
                                // Below is preferred whenever it fits (and the caret isn't in the way).
                                let below_ok = bar.union(&typing).b() + i.offset_y + i.h <= work.b() - m;
                                if !clickable && below_ok && !flipped {
                                    assert_eq!(p.dir, Dir::Below, "should be below: {ctx}");
                                }
                                n += 1;
                            }
                            }
                        }
                    }
                }
            }
        }
        assert!(n > 2000, "only {n} cases");
    }

    /// The reported case: WeType's bar near the bottom of a 1276×856 window area, caret above the bar.
    #[test]
    fn reported_bottom_edge_case() {
        let work = Rect::new(0.0, 0.0, 1276.0, 856.0);
        let bar = Rect::new(131.0, 763.0, 715.0, 52.0);
        let caret = Rect::new(150.0, 727.0, 2.0, 22.0);
        for c in [None, Some(caret)] {
            let i = PanelInput { work, bar, canvas: None, caret: c, clickable: false, w: 324.0, h: 264.0, offset_x: 0.0, offset_y: 4.0, scale: 1.0 };
            let p = place_panel(&i);
            assert_eq!(p.dir, Dir::Above);
            assert!(p.y + i.h <= caret.y, "covers the typing line (caret {c:?}): bottom {}", p.y + i.h);
        }
    }

    #[test]
    fn stale_or_unrelated_caret_is_ignored() {
        let bar = Rect::new(500.0, 500.0, 574.0, 43.0);
        assert!(usable_caret(&bar, Some(Rect::new(0.0, 0.0, 2.0, 20.0)), 1.0).is_none());
        assert!(usable_caret(&bar, Some(Rect::new(520.0, 470.0, 2.0, 22.0)), 1.0).is_some());
        assert!(usable_caret(&bar, Some(Rect::new(520.0, 470.0, 2.0, 0.0)), 1.0).is_none());
    }

    // Lead preview: the cases of prototype/scripts/test_place.mjs, plus scale.
    fn pv(work: Rect, panel: Rect, stack: Dir, need: f64, requested: bool) -> Placement {
        let avoid = vec![Rect::new(panel.x, if stack == Dir::Below { panel.y - 80.0 } else { panel.b() }, 500.0, 80.0)];
        place_preview(&PreviewInput { work, panel, avoid, stack, width: 380.0, need_h: need, min_h: 30.0 + 2.0 * 20.0 + 16.0, requested, margin: 8.0, gap: 6.0 })
    }

    #[test]
    fn preview_order() {
        let work = Rect::new(0.0, 0.0, 1920.0, 1040.0);
        // Room below: outer.
        let p = pv(work, Rect::new(600.0, 300.0, 219.0, 176.0), Dir::Below, 100.0, false);
        assert_eq!(p.kind, Kind::Outer);
        assert!(p.rect.y >= 476.0);
        // Panel at the bottom: beside.
        let p = pv(work, Rect::new(600.0, 850.0, 219.0, 176.0), Dir::Below, 100.0, false);
        assert_eq!(p.kind, Kind::Beside);
        // Stacked above near the top: outer above.
        let p = pv(work, Rect::new(600.0, 400.0, 219.0, 176.0), Dir::Above, 100.0, false);
        assert_eq!(p.kind, Kind::Outer);
        assert!(p.rect.b() <= 394.0);
        // Nothing fits on a tiny work area: overlay only when requested, else none.
        let tiny = Rect::new(0.0, 0.0, 240.0, 200.0);
        assert_eq!(pv(tiny, Rect::new(8.0, 8.0, 219.0, 176.0), Dir::Below, 300.0, false).kind, Kind::None);
        assert_eq!(pv(tiny, Rect::new(8.0, 8.0, 219.0, 176.0), Dir::Below, 300.0, true).kind, Kind::Overlay);
    }

    #[test]
    fn preview_never_overlaps_panel_or_avoid() {
        for &(sw, sh, s, task, ox, oy) in SCREENS {
            let work = Rect::new(ox, oy, sw, sh - task);
            for k in 0..10 {
                let (pw, ph) = panel(s);
                let py = work.y + (work.h - ph) * k as f64 / 9.0;
                let p = Rect::new(work.x + work.w / 3.0, py, pw, ph);
                let stack = if k < 5 { Dir::Below } else { Dir::Above };
                let r = pv(work, p, stack, 120.0 * s, false);
                if r.kind == Kind::None {
                    continue;
                }
                assert!(!r.rect.intersects(&p), "{r:?} over panel {p:?}");
                assert!(r.rect.x >= work.x && r.rect.r() <= work.r() && r.rect.y >= work.y && r.rect.b() <= work.b());
            }
        }
    }
}
