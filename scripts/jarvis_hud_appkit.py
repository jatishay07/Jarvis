#!/usr/bin/env python3
"""
Glass hover-only Manual Control HUD (AppKit).

Borderless top strip: pointer within ``hover_zone_px`` of the top of the visible desktop
can reveal a centered 340×58 liquid-glass track with a slim elliptical knob.
No title bar or label chrome. Right-click the control for Quit.

Semantics: knob **left** = standby / stand down, **right** = operational / welcome (when lab inactive).
Animations use NSAnimationContext / Core Animation — no NSTimer / performSelector on the delegate.

Requires: pip install pyobjc-framework-Cocoa
"""
from __future__ import annotations

import math
import os
import sys
import time
import traceback
from ctypes import c_double
from pathlib import Path

from jarvis_hud_lib import acquire_hud_singleton, lab_active, load_cfg, resolve_cfg_path, spawn_stand_down, spawn_welcome

try:
    import Quartz  # noqa: F401 — registers CGColorRef bridge so .CGColor() returns a proper CFType
except ImportError:
    pass

try:
    from Cocoa import (  # type: ignore[import-not-found]
        NSAnimationContext,
        NSApplication,
        NSApplicationActivationPolicyAccessory,
        NSBackingStoreBuffered,
        CABasicAnimation,
        CALayer,
        CAMediaTimingFunction,
        NSBezierPath,
        NSColor,
        NSCursor,
        NSEvent,
        NSGradient,
        NSLeftMouseDownMask,
        NSLeftMouseDraggedMask,
        NSLeftMouseUpMask,
        NSMouseMovedMask,
        NSOtherMouseDraggedMask,
        NSRightMouseDraggedMask,
        NSFloatingWindowLevel,
        NSMakeRect,
        NSMenu,
        NSMenuItem,
        NSScreen,
        NSShadow,
        NSTimer,
        NSView,
        NSViewHeightSizable,
        NSViewMaxXMargin,
        NSViewMinXMargin,
        NSViewWidthSizable,
        NSWindow,
        NSWindowCollectionBehaviorCanJoinAllSpaces,
        NSWindowCollectionBehaviorFullScreenAuxiliary,
        NSWindowCollectionBehaviorMoveToActiveSpace,
        NSWindowStyleMaskBorderless,
        NSWindowStyleMaskClosable,
        NSWindowStyleMaskTitled,
        NSVisualEffectBlendingModeWithinWindow,
        NSVisualEffectBlendingModeBehindWindow,
        NSVisualEffectMaterialHUDWindow,
        NSVisualEffectStateActive,
        NSVisualEffectView,
        NSColorSpace,
        NSGraphicsContext,
        NSObject,
        NSTrackingActiveAlways,
        NSTrackingArea,
        NSTrackingInVisibleRect,
        NSTrackingMouseEnteredAndExited,
        NSTrackingMouseMoved,
        NSFont,
        NSFontAttributeName,
        NSForegroundColorAttributeName,
        NSMutableAttributedString,
        NSMutableParagraphStyle,
        NSShadowAttributeName,
        NSTextAlignmentCenter,
        NSParagraphStyleAttributeName,
    )
    _HAVE_COCOA = True
except ImportError:
    _HAVE_COCOA = False


