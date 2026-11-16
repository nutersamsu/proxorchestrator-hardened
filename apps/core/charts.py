"""Server-side SVG line charts for Proxmox RRD data.

No JavaScript charting library: each chart is a small inline SVG that follows
the light/dark theme through CSS variables (see ``.po-chart`` in the
stylesheet). Every sample gets an invisible hover band with a ``<title>``, so
the browser shows the exact values as a tooltip.
"""

from datetime import datetime
from datetime import timezone as dt_timezone
from html import escape

from django.utils import timezone

WIDTH = 640
HEIGHT = 190
PAD_L = 58
PAD_R = 12
PAD_T = 12
PAD_B = 26
MAX_POINTS = 160

TIMEFRAMES = ("hour", "day", "week", "month", "year")
CONSOLIDATIONS = ("AVERAGE", "MAX")


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def _fmt_bytes(v, per_second=False):
    v = float(v)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(v) < 1024 or unit == "TiB":
            break
        v /= 1024
    text = f"{v:.0f} {unit}" if v >= 100 or unit == "B" else f"{v:.1f} {unit}"
    return text + ("/s" if per_second else "")


def fmt_value(v, unit):
    if v is None:
        return "—"
    if unit == "percent":
        return f"{v:.1f}%" if v < 10 else f"{v:.0f}%"
    if unit == "bytes":
        return _fmt_bytes(v)
    if unit == "bytes_s":
        return _fmt_bytes(v, per_second=True)
    return f"{v:.2f}" if v < 10 else f"{v:.0f}"


def _nice_max(v, unit):
    if unit == "percent":
        return 100.0 if v > 50 or v <= 0 else max(1.0, _nice_step_ceiling(v))
    if v <= 0:
        return 1.0
    if unit in ("bytes", "bytes_s"):
        # Round in the display unit (KiB/MiB/GiB…) so the axis reads 4/8/12/16 GiB.
        base = 1.0
        while v / base >= 1024:
            base *= 1024
        scaled = v / base
        for step in (1, 2, 4, 5, 8, 10, 16, 20, 25, 32, 40, 50, 64, 80, 100,
                     128, 160, 200, 256, 320, 400, 500, 512, 640, 800, 1000, 1024):
            if step >= scaled:
                return step * base
        return 1024 * base
    return _nice_step_ceiling(v)


def _nice_step_ceiling(v):
    """Smallest 1/2/2.5/5 x 10^n (or power-of-1024 friendly) value >= v."""
    exp = 1.0
    while exp * 10 <= v:
        exp *= 10
    while exp > v:
        exp /= 10
    for m in (1, 2, 2.5, 5, 10):
        if m * exp >= v:
            return m * exp
    return 10 * exp


def _fmt_time(ts, timeframe):
    dt = datetime.fromtimestamp(ts, tz=dt_timezone.utc)
    dt = timezone.localtime(dt)
    if timeframe in ("hour", "day"):
        return dt.strftime("%H:%M")
    if timeframe == "week":
        return dt.strftime("%a %H:%M")
    return dt.strftime("%d/%m")


def _fmt_time_full(ts):
    dt = timezone.localtime(datetime.fromtimestamp(ts, tz=dt_timezone.utc))
    return dt.strftime("%Y-%m-%d %H:%M")


# ---------------------------------------------------------------------------
# Data preparation
# ---------------------------------------------------------------------------

def _downsample(times, columns, use_max):
    n = len(times)
    if n <= MAX_POINTS:
        return times, columns
    size = n / MAX_POINTS
    out_t = []
    out_cols = [[] for _ in columns]
    for b in range(MAX_POINTS):
        lo, hi = int(b * size), int((b + 1) * size)
        if hi <= lo:
            continue
        out_t.append(times[hi - 1])
        for ci, col in enumerate(columns):
            chunk = [v for v in col[lo:hi] if v is not None]
            if not chunk:
                out_cols[ci].append(None)
            elif use_max:
                out_cols[ci].append(max(chunk))
            else:
                out_cols[ci].append(sum(chunk) / len(chunk))
    return out_t, out_cols


def _path(xs, ys):
    """SVG path, broken where a sample is missing."""
    parts = []
    pen_down = False
    for x, y in zip(xs, ys):
        if y is None:
            pen_down = False
            continue
        parts.append(f"{'L' if pen_down else 'M'}{x:.1f},{y:.1f}")
        pen_down = True
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Chart
# ---------------------------------------------------------------------------

