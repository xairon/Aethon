"""Premium animated fluid orb — Living Light visual engine.

Multi-layer QPainter rendering with organic blob deformation,
ambient particles, and audio-reactive state visualizations.
"""

import math
import random

from PyQt6.QtCore import (
    QEasingCurve, QPointF, QPropertyAnimation, QRectF,
    QSequentialAnimationGroup, Qt, QTimer, pyqtProperty,
)
from PyQt6.QtGui import (
    QBrush, QColor, QLinearGradient, QPainter, QPainterPath,
    QPen, QRadialGradient,
)
from PyQt6.QtWidgets import QWidget

from jarvis.gui.state import PipelineState, STATE_COLORS

# ── Utilities ────────────────────────────────────────────────

def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _lerp_color(c1: QColor, c2: QColor, t: float) -> QColor:
    return QColor(
        int(c1.red() + (c2.red() - c1.red()) * t),
        int(c1.green() + (c2.green() - c1.green()) * t),
        int(c1.blue() + (c2.blue() - c1.blue()) * t),
        int(c1.alpha() + (c2.alpha() - c1.alpha()) * t),
    )


# ── Ambient Particle ────────────────────────────────────────

class _Particle:
    """Tiny ambient particle orbiting the orb."""

    __slots__ = ("angle", "radius", "speed", "size", "alpha", "phase")

    def __init__(self, base_radius: float):
        self.angle = random.uniform(0, math.tau)
        self.radius = base_radius + random.uniform(15, 50)
        self.speed = random.uniform(0.003, 0.012)
        self.size = random.uniform(1.2, 2.8)
        self.alpha = random.uniform(0.15, 0.5)
        self.phase = random.uniform(0, math.tau)

    def tick(self, dt: float):
        self.angle = (self.angle + self.speed * dt) % math.tau

    def pos(self, cx: float, cy: float, time: float) -> QPointF:
        r = self.radius + 4 * math.sin(time * 0.5 + self.phase)
        return QPointF(cx + r * math.cos(self.angle),
                       cy + r * math.sin(self.angle))


# ── Blob Harmonics ──────────────────────────────────────────

# (frequency, base_amplitude, phase_speed)
BLOB_HARMONICS = [
    (2, 4.0, 0.7),
    (3, 3.0, 1.1),
    (5, 2.0, 0.5),
    (7, 1.2, 1.4),
    (11, 0.6, 1.9),
]

NUM_BLOB_POINTS = 90


# ── OrbWidget ───────────────────────────────────────────────