if _HAVE_COCOA:
    import objc

    _HUD_BUILD_ID = "appkit-figma-floating-control-2026-04-04zb"
    _DEBUG_VISIBILITY_MODES = {"normal", "always_visible", "titled_debug"}
    _REVEAL_MODES = {"edge", "edge_dwell"}

    CONTROL_OVERFLOW_PAD = 140.0
    CONTROL_OVERFLOW_PAD_Y = 30.0
    TRACK_W = 320.0
    CONTROL_W = TRACK_W + CONTROL_OVERFLOW_PAD * 2.0
    CONTROL_H = 80.0 + CONTROL_OVERFLOW_PAD_Y * 2.0
    TRACK_X = CONTROL_OVERFLOW_PAD
    TRACK_H = 68.0
    TRACK_Y = CONTROL_OVERFLOW_PAD_Y
    TRACK_PILL_INSET_Y = 2.0
    TRACK_PILL_H = TRACK_H - TRACK_PILL_INSET_Y * 2.0
    TRACK_PILL_RADIUS = TRACK_PILL_H / 2.0
    KNOB_W = 100.0
    KNOB_H = 64.0
    TRACK_EDGE_PAD = 0.0
    TRAVEL_X0 = TRACK_X + KNOB_W / 2.0 + TRACK_EDGE_PAD
    TRAVEL_X1 = TRACK_X + TRACK_W - KNOB_W / 2.0 - TRACK_EDGE_PAD
    TRAVEL_W = TRAVEL_X1 - TRAVEL_X0
    SNAP_MID = TRAVEL_X0 + TRAVEL_W / 2.0

    CYAN = (0.20, 0.90, 1.00, 1.0)
    BLUE_ACTIVE = (0.0, 0.718, 1.0, 1.0)  # rgba(0,183,255)
    GRAY_KNOB = (0.38, 0.40, 0.44, 1.0)
    SNAP_DURATION = 0.45
    KNOB_PULSE_PERIOD = 2.0
    KNOB_GLOW_PERIOD = 1.5
    _NSEVENT_MODIFIER_CONTROL = 1 << 18


    def _clamp01(v: float) -> float:
        return max(0.0, min(1.0, float(v)))


    def _mix_rgba(a: tuple[float, float, float, float], b: tuple[float, float, float, float], t: float) -> tuple[float, float, float, float]:
        u = _clamp01(t)
        return (
            a[0] + (b[0] - a[0]) * u,
            a[1] + (b[1] - a[1]) * u,
            a[2] + (b[2] - a[2]) * u,
            a[3] + (b[3] - a[3]) * u,
        )


    def _lerp(a: float, b: float, t: float) -> float:
        return float(a) + (float(b) - float(a)) * _clamp01(t)


    def _pulse(now: float, period: float, *, phase: float = 0.0) -> float:
        if period <= 0:
            return 0.0
        return 0.5 + 0.5 * math.sin((float(now) / float(period) + float(phase)) * math.tau)


    def _ns_color(rgba: tuple[float, float, float, float]) -> object:
        return NSColor.colorWithCalibratedRed_green_blue_alpha_(*rgba)


    def _gradient(start: tuple[float, float, float, float], end: tuple[float, float, float, float]):
        return NSGradient.alloc().initWithStartingColor_endingColor_(
            _ns_color(start),
            _ns_color(end),
        )


    def _rounded_rect(rect, radius: float) -> object:
        return NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(rect, radius, radius)


    def _oval(rect) -> object:
        return NSBezierPath.bezierPathWithOvalInRect_(rect)


    def _inset_rect(rect, dx: float, dy: float):
        return NSMakeRect(
            rect.origin.x + dx,
            rect.origin.y + dy,
            rect.size.width - 2.0 * dx,
            rect.size.height - 2.0 * dy,
        )


    def _rect_from_center(cx: float, cy: float, width: float, height: float):
        return NSMakeRect(cx - width / 2.0, cy - height / 2.0, width, height)


    def _gradient3(c0: tuple, c1: tuple, c2: tuple, mid: float = 0.5) -> object:
        """3-stop NSGradient."""
        colors = [_ns_color(c0), _ns_color(c1), _ns_color(c2)]
        locs = (c_double * 3)(0.0, mid, 1.0)
        return NSGradient.alloc().initWithColors_atLocations_colorSpace_(
            colors, locs, NSColorSpace.deviceRGBColorSpace(),
        )


    def _point_in_rect(point, rect) -> bool:
        return (
            point.x >= rect.origin.x
            and point.x <= rect.origin.x + rect.size.width
            and point.y >= rect.origin.y
            and point.y <= rect.origin.y + rect.size.height
        )


    def _visible_frame_under_mouse() -> object:
        return _visible_frame_for_point(NSEvent.mouseLocation())

    def _visible_frame_for_point(p) -> object:
        screens = NSScreen.screens() or []
        for screen in screens:
            f = screen.frame()
            if (
                f.origin.x <= p.x <= f.origin.x + f.size.width
                and f.origin.y <= p.y <= f.origin.y + f.size.height
            ):
                return screen.visibleFrame()
        ms = NSScreen.mainScreen()
        if ms is not None:
            return ms.visibleFrame()
        if screens:
            return screens[0].visibleFrame()
        return NSMakeRect(0, 0, 1440, 900)


    def _format_rect(rect) -> str:
        return (
            f"(x={float(rect.origin.x):.1f}, y={float(rect.origin.y):.1f}, "
            f"w={float(rect.size.width):.1f}, h={float(rect.size.height):.1f})"
        )


    def _normalize_debug_visibility_mode(raw: object) -> str:
        mode = str(raw or "normal").strip().lower()
        return mode if mode in _DEBUG_VISIBILITY_MODES else "normal"


    def _normalize_reveal_mode(raw: object) -> str:
        mode = str(raw or "edge_dwell").strip().lower().replace("-", "_")
        if mode in {"edge", "immediate", "edge_immediate", "hover"}:
            return "edge"
        return mode if mode in _REVEAL_MODES else "edge_dwell"


    def _set_named_timing_function(ctx, name: str) -> None:
        """Use a PyObjC-safe timing function instead of custom control points."""
        try:
            timing = CAMediaTimingFunction.functionWithName_(name)
        except Exception:
            timing = None
        if timing is not None:
            ctx.setTimingFunction_(timing)


    def _log_view_exception(view_name: str) -> None:
        print(f"Jarvis HUD {view_name} failed:", file=sys.stderr, flush=True)
        traceback.print_exc()


    class JarvisFlippedRootView(NSView):
        """Flipped content view for top-down layout (slider below hover band)."""

        def isFlipped(self) -> bool:  # noqa: N802
            return True


    class JarvisHoverSensorView(NSView):
        def initWithFrame_(self, frame):  # noqa: N802
            self = objc.super(JarvisHoverSensorView, self).initWithFrame_(frame)
            if self is None:
                return None
            self._delegate = None
            self._tracking = None
            self._show_indicator = False
            self.setWantsLayer_(True)
            return self

        def isFlipped(self) -> bool:  # noqa: N802
            return True

        def setDelegate_(self, delegate) -> None:  # noqa: N802
            self._delegate = delegate

        def setShowIndicator_(self, show: bool) -> None:  # noqa: N802
            self._show_indicator = bool(show)
            self.setNeedsDisplay_(True)

        def updateTrackingAreas(self) -> None:  # noqa: N802
            if self._tracking is not None:
                self.removeTrackingArea_(self._tracking)
            opts = (
                NSTrackingActiveAlways
                | NSTrackingInVisibleRect
                | NSTrackingMouseEnteredAndExited
                | NSTrackingMouseMoved
            )
            self._tracking = NSTrackingArea.alloc().initWithRect_options_owner_userInfo_(
                self.bounds(),
                opts,
                self,
                None,
            )
            self.addTrackingArea_(self._tracking)
            objc.super(JarvisHoverSensorView, self).updateTrackingAreas()

        def mouseEntered_(self, event) -> None:  # noqa: N802
            if self._delegate is not None:
                self._delegate.handle_hover_sensor_event()

        def mouseExited_(self, event) -> None:  # noqa: N802
            if self._delegate is not None:
                self._delegate.handle_hover_sensor_event()

        def mouseMoved_(self, event) -> None:  # noqa: N802
            if self._delegate is not None:
                self._delegate.handle_hover_sensor_event()

        def drawRect_(self, rect) -> None:  # noqa: N802
            try:
                NSColor.colorWithCalibratedWhite_alpha_(1.0, 0.012).setFill()
                NSBezierPath.fillRect_(self.bounds())
                if not self._show_indicator:
                    return
                NSColor.colorWithCalibratedRed_green_blue_alpha_(0.34, 0.94, 1.0, 0.20).setFill()
                NSBezierPath.fillRect_(
                    NSMakeRect(0, 0, self.bounds().size.width, min(2.0, self.bounds().size.height))
                )
            except Exception:
                _log_view_exception("hover sensor drawRect")


    class JarvisFallbackGlassView(NSView):
        """Drawn pill when NSVisualEffectView is disabled or unavailable."""

        def isFlipped(self) -> bool:  # noqa: N802
            return True

        def drawRect_(self, rect) -> None:  # noqa: N802
            try:
                b = self.bounds()
                radius = b.size.height / 2.0
                shell = _rounded_rect(b, radius)

                _ns_color((0.03, 0.04, 0.05, 0.16)).setFill()
                shell.fill()

                _gradient3(
                    (0.24, 0.24, 0.25, 0.52),
                    (0.18, 0.18, 0.19, 0.42),
                    (0.11, 0.11, 0.12, 0.34),
                    0.48,
                ).drawInBezierPath_angle_(shell, -45.0)

                NSGraphicsContext.currentContext().saveGraphicsState()
                shell.setClip()
                top_h = min(9.0, b.size.height * 0.14)
                _gradient(
                    (0.0, 0.0, 0.0, 0.40), (0.0, 0.0, 0.0, 0.0)
                ).drawInBezierPath_angle_(
                    NSBezierPath.bezierPathWithRect_(NSMakeRect(0.0, 0.0, b.size.width, top_h)),
                    90.0,
                )
                NSGraphicsContext.currentContext().restoreGraphicsState()

                NSGraphicsContext.currentContext().saveGraphicsState()
                shell.setClip()
                bot_h = min(5.0, b.size.height * 0.08)
                _gradient(
                    (1.0, 1.0, 1.0, 0.0), (1.0, 1.0, 1.0, 0.08)
                ).drawInBezierPath_angle_(
                    NSBezierPath.bezierPathWithRect_(
                        NSMakeRect(0.0, b.size.height - bot_h, b.size.width, bot_h)
                    ),
                    90.0,
                )
                NSGraphicsContext.currentContext().restoreGraphicsState()

                gloss = _rounded_rect(_inset_rect(b, 2.0, 2.0), max(1.0, radius - 2.0))
                _gradient3(
                    (1.0, 1.0, 1.0, 0.14),
                    (1.0, 1.0, 1.0, 0.0),
                    (0.0, 0.0, 0.0, 0.06),
                    0.45,
                ).drawInBezierPath_angle_(gloss, -45.0)

                NSGraphicsContext.currentContext().saveGraphicsState()
                shell.setClip()
                bot3 = b.size.height / 3.0
                _gradient(
                    (1.0, 1.0, 1.0, 0.0), (1.0, 1.0, 1.0, 0.05)
                ).drawInBezierPath_angle_(
                    _rounded_rect(
                        NSMakeRect(0.0, b.size.height - bot3, b.size.width, bot3),
                        radius * 0.5,
                    ),
                    90.0,
                )
                NSGraphicsContext.currentContext().restoreGraphicsState()

                edge = _rounded_rect(_inset_rect(b, 0.75, 0.75), max(1.0, radius - 0.75))
                _ns_color((0.39, 0.39, 0.39, 0.25)).setStroke()
                edge.setLineWidth_(1.5)
                edge.stroke()
            except Exception:
                _log_view_exception("fallback glass drawRect")


    class JarvisGlassKnobView(NSView):
        """Layer-backed elliptical knob (glass styling via draw + shadow)."""

        def initWithFrame_(self, frame):  # noqa: N802
            self = objc.super(JarvisGlassKnobView, self).initWithFrame_(frame)
            if self is None:
                return None
            self._activation = 0.0
            self.setWantsLayer_(True)
            return self

        def isFlipped(self) -> bool:  # noqa: N802
            return True

        def setFrameSize_(self, size) -> None:  # noqa: N802
            objc.super(JarvisGlassKnobView, self).setFrameSize_(size)

        def activation(self) -> float:
            return float(self._activation)

        def setActivation_(self, activation: float) -> None:  # noqa: N802
            self._activation = _clamp01(activation)
            self._set_activation_visuals(self._activation)
            self.setNeedsDisplay_(True)

        def setActiveVisual_(self, active: bool) -> None:  # noqa: N802
            self.setActivation_(1.0 if active else 0.0)

        def _set_activation_visuals(self, activation: float) -> None:
            pass  # visual state communicated through drawRect_ only

        def drawRect_(self, rect) -> None:  # noqa: N802
            try:
                b = self.bounds()
                active = _clamp01(self._activation)
                now = time.time()
                knob_pulse = _pulse(now, KNOB_PULSE_PERIOD)
                glow_pulse = _pulse(now, KNOB_GLOW_PERIOD)
                bw, bh = b.size.width, b.size.height
                radius = bh / 2.0

                shell = _rounded_rect(b, radius)

                layer = self.layer()
                if layer is not None:
                    # Keep the view layer transparent so only the pill-shaped draw passes
                    # contribute glow. Generic CALayer shadows reveal the view's rectangular
                    # bounds, which is what was surfacing as the blue box around the knob.
                    layer.setShadowOpacity_(0.0)
                    layer.setShadowRadius_(0.0)
                    layer.setShadowOffset_((0.0, 0.0))
                    layer.setMasksToBounds_(False)

                # Glow is now drawn in the parent track view (not here) to avoid clipping.

                # Knob body: dark transparent glass (Figma uses backdropFilter:blur behind 0.35 alpha fill)
                # Without backdrop blur we keep the fill nearly neutral/dark so the track shows through
                top_c = _mix_rgba((0.34, 0.35, 0.38, 0.20), (0.22, 0.30, 0.38, 0.50), active)
                mid_c = _mix_rgba((0.24, 0.25, 0.28, 0.14), (0.10, 0.16, 0.22, 0.35), active)
                bot_c = _mix_rgba((0.15, 0.16, 0.18, 0.10), (0.05, 0.08, 0.14, 0.22), active)
                _gradient3(top_c, mid_c, bot_c, 0.48).drawInBezierPath_angle_(shell, -45.0)

                # Inner light reflection — top-left white spot, blurred (Figma: blur(6px) white radial)
                NSGraphicsContext.currentContext().saveGraphicsState()
                shell.setClip()
                refl_rect = _rect_from_center(bw * 0.36, bh * 0.44, bw * 0.43, bh * 0.50)
                refl_shadow = NSShadow.alloc().init()
                refl_shadow.setShadowBlurRadius_(16.0)
                refl_shadow.setShadowOffset_((0.0, 0.0))
                refl_shadow.setShadowColor_(_ns_color((1.0, 1.0, 1.0, _lerp(0.15, 0.35, active))))
                refl_shadow.set()
                _ns_color((1.0, 1.0, 1.0, _lerp(0.10, 0.22, active))).setFill()
                _oval(refl_rect).fill()
                NSGraphicsContext.currentContext().restoreGraphicsState()

                # Glass shine overlay — matches Figma linear-gradient 135deg white 0.35 → transparent → black 0.12
                _gradient3(
                    (1.0, 1.0, 1.0, _lerp(0.10, 0.20, active)),
                    (1.0, 1.0, 1.0, 0.0),
                    (0.0, 0.0, 0.0, 0.10),
                    0.55,
                ).drawInBezierPath_angle_(shell, -45.0)

                # Bottom edge highlight — matches Figma bottom half rgba(255,255,255,0.08)
                NSGraphicsContext.currentContext().saveGraphicsState()
                shell.setClip()
                bot_path = NSBezierPath.bezierPathWithRect_(NSMakeRect(0.0, bh / 2.0, bw, bh / 2.0))
                _gradient(
                    (1.0, 1.0, 1.0, 0.0),
                    (1.0, 1.0, 1.0, _lerp(0.04, 0.08, active)),
                ).drawInBezierPath_angle_(bot_path, 90.0)
                NSGraphicsContext.currentContext().restoreGraphicsState()

                # Border — pulsing cyan ring with glow (Figma: 2px rgba(0,183,255,0.6), boxShadow 0 0 25px/50px)
                border = _rounded_rect(_inset_rect(b, 0.75, 0.75), max(1.0, radius - 0.75))
                border_alpha = _mix_rgba((0.0, 0.0, 0.0, 0.0), (0.0, 0.718, 1.0, _lerp(0.70, 0.90, glow_pulse)), active)
                # Outer glow on the border stroke
                border_shadow = NSShadow.alloc().init()
                border_shadow.setShadowBlurRadius_(_lerp(8.0, 16.0, glow_pulse) * active)
                border_shadow.setShadowOffset_((0.0, 0.0))
                border_shadow.setShadowColor_(_ns_color(_mix_rgba((0.0,0.0,0.0,0.0),(0.0, 0.718, 1.0, 1.0), active)))
                NSGraphicsContext.currentContext().saveGraphicsState()
                border_shadow.set()
                _ns_color(border_alpha).setStroke()
                border.setLineWidth_(1.5)
                border.stroke()
                NSGraphicsContext.currentContext().restoreGraphicsState()

                # Pulsing inner core — matches Figma w-8 h-4 radial-gradient(rgba(130,230,255,1) → rgba(0,183,255,0.7))
                # with boxShadow: 0 0 20px rgba(0,183,255,1), scale 1→1.25→1
                core_scale = 1.0 + 0.25 * active * glow_pulse
                core_rect = _rect_from_center(bw / 2.0, bh / 2.0, 30.0 * core_scale, 14.0 * core_scale)
                core_shadow = NSShadow.alloc().init()
                core_shadow.setShadowBlurRadius_(_lerp(6.0, 20.0, active))
                core_shadow.setShadowOffset_((0.0, 0.0))
                core_shadow.setShadowColor_(
                    _ns_color(
                        _mix_rgba(
                            (0.55, 0.55, 0.55, 0.40),
                            (0.0, 0.718, 1.0, _lerp(0.90, 1.00, glow_pulse)),
                            active,
                        )
                    )
                )
                core_path = _rounded_rect(core_rect, core_rect.size.height / 2.0)
                NSGraphicsContext.currentContext().saveGraphicsState()
                core_shadow.set()
                # Fill: center bright white-cyan → edge mid-cyan (matches Figma radial)
                _gradient(
                    _mix_rgba((0.71, 0.71, 0.71, 0.55), (0.51, 0.90, 1.0, 0.90), active),
                    _mix_rgba((0.47, 0.47, 0.47, 0.25), (0.00, 0.718, 1.0, 0.55), active),
                ).drawInBezierPath_angle_(core_path, 0.0)
                NSGraphicsContext.currentContext().restoreGraphicsState()
            except Exception:
                _log_view_exception("knob drawRect")


    class JarvisGlassSliderView(NSView):
        """Slim liquid-glass track with reliable full-pill click and knob drag."""

        def initWithFrame_(self, frame):  # noqa: N802
            self = objc.super(JarvisGlassSliderView, self).initWithFrame_(frame)
            if self is None:
                return None
            self._delegate = None
            self._logical = 0  # 0 left standby, 1 right active
            self._knob_cx = TRAVEL_X0 + (TRAVEL_X1 - TRAVEL_X0) * 0.0  # start left
            self._knob_scale = 1.0
            self._dragging = False
            self._drag_moved = False
            self._press_origin = None
            self._press_on_knob = False
            self._drag_threshold = 5.0
            self._press_scale = False
            self._hover_scale = False
            self._track_click = False
            self._pulse_timer = None
            self.setWantsLayer_(True)
            knob = JarvisGlassKnobView.alloc().initWithFrame_(NSMakeRect(0, 0, KNOB_W, KNOB_H))
            self._knob = knob
            self.addSubview_(knob)
            self._layout_knob_immediate()
            self._refresh_visual_state()
            self.updateTrackingAreas()
            self._pulse_timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                1.0 / 60.0,
                self,
                "pulseTick:",
                None,
                True,
            )
            if self._pulse_timer is not None and hasattr(self._pulse_timer, "setTolerance_"):
                self._pulse_timer.setTolerance_(0.004)
            return self

        def isFlipped(self) -> bool:  # noqa: N802
            return True

        def setDelegate_(self, d) -> None:  # noqa: N802
            self._delegate = d

        def _set_cursor(self, kind: str) -> None:
            try:
                if kind == "closed":
                    NSCursor.closedHandCursor().set()
                elif kind == "open":
                    NSCursor.openHandCursor().set()
                else:
                    NSCursor.arrowCursor().set()
            except Exception:
                pass

        def updateTrackingAreas(self) -> None:  # noqa: N802
            objc.super(JarvisGlassSliderView, self).updateTrackingAreas()
            for ta in list(self.trackingAreas()):
                ui = ta.userInfo()
                if ui is not None and ui.get("JarvisHUDSlider"):
                    self.removeTrackingArea_(ta)
            ta = NSTrackingArea.alloc().initWithRect_options_owner_userInfo_(
                self.bounds(),
                NSTrackingMouseEnteredAndExited
                | NSTrackingActiveAlways
                | NSTrackingMouseMoved
                | NSTrackingInVisibleRect,
                self,
                {"JarvisHUDSlider": True},
            )
            self.addTrackingArea_(ta)

        def setFrameSize_(self, size) -> None:  # noqa: N802
            objc.super(JarvisGlassSliderView, self).setFrameSize_(size)
            self.updateTrackingAreas()

        def logicalValue(self) -> int:
            return int(self._logical)

        def activationProgress(self) -> float:
            return _clamp01((self._knob_cx - TRAVEL_X0) / max(1.0, TRAVEL_X1 - TRAVEL_X0))

        def syncToLogical_(self, logical: int) -> None:  # noqa: N802
            self._logical = 1 if logical else 0
            self._knob_cx = TRAVEL_X1 if self._logical else TRAVEL_X0
            self._layout_knob_immediate()
            self._apply_hover_press_transform(animated=False)
            self._refresh_visual_state()

        def syncFromLab_(self, active: bool) -> None:  # noqa: N802
            self.syncToLogical_(1 if active else 0)

        def _knob_frame_for(self, cx: float, scale: float | None = None):
            s = self._knob_scale if scale is None else float(scale)
            cy = TRACK_Y + TRACK_H / 2.0
            w = KNOB_W * s
            h = KNOB_H * s
            ox = cx - w / 2.0
            oy = cy - h / 2.0
            return NSMakeRect(ox, oy, w, h)

        def _layout_knob_immediate(self) -> None:
            self._knob.setFrame_(self._knob_frame_for(self._knob_cx))

        def _cx_clamped(self, cx: float) -> float:
            return max(TRAVEL_X0, min(TRAVEL_X1, cx))

        def _refresh_visual_state(self) -> None:
            self._knob.setActivation_(self.activationProgress())
            self.setNeedsDisplay_(True)
            self._knob.setNeedsDisplay_(True)

        def _apply_hover_press_transform(self, *, animated: bool = True) -> None:
            s = 1.0
            if self._press_scale:
                s = 0.95
            elif self._hover_scale:
                s = 1.05
            self._knob_scale = s
            target_frame = self._knob_frame_for(self._knob_cx, s)
            if animated:
                def group(ctx) -> None:
                    ctx.setDuration_(0.16 if self._press_scale else 0.22)
                    _set_named_timing_function(ctx, "easeOut")
                    self._knob.animator().setFrame_(target_frame)

                NSAnimationContext.runAnimationGroup_completionHandler_(group, lambda: None)
            else:
                self._knob.setFrame_(target_frame)

        def mouseEntered_(self, event) -> None:  # noqa: N802
            self._hover_scale = True
            self._apply_hover_press_transform()
            p = self.convertPoint_fromView_(event.locationInWindow(), None)
            self._set_cursor("open" if _point_in_rect(p, self._knob.frame()) else "arrow")

        def mouseExited_(self, event) -> None:  # noqa: N802
            self._hover_scale = False
            self._apply_hover_press_transform()
            if not self._dragging:
                self._set_cursor("arrow")

        def mouseMoved_(self, event) -> None:  # noqa: N802
            if self._dragging:
                self._set_cursor("closed")
                return
            p = self.convertPoint_fromView_(event.locationInWindow(), None)
            self._set_cursor("open" if _point_in_rect(p, self._knob.frame()) else "arrow")

        def acceptsFirstResponder(self) -> bool:  # noqa: N802
            return True

        def acceptsFirstMouse_(self, event) -> bool:  # noqa: N802
            return True

        def rightMouseDown_(self, event) -> None:  # noqa: N802
            from Cocoa import NSApp  # type: ignore[import-not-found]

            menu = NSMenu.alloc().init()
            quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "Quit Jarvis HUD",
                "terminate:",
                "q",
            )
            quit_item.setTarget_(NSApp)
            menu.addItem_(quit_item)
            NSMenu.popUpContextMenu_withEvent_forView_(menu, event, self)

        def mouseDown_(self, event) -> None:  # noqa: N802
            if int(event.modifierFlags()) & _NSEVENT_MODIFIER_CONTROL:
                self.rightMouseDown_(event)
                return
            p = self.convertPoint_fromView_(event.locationInWindow(), None)
            self._press_origin = None
            self._press_on_knob = _point_in_rect(p, self._knob.frame())
            self._dragging = False
            self._drag_moved = False
            self._press_scale = False
            if not self._press_on_knob:
                self._apply_hover_press_transform(animated=False)
                self._set_cursor("arrow")
                self._track_click = True
                self._press_origin = p
                return
            self._press_origin = p
            self._press_scale = True
            self._apply_hover_press_transform()
            self._set_cursor("closed")

        def mouseDragged_(self, event) -> None:  # noqa: N802
            self._track_click = False
            if self._press_origin is None or not self._press_on_knob:
                return
            p = self.convertPoint_fromView_(event.locationInWindow(), None)
            dx = abs(p.x - self._press_origin.x)
            dy = abs(p.y - self._press_origin.y)
            if not self._dragging and max(dx, dy) < self._drag_threshold:
                return
            self._dragging = True
            self._drag_moved = True
            self._set_cursor("closed")
            self._knob_cx = self._cx_clamped(p.x)
            self._layout_knob_immediate()
            self._refresh_visual_state()

        def mouseUp_(self, event) -> None:  # noqa: N802
            self._press_scale = False
            self._apply_hover_press_transform()
            if self._track_click:
                self._track_click = False
                self._press_origin = None
                prev = self._logical
                target_cx = TRAVEL_X1 if self._logical == 0 else TRAVEL_X0
                self._spring_knob_x_to(target_cx)
                new = 1 if target_cx >= SNAP_MID else 0
                self._logical = new
                self._refresh_visual_state()
                local = self.convertPoint_fromView_(event.locationInWindow(), None)
                self._set_cursor("open" if _point_in_rect(local, self._knob.frame()) else "arrow")
                if new != prev and self._delegate is not None:
                    self._delegate.handle_slider_change(self, prev, new)
                return
            if self._press_origin is None or not self._press_on_knob:
                self._press_origin = None
                self._press_on_knob = False
                self._dragging = False
                self._drag_moved = False
                self._track_click = False
                local = self.convertPoint_fromView_(event.locationInWindow(), None)
                self._set_cursor("open" if _point_in_rect(local, self._knob.frame()) else "arrow")
                return
            prev = self._logical
            target_cx = TRAVEL_X1 if self._logical == 0 else TRAVEL_X0
            if self._drag_moved:
                target_cx = TRAVEL_X0 if self._knob_cx < SNAP_MID else TRAVEL_X1
            self._press_origin = None
            self._press_on_knob = False
            self._dragging = False
            self._drag_moved = False
            self._spring_knob_x_to(target_cx)
            new = 1 if target_cx >= SNAP_MID else 0
            self._logical = new
            self._refresh_visual_state()
            local = self.convertPoint_fromView_(event.locationInWindow(), None)
            self._set_cursor("open" if _point_in_rect(local, self._knob.frame()) else "arrow")
            if new != prev and self._delegate is not None:
                self._delegate.handle_slider_change(self, prev, new)

        def _spring_knob_x_to(self, target_cx: float) -> None:
            """Slow, slightly elastic snap tuned to feel heavier than a standard switch."""
            target_frame = self._knob_frame_for(target_cx)

            def group(ctx) -> None:
                ctx.setDuration_(SNAP_DURATION)
                _set_named_timing_function(ctx, "easeOut")
                self._knob.animator().setFrame_(target_frame)

            def complete() -> None:
                self._knob_cx = target_cx
                self._refresh_visual_state()

            NSAnimationContext.runAnimationGroup_completionHandler_(group, complete)

        def pulseTick_(self, timer) -> None:  # noqa: N802
            if self.window() is None:
                return
            self.setNeedsDisplay_(True)
            if self._knob is not None:
                self._knob.setNeedsDisplay_(True)

        def drawRect_(self, rect) -> None:  # noqa: N802
            try:
                b = self.bounds()
                now = time.time()
                t = self.activationProgress()
                track_rect = NSMakeRect(TRACK_X, TRACK_Y + TRACK_PILL_INSET_Y, TRACK_W, TRACK_PILL_H)
                knob_pulse = _pulse(now, KNOB_PULSE_PERIOD)
                glow_pulse = _pulse(now, KNOB_GLOW_PERIOD)
                radius = track_rect.size.height / 2.0
                shell = _rounded_rect(track_rect, radius)

                track_glow_pulse = _pulse(now, 2.5)
                inner_glow_alpha = _lerp(0.60, 0.90, track_glow_pulse)
                glow_end = _mix_rgba(
                    (0.39, 0.39, 0.39, 0.08),
                    (0.0, 0.718, 1.0, 0.20 * inner_glow_alpha * t),
                    t,
                )
                _gradient((0.31, 0.31, 0.31, 0.15), glow_end).drawInBezierPath_angle_(shell, 0.0)

                # Track border — matches Figma rgba(100,100,100,0.25) / 1.5px
                track_edge = _rounded_rect(_inset_rect(track_rect, 0.75, 0.75), max(1.0, radius - 0.75))
                _ns_color((0.39, 0.39, 0.39, 0.25)).setStroke()
                track_edge.setLineWidth_(1.5)
                track_edge.stroke()

                knob_frame = self._knob_frame_for(self._knob_cx, self._knob_scale)
                cx = knob_frame.origin.x + knob_frame.size.width / 2.0
                cy = knob_frame.origin.y + knob_frame.size.height / 2.0

                # NSShadow glow drawn in the track view — not clipped to knob bounds.
                # Knob body is now opaque enough to block the fill from bleeding through.
                if t > 0.01:
                    glow_shape = _rounded_rect(knob_frame, knob_frame.size.height / 2.0)
                    glow_shadow = NSShadow.alloc().init()
                    glow_shadow.setShadowBlurRadius_(_lerp(70.0, 100.0, glow_pulse))
                    glow_shadow.setShadowOffset_((0.0, 0.0))
                    glow_shadow.setShadowColor_(_ns_color((0.0, 0.72, 1.0, 1.0 * t)))
                    NSGraphicsContext.currentContext().saveGraphicsState()
                    glow_shadow.set()
                    _ns_color((0.0, 0.72, 1.0, _lerp(0.45, 0.60, glow_pulse) * t)).setFill()
                    glow_shape.fill()
                    NSGraphicsContext.currentContext().restoreGraphicsState()
            except Exception:
                _log_view_exception("slider drawRect")


    # ── Overlay: full-screen dark grid background ─────────────────────────────

    class JarvisBackgroundView(NSView):
        def initWithFrame_(self, frame):  # noqa: N802
            self = objc.super(JarvisBackgroundView, self).initWithFrame_(frame)
            if self is None:
                return None
            self._cfg_bg = {}
            return self

        def setCfg_(self, bg_cfg):
            self._cfg_bg = bg_cfg or {}

        def drawRect_(self, rect):  # noqa: N802
            try:
                bg = self._cfg_bg
                base_alpha = float(bg.get("base_alpha", 0.50))
                grid_size = float(bg.get("grid_size_px", 50))
                grid_alpha_base = float(bg.get("grid_alpha", 0.12))
                grid_alpha = _lerp(grid_alpha_base * 0.65, grid_alpha_base * 1.4,
                                   _pulse(time.time(), 8.0))
                period = float(bg.get("scan_period_seconds", 4.0))

                bounds = self.bounds()
                w = float(bounds.size.width)
                h = float(bounds.size.height)

                # Base dark fill
                _ns_color((0.0, 0.0, 0.0, base_alpha)).setFill()
                NSBezierPath.fillRect_(bounds)

                # Cyan grid lines
                _ns_color((0.0, 0.718, 1.0, grid_alpha)).setStroke()
                grid_path = NSBezierPath.bezierPath()
                grid_path.setLineWidth_(1.0)
                x = 0.0
                while x <= w:
                    grid_path.moveToPoint_((x, 0.0))
                    grid_path.lineToPoint_((x, h))
                    x += grid_size
                y = 0.0
                while y <= h:
                    grid_path.moveToPoint_((0.0, y))
                    grid_path.lineToPoint_((w, y))
                    y += grid_size
                grid_path.stroke()

                # Scan line (y-up, sweeps from top to bottom visually)
                if period > 0:
                    frac = (time.time() % period) / period
                    scan_y = h * (1.0 - frac)  # y-up: top = h, bottom = 0

                    # Gradient trail above the leading edge
                    trail_steps = 10
                    trail_height = 14.0
                    for _ti in range(trail_steps):
                        trail_y = scan_y + _ti * trail_height
                        if trail_y > h:
                            break
                        trail_alpha = 0.28 * (1.0 - _ti / trail_steps)
                        _ns_color((0.0, 0.718, 1.0, trail_alpha)).setFill()
                        NSBezierPath.fillRect_(NSMakeRect(0.0, trail_y, w, trail_height))

                    # Bright glowing leading edge
                    _ns_color((0.0, 0.85, 1.0, 0.9)).setFill()
                    NSBezierPath.fillRect_(NSMakeRect(0.0, scan_y - 1.5, w, 3.0))

                # Corner accents (L-shapes, 64×64px)
                accent_sz = 64.0
                stroke_w = 2.0
                _ns_color((0.0, 0.718, 1.0, 0.4)).setStroke()
                for cx, cy, sx, sy in (
                    (0.0, h, 1.0, -1.0),       # top-left
                    (w, h, -1.0, -1.0),         # top-right
                    (0.0, 0.0, 1.0, 1.0),       # bottom-left
                    (w, 0.0, -1.0, 1.0),        # bottom-right
                ):
                    p = NSBezierPath.bezierPath()
                    p.setLineWidth_(stroke_w)
                    p.moveToPoint_((cx + sx * accent_sz, cy))
                    p.lineToPoint_((cx, cy))
                    p.lineToPoint_((cx, cy + sy * accent_sz))
                    p.stroke()
            except Exception:
                _log_view_exception("background drawRect")

    # ── Overlay: Arc Reactor (spinning gradient ring + orbiting particles) ────

    class JarvisArcReactorView(NSView):
        def initWithFrame_(self, frame):  # noqa: N802
            self = objc.super(JarvisArcReactorView, self).initWithFrame_(frame)
            if self is None:
                return None
            self._arc_angle = 0.0
            self._speaking = False
            self._particle_phases = [i / 8.0 for i in range(8)]
            self._cfg_arc = {}
            self._delegate = None
            self._hover = False
            return self

        def setDelegate_(self, delegate):
            self._delegate = delegate

        def mouseDown_(self, event) -> None:  # noqa: N802
            try:
                if self._delegate is not None:
                    self._delegate.arcReactorClicked()
            except Exception:
                pass

        def mouseEntered_(self, event) -> None:  # noqa: N802
            self._hover = True
            self.setNeedsDisplay_(True)

        def mouseExited_(self, event) -> None:  # noqa: N802
            self._hover = False
            self.setNeedsDisplay_(True)

        def updateTrackingAreas(self) -> None:  # noqa: N802
            try:
                for area in (self.trackingAreas() or []):
                    self.removeTrackingArea_(area)
                opts = (
                    NSTrackingMouseEnteredAndExited
                    | NSTrackingActiveAlways
                    | NSTrackingInVisibleRect
                )
                area = NSTrackingArea.alloc().initWithRect_options_owner_userInfo_(
                    self.bounds(), opts, self, None
                )
                self.addTrackingArea_(area)
            except Exception:
                pass

        def setCfg_(self, arc_cfg):
            self._cfg_arc = arc_cfg or {}

        def advanceTick_(self, dt):
            period = 0.8 if self._speaking else float(self._cfg_arc.get("rotation_period_seconds", 4.0))
            self._arc_angle = (self._arc_angle + (math.tau / period) * dt) % math.tau
            self.setNeedsDisplay_(True)

        def drawRect_(self, rect):  # noqa: N802
            try:
                arc = self._cfg_arc
                bounds = self.bounds()
                w = float(bounds.size.width)
                h = float(bounds.size.height)
                cx = w / 2.0
                cy = h / 2.0

                ring_diam = float(arc.get("ring_diameter_px", 280))
                stroke_w = float(arc.get("ring_stroke_width", 6.0))
                orbit_r = float(arc.get("orbit_radius_px", 150))
                n_particles = int(arc.get("particle_count", 8))

                # Central glow
                glow_shadow = NSShadow.alloc().init()
                glow_shadow.setShadowBlurRadius_(60.0)
                glow_shadow.setShadowOffset_((0.0, 0.0))
                glow_shadow.setShadowColor_(_ns_color((0.0, 0.718, 1.0, 0.25)))
                NSGraphicsContext.currentContext().saveGraphicsState()
                glow_shadow.set()
                _ns_color((0.0, 0.718, 1.0, 0.05)).setFill()
                _oval(_rect_from_center(cx, cy, 20.0, 20.0)).fill()
                NSGraphicsContext.currentContext().restoreGraphicsState()

                # Ring: bright cyan stroke with layered glow; brighter when hovered
                hover_boost = 1.35 if getattr(self, "_hover", False) else 1.0
                ring_oval = _oval(_rect_from_center(cx, cy, ring_diam, ring_diam))
                ring_shadow = NSShadow.alloc().init()
                ring_shadow.setShadowBlurRadius_(18.0 * hover_boost)
                ring_shadow.setShadowOffset_((0.0, 0.0))
                ring_shadow.setShadowColor_(_ns_color((0.0, 0.718, 1.0, min(1.0, 0.9 * hover_boost))))
                NSGraphicsContext.currentContext().saveGraphicsState()
                ring_shadow.set()
                ring_oval.setLineWidth_(stroke_w * hover_boost)
                _ns_color((0.78, 0.94, 1.0, 0.95)).setStroke()
                ring_oval.stroke()
                NSGraphicsContext.currentContext().restoreGraphicsState()

                # Ring glow passes
                for blur_r, glow_a in ((20.0 * hover_boost, 0.3 * hover_boost), (40.0, 0.15)):
                    rs = NSShadow.alloc().init()
                    rs.setShadowBlurRadius_(blur_r)
                    rs.setShadowOffset_((0.0, 0.0))
                    rs.setShadowColor_(_ns_color((0.0, 0.718, 1.0, glow_a)))
                    NSGraphicsContext.currentContext().saveGraphicsState()
                    rs.set()
                    _ns_color((0.0, 0.718, 1.0, 0.01)).setFill()
                    _oval(_rect_from_center(cx, cy, ring_diam, ring_diam)).fill()
                    NSGraphicsContext.currentContext().restoreGraphicsState()

                # Orbiting particles with comet tails + glow
                now = time.time()
                _TAIL_STEPS = 12
                _TAIL_ARC = 0.45   # radians the tail spans behind each particle
                _HEAD_R = 4.5      # head radius in points
                for i in range(n_particles):
                    base_angle = self._arc_angle + i * (math.tau / n_particles)
                    head_alpha = 0.75 + 0.25 * _pulse(now, 4.0, phase=self._particle_phases[i])

                    # Comet tail — segments fading behind the particle
                    for _t in range(_TAIL_STEPS):
                        tail_frac = (_t + 1) / _TAIL_STEPS
                        tail_angle = base_angle - _TAIL_ARC * tail_frac
                        tx = cx + orbit_r * math.cos(tail_angle)
                        ty = cy + orbit_r * math.sin(tail_angle)
                        tail_r = _HEAD_R * (1.0 - tail_frac * 0.8)
                        tail_alpha = head_alpha * (1.0 - tail_frac) * 0.55
                        _ns_color((0.0, 0.718, 1.0, tail_alpha)).setFill()
                        _oval(_rect_from_center(tx, ty, tail_r * 2, tail_r * 2)).fill()

                    # Particle head with glow halo
                    px = cx + orbit_r * math.cos(base_angle)
                    py = cy + orbit_r * math.sin(base_angle)
                    _ps = NSShadow.alloc().init()
                    _ps.setShadowBlurRadius_(12.0)
                    _ps.setShadowOffset_((0.0, 0.0))
                    _ps.setShadowColor_(_ns_color((0.0, 0.85, 1.0, head_alpha * 0.8)))
                    NSGraphicsContext.currentContext().saveGraphicsState()
                    _ps.set()
                    _ns_color((0.0, 0.718, 1.0, head_alpha)).setFill()
                    _oval(_rect_from_center(px, py, _HEAD_R * 2, _HEAD_R * 2)).fill()
                    NSGraphicsContext.currentContext().restoreGraphicsState()
            except Exception:
                _log_view_exception("arc reactor drawRect")

    # ── Overlay: Dictation (holographic typing display) ───────────────────────

    class JarvisDictationView(NSView):
        def initWithFrame_(self, frame):  # noqa: N802
            self = objc.super(JarvisDictationView, self).initWithFrame_(frame)
            if self is None:
                return None
            self._full_text = ""
            self._chars_shown = 0
            self._typing_start_time = 0.0
            self._file_mtime = 0.0
            self._done_typing = False
            self._dictation_file = Path.home() / ".jarvis" / "dictation_text.txt"
            self._ms_per_char = 60.0
            self._cursor_blink_period = 1.5
            self._cfg_dict = {}
            return self

        def setCfg_(self, dict_cfg, state_dir=None):
            self._cfg_dict = dict_cfg or {}
            self._ms_per_char = float(self._cfg_dict.get("ms_per_char", 60))
            self._cursor_blink_period = float(self._cfg_dict.get("cursor_blink_period_seconds", 1.5))
            if state_dir is not None:
                self._dictation_file = Path(state_dir) / "dictation_text.txt"

        def advanceTick_(self, now):
            try:
                stat = self._dictation_file.stat()
                if stat.st_mtime != self._file_mtime:
                    self._file_mtime = stat.st_mtime
                    self._full_text = self._dictation_file.read_text(encoding="utf-8").strip()
                    self._chars_shown = 0
                    self._typing_start_time = now
                    self._done_typing = False
            except FileNotFoundError:
                if self._full_text:
                    self._full_text = ""
                    self._chars_shown = 0
                    self._done_typing = False
                    self._file_mtime = 0.0

            if not self._done_typing and self._full_text:
                elapsed_ms = (now - self._typing_start_time) * 1000.0
                self._chars_shown = min(int(elapsed_ms / max(1.0, self._ms_per_char)), len(self._full_text))
                if self._chars_shown >= len(self._full_text):
                    self._done_typing = True

            self.setNeedsDisplay_(True)

        def drawRect_(self, rect):  # noqa: N802
            try:
                NSColor.clearColor().setFill()
                NSBezierPath.fillRect_(self.bounds())

                display_text = self._full_text[:self._chars_shown] if self._full_text else ""
                if not display_text and (self._done_typing or not self._full_text):
                    return

                bounds = self.bounds()
                bw = float(bounds.size.width)
                bh = float(bounds.size.height)
                font_size = float(self._cfg_dict.get("font_size_pt", 48.0))

                font = NSFont.systemFontOfSize_(font_size)
                para = NSMutableParagraphStyle.alloc().init()
                para.setAlignment_(NSTextAlignmentCenter)

                text_color = _ns_color((0.0, 0.718, 1.0, 1.0))

                attr_str = NSMutableAttributedString.alloc().initWithString_(display_text or " ")
                length = attr_str.length()
                attr_str.addAttribute_value_range_(NSFontAttributeName, font, (0, length))
                attr_str.addAttribute_value_range_(NSForegroundColorAttributeName, text_color, (0, length))
                attr_str.addAttribute_value_range_(NSParagraphStyleAttributeName, para, (0, length))

                # Glow layers
                for blur_r, glow_a in ((20.0, 0.5), (8.0, 0.9)):
                    glow_s = NSShadow.alloc().init()
                    glow_s.setShadowBlurRadius_(blur_r)
                    glow_s.setShadowOffset_((0.0, 0.0))
                    glow_s.setShadowColor_(_ns_color((0.0, 0.718, 1.0, glow_a)))
                    NSGraphicsContext.currentContext().saveGraphicsState()
                    glow_s.set()
                    draw_rect = NSMakeRect(0.0, (bh - font_size * 1.4) / 2.0, bw, font_size * 1.4)
                    attr_str.drawInRect_(draw_rect)
                    NSGraphicsContext.currentContext().restoreGraphicsState()

                # Blinking cursor
                now = time.time()
                cursor_on = _pulse(now, self._cursor_blink_period) > 0.5
                if cursor_on and not self._done_typing:
                    text_size = attr_str.size()
                    text_w = float(text_size.width)
                    cursor_x = bw / 2.0 + text_w / 2.0 + 2.0
                    cursor_h = font_size * 1.1
                    cursor_rect = NSMakeRect(cursor_x, (bh - cursor_h) / 2.0, 2.0, cursor_h)
                    _ns_color((0.0, 0.718, 1.0, 1.0)).setFill()
                    NSBezierPath.fillRect_(cursor_rect)
            except Exception:
                _log_view_exception("dictation drawRect")

    # ── Overlay: Projects Panel (scrollable repo list) ────────────────────────

    class JarvisProjectsView(NSView):
        def initWithFrame_(self, frame):  # noqa: N802
            self = objc.super(JarvisProjectsView, self).initWithFrame_(frame)
            if self is None:
                return None
            self._repos: list[dict] = []          # [{name, html_url}, ...]
            self._active_project: str | None = None
            self._scroll_offset: float = 0.0      # pixels scrolled from top
            self._target_scroll: float = 0.0
            self._hover_index: int = -1
            self._card_h: float = 64.0
            self._card_gap: float = 10.0
            self._header_h: float = 56.0
            self._padding: float = 16.0
            self.setWantsLayer_(True)
            return self

        def setRepos_(self, repos):
            self._repos = repos or []
            self.setNeedsDisplay_(True)

        def setActiveProject_(self, name):
            self._active_project = name
            self.setNeedsDisplay_(True)

        def advanceTick_(self, _dt):
            # Smooth-scroll: lerp offset toward target
            delta = self._target_scroll - self._scroll_offset
            if abs(delta) > 0.5:
                self._scroll_offset += delta * 0.18
                self.setNeedsDisplay_(True)
            elif abs(delta) > 0.0:
                self._scroll_offset = self._target_scroll
                self.setNeedsDisplay_(True)

        def _total_content_height(self) -> float:
            n = len(self._repos)
            if n == 0:
                return self._header_h
            return self._header_h + self._padding + n * (self._card_h + self._card_gap)

        def _max_scroll(self) -> float:
            bounds_h = float(self.bounds().size.height)
            return max(0.0, self._total_content_height() - bounds_h)

        def scrollWheel_(self, event) -> None:  # noqa: N802
            delta = float(event.scrollingDeltaY()) * (-1 if event.isDirectionInvertedFromDevice() else 1)
            self._target_scroll = max(0.0, min(self._max_scroll(), self._target_scroll - delta * 2.0))

        def mouseMoved_(self, event) -> None:  # noqa: N802
            loc = self.convertPoint_fromView_(event.locationInWindow(), None)
            y = float(self.bounds().size.height) - float(loc.y) + self._scroll_offset
            y -= self._header_h + self._padding
            idx = int(y // (self._card_h + self._card_gap))
            new_hover = idx if 0 <= idx < len(self._repos) else -1
            if new_hover != self._hover_index:
                self._hover_index = new_hover
                self.setNeedsDisplay_(True)

        def mouseDown_(self, event) -> None:  # noqa: N802
            loc = self.convertPoint_fromView_(event.locationInWindow(), None)
            y = float(self.bounds().size.height) - float(loc.y) + self._scroll_offset
            y -= self._header_h + self._padding
            idx = int(y // (self._card_h + self._card_gap))
            if 0 <= idx < len(self._repos):
                repo = self._repos[idx]
                self._active_project = repo["name"]
                self.setNeedsDisplay_(True)
                # Notify delegate via notification
                try:
                    from Cocoa import NSNotificationCenter  # type: ignore[import-not-found]
                    NSNotificationCenter.defaultCenter().postNotificationName_object_userInfo_(
                        "JarvisProjectSelected", self, {"repo": repo},
                    )
                except Exception:
                    pass

        def updateTrackingAreas(self) -> None:  # noqa: N802
            try:
                for area in (self.trackingAreas() or []):
                    self.removeTrackingArea_(area)
                from Cocoa import NSTrackingArea  # type: ignore[import-not-found]
                opts = (
                    0x01   # NSTrackingMouseEnteredAndExited
                    | 0x02  # NSTrackingMouseMoved
                    | 0x20  # NSTrackingActiveInKeyWindow
                    | 0x80  # NSTrackingInVisibleRect
                    | 0x100  # NSTrackingActiveAlways
                )
                area = NSTrackingArea.alloc().initWithRect_options_owner_userInfo_(
                    self.bounds(), opts, self, None
                )
                self.addTrackingArea_(area)
            except Exception:
                pass

        def drawRect_(self, rect) -> None:  # noqa: N802
            try:
                bounds = self.bounds()
                w = float(bounds.size.width)
                h = float(bounds.size.height)
                offset = self._scroll_offset
                now = time.time()

                # Panel background
                _ns_color((0.0, 0.0, 0.0, 0.75)).setFill()
                NSBezierPath.fillRect_(bounds)

                # Cyan border glow via shadow
                border_shadow = NSShadow.alloc().init()
                border_shadow.setShadowBlurRadius_(12.0)
                border_shadow.setShadowOffset_((0.0, 0.0))
                border_shadow.setShadowColor_(_ns_color((0.0, 0.718, 1.0, 0.5)))
                NSGraphicsContext.currentContext().saveGraphicsState()
                border_shadow.set()
                _ns_color((0.0, 0.718, 1.0, 0.25)).setStroke()
                border_path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                    NSMakeRect(1.0, 1.0, w - 2.0, h - 2.0), 16.0, 16.0
                )
                border_path.setLineWidth_(1.5)
                border_path.stroke()
                NSGraphicsContext.currentContext().restoreGraphicsState()

                # Clip to panel bounds
                clip_path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                    bounds, 16.0, 16.0
                )
                clip_path.setClip()

                # Header
                header_label = "PROJECTS"
                header_attrs = {
                    NSFontAttributeName: NSFont.systemFontOfSize_weight_(16.0, -0.4),
                    NSForegroundColorAttributeName: _ns_color((0.0, 0.718, 1.0, 0.9)),
                }
                h_str = NSMutableAttributedString.alloc().initWithString_attributes_(
                    header_label, header_attrs
                )
                h_size = h_str.size()
                h_w = float(h_size.width)
                h_h_sz = float(h_size.height)
                h_shadow = NSShadow.alloc().init()
                h_shadow.setShadowBlurRadius_(10.0)
                h_shadow.setShadowOffset_((0.0, 0.0))
                h_shadow.setShadowColor_(_ns_color((0.0, 0.718, 1.0, 0.6)))
                NSGraphicsContext.currentContext().saveGraphicsState()
                h_shadow.set()
                h_str.drawAtPoint_(((w - h_w) / 2.0, h - self._header_h / 2.0 - h_h_sz / 2.0))
                NSGraphicsContext.currentContext().restoreGraphicsState()

                # Header separator
                _ns_color((0.0, 0.718, 1.0, 0.2)).setStroke()
                sep = NSBezierPath.bezierPath()
                sep.setLineWidth_(1.0)
                sep.moveToPoint_((self._padding, h - self._header_h))
                sep.lineToPoint_((w - self._padding, h - self._header_h))
                sep.stroke()

                # Cards
                card_w = w - self._padding * 2
                for i, repo in enumerate(self._repos):
                    card_y_from_top = self._header_h + self._padding + i * (self._card_h + self._card_gap)
                    card_screen_y = h - card_y_from_top - self._card_h + offset
                    # Skip invisible cards
                    if card_screen_y + self._card_h < 0 or card_screen_y > h:
                        continue

                    is_active = repo["name"] == self._active_project
                    is_hover = i == self._hover_index

                    # Card fill
                    if is_active:
                        fill_alpha = 0.22
                        border_alpha = 0.6
                        text_alpha = 1.0
                        glow_alpha = 0.7
                    elif is_hover:
                        fill_alpha = 0.14
                        border_alpha = 0.35
                        text_alpha = 0.95
                        glow_alpha = 0.4
                    else:
                        fill_alpha = 0.08
                        border_alpha = 0.18
                        text_alpha = 0.75
                        glow_alpha = 0.0

                    card_rect = NSMakeRect(self._padding, card_screen_y, card_w, self._card_h)
                    card_path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                        card_rect, 10.0, 10.0
                    )

                    # Glow behind active card
                    if glow_alpha > 0:
                        gs = NSShadow.alloc().init()
                        gs.setShadowBlurRadius_(16.0)
                        gs.setShadowOffset_((0.0, 0.0))
                        gs.setShadowColor_(_ns_color((0.0, 0.718, 1.0, glow_alpha)))
                        NSGraphicsContext.currentContext().saveGraphicsState()
                        gs.set()
                        _ns_color((0.0, 0.718, 1.0, 0.01)).setFill()
                        card_path.fill()
                        NSGraphicsContext.currentContext().restoreGraphicsState()

                    _ns_color((0.0, 0.718, 1.0, fill_alpha)).setFill()
                    card_path.fill()
                    _ns_color((0.0, 0.718, 1.0, border_alpha)).setStroke()
                    card_path.setLineWidth_(1.2)
                    card_path.stroke()

                    # Active indicator dot (right side)
                    if is_active:
                        dot_x = self._padding + card_w - 20.0
                        dot_y = card_screen_y + self._card_h / 2.0 - 3.0
                        dot_pulse = 0.7 + 0.3 * _pulse(now, 1.5)
                        _ns_color((0.0, 0.9, 1.0, dot_pulse)).setFill()
                        _oval(NSMakeRect(dot_x, dot_y, 6.0, 6.0)).fill()

                    # Project name
                    label_attrs = {
                        NSFontAttributeName: NSFont.systemFontOfSize_weight_(17.0, -0.4),
                        NSForegroundColorAttributeName: _ns_color((0.0, 0.85, 1.0, text_alpha)),
                    }
                    if is_active:
                        ts = NSShadow.alloc().init()
                        ts.setShadowBlurRadius_(8.0)
                        ts.setShadowOffset_((0.0, 0.0))
                        ts.setShadowColor_(_ns_color((0.0, 0.718, 1.0, 0.5)))
                        label_attrs[NSShadowAttributeName] = ts

                    label_str = NSMutableAttributedString.alloc().initWithString_attributes_(
                        repo["name"], label_attrs
                    )
                    l_size = label_str.size()
                    label_str.drawAtPoint_((
                        self._padding + (card_w - float(l_size.width)) / 2.0,
                        card_screen_y + (self._card_h - float(l_size.height)) / 2.0,
                    ))

                # Top/bottom fade masks using NSGradient (no raw Quartz CGContext needed)
                for fade_y, direction in ((h - self._header_h - 32.0, True), (0.0, False)):
                    grad_rect = NSMakeRect(0.0, fade_y, w, 32.0)
                    try:
                        c0 = _ns_color((0.0, 0.0, 0.0, 0.0 if direction else 0.55))
                        c1 = _ns_color((0.0, 0.0, 0.0, 0.55 if direction else 0.0))
                        grad = NSGradient.alloc().initWithStartingColor_endingColor_(c0, c1)
                        angle = 270.0 if direction else 90.0  # 270=down, 90=up
                        grad.drawInRect_angle_(grad_rect, angle)
                    except Exception:
                        _ns_color((0.0, 0.0, 0.0, 0.45)).setFill()
                        NSBezierPath.fillRect_(grad_rect)

            except Exception:
                _log_view_exception("projects drawRect")

    class JarvisHUDDelegate(NSObject):
        def init(self):  # noqa: N802
            self = objc.super(JarvisHUDDelegate, self).init()
            if self is None:
                return None
            self._win = None
            self._slide_container = None
            self._slider = None
            self._cfg = None
            self._cfg_path = None
            self._hide_gen = 0
            self._hover_px = 80.0
            self._anchor_bottom = False
            self._hide_delay = 0.38
            self._reveal_mode = "edge_dwell"
            self._reveal_dwell = 0.40
            self._hover_zone_entered_at = None
            self._hover_zone_satisfied = False
            self._last_want = False
            self._hide_pending = False
            self._slide_shown = False
            self._local_monitor = None
            self._global_monitor = None
            self._click_monitor = None
            self._hover_timer = None
            self._sensor_windows = []
            self._cooldown = 2.5
            self._last_fire = 0.0
            self._debug_visibility_mode = "normal"
            self._host_kind = "unknown"
            self._margin_top = 4.0
            self._margin_bottom = 100.0
            self._titled_debug = False
            self._window_width = CONTROL_W
            self._window_height = CONTROL_H + 8.0
            self._poll_interval = 0.08
            self._sensor_height = 8.0
            self._show_anchor_strip = False
            self._hidden_offset = 14.0
            self._show_duration = 0.26
            self._hide_duration = 0.18
            self._visibility_animating = False
            self._visibility_generation = 0
            # Overlay windows
            self._overlay_bg_windows = []
            self._overlay_arc_win = None
            self._overlay_arc_view = None
            self._overlay_dict_win = None
            self._overlay_dict_view = None
            self._overlay_lab_was_active = False
            self._overlay_anim_timer = None
            self._overlay_poll_timer = None
            self._overlay_last_anim_time = time.time()
            # Projects overlay
            self._overlay_projects_win = None
            self._overlay_projects_view = None
            self._overlay_projects_active = False
            self._overlay_projects_cache_mtime = 0.0
            return self

        def _target_window_frame_for_cursor(self):
            vf = _visible_frame_under_mouse()
            win_w = float(self._window_width)
            win_h = float(self._window_height)
            win_x = vf.origin.x + (vf.size.width - win_w) / 2.0
            if self._anchor_bottom:
                win_y = vf.origin.y + float(self._margin_bottom) - CONTROL_OVERFLOW_PAD_Y
            elif self._titled_debug:
                win_y = vf.origin.y + vf.size.height - win_h - 24.0
            else:
                win_y = vf.origin.y + vf.size.height - win_h - float(self._margin_top) + CONTROL_OVERFLOW_PAD_Y
            return vf, NSMakeRect(win_x, win_y, win_w, win_h)

        def _hidden_window_frame_for(self, frame):
            if self._titled_debug:
                return frame
            offset = float(self._hidden_offset)
            if self._anchor_bottom:
                offset = max(offset, CONTROL_OVERFLOW_PAD_Y + TRACK_H + 24.0)
                return NSMakeRect(frame.origin.x, frame.origin.y - offset, frame.size.width, frame.size.height)
            offset = max(offset, CONTROL_OVERFLOW_PAD_Y + TRACK_H + 24.0)
            return NSMakeRect(frame.origin.x, frame.origin.y + offset, frame.size.width, frame.size.height)

        def _reposition_window_for_cursor(self, *, visible: bool | None = None) -> None:
            if self._win is None:
                return
            _, target_visible = self._target_window_frame_for_cursor()
            if visible is None:
                visible = self._slide_shown or self._debug_visibility_mode != "normal"
            target = target_visible if visible else self._hidden_window_frame_for(target_visible)
            current = self._win.frame()
            if (
                abs(float(current.origin.x) - float(target.origin.x)) < 0.5
                and abs(float(current.origin.y) - float(target.origin.y)) < 0.5
                and abs(float(current.size.width) - float(target.size.width)) < 0.5
                and abs(float(current.size.height) - float(target.size.height)) < 0.5
            ):
                return
            self._win.setFrame_display_(target, False)

        def _sensor_frame_for_screen(self, screen):
            vf = screen.visibleFrame()
            h = float(self._sensor_height)
            if self._anchor_bottom:
                y = vf.origin.y
            else:
                y = vf.origin.y + vf.size.height - h
            return NSMakeRect(vf.origin.x, y, vf.size.width, h)

        def _refresh_sensor_windows(self) -> None:
            existing = list(self._sensor_windows)
            self._sensor_windows = []
            for entry in existing:
                try:
                    entry["window"].orderOut_(None)
                    entry["window"].close()
                except Exception:
                    pass
            if self._debug_visibility_mode != "normal":
                return
            for screen in NSScreen.screens() or []:
                frame = self._sensor_frame_for_screen(screen)
                win = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
                    frame,
                    NSWindowStyleMaskBorderless,
                    NSBackingStoreBuffered,
                    False,
                )
                win.setOpaque_(False)
                win.setBackgroundColor_(NSColor.clearColor())
                win.setLevel_(NSFloatingWindowLevel)
                win.setIgnoresMouseEvents_(False)
                win.setAcceptsMouseMovedEvents_(True)
                win.setReleasedWhenClosed_(False)
                win.setCollectionBehavior_(
                    NSWindowCollectionBehaviorMoveToActiveSpace
                    | NSWindowCollectionBehaviorFullScreenAuxiliary
                )
                if hasattr(win, "setHasShadow_"):
                    win.setHasShadow_(False)
                sensor = JarvisHoverSensorView.alloc().initWithFrame_(
                    NSMakeRect(0, 0, frame.size.width, frame.size.height)
                )
                sensor.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)
                sensor.setDelegate_(self)
                sensor.setShowIndicator_(self._show_anchor_strip)
                win.setContentView_(sensor)
                win.orderFrontRegardless()
                self._sensor_windows.append({"window": win, "view": sensor})

        def handle_hover_sensor_event(self) -> None:
            self._sync_hover_visibility_from_cursor()

        def _reset_reveal_gate(self) -> None:
            self._hover_zone_entered_at = None
            self._hover_zone_satisfied = False

        def _want_slide_visible(self) -> bool:
            cursor_in_zone = self._cursor_in_hover_zone()
            mouse_in_window = self._mouse_in_window_frame()
            if self._slide_shown:
                if not cursor_in_zone:
                    self._reset_reveal_gate()
                return cursor_in_zone or mouse_in_window
            if self._reveal_mode == "edge":
                if not cursor_in_zone:
                    self._reset_reveal_gate()
                return cursor_in_zone or mouse_in_window
            if cursor_in_zone:
                now = time.time()
                if self._hover_zone_entered_at is None:
                    self._hover_zone_entered_at = now
                if now - float(self._hover_zone_entered_at) >= self._reveal_dwell:
                    self._hover_zone_satisfied = True
                return self._hover_zone_satisfied
            self._reset_reveal_gate()
            return mouse_in_window

        def _sync_hover_visibility_from_cursor(self) -> None:
            if self._win is None:
                return
            if self._debug_visibility_mode != "normal":
                self._reset_reveal_gate()
                self._reposition_window_for_cursor()
                if not self._slide_shown:
                    self._slide_shown = True
                    if self._slider is not None:
                        self._slider.syncFromLab_(lab_active(self._cfg))
                    self._set_slide_visible(True, immediate=True)
                return
            want = self._want_slide_visible()
            if want:
                if self._slide_shown and not self._visibility_animating:
                    self._reposition_window_for_cursor(visible=True)
                if self._hide_pending or not self._last_want:
                    self._hide_gen += 1
                self._hide_pending = False
                self._last_want = True
                if not self._slide_shown and not self._visibility_animating:
                    self._slide_shown = True
                    if self._slider is not None:
                        self._slider.syncFromLab_(lab_active(self._cfg))
                    self._set_slide_visible(True)
            else:
                if self._last_want:
                    self._last_want = False
                    if self._slide_shown and not self._hide_pending:
                        self._hide_pending = True
                        self._schedule_hide_debounced()

        def _cursor_in_hover_zone(self) -> bool:
            loc = NSEvent.mouseLocation()
            vf = _visible_frame_for_point(loc)
            h = float(self._hover_px)
            if self._anchor_bottom:
                return loc.y <= vf.origin.y + h
            top = vf.origin.y + vf.size.height
            return loc.y >= top - h

        def _schedule_hide_debounced(self) -> None:
            gen = self._hide_gen

            def complete() -> None:
                self._hide_pending = False
                if gen != self._hide_gen:
                    return
                if self._cursor_in_hover_zone() or self._mouse_in_window_frame():
                    return
                self._slide_shown = False
                self._set_slide_visible(False)

            def group(ctx) -> None:
                ctx.setDuration_(self._hide_delay)

            NSAnimationContext.runAnimationGroup_completionHandler_(group, complete)

        def _mouse_in_window_frame(self) -> bool:
            if not self._slide_shown or self._win is None or not bool(self._win.isVisible()):
                return False
            loc = NSEvent.mouseLocation()
            f = self._win.frame()
            pad_x = max(0.0, CONTROL_OVERFLOW_PAD - 12.0)
            pad_y = max(0.0, CONTROL_OVERFLOW_PAD_Y - 12.0)
            fx = f.origin.x + pad_x
            fy = f.origin.y + pad_y
            fw = max(1.0, f.size.width - 2.0 * pad_x)
            fh = max(1.0, f.size.height - 2.0 * pad_y)
            return (
                loc.x >= fx
                and loc.x <= fx + fw
                and loc.y >= fy
                and loc.y <= fy + fh
            )

        def _set_slide_visible(self, vis: bool, *, immediate: bool = False) -> None:
            sc = self._slide_container
            win = self._win
            if sc is None or win is None:
                return
            self._visibility_generation += 1
            generation = self._visibility_generation
            if self._debug_visibility_mode == "normal" and not self._titled_debug:
                _, visible_frame = self._target_window_frame_for_cursor()
                hidden_frame = self._hidden_window_frame_for(visible_frame)
                target_frame = visible_frame if vis else hidden_frame
                win.setIgnoresMouseEvents_(not vis)
                sc.setHidden_(False)
                sc.setAlphaValue_(1.0)
                if immediate:
                    self._visibility_animating = False
                    win.setAlphaValue_(1.0 if vis else 0.0)
                    win.setFrame_display_(target_frame, False)
                    if vis:
                        win.orderFrontRegardless()
                    else:
                        win.orderOut_(None)
                    return
                if vis:
                    win.setFrame_display_(hidden_frame, False)
                    win.setAlphaValue_(1.0)
                    win.orderFrontRegardless()
                self._visibility_animating = True

                def complete() -> None:
                    if generation != self._visibility_generation:
                        return
                    self._visibility_animating = False
                    if not vis:
                        win.orderOut_(None)

                def group(ctx) -> None:
                    ctx.setDuration_(self._show_duration if vis else self._hide_duration)
                    _set_named_timing_function(ctx, "easeOut" if vis else "easeInEaseOut")
                    if not vis:
                        win.animator().setAlphaValue_(0.0)
                    win.animator().setFrame_display_(target_frame, False)

                NSAnimationContext.runAnimationGroup_completionHandler_(group, complete)
                return
            self._win.setIgnoresMouseEvents_(not vis)
            if immediate:
                self._visibility_animating = False
                sc.setHidden_(not vis)
                sc.setAlphaValue_(1.0 if vis else 0.0)
                f = sc.frame()
                target_y = self._slide_y_visible if vis else self._slide_y_hidden
                sc.setFrame_(NSMakeRect(f.origin.x, target_y, f.size.width, f.size.height))
                return
            if vis:
                sc.setHidden_(False)
            self._visibility_animating = True

            def complete() -> None:
                if generation != self._visibility_generation:
                    return
                self._visibility_animating = False
                if not vis:
                    sc.setHidden_(True)

            def group(ctx) -> None:
                ctx.setDuration_(self._show_duration if vis else self._hide_duration)
                _set_named_timing_function(ctx, "easeOut" if vis else "easeInEaseOut")
                f = sc.frame()
                base_y = self._slide_y_visible
                hide_y = self._slide_y_hidden
                target_y = base_y if vis else hide_y
                sc.animator().setAlphaValue_(1.0 if vis else 0.0)
                sc.animator().setFrame_(NSMakeRect(f.origin.x, target_y, f.size.width, f.size.height))

            NSAnimationContext.runAnimationGroup_completionHandler_(group, complete)

        def hoverPollTick_(self, timer) -> None:  # noqa: N802
            self._sync_hover_visibility_from_cursor()

        def _update_track_glow(self, activation: float) -> None:
            pass  # track glow layer removed to prevent CALayer crash

        def handle_slider_change(self, slider, prev: int, new: int) -> None:
            now = time.time()
            if now - self._last_fire < self._cooldown:
                slider.syncToLogical_(prev)
                return
            if new == 1 and prev == 0:
                if not lab_active(self._cfg):
                    self._show_overlays()
                    self._overlay_lab_was_active = True
                    spawn_welcome(self._cfg_path)
                    self._last_fire = now
            elif new == 0 and prev == 1:
                spawn_stand_down(self._cfg_path)
                self._last_fire = now
            self._update_track_glow(float(new))

        def _make_overlay_window(self, frame):
            """Create a borderless, non-interactive, always-on-top overlay window."""
            win = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
                frame, NSWindowStyleMaskBorderless, NSBackingStoreBuffered, False,
            )
            win.setOpaque_(False)
            win.setBackgroundColor_(NSColor.clearColor())
            win.setLevel_(NSFloatingWindowLevel - 1)
            win.setIgnoresMouseEvents_(True)
            win.setHasShadow_(False)
            win.setReleasedWhenClosed_(False)
            win.setCollectionBehavior_(
                NSWindowCollectionBehaviorCanJoinAllSpaces   # 1
                | NSWindowCollectionBehaviorFullScreenAuxiliary  # 256
                | 16   # NSWindowCollectionBehaviorStationary — not exported by PyObjC
                | 64   # NSWindowCollectionBehaviorIgnoresCycle
            )
            win.setAlphaValue_(0.0)
            return win

        def _build_overlay_windows(self):
            cfg = self._cfg
            overlay_cfg = cfg.get("hud_overlay", {})
            if not overlay_cfg.get("enabled", True):
                return

            state_dir = str(Path(os.path.expanduser(cfg.get("state_dir", "~/.jarvis"))))

            main_screen = NSScreen.mainScreen()
            if main_screen is None:
                return
            main_frame = main_screen.frame()

            # Background: one per screen
            bg_cfg = overlay_cfg.get("background", {})
            if bg_cfg.get("enabled", True):
                for screen in (NSScreen.screens() or [main_screen]):
                    sf = screen.frame()
                    win = self._make_overlay_window(sf)
                    win.setLevel_(-1)  # NSNormalWindowLevel-1: behind all app windows
                    view = JarvisBackgroundView.alloc().initWithFrame_(
                        NSMakeRect(0, 0, float(sf.size.width), float(sf.size.height))
                    )
                    view.setCfg_(bg_cfg)
                    win.setContentView_(view)
                    win.orderFrontRegardless()
                    self._overlay_bg_windows.append({"window": win, "view": view, "screen": screen})

            # Arc Reactor: centered on main screen
            arc_cfg = overlay_cfg.get("arc_reactor", {})
            if arc_cfg.get("enabled", True):
                size_px = float(arc_cfg.get("size_px", 300))
                arc_x = float(main_frame.origin.x) + (float(main_frame.size.width) - size_px) / 2.0
                arc_y = float(main_frame.origin.y) + (float(main_frame.size.height) - size_px) / 2.0
                arc_frame = NSMakeRect(arc_x, arc_y, size_px, size_px)
                win = self._make_overlay_window(arc_frame)
                win.setLevel_(-1)  # behind all app windows
                view = JarvisArcReactorView.alloc().initWithFrame_(
                    NSMakeRect(0, 0, size_px, size_px)
                )
                view.setCfg_(arc_cfg)
                view.setDelegate_(self)
                win.setIgnoresMouseEvents_(False)
                win.setAcceptsMouseMovedEvents_(True)
                win.setContentView_(view)
                win.orderFrontRegardless()
                self._overlay_arc_win = win
                self._overlay_arc_view = view

            # Dictation: centered horizontally, at 60% height
            dict_cfg = overlay_cfg.get("dictation", {})
            if dict_cfg.get("enabled", True):
                dict_w = float(dict_cfg.get("window_width", 800))
                dict_h = float(dict_cfg.get("window_height", 120))
                y_frac = float(dict_cfg.get("screen_y_fraction", 0.90))
                dict_x = float(main_frame.origin.x) + (float(main_frame.size.width) - dict_w) / 2.0
                dict_y = float(main_frame.origin.y) + float(main_frame.size.height) * (1.0 - y_frac) - dict_h / 2.0
                dict_frame = NSMakeRect(dict_x, dict_y, dict_w, dict_h)
                win = self._make_overlay_window(dict_frame)
                win.setLevel_(-1)  # behind all app windows
                view = JarvisDictationView.alloc().initWithFrame_(
                    NSMakeRect(0, 0, dict_w, dict_h)
                )
                view.setCfg_(dict_cfg, state_dir=state_dir)
                win.setContentView_(view)
                win.orderFrontRegardless()
                self._overlay_dict_win = win
                self._overlay_dict_view = view

            # Keep slider on top
            if self._win is not None:
                self._win.orderFrontRegardless()

        def _build_projects_overlay(self):
            cfg = self._cfg
            if not cfg.get("projects", {}).get("enabled", True):
                return
            main_screen = NSScreen.mainScreen()
            if main_screen is None:
                return
            mf = main_screen.frame()
            panel_w = 300.0
            panel_h = min(480.0, float(mf.size.height) * 0.65)
            panel_x = float(mf.origin.x) + float(mf.size.width) - panel_w - 24.0
            panel_y = float(mf.origin.y) + (float(mf.size.height) - panel_h) / 2.0
            win = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
                NSMakeRect(panel_x, panel_y, panel_w, panel_h),
                NSWindowStyleMaskBorderless,
                NSBackingStoreBuffered,
                False,
            )
            win.setOpaque_(False)
            win.setBackgroundColor_(NSColor.clearColor())
            win.setLevel_(NSFloatingWindowLevel)
            win.setIgnoresMouseEvents_(False)
            win.setAcceptsMouseMovedEvents_(True)
            win.setHasShadow_(False)
            win.setReleasedWhenClosed_(False)
            win.setCollectionBehavior_(
                NSWindowCollectionBehaviorCanJoinAllSpaces
                | NSWindowCollectionBehaviorFullScreenAuxiliary
                | 16  # Stationary
            )
            win.setAlphaValue_(0.0)
            view = JarvisProjectsView.alloc().initWithFrame_(
                NSMakeRect(0, 0, panel_w, panel_h)
            )
            win.setContentView_(view)
            # Listen for card clicks
            try:
                from Cocoa import NSNotificationCenter  # type: ignore[import-not-found]
                NSNotificationCenter.defaultCenter().addObserver_selector_name_object_(
                    self, "projectSelected:", "JarvisProjectSelected", None,
                )
            except Exception:
                pass
            self._overlay_projects_win = win
            self._overlay_projects_view = view

        def projectSelected_(self, notification) -> None:  # noqa: N802
            try:
                repo = notification.userInfo().get("repo", {})
                if not repo:
                    return
                name = repo.get("name", "")
                html_url = repo.get("html_url", "")
                state = Path(os.path.expanduser(self._cfg.get("state_dir", "~/.jarvis")))
                # Write active project file
                (state / "active_project.json").write_text(
                    json.dumps({"name": name, "ts": time.time()}), encoding="utf-8"
                )
                # Open in editor
                pc = self._cfg.get("projects", {})
                local_path = pc.get("local_paths", {}).get(name)
                editor = pc.get("default_editor", "cursor").lower()
                app = "Cursor" if editor == "cursor" else "Kiro"
                if local_path:
                    subprocess.run(["open", "-a", app, os.path.expanduser(local_path)], capture_output=True)
                elif html_url:
                    subprocess.run(["open", html_url], capture_output=True)
                if self._overlay_projects_view is not None:
                    self._overlay_projects_view.setActiveProject_(name)
            except Exception:
                pass

        def _show_projects_panel(self):
            if self._overlay_projects_win is None:
                return
            self._overlay_projects_win.orderFrontRegardless()
            NSAnimationContext.beginGrouping()
            NSAnimationContext.currentContext().setDuration_(0.5)
            self._overlay_projects_win.animator().setAlphaValue_(1.0)
            NSAnimationContext.endGrouping()

        def _hide_projects_panel(self):
            if self._overlay_projects_win is None:
                return
            win = self._overlay_projects_win

            def _complete():
                try:
                    win.orderOut_(None)
                except Exception:
                    pass

            NSAnimationContext.runAnimationGroup_completionHandler_(
                lambda ctx: (ctx.setDuration_(0.4), win.animator().setAlphaValue_(0.0)),
                _complete,
            )

        def _refresh_projects_repos(self):
            """Load repos from cache file into the projects view."""
            if self._overlay_projects_view is None:
                return
            try:
                state = Path(os.path.expanduser(self._cfg.get("state_dir", "~/.jarvis")))
                cache_file = state / "projects_cache.json"
                if not cache_file.is_file():
                    return
                mtime = cache_file.stat().st_mtime
                if mtime == self._overlay_projects_cache_mtime:
                    return
                self._overlay_projects_cache_mtime = mtime
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                self._overlay_projects_view.setRepos_(data.get("repos", []))
            except Exception:
                pass

        def arcReactorClicked(self) -> None:
            """Toggle the projects panel open/closed."""
            try:
                if self._overlay_projects_active:
                    self._overlay_projects_active = False
                    self._hide_projects_panel()
                else:
                    self._overlay_projects_active = True
                    self._refresh_projects_repos()
                    self._show_projects_panel()
            except Exception:
                pass

        def _start_overlay_timers(self):
            self._overlay_anim_timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                1.0 / 60.0, self, "overlayAnimTick:", None, True,
            )
            if hasattr(self._overlay_anim_timer, "setTolerance_"):
                self._overlay_anim_timer.setTolerance_(0.008)
            self._overlay_poll_timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                0.5, self, "overlayPollTick:", None, True,
            )
            if hasattr(self._overlay_poll_timer, "setTolerance_"):
                self._overlay_poll_timer.setTolerance_(0.1)
            # Subscribe to Space and screen-layout changes for instant re-ordering/re-anchoring
            try:
                from Cocoa import NSWorkspace, NSNotificationCenter  # type: ignore[import-not-found]
                NSWorkspace.sharedWorkspace().notificationCenter().addObserver_selector_name_object_(
                    self, "overlaySpaceDidChange:", "NSWorkspaceActiveSpaceDidChangeNotification", None,
                )
                NSNotificationCenter.defaultCenter().addObserver_selector_name_object_(
                    self, "overlayScreenDidChange:", "NSApplicationDidChangeScreenParametersNotification", None,
                )
            except Exception:
                pass

        def overlaySpaceDidChange_(self, notification) -> None:  # noqa: N802
            """Re-order overlay windows to front of their z-level instantly on Space switch."""
            if self._overlay_lab_was_active:
                for win in self._all_overlay_windows():
                    try:
                        win.orderFrontRegardless()
                    except Exception:
                        pass
                if self._win is not None:
                    try:
                        self._win.orderFrontRegardless()
                    except Exception:
                        pass

        def overlayScreenDidChange_(self, notification) -> None:  # noqa: N802
            """Re-anchor overlay windows when Dock/menu bar changes screen layout."""
            try:
                main_screen = NSScreen.mainScreen()
                if main_screen is None:
                    return
                main_frame = main_screen.frame()
                for entry in self._overlay_bg_windows:
                    scr = entry.get("screen")
                    if scr is not None:
                        entry["window"].setFrame_display_(scr.frame(), False)
                if self._overlay_arc_win is not None:
                    size_px = float(self._overlay_arc_win.frame().size.width)
                    arc_x = float(main_frame.origin.x) + (float(main_frame.size.width) - size_px) / 2.0
                    arc_y = float(main_frame.origin.y) + (float(main_frame.size.height) - size_px) / 2.0
                    self._overlay_arc_win.setFrame_display_(
                        NSMakeRect(arc_x, arc_y, size_px, size_px), False
                    )
            except Exception:
                pass

        def overlayAnimTick_(self, timer) -> None:  # noqa: N802
            now = time.time()
            dt = now - self._overlay_last_anim_time
            self._overlay_last_anim_time = now
            if self._overlay_arc_view is not None:
                try:
                    self._overlay_arc_view.advanceTick_(dt)
                except Exception:
                    pass
            if self._overlay_dict_view is not None:
                try:
                    self._overlay_dict_view.advanceTick_(now)
                except Exception:
                    pass
            for entry in self._overlay_bg_windows:
                try:
                    entry["view"].setNeedsDisplay_(True)
                except Exception:
                    pass
            # Projects panel scroll animation
            if self._overlay_projects_view is not None:
                try:
                    self._overlay_projects_view.advanceTick_(dt)
                except Exception:
                    pass

        def overlayPollTick_(self, timer) -> None:  # noqa: N802
            active = lab_active(self._cfg)
            if active != self._overlay_lab_was_active:
                self._overlay_lab_was_active = active
                if active:
                    self._show_overlays()
                else:
                    self._hide_overlays()

            # Projects panel: show when prompt or active_project file exists
            try:
                state = Path(os.path.expanduser(self._cfg.get("state_dir", "~/.jarvis")))
                projects_wanted = (state / "projects_prompt.json").exists() or (state / "active_project.json").exists()
                if projects_wanted != self._overlay_projects_active:
                    self._overlay_projects_active = projects_wanted
                    if projects_wanted:
                        self._refresh_projects_repos()
                        self._show_projects_panel()
                    else:
                        self._hide_projects_panel()
                elif projects_wanted:
                    # Keep repos in sync if cache was refreshed
                    self._refresh_projects_repos()
                    # Sync active project name
                    active_file = state / "active_project.json"
                    if active_file.exists() and self._overlay_projects_view is not None:
                        try:
                            d = json.loads(active_file.read_text(encoding="utf-8"))
                            self._overlay_projects_view.setActiveProject_(d.get("name"))
                        except Exception:
                            pass
            except Exception:
                pass

        def _all_overlay_windows(self):
            wins = [e["window"] for e in self._overlay_bg_windows]
            if self._overlay_arc_win is not None:
                wins.append(self._overlay_arc_win)
            if self._overlay_dict_win is not None:
                wins.append(self._overlay_dict_win)
            return wins

        def _show_overlays(self):
            for win in self._all_overlay_windows():
                win.orderFrontRegardless()
            if self._win is not None:
                self._win.orderFrontRegardless()
            NSAnimationContext.beginGrouping()
            NSAnimationContext.currentContext().setDuration_(0.6)
            for win in self._all_overlay_windows():
                win.animator().setAlphaValue_(1.0)
            NSAnimationContext.endGrouping()

        def _hide_overlays(self):
            NSAnimationContext.beginGrouping()
            NSAnimationContext.currentContext().setDuration_(0.5)
            for win in self._all_overlay_windows():
                win.animator().setAlphaValue_(0.0)
            NSAnimationContext.endGrouping()

        def applicationDidFinishLaunching_(self, notification) -> None:  # noqa: N802
            from Cocoa import NSApp  # type: ignore[import-not-found]
            try:
                cfg = self._cfg
                hud = cfg.get("hud_slider") or {}
                self._cooldown = float(hud.get("cooldown_seconds", 2.5))
                self._hide_delay = float(hud.get("hide_delay_seconds", 0.38))
                self._reveal_mode = _normalize_reveal_mode(hud.get("reveal_mode", "edge_dwell"))
                self._reveal_dwell = max(0.0, float(hud.get("reveal_dwell_seconds", 0.4)))
                hover_px = float(hud.get("hover_zone_px", 80))
                use_blur = hud.get("use_blur", True)
                pos = str(hud.get("position", "top")).lower()
                margin_bottom = float(hud.get("margin_from_bottom", 100))
                show_anchor_strip = bool(hud.get("show_top_anchor_strip", True))
                debug_mode = _normalize_debug_visibility_mode(
                    os.environ.get("JARVIS_HUD_DEBUG_VISIBILITY_MODE")
                    or hud.get("debug_visibility_mode", "normal")
                )
                force_visible = debug_mode != "normal"
                titled_debug = debug_mode == "titled_debug"
                anchor_bottom = pos == "bottom"
                slot_h = CONTROL_H + 8.0

                self._last_fire = 0.0
                self._hide_gen = 0
                self._last_want = False
                self._hide_pending = False
                self._slide_shown = force_visible
                self._debug_visibility_mode = debug_mode
                self._margin_top = float(hud.get("margin_from_top", 4.0))
                self._margin_bottom = margin_bottom
                self._titled_debug = titled_debug
                self._show_anchor_strip = show_anchor_strip and not anchor_bottom
                self._window_width = CONTROL_W + 36.0 if titled_debug else CONTROL_W
                self._window_height = slot_h + 16.0 if titled_debug else slot_h
                self._poll_interval = 0.08
                self._hidden_offset = max(
                    8.0,
                    CONTROL_OVERFLOW_PAD_Y + TRACK_PILL_INSET_Y + 24.0,
                    float(hud.get("slide_hidden_offset_px", 14.0)),
                )
                self._show_duration = max(0.16, float(hud.get("show_animation_seconds", 0.34)))
                self._hide_duration = max(0.10, float(hud.get("hide_animation_seconds", 0.18)))
                self._visibility_animating = False
                self._visibility_generation = 0

                vf, frame = self._target_window_frame_for_cursor()
                style_mask = (
                    NSWindowStyleMaskTitled | NSWindowStyleMaskClosable
                    if titled_debug
                    else NSWindowStyleMaskBorderless
                )

                win = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
                    frame,
                    style_mask,
                    NSBackingStoreBuffered,
                    False,
                )
                if titled_debug:
                    win.setOpaque_(True)
                    win.setBackgroundColor_(NSColor.windowBackgroundColor())
                    win.setTitle_("JARVIS HUD DEBUG")
                else:
                    win.setOpaque_(False)
                    win.setBackgroundColor_(NSColor.clearColor())
                win.setLevel_(NSFloatingWindowLevel)
                win.setIgnoresMouseEvents_(not force_visible)
                win.setAcceptsMouseMovedEvents_(True)
                win.setReleasedWhenClosed_(False)
                win.setCollectionBehavior_(
                    NSWindowCollectionBehaviorMoveToActiveSpace
                    | NSWindowCollectionBehaviorFullScreenAuxiliary
                )

                self._hover_px = hover_px
                self._anchor_bottom = anchor_bottom

                root = JarvisFlippedRootView.alloc().initWithFrame_(
                    NSMakeRect(0, 0, frame.size.width, frame.size.height)
                )
                root.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)

                slide_w = CONTROL_W
                slide_h = CONTROL_H
                cx = (frame.size.width - slide_w) / 2.0
                if titled_debug:
                    slide_y_visible = 8.0
                    slide_y_hidden = 12.0
                elif anchor_bottom:
                    slide_y_visible = slot_h - slide_h
                    slide_y_hidden = slide_y_visible
                else:
                    slide_y_visible = 0.0
                    slide_y_hidden = slide_y_visible

                slide_start_y = slide_y_visible
                slide = NSView.alloc().initWithFrame_(NSMakeRect(cx, slide_start_y, slide_w, slide_h))
                slide.setWantsLayer_(True)
                slide.setAutoresizingMask_(NSViewMinXMargin | NSViewMaxXMargin)
                slide.setAlphaValue_(1.0)
                slide.setHidden_(False)

                self._slide_container = slide
                self._slide_y_visible = slide_y_visible
                self._slide_y_hidden = slide_y_hidden

                glass_host = None
                host_kind = "fallback"
                track_rect = NSMakeRect(TRACK_X, TRACK_Y + TRACK_PILL_INSET_Y, TRACK_W, TRACK_PILL_H)
                if use_blur:
                    try:
                        glass_host = JarvisFlippedRootView.alloc().initWithFrame_(NSMakeRect(0, 0, CONTROL_W, CONTROL_H))
                        glass_host.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)
                        glass_host.setWantsLayer_(True)
                        ve = NSVisualEffectView.alloc().initWithFrame_(track_rect)
                        ve.setBlendingMode_(NSVisualEffectBlendingModeWithinWindow)
                        ve.setMaterial_(NSVisualEffectMaterialHUDWindow)
                        ve.setState_(NSVisualEffectStateActive)
                        ve.setAutoresizingMask_(NSViewWidthSizable)
                        ve.setWantsLayer_(True)
                        if ve.layer() is not None:
                            ve.layer().setCornerRadius_(TRACK_PILL_RADIUS)
                            ve.layer().setMasksToBounds_(True)
                            ve_bg = _ns_color((0.03, 0.04, 0.05, 0.14))
                            if hasattr(ve_bg, "CGColor"):
                                ve.layer().setBackgroundColor_(ve_bg.CGColor())
                        glass_host.addSubview_(ve)
                        bg = JarvisFallbackGlassView.alloc().initWithFrame_(track_rect)
                        bg.setAutoresizingMask_(NSViewWidthSizable)
                        bg.setAlphaValue_(0.42)
                        glass_host.addSubview_(bg)
                        slider = JarvisGlassSliderView.alloc().initWithFrame_(glass_host.bounds())
                        slider.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)
                        slider.setDelegate_(self)
                        glass_host.addSubview_(slider)
                        self._slider = slider
                        host_kind = "blur"
                    except Exception:
                        glass_host = None

                if glass_host is None:
                    glass_host = JarvisFlippedRootView.alloc().initWithFrame_(NSMakeRect(0, 0, CONTROL_W, CONTROL_H))
                    glass_host.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)
                    fb = JarvisFallbackGlassView.alloc().initWithFrame_(track_rect)
                    fb.setAutoresizingMask_(NSViewWidthSizable)
                    glass_host.addSubview_(fb)
                    slider = JarvisGlassSliderView.alloc().initWithFrame_(glass_host.bounds())
                    slider.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)
                    slider.setDelegate_(self)
                    glass_host.addSubview_(slider)
                    self._slider = slider
                    host_kind = "fallback"

                glass_host.setFrame_(NSMakeRect(0, 0, CONTROL_W, CONTROL_H))
                slide.addSubview_(glass_host)
                root.addSubview_(slide)

                win.setContentView_(root)
                self._win = win
                self._host_kind = host_kind
                self._slider.syncFromLab_(lab_active(cfg))
                self._set_slide_visible(force_visible, immediate=True)
                self._refresh_sensor_windows()

                if force_visible:
                    NSApp.activateIgnoringOtherApps_(True)
                    win.makeKeyAndOrderFront_(None)
                    win.orderFrontRegardless()
                else:
                    win.orderOut_(None)

                mask = (
                    NSMouseMovedMask
                    | NSLeftMouseDraggedMask
                    | NSRightMouseDraggedMask
                    | NSOtherMouseDraggedMask
                    | NSLeftMouseDownMask
                    | NSLeftMouseUpMask
                )

                def _monitor_handler(event):
                    self._sync_hover_visibility_from_cursor()
                    return event

                if not force_visible:
                    self._local_monitor = NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
                        mask, _monitor_handler
                    )
                    self._global_monitor = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
                        mask, lambda event: self._sync_hover_visibility_from_cursor()
                    )
                    self._hover_timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                        self._poll_interval,
                        self,
                        "hoverPollTick:",
                        None,
                        True,
                    )
                    if self._hover_timer is not None and hasattr(self._hover_timer, "setTolerance_"):
                        self._hover_timer.setTolerance_(0.02)

                # Peek on launch: immediately show the HUD so the user can see it
                if not force_visible:
                    peek_secs = float(hud.get("peek_on_launch_seconds", 0.0))
                    if peek_secs > 0:
                        self._slide_shown = True
                        self._set_slide_visible(True, immediate=True)
                        NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                            peek_secs, self, "peekHideTimer:", None, False
                        )

                print(
                    "Jarvis HUD:"
                    f" build={_HUD_BUILD_ID}"
                    f" mode={debug_mode}"
                    f" host={host_kind}"
                    f" blur={use_blur}"
                    f" reveal={self._reveal_mode}"
                    f" dwell={self._reveal_dwell:.2f}s"
                    f" hover={hover_px}px"
                    f" poll={self._poll_interval:.2f}s"
                    f" visibleFrame={_format_rect(vf)}"
                    f" window={_format_rect(win.frame())}"
                    f" slide={_format_rect(slide.frame())}"
                    f" slideHidden={bool(slide.isHidden())}"
                    f" slideAlpha={float(slide.alphaValue()):.2f}",
                    file=sys.stderr,
                    flush=True,
                )

                try:
                    self._build_overlay_windows()
                    self._build_projects_overlay()
                    self._start_overlay_timers()
                    # Sync initial overlay state with current lab session.
                    self._overlay_lab_was_active = lab_active(cfg)
                    if self._overlay_lab_was_active:
                        self._show_overlays()
                except Exception:
                    print("Overlay build failed (non-fatal):", file=sys.stderr, flush=True)
                    traceback.print_exc()
            except Exception:
                print("Jarvis HUD launch failed:", file=sys.stderr, flush=True)
                traceback.print_exc()

        def peekHideTimer_(self, timer) -> None:  # noqa: N802
            if not (self._cursor_in_hover_zone() or self._mouse_in_window_frame()):
                self._slide_shown = False
                self._set_slide_visible(False)

        def applicationWillTerminate_(self, notification) -> None:  # noqa: N802
            try:
                from Cocoa import NSWorkspace, NSNotificationCenter  # type: ignore[import-not-found]
                NSWorkspace.sharedWorkspace().notificationCenter().removeObserver_(self)
                NSNotificationCenter.defaultCenter().removeObserver_(self)
            except Exception:
                pass
            if self._hover_timer is not None:
                self._hover_timer.invalidate()
                self._hover_timer = None
            if self._overlay_anim_timer is not None:
                self._overlay_anim_timer.invalidate()
                self._overlay_anim_timer = None
            if self._overlay_poll_timer is not None:
                self._overlay_poll_timer.invalidate()
                self._overlay_poll_timer = None
            for win in self._all_overlay_windows():
                try:
                    win.orderOut_(None)
                    win.close()
                except Exception:
                    pass
            self._overlay_bg_windows = []
            self._overlay_arc_win = None
            self._overlay_dict_win = None
            if self._overlay_projects_win is not None:
                try:
                    self._overlay_projects_win.orderOut_(None)
                    self._overlay_projects_win.close()
                except Exception:
                    pass
                self._overlay_projects_win = None
            for entry in self._sensor_windows:
                try:
                    entry["window"].orderOut_(None)
                    entry["window"].close()
                except Exception:
                    pass
            self._sensor_windows = []
            if self._local_monitor is not None:
                NSEvent.removeMonitor_(self._local_monitor)
                self._local_monitor = None
            if self._global_monitor is not None:
                NSEvent.removeMonitor_(self._global_monitor)
                self._global_monitor = None
            if self._click_monitor is not None:
                NSEvent.removeMonitor_(self._click_monitor)
                self._click_monitor = None

        def applicationShouldTerminateAfterLastWindowClosed_(self, sender) -> bool:  # noqa: N802
            return True


def main() -> int:
    if not _HAVE_COCOA:
        print(
            "Install PyObjC for the native slider HUD:\n"
            "  pip install pyobjc-framework-Cocoa\n"
            "Or run (no slider): ./scripts/jarvis_hud_dialog.sh",
            file=sys.stderr,
        )
        return 1

    cfg_path = resolve_cfg_path(sys.argv)
    if not cfg_path.is_file():
        print(f"Missing config: {cfg_path}", file=sys.stderr)
        return 1
    cfg = load_cfg(cfg_path)
    if not acquire_hud_singleton(cfg):
        print("Jarvis HUD already running; skipping duplicate AppKit instance.", file=sys.stderr, flush=True)
        return 0

    print(f"Jarvis HUD: build={_HUD_BUILD_ID}", file=sys.stderr, flush=True)

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

    delegate = JarvisHUDDelegate.alloc().init()
    delegate._cfg = cfg
    delegate._cfg_path = cfg_path
    app.setDelegate_(delegate)

    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
