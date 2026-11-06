// Lot map: progressive enhancement for the server-rendered SVG plan.
// Hooks (set by templates/lots/_plan.html): #lotmap-stage > svg#lot-map-svg[data-lot-id],
// g.bay[data-slot-id][data-code][data-type][data-state], #lot-route, [data-you="true"].
// Optional stage attributes: data-state-url (admin live updates), data-parked-url (search).

const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
const still = () => reduceMotion.matches;

const TYPE_LABEL = {
  TwoWheeler: "Two-wheeler",
  Standard: "Car",
  EV: "Electric vehicle",
  Accessible: "Accessible",
};
const STATE_LABEL = { free: "Free", reserved: "Reserved", occupied: "Occupied", blocked: "Blocked" };
const STATES = Object.keys(STATE_LABEL);

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
const easeInOut = (t) => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2);
const normaliseReg = (s) => s.toUpperCase().replace(/[^A-Z0-9]/g, "");

function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "text") node.textContent = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v);
  }
  for (const child of children) node.append(child);
  return node;
}

function svgEl(tag, attrs = {}) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  return node;
}

function ago(iso) {
  if (!iso) return "";
  const mins = Math.max(0, Math.round((Date.now() - Date.parse(iso)) / 60000));
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} m`;
  return `${Math.floor(mins / 60)} h ${mins % 60} m`;
}

// ---------------------------------------------------------------------------
// Camera: a critically damped spring drives a CSS transform on one composited
// layer that holds the SVG (rendered once). Moving the layer costs no repaint, so
// wheel, drag, buttons and fly-to stay at display frame rate on large lots. When
// the camera settles, the layer is re-rasterised at the new scale so text stays sharp.
// ---------------------------------------------------------------------------
class Camera {
  constructor(svg, stage) {
    this.svg = svg;
    this.stage = stage;
    const vb = svg.viewBox.baseVal;
    this.world = { x: 0, y: 0, w: vb.width, h: vb.height };
    this.layer = el("div", { class: "lotmap-world" });
    svg.before(this.layer);
    this.layer.append(svg);
    this.settleTimer = 0;
    this.layout();
    this.view = { ...this.world };
    this.target = { ...this.world };
    this.vel = { x: 0, y: 0, w: 0, h: 0 };
    this.listeners = new Set();
    this.raf = 0;
    this.last = 0;
    this.fit(true);
  }

  // Size the SVG so that 1 world unit = k CSS px when the camera shows the full width.
  layout() {
    const r = this.stage.getBoundingClientRect();
    this.k = (r.width || this.world.w) / this.world.w;
    this.svg.style.width = `${this.world.w * this.k}px`;
    this.svg.style.height = `${this.world.h * this.k}px`;
  }

  // World units to CSS px inside the layer (for HTML overlays such as the marker).
  px(v) {
    return v * this.k;
  }

  aspect() {
    const r = this.stage.getBoundingClientRect();
    return r.width && r.height ? r.width / r.height : this.world.w / this.world.h;
  }

  // Keep the target inside the lot with a soft margin, at a sane zoom.
  constrain(t) {
    const a = this.aspect();
    const maxW = Math.max(this.world.w, this.world.h * a) * 1.04;
    const minW = maxW / 6;
    const w = clamp(t.w, minW, maxW);
    const h = w / a;
    const padX = Math.max(0, (w - this.world.w) / 2) + w * 0.08;
    const padY = Math.max(0, (h - this.world.h) / 2) + h * 0.08;
    return {
      w,
      h,
      x: clamp(t.x, -padX, this.world.w - w + padX),
      y: clamp(t.y, -padY, this.world.h - h + padY),
    };
  }

  set(target, instant = false) {
    this.target = this.constrain(target);
    if (instant || still()) {
      this.view = { ...this.target };
      this.vel = { x: 0, y: 0, w: 0, h: 0 };
      this.apply();
      this.settle();
      return;
    }
    this.kick();
  }

  fit(instant = false) {
    const a = this.aspect();
    let w = this.world.w * 1.04;
    let h = w / a;
    if (h < this.world.h * 1.04) {
      h = this.world.h * 1.04;
      w = h * a;
    }
    this.set({ x: (this.world.w - w) / 2, y: (this.world.h - h) / 2, w, h }, instant);
  }

  fitWidth(instant = false) {
    const a = this.aspect();
    const w = this.world.w * 1.02;
    const h = w / a;
    if (h >= this.world.h) return this.fit(instant);
    this.set({ x: (this.world.w - w) / 2, y: this.world.h - h + h * 0.04, w, h }, instant);
  }

  zoomAt(factor, px, py) {
    // px, py: point in world units that stays under the cursor.
    const t = this.target;
    const w = t.w * factor;
    const h = t.h * factor;
    this.set({ x: px - (px - t.x) * factor, y: py - (py - t.y) * factor, w, h });
  }

  panBy(dx, dy, instant = false) {
    const t = this.target;
    this.set({ ...t, x: t.x + dx, y: t.y + dy }, instant);
  }

  flyTo(cx, cy, width) {
    const a = this.aspect();
    const w = width;
    const h = w / a;
    this.set({ x: cx - w / 2, y: cy - h / 2, w, h });
  }

  toWorld(clientX, clientY) {
    const r = this.stage.getBoundingClientRect();
    const unit = this.view.w / r.width;
    return {
      x: this.view.x + (clientX - r.left) * unit,
      y: this.view.y + (clientY - r.top) * unit,
    };
  }

  kick() {
    clearTimeout(this.settleTimer);
    this.layer.style.willChange = "transform";
    if (!this.raf) {
      this.last = performance.now();
      this.raf = requestAnimationFrame((t) => this.tick(t));
    }
  }

  tick(now) {
    const dt = Math.min(0.032, (now - this.last) / 1000);
    this.last = now;
    // Spring: stiffness 170, damping 26 (critically damped feel, no wobble).
    let moving = false;
    for (const k of ["x", "y", "w", "h"]) {
      const force = 170 * (this.target[k] - this.view[k]) - 26 * this.vel[k];
      this.vel[k] += force * dt;
      this.view[k] += this.vel[k] * dt;
      if (Math.abs(this.target[k] - this.view[k]) > 0.05 || Math.abs(this.vel[k]) > 0.05) {
        moving = true;
      }
    }
    if (!moving) {
      this.view = { ...this.target };
      this.vel = { x: 0, y: 0, w: 0, h: 0 };
    }
    this.apply();
    this.raf = moving ? requestAnimationFrame((t) => this.tick(t)) : 0;
    if (!moving) this.settle();
  }

  // Once still: drop will-change so the browser re-rasterises crisply at this zoom,
  // and publish the zoom level for label fading (style work happens once, not per frame).
  settle() {
    clearTimeout(this.settleTimer);
    this.settleTimer = setTimeout(() => {
      this.layer.style.willChange = "auto";
      const zoom = this.world.w / this.view.w;
      this.stage.style.setProperty("--zoom", zoom.toFixed(3));
    }, 120);
  }

  apply() {
    const v = this.view;
    const scale = this.world.w / v.w;
    const tx = -v.x * this.k * scale;
    const ty = -v.y * this.k * scale;
    this.layer.style.transform = `translate3d(${tx}px, ${ty}px, 0) scale(${scale})`;
    for (const fn of this.listeners) fn(v);
  }
}

// ---------------------------------------------------------------------------
// Gestures: drag with momentum, wheel and trackpad zoom at the cursor, pinch.
// ---------------------------------------------------------------------------
function bindGestures(camera, stage, svg) {
  const pointers = new Map();
  let lastMove = null;
  let velocity = { x: 0, y: 0 };
  let pinchStart = null;
  let dragged = false;

  svg.addEventListener(
    "wheel",
    (e) => {
      e.preventDefault();
      const p = camera.toWorld(e.clientX, e.clientY);
      // Trackpad pinch arrives as ctrl+wheel with small deltas; mouse wheels jump by ~100.
      const intensity = e.ctrlKey ? 0.012 : 0.0016;
      camera.zoomAt(Math.exp(e.deltaY * intensity), p.x, p.y);
    },
    { passive: false },
  );

  svg.addEventListener("pointerdown", (e) => {
    if (e.button !== 0 && e.pointerType === "mouse") return;
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    dragged = false;
    velocity = { x: 0, y: 0 };
    lastMove = { t: performance.now(), x: e.clientX, y: e.clientY };
    if (pointers.size === 2) {
      const [a, b] = [...pointers.values()];
      pinchStart = { d: Math.hypot(a.x - b.x, a.y - b.y), w: camera.target.w };
    }
  });

  svg.addEventListener("pointermove", (e) => {
    if (!pointers.has(e.pointerId)) return;
    const prev = pointers.get(e.pointerId);
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    const r = stage.getBoundingClientRect();
    const scale = camera.view.w / r.width;
    if (pointers.size === 2 && pinchStart) {
      const [a, b] = [...pointers.values()];
      const d = Math.hypot(a.x - b.x, a.y - b.y);
      const mid = camera.toWorld((a.x + b.x) / 2, (a.y + b.y) / 2);
      const factor = (pinchStart.w * (pinchStart.d / d)) / camera.target.w;
      camera.zoomAt(factor, mid.x, mid.y);
      return;
    }
    const dx = e.clientX - prev.x;
    const dy = e.clientY - prev.y;
    if (!dragged && Math.hypot(e.clientX - lastMove.x, e.clientY - lastMove.y) > 4) {
      dragged = true;
      svg.setPointerCapture(e.pointerId);
      stage.classList.add("is-dragging");
    }
    if (!dragged) return;
    const now = performance.now();
    const dt = Math.max(1, now - lastMove.t);
    velocity = { x: (-dx * scale) / dt, y: (-dy * scale) / dt };
    lastMove = { t: now, x: e.clientX, y: e.clientY };
    camera.panBy(-dx * scale, -dy * scale, true);
  });

  const end = (e) => {
    pointers.delete(e.pointerId);
    if (pointers.size < 2) pinchStart = null;
    if (pointers.size === 0) {
      stage.classList.remove("is-dragging");
      if (dragged && !still()) {
        // Momentum: glide on in the flick direction (about 280ms of travel).
        camera.panBy(velocity.x * 280, velocity.y * 280);
      }
    }
  };
  svg.addEventListener("pointerup", end);
  svg.addEventListener("pointercancel", end);
  // A drag must not count as a click on the bay underneath.
  svg.addEventListener(
    "click",
    (e) => {
      if (dragged) {
        e.preventDefault();
        e.stopPropagation();
        dragged = false;
      }
    },
    true,
  );
}

// ---------------------------------------------------------------------------
// Controls: zoom buttons, fit, keyboard.
// ---------------------------------------------------------------------------
function bindControls(camera, stage) {
  const centre = () => ({
    x: camera.target.x + camera.target.w / 2,
    y: camera.target.y + camera.target.h / 2,
  });
  const zoom = (f) => {
    const c = centre();
    camera.zoomAt(f, c.x, c.y);
  };
  const controls = el("div", { class: "lotmap-controls", role: "group", "aria-label": "Map controls" }, [
    el("button", { type: "button", class: "lotmap-ctl", "aria-label": "Zoom in", text: "+", onclick: () => zoom(0.7) }),
    el("button", { type: "button", class: "lotmap-ctl", "aria-label": "Zoom out", text: "−", onclick: () => zoom(1 / 0.7) }),
    el("button", { type: "button", class: "lotmap-ctl lotmap-ctl--fit", "aria-label": "Fit whole lot", text: "Fit", onclick: () => camera.fit() }),
  ]);
  stage.append(controls);

  stage.addEventListener("keydown", (e) => {
    if (e.target.closest("input, select, textarea")) return;
    const step = camera.target.w * 0.12;
    const keys = {
      "+": () => zoom(0.7),
      "=": () => zoom(0.7),
      "-": () => zoom(1 / 0.7),
      0: () => camera.fit(),
      ArrowLeft: () => camera.panBy(-step, 0),
      ArrowRight: () => camera.panBy(step, 0),
      ArrowUp: () => camera.panBy(0, -step),
      ArrowDown: () => camera.panBy(0, step),
    };
    if (keys[e.key] && !e.target.closest(".bay")) {
      e.preventDefault();
      keys[e.key]();
    }
  });
}

// ---------------------------------------------------------------------------
// Hover and focus card: a glass card that eases after the pointer.
// ---------------------------------------------------------------------------
function bindCard(stage, svg, details, live, showState) {
  const card = el("div", { class: "lotmap-card", "aria-hidden": "true" });
  stage.append(card);
  let pos = { x: 0, y: 0 };
  let goal = { x: 0, y: 0 };
  let raf = 0;
  let shownFor = null;

  const follow = () => {
    pos.x += (goal.x - pos.x) * 0.22;
    pos.y += (goal.y - pos.y) * 0.22;
    card.style.transform = `translate3d(${pos.x}px, ${pos.y}px, 0)`;
    raf = Math.hypot(goal.x - pos.x, goal.y - pos.y) > 0.5 ? requestAnimationFrame(follow) : 0;
  };

  const render = (bay) => {
    const id = bay.dataset.slotId;
    const state = bay.dataset.state || "free";
    const info = details(id) || {};
    card.replaceChildren(
      el("div", { class: "lotmap-card__head" }, [
        el("strong", { class: "lotmap-card__code", text: bay.dataset.code }),
        ...(showState
          ? [el("span", { class: `lotmap-chip lotmap-chip--${state}`, text: STATE_LABEL[state] || state })]
          : []),
      ]),
      el("div", { class: "lotmap-card__type", text: TYPE_LABEL[bay.dataset.type] || bay.dataset.type }),
      ...(info.reg
        ? [
            el("div", { class: "lotmap-card__reg", text: info.reg }),
            el("div", { class: "lotmap-card__meta", text: [info.driver, info.ref].filter(Boolean).join(" · ") }),
            ...(info.since && state === "occupied"
              ? [el("div", { class: "lotmap-card__meta", text: `Parked ${ago(info.since)}` })]
              : []),
          ]
        : []),
    );
    if (bay.dataset.you === "true") card.append(el("div", { class: "lotmap-card__you", text: "Your slot" }));
  };

  const place = (clientX, clientY, snap) => {
    const r = stage.getBoundingClientRect();
    const cw = card.offsetWidth || 220;
    const ch = card.offsetHeight || 110;
    let x = clientX - r.left + 18;
    let y = clientY - r.top - ch - 14;
    if (x + cw > r.width - 8) x = clientX - r.left - cw - 18;
    if (y < 8) y = clientY - r.top + 22;
    goal = { x: clamp(x, 8, r.width - cw - 8), y: clamp(y, 8, r.height - ch - 8) };
    if (snap || still()) {
      pos = { ...goal };
      card.style.transform = `translate3d(${pos.x}px, ${pos.y}px, 0)`;
    } else if (!raf) {
      raf = requestAnimationFrame(follow);
    }
  };

  const show = (bay, clientX, clientY) => {
    const fresh = shownFor !== bay;
    shownFor = bay;
    render(bay);
    card.classList.add("is-visible");
    place(clientX, clientY, fresh && !card.dataset.everShown);
    card.dataset.everShown = "1";
  };
  const hide = () => {
    shownFor = null;
    card.classList.remove("is-visible");
  };

  svg.addEventListener("pointermove", (e) => {
    const bay = e.target.closest(".bay");
    if (!bay || stage.classList.contains("is-dragging")) return hide();
    show(bay, e.clientX, e.clientY);
  });
  svg.addEventListener("pointerleave", hide);
  svg.addEventListener("focusin", (e) => {
    const bay = e.target.closest(".bay");
    if (!bay) return;
    const b = bay.getBoundingClientRect();
    show(bay, b.right, b.top);
    live(`${bay.dataset.code}, ${TYPE_LABEL[bay.dataset.type] || ""}, ${STATE_LABEL[bay.dataset.state] || ""}`);
  });
  svg.addEventListener("focusout", hide);

  return {
    showAt(bay) {
      const b = bay.getBoundingClientRect();
      show(bay, b.right, b.top);
    },
    refresh() {
      if (shownFor) render(shownFor);
    },
  };
}

// ---------------------------------------------------------------------------
// Overlays on the camera layer. They animate with transform and opacity only, so the
// rendered map underneath never repaints.
// ---------------------------------------------------------------------------
function overlaySvg(camera) {
  const { w, h } = camera.world;
  const svg = svgEl("svg", {
    class: "lotmap-overlay",
    viewBox: `0 0 ${w} ${h}`,
    "aria-hidden": "true",
    focusable: "false",
  });
  svg.style.width = camera.svg.style.width;
  svg.style.height = camera.svg.style.height;
  camera.layer.append(svg);
  return svg;
}

function beacon(camera, bay) {
  const r = bay.querySelector("rect").getBBox();
  const node = el("div", { class: "lotmap-beacon", "aria-hidden": "true" });
  node.style.left = `${camera.px(r.x + r.width / 2)}px`;
  node.style.top = `${camera.px(r.y + r.height / 2)}px`;
  node.style.setProperty("--size", `${camera.px(Math.max(r.width, r.height)) * 1.5}px`);
  camera.layer.append(node);
  return node;
}

function animateRoute(camera, route, you) {
  if (!route || !you || !route.getAttribute("points")) return;
  // End the route at the bay's edge so the line never covers the slot code.
  const pts = route.getAttribute("points").trim().split(/\s+/).map((pair) => pair.split(",").map(Number));
  const r = you.querySelector("rect").getBBox();
  if (pts.length >= 2) {
    const [, laneY] = pts[pts.length - 2];
    pts[pts.length - 1][1] = laneY < r.y ? r.y : r.y + r.height;
    route.setAttribute("points", pts.map((p) => p.join(",")).join(" "));
  }
  const overlay = overlaySvg(camera);
  overlay.append(route); // the route draws on its own small layer
  const length = route.getTotalLength();
  if (still() || !length) {
    route.classList.add("is-drawn");
    return;
  }
  route.style.strokeDasharray = `${length}`;
  route.style.strokeDashoffset = `${length}`;
  const delay = 650;
  const duration = 1400;
  route
    .animate([{ strokeDashoffset: length }, { strokeDashoffset: 0 }], {
      duration,
      delay,
      easing: "cubic-bezier(0.65, 0, 0.35, 1)",
      fill: "forwards",
    })
    .finished.then(() => {
      route.style.strokeDasharray = "";
      route.style.strokeDashoffset = "";
      route.classList.add("is-drawn");
    });

  const marker = el("div", { class: "lotmap-marker", "aria-hidden": "true" }, [
    el("span", { class: "lotmap-marker__glyph", text: you.dataset.type === "TwoWheeler" ? "🛵" : "🚗" }),
  ]);
  camera.layer.append(marker);
  const start = performance.now() + delay;
  const step = (now) => {
    const t = clamp((now - start) / duration, 0, 1);
    const at = route.getPointAtLength(easeInOut(t) * length);
    marker.style.transform = `translate3d(${camera.px(at.x)}px, ${camera.px(at.y)}px, 0)`;
    if (t < 1) requestAnimationFrame(step);
    else marker.classList.add("is-parked");
  };
  requestAnimationFrame(step);
}

// ---------------------------------------------------------------------------
// Rolling counters.
// ---------------------------------------------------------------------------
function rollNumber(node, to) {
  const from = Number(node.dataset.value ?? node.textContent.replace(/\D/g, "")) || 0;
  node.dataset.value = String(to);
  if (from === to) return;
  if (still()) {
    node.textContent = String(to);
    return;
  }
  node.classList.remove("is-up", "is-down");
  void node.offsetWidth;
  node.classList.add(to > from ? "is-up" : "is-down");
  const start = performance.now();
  const step = (now) => {
    const t = clamp((now - start) / 700, 0, 1);
    node.textContent = String(Math.round(from + (to - from) * easeInOut(t)));
    if (t < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

function ripple(camera, bay) {
  if (still()) return;
  const r = bay.querySelector("rect").getBBox();
  const ring = el("div", { class: `lotmap-ripple lotmap-ripple--${bay.dataset.state}`, "aria-hidden": "true" });
  const size = camera.px(Math.max(r.width, r.height));
  ring.style.left = `${camera.px(r.x + r.width / 2)}px`;
  ring.style.top = `${camera.px(r.y + r.height / 2)}px`;
  ring.style.width = ring.style.height = `${size}px`;
  camera.layer.append(ring);
  ring
    .animate(
      [
        { transform: "translate(-50%, -50%) scale(1)", opacity: 0.9 },
        { transform: "translate(-50%, -50%) scale(2.8)", opacity: 0 },
      ],
      { duration: 900, easing: "cubic-bezier(0, 0, 0.5, 1)" },
    )
    .finished.then(() => ring.remove());
}

// ---------------------------------------------------------------------------
// Filters: dim bays outside the chosen states and types.
// ---------------------------------------------------------------------------
function bindFilters(stage, svg, host) {
  if (!host) return { recount() {} };
  const active = { state: new Set(), type: new Set() };
  const chips = [];
  const apply = () => {
    for (const bay of svg.querySelectorAll(".bay")) {
      const okState = !active.state.size || active.state.has(bay.dataset.state);
      const okType = !active.type.size || active.type.has(bay.dataset.type);
      bay.classList.toggle("is-dim", !(okState && okType));
    }
  };
  const make = (kind, value, label) => {
    const count = el("span", { class: "lotmap-filter__count" });
    const chip = el(
      "button",
      {
        type: "button",
        class: `lotmap-filter lotmap-filter--${kind}-${value}`,
        "aria-pressed": "false",
        onclick: () => {
          const set = active[kind];
          set.has(value) ? set.delete(value) : set.add(value);
          chip.setAttribute("aria-pressed", String(set.has(value)));
          apply();
        },
      },
      [el("span", { class: "lotmap-filter__label", text: label }), count],
    );
    chips.push({ kind, value, count });
    return chip;
  };
  host.replaceChildren(
    el("div", { class: "lotmap-filters__group", role: "group", "aria-label": "Filter by status" },
      STATES.map((s) => make("state", s, STATE_LABEL[s]))),
    el("div", { class: "lotmap-filters__group", role: "group", "aria-label": "Filter by vehicle type" },
      [["TwoWheeler", "2W"], ["Standard", "Car"], ["EV", "EV"], ["Accessible", "Accessible"]].map(([t, l]) =>
        make("type", t, l))),
  );
  const recount = () => {
    const bays = [...svg.querySelectorAll(".bay")];
    for (const c of chips) {
      const n = bays.filter((b) => b.dataset[c.kind] === c.value).length;
      rollNumber(c.count, n);
    }
    apply();
  };
  recount();
  return { recount };
}

// ---------------------------------------------------------------------------
// Mini-map: a small overview with the current viewport.
// ---------------------------------------------------------------------------
function bindMinimap(stage, svg, camera) {
  const { w, h } = camera.world;
  const mini = svgEl("svg", {
    class: "lotmap-minimap",
    viewBox: `0 0 ${w} ${h}`,
    "aria-hidden": "true",
    focusable: "false",
  });
  for (const bay of svg.querySelectorAll(".bay rect")) {
    const r = bay.getBBox();
    mini.append(
      svgEl("rect", {
        x: r.x, y: r.y, width: r.width, height: r.height,
        class: `lotmap-minimap__bay lotmap-minimap__bay--${bay.closest(".bay").dataset.state}`,
      }),
    );
  }
  const frame = svgEl("rect", { class: "lotmap-minimap__frame" });
  mini.append(frame);
  const wrap = el("div", { class: "lotmap-minimap-wrap" });
  wrap.append(mini);
  stage.append(wrap);
  camera.listeners.add((v) => {
    frame.setAttribute("x", v.x);
    frame.setAttribute("y", v.y);
    frame.setAttribute("width", v.w);
    frame.setAttribute("height", v.h);
  });
  mini.addEventListener("pointerdown", (e) => {
    const r = mini.getBoundingClientRect();
    const x = ((e.clientX - r.left) / r.width) * w;
    const y = ((e.clientY - r.top) / r.height) * h;
    camera.set({ ...camera.target, x: x - camera.target.w / 2, y: y - camera.target.h / 2 });
  });
  return {
    sync() {
      const bays = [...svg.querySelectorAll(".bay")];
      const minis = mini.querySelectorAll(".lotmap-minimap__bay");
      bays.forEach((bay, i) => {
        if (minis[i]) minis[i].setAttribute("class", `lotmap-minimap__bay lotmap-minimap__bay--${bay.dataset.state}`);
      });
    },
  };
}

// ---------------------------------------------------------------------------
// Live updates (admin): poll state.json, cross-fade changed bays.
// ---------------------------------------------------------------------------
function bindLive(stage, svg, url, onChange, card, minimap, filters, camera) {
  const ageNode = document.querySelector("[data-live-age]");
  let updatedAt = Date.now();
  let timer = 0;
  const counters = () => {
    const totals = Object.fromEntries(STATES.map((s) => [s, 0]));
    for (const bay of svg.querySelectorAll(".bay")) totals[bay.dataset.state] = (totals[bay.dataset.state] || 0) + 1;
    for (const s of STATES) {
      for (const node of document.querySelectorAll(`[data-counter="${s}"]`)) rollNumber(node, totals[s]);
    }
  };
  const poll = async () => {
    if (document.hidden) return;
    try {
      const res = await fetch(url, { headers: { Accept: "application/json" }, credentials: "same-origin" });
      if (!res.ok) return;
      const data = await res.json();
      onChange(data.slots);
      let changed = 0;
      for (const bay of svg.querySelectorAll(".bay")) {
        const next = data.slots[bay.dataset.slotId];
        if (!next || next.state === bay.dataset.state) continue;
        bay.classList.remove(`bay--${bay.dataset.state}`);
        bay.classList.add(`bay--${next.state}`);
        bay.dataset.state = next.state;
        const link = bay.closest("a") || bay;
        const label = link.getAttribute("aria-label");
        if (label) link.setAttribute("aria-label", label.replace(/(free|reserved|occupied|blocked)$/i, next.state));
        ripple(camera, bay);
        changed += 1;
      }
      updatedAt = Date.parse(data.updated_at) || Date.now();
      if (changed) {
        counters();
        minimap?.sync();
        filters?.recount();
        card.refresh();
      }
    } catch {
      // Network blips are fine; the next poll catches up.
    }
  };
  const schedule = () => {
    clearInterval(timer);
    timer = setInterval(poll, 10000);
  };
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) poll();
  });
  setInterval(() => {
    if (ageNode) {
      const s = Math.max(0, Math.round((Date.now() - updatedAt) / 1000));
      ageNode.textContent = s < 2 ? "just now" : `${s} s ago`;
    }
  }, 1000);
  counters();
  schedule();
  poll();
}

// ---------------------------------------------------------------------------
// Search with suggestions (admin).
// ---------------------------------------------------------------------------
function bindSearch(input, url, lotId, onPickHere) {
  if (!input || !url) return;
  const form = input.closest("form");
  const list = el("ul", { class: "lotmap-suggest", role: "listbox", id: "lotmap-suggest" });
  input.setAttribute("role", "combobox");
  input.setAttribute("aria-autocomplete", "list");
  input.setAttribute("aria-controls", "lotmap-suggest");
  input.setAttribute("aria-expanded", "false");
  input.setAttribute("autocomplete", "off");
  input.parentElement.classList.add("lotmap-search");
  input.after(list);
  let parked = [];
  let items = [];
  let index = -1;
  let timer = 0;

  const load = async () => {
    try {
      const res = await fetch(url, { headers: { Accept: "application/json" }, credentials: "same-origin" });
      if (res.ok) parked = await res.json();
    } catch {
      parked = [];
    }
  };
  load();
  setInterval(load, 30000);

  const close = () => {
    list.classList.remove("is-open");
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
    index = -1;
  };
  const choose = (item) => {
    input.value = item.reg;
    close();
    if (String(item.lot_id) === String(lotId)) onPickHere(item);
    else form.requestSubmit();
  };
  const render = () => {
    const q = normaliseReg(input.value);
    items = q.length < 2 ? [] : parked.filter((p) => normaliseReg(p.reg).includes(q)).slice(0, 6);
    list.replaceChildren(
      ...items.map((p, i) =>
        el("li", {
          role: "option",
          id: `lotmap-opt-${i}`,
          class: "lotmap-suggest__item",
          "aria-selected": String(i === index),
          onpointerdown: (e) => {
            e.preventDefault();
            choose(p);
          },
        }, [
          el("strong", { text: p.reg }),
          el("span", { text: `${p.code} · ${p.lot}` }),
        ]),
      ),
    );
    const open = items.length > 0;
    list.classList.toggle("is-open", open);
    input.setAttribute("aria-expanded", String(open));
  };
  input.addEventListener("input", () => {
    clearTimeout(timer);
    index = -1;
    timer = setTimeout(render, 90);
  });
  input.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if (list.classList.contains("is-open")) close();
      else input.value = "";
      return;
    }
    if (!items.length) return;
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      index = (index + (e.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
      render();
      input.setAttribute("aria-activedescendant", `lotmap-opt-${index}`);
    } else if (e.key === "Enter" && index >= 0) {
      e.preventDefault();
      choose(items[index]);
    }
  });
  input.addEventListener("blur", () => setTimeout(close, 120));
}

// ---------------------------------------------------------------------------
// Boot.
// ---------------------------------------------------------------------------
function boot() {
  const stage = document.getElementById("lotmap-stage");
  const svg = document.getElementById("lot-map-svg");
  if (!stage || !svg) return;
  stage.classList.add("is-enhanced");

  const liveRegion = el("div", { class: "visually-hidden", "aria-live": "polite" });
  stage.append(liveRegion);
  const say = (text) => {
    liveRegion.textContent = text;
  };

  let slotInfo = {};
  const camera = new Camera(svg, stage);
  bindGestures(camera, stage, svg);
  bindControls(camera, stage);
  const isAdmin = Boolean(stage.dataset.stateUrl);
  const card = bindCard(stage, svg, (id) => slotInfo[id], say, isAdmin);
  if (isAdmin) camera.fitWidth(true);
  const minimap = stage.dataset.stateUrl ? bindMinimap(stage, svg, camera) : null;
  const filters = bindFilters(stage, svg, document.querySelector("[data-lotmap-filters]"));

  // Entrance: the lot fades up, then the camera flies to "your" bay.
  requestAnimationFrame(() => stage.classList.add("is-ready"));
  const you = svg.querySelector('[data-you="true"]');
  const focusBay = (bay, announce) => {
    const r = bay.querySelector("rect").getBBox();
    const width = Math.max(420, Math.min(camera.world.w * 0.62, 640));
    setTimeout(() => {
      camera.flyTo(r.x + r.width / 2, r.y + r.height / 2, width);
      bay.classList.add("is-found");
      document.querySelectorAll(".lotmap-beacon").forEach((b) => b.remove());
      beacon(camera, bay);
      setTimeout(() => card.showAt(bay), still() ? 0 : 900);
    }, still() ? 0 : 250);
    if (announce) say(announce);
  };
  const route = document.getElementById("lot-route");
  if (you && route && route.getAttribute("points") && !isAdmin) {
    // Frame the whole drive: from the driveway to the bay, with breathing room.
    const pts = route.getAttribute("points").trim().split(/\s+/).map((pair) => pair.split(",").map(Number));
    const r = you.querySelector("rect").getBBox();
    const xs = [...pts.map((p) => p[0]), r.x, r.x + r.width];
    const ys = [...pts.map((p) => p[1]), r.y, r.y + r.height];
    const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
    const a = camera.aspect();
    let w = Math.max(420, (maxX - minX) * 1.18);
    if (w / a < (maxY - minY) * 1.25) w = (maxY - minY) * 1.25 * a;
    setTimeout(() => {
      camera.flyTo((minX + maxX) / 2, (minY + maxY) / 2, w);
      you.classList.add("is-found");
      beacon(camera, you);
      setTimeout(() => card.showAt(you), still() ? 0 : 2200);
    }, still() ? 0 : 250);
    say(`Your slot ${you.dataset.code} is highlighted on the map.`);
    animateRoute(camera, route, you);
  } else if (you) {
    focusBay(you, `Your slot ${you.dataset.code} is highlighted on the map.`);
  }

  if (stage.dataset.stateUrl) {
    window.lotmapLive = true; // the 30 s HTMX full refresh stands down while live polling runs
    bindLive(stage, svg, stage.dataset.stateUrl, (slots) => (slotInfo = slots), card, minimap, filters, camera);
  }
  bindSearch(
    document.querySelector("[data-lotmap-search]"),
    stage.dataset.parkedUrl,
    svg.dataset.lotId,
    (item) => {
      const bay = svg.querySelector(`.bay[data-slot-id="${item.slot_id}"]`);
      if (!bay) return;
      svg.querySelectorAll(".is-found").forEach((b) => b.classList.remove("is-found"));
      focusBay(bay, `${item.reg} is parked in ${item.code}.`);
    },
  );

  window.addEventListener("resize", () => {
    camera.layout();
    camera.set(camera.target, true);
  });

  const lotSelect = document.getElementById("lot-select");
  if (lotSelect) {
    lotSelect.addEventListener("change", () => {
      const search = document.querySelector("[data-lotmap-search]");
      if (search) search.value = "";
      stage.classList.add("is-leaving");
      setTimeout(() => lotSelect.form.requestSubmit(), still() ? 0 : 220);
    });
  }
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
else boot();