class OrbWidget(QWidget):
    """Premium animated fluid orb reflecting pipeline state."""

    ORB_BASE_RADIUS = 82
    WIDGET_SIZE = 280
    TRANSITION_MS = 400

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(self.WIDGET_SIZE, self.WIDGET_SIZE)
        self.setMaximumSize(self.WIDGET_SIZE, self.WIDGET_SIZE)

        # State
        self._state = PipelineState.STOPPED
        self._color = QColor(STATE_COLORS[PipelineState.STOPPED])
        self._prev_color = QColor(self._color)
        self._target_color = QColor(self._color)

        # Animated properties
        self._glow_intensity = 0.15
        self._scale = 1.0
        self._color_blend = 0.0
        self._audio_level = 0.0
        self._smooth_audio = 0.0  # Smoothed for visuals

        # Time tracking
        self._time = 0.0
        self._phases = [random.uniform(0, math.tau) for _ in BLOB_HARMONICS]
        self._deform_intensity = 0.0       # Current deformation amount
        self._target_deform = 0.0          # Target deformation
        self._glow_target = 0.15

        # Particles
        self._particles = [_Particle(self.ORB_BASE_RADIUS) for _ in range(18)]

        # Loading arc
        self._loading_angle = 0.0

        # Animations (Qt property-based)
        self._color_anim: QPropertyAnimation | None = None
        self._breathe_anim: QSequentialAnimationGroup | None = None

        # Master tick timer — 60fps
        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(16)
        self._tick_timer.timeout.connect(self._tick)
        self._tick_timer.start()

    # ── Qt Properties ────────────────────────────────────

    @pyqtProperty(float)
    def scale(self):
        return self._scale

    @scale.setter
    def scale(self, val):
        self._scale = val

    @pyqtProperty(float)
    def color_blend(self):
        return self._color_blend

    @color_blend.setter
    def color_blend(self, val):
        self._color_blend = val
        self._color = _lerp_color(self._prev_color, self._target_color, val)

    # ── Public API ───────────────────────────────────────

    def set_state(self, state: PipelineState):
        if state == self._state:
            return
        self._state = state
        self._stop_animations()

        # Color transition
        self._prev_color = QColor(self._color)
        self._target_color = QColor(STATE_COLORS[state])

        if state == PipelineState.LOADING:
            # Snap color — no animation during CUDA init
            self._color = QColor(self._target_color)
            self._target_deform = 0.3
            self._glow_target = 0.5
            return

        # Animate color blend
        self._color_anim = QPropertyAnimation(self, b"color_blend")
        self._color_anim.setDuration(self.TRANSITION_MS)
        self._color_anim.setStartValue(0.0)
        self._color_anim.setEndValue(1.0)
        self._color_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._color_anim.start()

        # State-specific params
        if state == PipelineState.STOPPED:
            self._target_deform = 0.0
            self._glow_target = 0.1
        elif state == PipelineState.IDLE:
            self._target_deform = 0.5
            self._glow_target = 0.35
            self._start_breathing()
        elif state == PipelineState.LISTENING:
            self._target_deform = 0.9
            self._glow_target = 0.6
        elif state == PipelineState.THINKING:
            self._target_deform = 0.7
            self._glow_target = 0.65
        elif state == PipelineState.SPEAKING:
            self._target_deform = 0.85
            self._glow_target = 0.7

    def set_audio_level(self, level: float):
        self._audio_level = max(0.0, min(1.0, level))

    # ── Animation Helpers ────────────────────────────────

    def _stop_animations(self):
        if self._color_anim is not None:
            self._color_anim.stop()
        if self._breathe_anim is not None:
            self._breathe_anim.stop()
        self._scale = 1.0

    def _start_breathing(self):
        grow = QPropertyAnimation(self, b"scale")
        grow.setDuration(2000)
        grow.setStartValue(1.0)
        grow.setEndValue(1.04)
        grow.setEasingCurve(QEasingCurve.Type.InOutSine)

        shrink = QPropertyAnimation(self, b"scale")
        shrink.setDuration(2000)
        shrink.setStartValue(1.04)
        shrink.setEndValue(1.0)
        shrink.setEasingCurve(QEasingCurve.Type.InOutSine)

        self._breathe_anim = QSequentialAnimationGroup(self)
        self._breathe_anim.addAnimation(grow)
        self._breathe_anim.addAnimation(shrink)
        self._breathe_anim.setLoopCount(-1)
        self._breathe_anim.start()

    # ── Tick (60fps) ─────────────────────────────────────

    def _tick(self):
        dt = 1.0  # Normalized tick (16ms ≈ 1 unit)
        self._time += 0.016

        # Smooth audio level
        self._smooth_audio += (self._audio_level - self._smooth_audio) * 0.18

        # Smooth deformation intensity
        self._deform_intensity += (self._target_deform - self._deform_intensity) * 0.08

        # Smooth glow
        self._glow_intensity += (self._glow_target - self._glow_intensity) * 0.06

        # Advance harmonic phases
        for i, (_, _, speed) in enumerate(BLOB_HARMONICS):
            accel = 1.0
            if self._state == PipelineState.THINKING:
                accel = 2.5
            elif self._state in (PipelineState.LISTENING, PipelineState.SPEAKING):
                accel = 1.5 + self._smooth_audio * 1.5
            self._phases[i] = (self._phases[i] + speed * 0.016 * accel) % math.tau

        # Loading arc
        if self._state == PipelineState.LOADING:
            self._loading_angle = (self._loading_angle + 4.0) % 360.0

        # Advance particles
        for p in self._particles:
            p.tick(dt)

        self.update()

    # ── Visibility — pause le timer quand le widget est masqué ──

    def showEvent(self, event):
        super().showEvent(event)
        if not self._tick_timer.isActive():
            self._tick_timer.start()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._tick_timer.stop()

    # ── Painting ─────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx, cy = self.width() / 2, self.height() / 2
        center = QPointF(cx, cy)
        radius = self.ORB_BASE_RADIUS * self._scale

        # Audio boost for listening/speaking
        audio_boost = 0.0
        if self._state in (PipelineState.LISTENING, PipelineState.SPEAKING):
            audio_boost = self._smooth_audio

        glow_total = self._glow_intensity + audio_boost * 0.3

        # 1 — Deep ambient glow (atmosphere)
        self._paint_ambient_glow(painter, center, radius, glow_total)

        # 2 — Particles (behind orb)
        self._paint_particles(painter, cx, cy, glow_total)

        # 3 — Outer aura ring
        self._paint_aura(painter, center, radius, glow_total)

        # 4 — Main blob body
        blob_path = self._compute_blob_path(cx, cy, radius)
        self._paint_blob_body(painter, blob_path, center, radius)

        # 5 — Inner light
        self._paint_inner_light(painter, center, radius * 0.45)

        # 6 — Surface sheen
        self._paint_sheen(painter, cx, cy, radius)

        # 7 — State overlays
        if self._state == PipelineState.LISTENING:
            self._paint_audio_ring(painter, center, radius)
        elif self._state == PipelineState.THINKING:
            self._paint_thinking_ring(painter, center, radius)
        elif self._state == PipelineState.SPEAKING:
            self._paint_audio_bars(painter, center, radius)
        elif self._state == PipelineState.LOADING:
            self._paint_loading_arc(painter, center, radius)

        painter.end()

    # ── Blob Computation ─────────────────────────────────

    def _compute_blob_path(self, cx: float, cy: float, radius: float) -> QPainterPath:
        path = QPainterPath()
        points: list[QPointF] = []

        for i in range(NUM_BLOB_POINTS):
            angle = math.tau * i / NUM_BLOB_POINTS
            r = radius

            # Harmonic deformation
            for j, (freq, amp, _) in enumerate(BLOB_HARMONICS):
                r += amp * self._deform_intensity * math.sin(
                    freq * angle + self._phases[j]
                )

            # Audio reactivity
            if self._state in (PipelineState.LISTENING, PipelineState.SPEAKING):
                r += self._smooth_audio * 6 * math.sin(
                    4 * angle + self._phases[0] * 2
                )
                r += self._smooth_audio * 3 * math.cos(
                    7 * angle + self._phases[1] * 3
                )

            points.append(QPointF(cx + r * math.cos(angle),
                                  cy + r * math.sin(angle)))

        # Build smooth path using Catmull-Rom → cubic Bezier conversion
        n = len(points)
        path.moveTo(points[0])
        for i in range(n):
            p0 = points[(i - 1) % n]
            p1 = points[i]
            p2 = points[(i + 1) % n]
            p3 = points[(i + 2) % n]

            # Catmull-Rom to Bezier control points (tension=0.5)
            cp1 = QPointF(p1.x() + (p2.x() - p0.x()) / 6,
                          p1.y() + (p2.y() - p0.y()) / 6)
            cp2 = QPointF(p2.x() - (p3.x() - p1.x()) / 6,
                          p2.y() - (p3.y() - p1.y()) / 6)
            path.cubicTo(cp1, cp2, p2)

        path.closeSubpath()
        return path

    # ── Paint Layers ─────────────────────────────────────

    def _paint_ambient_glow(self, p: QPainter, center: QPointF,
                            radius: float, intensity: float):
        """Soft diffuse glow creating atmosphere."""
        glow_r = radius * 2.2
        gc = QColor(self._color)
        grad = QRadialGradient(center, glow_r)
        gc.setAlphaF(intensity * 0.22)
        grad.setColorAt(0.0, gc)
        gc.setAlphaF(intensity * 0.08)
        grad.setColorAt(0.5, gc)
        gc.setAlphaF(0.0)
        grad.setColorAt(1.0, gc)
        p.setBrush(QBrush(grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(center, glow_r, glow_r)

    def _paint_aura(self, p: QPainter, center: QPointF,
                    radius: float, intensity: float):
        """Secondary glow ring around the orb."""
        aura_r = radius * 1.35
        gc = QColor(self._color)
        grad = QRadialGradient(center, aura_r)
        gc.setAlphaF(intensity * 0.35)
        grad.setColorAt(0.65, gc)
        gc.setAlphaF(0.0)
        grad.setColorAt(1.0, gc)
        p.setBrush(QBrush(grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(center, aura_r, aura_r)

    def _paint_particles(self, p: QPainter, cx: float, cy: float,
                         intensity: float):
        """Ambient floating particles."""
        p.setPen(Qt.PenStyle.NoPen)
        for part in self._particles:
            pos = part.pos(cx, cy, self._time)
            pc = QColor(self._color)
            alpha = part.alpha * intensity * 1.5
            pc.setAlphaF(min(alpha, 0.7))
            p.setBrush(QBrush(pc))
            p.drawEllipse(pos, part.size, part.size)

    def _paint_blob_body(self, p: QPainter, blob: QPainterPath,
                         center: QPointF, radius: float):
        """Main orb body with rich gradient, clipped to blob shape."""
        # Gradient shifted up-left for lighting effect
        offset = QPointF(-radius * 0.3, -radius * 0.35)
        grad = QRadialGradient(center + offset, radius * 1.3)
        grad.setColorAt(0.0, QColor(self._color).lighter(155))
        grad.setColorAt(0.4, QColor(self._color).lighter(115))
        grad.setColorAt(0.75, self._color)
        grad.setColorAt(1.0, QColor(self._color).darker(180))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPath(blob)

        # Subtle edge highlight
        edge_pen = QPen(QColor(255, 255, 255, 15), 1.0)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(edge_pen)
        p.drawPath(blob)

    def _paint_inner_light(self, p: QPainter, center: QPointF, radius: float):
        """Bright inner core glow."""
        gc = QColor(self._color).lighter(180)
        grad = QRadialGradient(center, radius)
        gc.setAlphaF(0.35)
        grad.setColorAt(0.0, gc)
        gc.setAlphaF(0.0)
        grad.setColorAt(1.0, gc)
        p.setBrush(QBrush(grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(center, radius, radius)

    def _paint_sheen(self, p: QPainter, cx: float, cy: float, radius: float):
        """Surface highlight / specular reflection."""
        hx = cx - radius * 0.22
        hy = cy - radius * 0.28
        hr = radius * 0.3
        grad = QRadialGradient(QPointF(hx, hy), hr)
        grad.setColorAt(0.0, QColor(255, 255, 255, 80))
        grad.setColorAt(0.5, QColor(255, 255, 255, 20))
        grad.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(hx, hy), hr, hr)

    # ── State Overlays ───────────────────────────────────

    def _paint_audio_ring(self, p: QPainter, center: QPointF, radius: float):
        """Listening state — pulsing audio ring."""
        ring_r = radius + 14 + self._smooth_audio * 8
        segments = 72
        level = self._smooth_audio

        pen_c = QColor(self._color)
        pen_c.setAlphaF(0.4 + level * 0.5)
        p.setPen(QPen(pen_c, 2.0 + level * 1.5,
                       Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)

        path = QPainterPath()
        for i in range(segments + 1):
            angle = math.tau * i / segments
            wave = 1.0 + level * 0.12 * math.sin(
                angle * 6 + self._time * 4
            ) + level * 0.06 * math.cos(
                angle * 10 + self._time * 7
            )
            r = ring_r * wave
            x = center.x() + r * math.cos(angle)
            y = center.y() + r * math.sin(angle)
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        p.drawPath(path)

    def _paint_thinking_ring(self, p: QPainter, center: QPointF, radius: float):
        """Thinking state — orbiting dots with trail."""
        orbit_r = radius + 18
        num_dots = 10
        rot = self._time * 3.0  # Radians rotation

        p.setPen(Qt.PenStyle.NoPen)
        for i in range(num_dots):
            angle = rot + math.tau * i / num_dots
            x = center.x() + orbit_r * math.cos(angle)
            y = center.y() + orbit_r * math.sin(angle)

            # Trail effect: leading dots brighter, trailing dimmer
            alpha = 1.0 - (i / num_dots) * 0.85
            size = 3.5 - i * 0.25
            dc = QColor(self._color)
            dc.setAlphaF(alpha * 0.8)
            p.setBrush(QBrush(dc))
            p.drawEllipse(QPointF(x, y), max(size, 1.2), max(size, 1.2))

    def _paint_audio_bars(self, p: QPainter, center: QPointF, radius: float):
        """Speaking state — radial audio bars."""
        bar_count = 28
        bar_base = radius + 10
        max_h = 22.0
        bar_w = 3.5
        level = self._smooth_audio

        for i in range(bar_count):
            angle = math.tau * i / bar_count
            # Varied bar heights based on audio + animated pattern
            h = max_h * level * (
                0.4 + 0.6 * abs(math.sin(
                    angle * 3 + self._time * 5 + level * 8
                ))
            )

            x1 = center.x() + bar_base * math.cos(angle)
            y1 = center.y() + bar_base * math.sin(angle)
            x2 = center.x() + (bar_base + h) * math.cos(angle)
            y2 = center.y() + (bar_base + h) * math.sin(angle)

            bc = QColor(self._color)
            bc.setAlphaF(0.4 + 0.6 * (h / max_h) if max_h > 0 else 0.4)
            p.setPen(QPen(bc, bar_w, Qt.PenStyle.SolidLine,
                         Qt.PenCapStyle.RoundCap))
            p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    def _paint_loading_arc(self, p: QPainter, center: QPointF, radius: float):
        """Loading state — spinning arc indicator."""
        arc_r = radius + 16
        pen_c = QColor(self._color)
        pen_c.setAlphaF(0.7)
        p.setPen(QPen(pen_c, 3.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)

        rect = QRectF(center.x() - arc_r, center.y() - arc_r,
                       arc_r * 2, arc_r * 2)
        start = int(self._loading_angle * 16)
        span = 90 * 16  # 90-degree arc
        p.drawArc(rect, start, span)

        # Secondary arc (opposite side, dimmer)
        pen_c.setAlphaF(0.3)
        p.setPen(QPen(pen_c, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(rect, start + 180 * 16, 60 * 16)