def line_chart(title, times, series, unit, timeframe="hour", use_max=False, fill_first=True):
    """Render one chart.

    series: list of (label, values) — values aligned with ``times``; None = gap.
    unit: 'percent' | 'bytes' | 'bytes_s' | 'number'.
    Returns a dict for the template: title, svg (markup), legend.
    """
    times = list(times)
    columns = [list(vals) for _, vals in series]
    times, columns = _downsample(times, columns, use_max)
    labels = [label for label, _ in series]

    plot_w = WIDTH - PAD_L - PAD_R
    plot_h = HEIGHT - PAD_T - PAD_B
    present = [v for col in columns for v in col if v is not None]
    top = _nice_max(max(present) if present else 0, unit)

    n = len(times)
    if n >= 2:
        t0, t1 = times[0], times[-1]
        span = (t1 - t0) or 1
        xs = [PAD_L + (t - t0) / span * plot_w for t in times]
    else:
        xs = [PAD_L + plot_w / 2] * n

    def y_of(v):
        if v is None:
            return None
        return PAD_T + plot_h - min(max(v, 0) / top, 1.0) * plot_h

    out = [
        f'<svg class="po-chart" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" '
        f'aria-label="{escape(title)}" preserveAspectRatio="none">'
    ]

    # Grid and Y labels
    for i in range(5):
        frac = i / 4
        y = PAD_T + plot_h - frac * plot_h
        out.append(f'<line class="grid" x1="{PAD_L}" x2="{WIDTH - PAD_R}" y1="{y:.1f}" y2="{y:.1f}"/>')
        out.append(
            f'<text class="axis" x="{PAD_L - 6}" y="{y + 3:.1f}" text-anchor="end">'
            f"{escape(fmt_value(top * frac, unit))}</text>"
        )

    # X labels
    if n >= 2:
        for i in range(5):
            idx = round(i / 4 * (n - 1))
            anchor = "start" if i == 0 else "end" if i == 4 else "middle"
            out.append(
                f'<text class="axis" x="{xs[idx]:.1f}" y="{HEIGHT - 8}" text-anchor="{anchor}">'
                f"{escape(_fmt_time(times[idx], timeframe))}</text>"
            )

    # Series (first one as a filled area, like the PVE graphs)
    for si, col in enumerate(columns):
        ys = [y_of(v) for v in col]
        d = _path(xs, ys)
        if not d:
            continue
        if si == 0 and fill_first:
            base = PAD_T + plot_h
            segments = []
            seg = []
            for x, y in zip(xs, ys):
                if y is None:
                    if seg:
                        segments.append(seg)
                    seg = []
                else:
                    seg.append((x, y))
            if seg:
                segments.append(seg)
            for seg in segments:
                pts = " ".join(f"L{x:.1f},{y:.1f}" for x, y in seg)
                out.append(
                    f'<path class="area s{si}" d="M{seg[0][0]:.1f},{base:.1f} {pts} '
                    f'L{seg[-1][0]:.1f},{base:.1f} Z"/>'
                )
        out.append(f'<path class="line s{si}" d="{d}"/>')

    # Hover bands with exact values
    if n:
        band = plot_w / max(n, 1)
        for i in range(n):
            vals = "; ".join(
                f"{labels[ci]}: {fmt_value(columns[ci][i], unit)}" for ci in range(len(columns))
            )
            tip = f"{_fmt_time_full(times[i])} — {vals}"
            out.append(
                f'<rect class="hover" x="{xs[i] - band / 2:.1f}" y="{PAD_T}" '
                f'width="{band:.1f}" height="{plot_h}"><title>{escape(tip)}</title></rect>'
            )

    out.append("</svg>")

    legend = []
    for si, col in enumerate(columns):
        vals = [v for v in col if v is not None]
        legend.append({
            "label": labels[si],
            "css": f"s{si}",
            "last": fmt_value(vals[-1] if vals else None, unit),
            "max": fmt_value(max(vals) if vals else None, unit),
        })
    return {"title": title, "svg": "".join(out), "legend": legend, "empty": not present}


# ---------------------------------------------------------------------------
# Chart sets matching the PVE Summary panels
# ---------------------------------------------------------------------------

def _col(samples, key, scale=1.0):
    out = []
    for s in samples:
        v = s.get(key)
        try:
            out.append(float(v) * scale if v is not None else None)
        except (TypeError, ValueError):
            out.append(None)
    return out


def build_charts(samples, kind, timeframe="hour", cf="AVERAGE"):
    samples = sorted((s for s in samples if s.get("time")), key=lambda s: s["time"])
    times = [int(s["time"]) for s in samples]
    use_max = cf == "MAX"

    def chart(title, series, unit, fill_first=True):
        return line_chart(title, times, series, unit, timeframe, use_max, fill_first)

    if kind == "node":
        return [
            chart("CPU usage", [("CPU", _col(samples, "cpu", 100)),
                                ("IO delay", _col(samples, "iowait", 100))], "percent"),
            chart("Server load", [("Load average", _col(samples, "loadavg"))], "number"),
            chart("Memory usage", [("Used", _col(samples, "memused")),
                                   ("Total", _col(samples, "memtotal"))], "bytes"),
            chart("Network traffic", [("In", _col(samples, "netin")),
                                      ("Out", _col(samples, "netout"))], "bytes_s", fill_first=False),
            chart("CPU pressure stall", [("Some", _col(samples, "pressurecpusome"))], "percent"),
            chart("IO pressure stall", [("Some", _col(samples, "pressureiosome")),
                                        ("Full", _col(samples, "pressureiofull"))], "percent"),
        ]
    return [
        chart("CPU usage", [("CPU", _col(samples, "cpu", 100))], "percent"),
        chart("Memory usage", [("Used", _col(samples, "mem")),
                               ("Total", _col(samples, "maxmem"))], "bytes"),
        chart("Network traffic", [("In", _col(samples, "netin")),
                                  ("Out", _col(samples, "netout"))], "bytes_s", fill_first=False),
        chart("Disk IO", [("Read", _col(samples, "diskread")),
                          ("Write", _col(samples, "diskwrite"))], "bytes_s", fill_first=False),
    ]
