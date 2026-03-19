/* ── Audio context (lazy init) ─────────────────────────────────────────────── */
let _audioCtx = null;

function getAudioCtx() {
  if (!_audioCtx) {
    _audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  }
  return _audioCtx;
}

/* ── Combo tracker — rising pitch for rapid checks ────────────────────────── */
let _comboCount = 0;
let _comboTimer = null;

function getComboMultiplier() {
  _comboCount++;
  if (_comboTimer) clearTimeout(_comboTimer);
  _comboTimer = setTimeout(() => { _comboCount = 0; }, 3000);
  return Math.min(_comboCount, 8);
}

/* ── Sound effects ────────────────────────────────────────────────────────── */
function playCheckSound(isChecking) {
  try {
    const ctx = getAudioCtx();
    const now = ctx.currentTime;
    const combo = isChecking ? getComboMultiplier() : 0;
    const pitchBoost = combo * 50;

    if (isChecking) {
      // Warm two-note "done" chime — lower, rounder, less retro
      const n1 = ctx.createOscillator();
      const g1 = ctx.createGain();
      n1.connect(g1);
      g1.connect(ctx.destination);
      n1.type = 'triangle';
      n1.frequency.setValueAtTime(523 + pitchBoost * 0.6, now);       // C5
      g1.gain.setValueAtTime(0, now);
      g1.gain.linearRampToValueAtTime(0.2, now + 0.008);
      g1.gain.exponentialRampToValueAtTime(0.001, now + 0.15);
      n1.start(now);
      n1.stop(now + 0.16);

      const n2 = ctx.createOscillator();
      const g2 = ctx.createGain();
      n2.connect(g2);
      g2.connect(ctx.destination);
      n2.type = 'triangle';
      n2.frequency.setValueAtTime(659 + pitchBoost * 0.8, now + 0.08); // E5 — major third up
      g2.gain.setValueAtTime(0, now + 0.08);
      g2.gain.linearRampToValueAtTime(0.22, now + 0.088);
      g2.gain.exponentialRampToValueAtTime(0.04, now + 0.25);
      g2.gain.exponentialRampToValueAtTime(0.001, now + 0.5);
      n2.start(now + 0.08);
      n2.stop(now + 0.52);

    } else {
      _comboCount = 0;
      // Soft descending tone for uncheck
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.type = 'sine';
      osc.frequency.setValueAtTime(400, now);
      osc.frequency.exponentialRampToValueAtTime(240, now + 0.15);
      gain.gain.setValueAtTime(0, now);
      gain.gain.linearRampToValueAtTime(0.12, now + 0.01);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.18);
      osc.start(now);
      osc.stop(now + 0.2);
    }
  } catch (e) {}
}

function playAllDoneSound() {
  try {
    const ctx = getAudioCtx();
    const now = ctx.currentTime;
    // Triumphant three-note chord: C5, E5, G5 with shimmer
    const notes = [523, 659, 784];
    notes.forEach((freq, i) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.type = 'sine';
      osc.frequency.setValueAtTime(freq, now + i * 0.08);
      gain.gain.setValueAtTime(0, now + i * 0.08);
      gain.gain.linearRampToValueAtTime(0.2, now + i * 0.08 + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.001, now + i * 0.08 + 0.5);
      osc.start(now + i * 0.08);
      osc.stop(now + i * 0.08 + 0.5);
    });
    // High shimmer overtone
    const shimmer = ctx.createOscillator();
    const sGain = ctx.createGain();
    shimmer.connect(sGain);
    sGain.connect(ctx.destination);
    shimmer.type = 'triangle';
    shimmer.frequency.setValueAtTime(1568, now + 0.2);
    shimmer.frequency.exponentialRampToValueAtTime(2093, now + 0.6);
    sGain.gain.setValueAtTime(0, now + 0.2);
    sGain.gain.linearRampToValueAtTime(0.08, now + 0.25);
    sGain.gain.exponentialRampToValueAtTime(0.001, now + 0.8);
    shimmer.start(now + 0.2);
    shimmer.stop(now + 0.8);
  } catch (e) {}
}

function playWeekCellSound(isChecking) {
  try {
    const ctx = getAudioCtx();
    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.type = 'sine';
    if (isChecking) {
      osc.frequency.setValueAtTime(600, now);
      osc.frequency.exponentialRampToValueAtTime(900, now + 0.04);
    } else {
      osc.frequency.setValueAtTime(500, now);
      osc.frequency.exponentialRampToValueAtTime(350, now + 0.05);
    }
    gain.gain.setValueAtTime(0, now);
    gain.gain.linearRampToValueAtTime(0.12, now + 0.005);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.07);
    osc.start(now);
    osc.stop(now + 0.08);
  } catch (e) {}
}

function playSliderTick() {
  try {
    const ctx = getAudioCtx();
    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.type = 'sine';
    osc.frequency.setValueAtTime(1200, now);
    gain.gain.setValueAtTime(0.06, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.03);
    osc.start(now);
    osc.stop(now + 0.035);
  } catch (e) {}
}

/* ── Theme color helpers ──────────────────────────────────────────────────── */
function getThemeColors() {
  const cs = getComputedStyle(document.body);
  const base = cs.getPropertyValue('--theme').trim();
  const dim = cs.getPropertyValue('--theme-dim').trim();
  return [base, dim];
}

function getThemeParticleColors() {
  const [base, dim] = getThemeColors();
  // Generate lighter/brighter tints from the base color
  return [base, dim, base, dim, base];
}

/* ── Checkbox particle burst ──────────────────────────────────────────────── */
function spawnCheckParticlesAt(cx, cy) {
  const count = 8 + Math.floor(Math.random() * 6);
  const colors = getThemeParticleColors();

  for (let i = 0; i < count; i++) {
    const p = document.createElement('div');
    p.className = 'check-particle';
    const size = 3 + Math.random() * 5;
    const angle = (Math.PI * 2 / count) * i + (Math.random() - 0.5) * 0.5;
    const dist = 20 + Math.random() * 35;
    const dx = Math.cos(angle) * dist;
    const dy = Math.sin(angle) * dist;
    const color = colors[Math.floor(Math.random() * colors.length)];

    p.style.position = 'fixed';
    p.style.left = cx + 'px';
    p.style.top = cy + 'px';
    p.style.width = size + 'px';
    p.style.height = size + 'px';
    p.style.background = color;
    p.style.borderRadius = '50%';
    p.style.pointerEvents = 'none';
    p.style.zIndex = '9999';
    p.style.boxShadow = '0 0 ' + (size + 2) + 'px ' + color;
    p.style.setProperty('--dx', dx + 'px');
    p.style.setProperty('--dy', dy + 'px');
    p.style.animation = 'check-burst 0.5s ease-out forwards';
    document.body.appendChild(p);
    setTimeout(() => p.remove(), 600);
  }
}

/* ── Confetti celebration ─────────────────────────────────────────────────── */
let _celebrationShown = false;

function launchConfetti() {
  if (_celebrationShown) return;
  _celebrationShown = true;
  setTimeout(() => { _celebrationShown = false; }, 5000);

  const [base, dim] = getThemeColors();
  const colors = [base, dim, base, dim, base, '#fff'];
  const count = 60;

  for (let i = 0; i < count; i++) {
    const c = document.createElement('div');
    c.className = 'confetti-piece';
    const color = colors[Math.floor(Math.random() * colors.length)];
    const size = 4 + Math.random() * 6;
    const x = 20 + Math.random() * 60; // center-ish %
    const drift = (Math.random() - 0.5) * 200;
    const dur = 1.5 + Math.random() * 2;
    const delay = Math.random() * 0.5;
    const spin = Math.random() * 720 - 360;

    c.style.position = 'fixed';
    c.style.left = x + 'vw';
    c.style.top = '-10px';
    c.style.width = size + 'px';
    c.style.height = size * (Math.random() > 0.5 ? 1 : 2.5) + 'px';
    c.style.background = color;
    c.style.borderRadius = Math.random() > 0.5 ? '50%' : '2px';
    c.style.pointerEvents = 'none';
    c.style.zIndex = '10000';
    c.style.opacity = '1';
    c.style.setProperty('--drift', drift + 'px');
    c.style.setProperty('--spin', spin + 'deg');
    c.style.animation = 'confetti-fall ' + dur + 's ease-in ' + delay + 's forwards';
    document.body.appendChild(c);
    setTimeout(() => c.remove(), (dur + delay) * 1000 + 200);
  }
}

/* ── Segmented slider (Alpine component) ─────────────────────────────────── */
function segSlider(goal, initial, habitId, unit, step) {
  step = step || 0.5;
  const numSegs = Math.round(goal / step);
  const stepSize = step;

  return {
    goal: goal,
    value: initial,
    unit: unit,
    habitId: habitId,
    dragging: false,
    totalSegs: numSegs,
    segments: Array.from({length: numSegs - 1}, (_, i) => i + 1),
    _particleTimer: null,
    _saveTimer: null,
    _lastSnap: initial,

    get overGoal() { return this.value > this.goal; },
    get fillPct() {
      return this.value / this.goal * 100;
    },
    get goalLabel() { return this.fmt(this.goal) + this.unit; },
    get currentLabel() { return this.fmt(this.value) + this.unit; },

    fmt(v) {
      return v % 1 === 0 ? v.toFixed(0) : v.toFixed(1);
    },

    init() {
      this._onMove = (e) => this.onDrag(e);
      this._onUp = () => this.stopDrag();
      if (this.overGoal) this.startParticles();
    },

    valFromEvent(e) {
      const track = document.getElementById('seg-track-' + this.habitId);
      const rect = track.getBoundingClientRect();
      const clientX = e.touches ? e.touches[0].clientX : e.clientX;
      let ratio = (clientX - rect.left) / rect.width;
      ratio = Math.max(0, Math.min(1.5, ratio));
      let raw = ratio * this.goal;
      let snapped = Math.round(raw / stepSize) * stepSize;
      return Math.round(snapped * 10) / 10;
    },

    startDrag(e) {
      this.dragging = true;
      this.value = this.valFromEvent(e);
      this._lastSnap = this.value;
      this.sync();
      document.addEventListener('mousemove', this._onMove);
      document.addEventListener('mouseup', this._onUp);
      document.addEventListener('touchmove', this._onMove);
      document.addEventListener('touchend', this._onUp);
    },

    onDrag(e) {
      if (!this.dragging) return;
      this.value = this.valFromEvent(e);
      // Tick sound on each new segment snap
      if (this.value !== this._lastSnap) {
        playSliderTick();
        this._lastSnap = this.value;
      }
      this.sync();
    },

    stopDrag() {
      this.dragging = false;
      document.removeEventListener('mousemove', this._onMove);
      document.removeEventListener('mouseup', this._onUp);
      document.removeEventListener('touchmove', this._onMove);
      document.removeEventListener('touchend', this._onUp);
      this.autoSave();
    },

    sync() {
      const input = document.getElementById('metric-input-' + this.habitId);
      if (input) input.value = this.value;

      const wrap = document.getElementById('seg-wrap-' + this.habitId);
      const row = wrap ? wrap.closest('.habit-row') : null;
      if (this.overGoal) {
        if (wrap) wrap.classList.add('on-fire');
        if (row) row.classList.add('on-fire');
        this.startParticles();
      } else {
        if (wrap) wrap.classList.remove('on-fire');
        if (row) row.classList.remove('on-fire');
        this.stopParticles();
      }
    },

    autoSave() {
      if (this._saveTimer) clearTimeout(this._saveTimer);
      this._saveTimer = setTimeout(() => {
        const form = document.getElementById('detail-form-' + this.habitId);
        if (form) htmx.trigger(form, 'submit');
      }, 400);
    },

    startParticles() {
      if (this._particleTimer) return;
      this._particleTimer = setInterval(() => this.spawnParticle(), 120);
    },

    stopParticles() {
      if (this._particleTimer) {
        clearInterval(this._particleTimer);
        this._particleTimer = null;
      }
    },

    spawnParticle() {
      const container = document.getElementById('seg-particles-' + this.habitId);
      if (!container) return;
      const fill = container.closest('.seg-slider-track')?.querySelector('.seg-slider-fill');
      if (!fill) return;

      const p = document.createElement('div');
      p.className = 'seg-particle';

      const fillW = fill.offsetWidth;
      const x = Math.random() * fillW;
      const size = 2 + Math.random() * 4;

      const colors = getThemeParticleColors();
      const color = colors[Math.floor(Math.random() * colors.length)];

      p.style.left = x + 'px';
      p.style.top = (-size) + 'px';
      p.style.width = size + 'px';
      p.style.height = size + 'px';
      p.style.background = color;
      p.style.boxShadow = '0 0 ' + (size + 2) + 'px ' + color;

      const dx = (Math.random() - 0.5) * 30;
      const dy = -(10 + Math.random() * 30);
      p.style.setProperty('--px', dx + 'px');
      p.style.setProperty('--py', dy + 'px');
      p.style.animation = 'particle-float ' + (0.6 + Math.random() * 0.8) + 's ease-out forwards';

      container.appendChild(p);
      setTimeout(() => p.remove(), 1500);
    },
  };
}

/* ── Progress bar update ───────────────────────────────────────────────────── */
let _prevDone = -1;

function updateProgress() {
  const params = new URLSearchParams(window.location.search);
  const dateParam = params.get('date') ? '?log_date=' + params.get('date') : '';
  fetch('/api/summary' + dateParam)
    .then(r => r.json())
    .then(s => {
      const doneEl = document.getElementById('done-count');
      const totalEl = document.getElementById('total-count');
      const bar = document.getElementById('progress-bar');
      if (doneEl) doneEl.textContent = s.done;
      if (totalEl) totalEl.textContent = s.total;
      if (bar) {
        const pct = s.total > 0 ? Math.round(s.done / s.total * 100) : 0;
        bar.style.width = pct + '%';

        // Glow effect when progress bar is full
        const header = document.getElementById('progress-header');
        if (pct >= 100) {
          bar.classList.add('progress-full');
          if (header) header.classList.add('progress-complete');
          // Celebrate when we first hit 100%
          if (_prevDone >= 0 && _prevDone < s.total && s.done >= s.total) {
            playAllDoneSound();
            launchConfetti();
          }
        } else {
          bar.classList.remove('progress-full');
          if (header) header.classList.remove('progress-complete');
        }
      }
      _prevDone = s.done;
    })
    .catch(() => {});
}

// Initialize _prevDone on page load
document.addEventListener('DOMContentLoaded', () => {
  const doneEl = document.getElementById('done-count');
  if (doneEl) _prevDone = parseInt(doneEl.textContent) || 0;
});

/* ── Capture checkbox position BEFORE the swap ────────────────────────────── */
let _pendingParticle = null;
let _pendingStartRect = null;

document.body.addEventListener('htmx:beforeSwap', function(evt) {
  const target = evt.detail.target;
  if (target && target.classList && target.classList.contains('habit-row')) {
    const checkbox = target.querySelector('.checkbox-box');
    if (checkbox) {
      const rect = checkbox.getBoundingClientRect();
      const wasChecked = checkbox.classList.contains('checked');
      _pendingParticle = {
        x: rect.left + rect.width / 2,
        y: rect.top + rect.height / 2,
        wasChecked: wasChecked,
      };
      // Capture the full row rect for FLIP animation
      _pendingStartRect = target.getBoundingClientRect();
    }
  }
});

/* ── Helper: ensure "Completed" label exists ─────────────────────────────── */
function ensureCompletedLabel(complete) {
  if (!complete.querySelector('.habits-done-label')) {
    const label = document.createElement('div');
    label.className = 'habits-done-label';
    label.textContent = 'Completed';
    complete.prepend(label);
  }
}

/* ── Find incomplete/complete sections for a row's category card ──────────── */
function getSectionsForRow(row) {
  const complete = document.getElementById('habits-complete');
  // Use the data-category-id on the row to find its home card
  const catId = row.dataset.categoryId || '';
  const cardSelector = catId
    ? '.category-card[data-category-id="' + catId + '"]'
    : '.category-card[data-category-id="none"]';
  const card = document.querySelector(cardSelector);
  if (card) {
    return {
      incomplete: card.querySelector('.habits-list'),
      complete: complete,
      card: card,
    };
  }
  // Fallback: try the card the row is currently inside
  const parentCard = row.closest('.category-card');
  if (parentCard) {
    return {
      incomplete: parentCard.querySelector('.habits-list'),
      complete: complete,
      card: parentCard,
    };
  }
  return {
    incomplete: document.querySelector('.habits-list'),
    complete: complete,
    card: null,
  };
}

/* ── Update category card all-done state ──────────────────────────────────── */
function updateCategoryCardStates() {
  document.querySelectorAll('.category-card[data-category-id]').forEach(card => {
    const rows = card.querySelectorAll('.habit-row');
    if (rows.length === 0) return;
    const allDone = Array.from(rows).every(r => r.querySelector('.checkbox-box.checked'));
    card.classList.toggle('category-all-done', allDone);
  });
}

/* ── Move row to correct section without animation ───────────────────────── */
function moveRowToCorrectSection(row) {
  const isCompleted = row.querySelector('.checkbox-box.checked') !== null;
  const { incomplete, complete } = getSectionsForRow(row);
  if (!incomplete || !complete) return;

  const targetParent = isCompleted ? complete : incomplete;
  if (row.parentElement === targetParent) return;

  if (isCompleted) {
    ensureCompletedLabel(complete);
    complete.style.display = '';
    complete.appendChild(row);
  } else {
    incomplete.appendChild(row);
    if (complete.querySelectorAll('.habit-row').length === 0) {
      complete.style.display = 'none';
    }
  }
  updateCategoryCardStates();
}

/* ── Animated move: FLIP-based — row is moved immediately, then animated ──── */
function animateRowToSection(row, startRect) {
  const isCompleted = row.querySelector('.checkbox-box.checked') !== null;
  const { incomplete, complete } = getSectionsForRow(row);
  if (!incomplete || !complete) return;

  const targetParent = isCompleted ? complete : incomplete;
  if (row.parentElement === targetParent) {
    updateCategoryCardStates();
    return;
  }
  if (!startRect) {
    moveRowToCorrectSection(row);
    return;
  }

  const DURATION = 1200;

  // FLIP Step 1 (First): startRect was captured before the swap

  // FLIP Step 2 (Move): move the row to its final DOM position immediately
  // — it's interactive right away at its new location
  if (isCompleted) {
    ensureCompletedLabel(complete);
    complete.style.display = '';
    complete.appendChild(row);
  } else {
    incomplete.appendChild(row);
    if (complete.querySelectorAll('.habit-row').length === 0) {
      complete.style.display = 'none';
    }
  }
  updateCategoryCardStates();

  // FLIP Step 3 (Last): measure where the row ended up
  const endRect = row.getBoundingClientRect();

  // FLIP Step 4 (Invert): calculate the delta and apply inverse transform
  const dx = startRect.left - endRect.left;
  const dy = startRect.top - endRect.top;

  if (Math.abs(dx) < 1 && Math.abs(dy) < 1) return; // no visible move

  row.classList.add('habit-row-animating');

  // Use Web Animations API — immune to CSS interference
  const anim = row.animate([
    { transform: `translate(${dx}px, ${dy}px)` },
    { transform: 'translate(0, 0)' }
  ], {
    duration: DURATION,
    easing: 'cubic-bezier(0.16, 1, 0.3, 1)',
    fill: 'none',
  });

  anim.onfinish = () => {
    row.classList.remove('habit-row-animating');
  };
}

/* ── Sync week grid quietly (plain fetch, no HTMX events) ───────────────── */
function syncWeekGridQuiet() {
  const weekContainer = document.getElementById('week-grid-container');
  if (!weekContainer) return;
  const params = new URLSearchParams(window.location.search);
  const dateParam = params.get('date') || '';
  const url = '/app/week' + (dateParam ? '?week=' + dateParam : '');
  fetch(url).then(r => r.text()).then(html => {
    weekContainer.innerHTML = html;
    htmx.process(weekContainer);
  }).catch(() => {});
}

/* ── Sync all habit rows quietly (plain fetch, no HTMX events) ───────────── */
function syncHabitRowsQuiet() {
  const params = new URLSearchParams(window.location.search);
  const logDate = params.get('date') || '';
  document.querySelectorAll('.habit-row').forEach(row => {
    const match = row.id.match(/^habit-(\d+)$/);
    if (!match) return;
    const habitId = match[1];
    const url = '/habits/' + habitId + '/row' + (logDate ? '?log_date=' + logDate : '');
    fetch(url).then(r => r.text()).then(html => {
      const temp = document.createElement('div');
      temp.innerHTML = html;
      const newRow = temp.firstElementChild;
      const currentRow = document.getElementById('habit-' + habitId);
      if (currentRow && newRow) {
        currentRow.replaceWith(newRow);
        htmx.process(newRow);
        moveRowToCorrectSection(newRow);
      }
    }).catch(() => {});
  });
}

/* ── HTMX afterSwap: only fires for user-initiated HTMX actions ─────────── */
document.body.addEventListener('htmx:afterSwap', function(evt) {
  const swapped = evt.detail.target;

  // ── Habit row swapped (user clicked a checkbox) ──
  if (swapped && swapped.classList && swapped.classList.contains('habit-row')) {
    const rowId = swapped.id;
    const row = rowId ? document.getElementById(rowId) : null;
    if (!row) return;

    row.classList.remove('habit-flash');
    void row.offsetWidth;
    row.classList.add('habit-flash');

    if (_pendingParticle && !_pendingParticle.wasChecked) {
      spawnCheckParticlesAt(_pendingParticle.x, _pendingParticle.y);
    }
    _pendingParticle = null;

    animateRowToSection(row, _pendingStartRect);
    _pendingStartRect = null;
    syncWeekGridQuiet();
    updateProgress();
    updateCategoryCardStates();
  }

});

// ── Week grid: listen for week-toggle responses to sync habit rows ──
document.body.addEventListener('htmx:afterSettle', function(evt) {
  const target = evt.detail.target;
  if (target && target.id === 'week-grid-container') {
    syncHabitRowsQuiet();
    updateProgress();
    // Update card states after rows sync (with delay for fetch to complete)
    setTimeout(updateCategoryCardStates, 500);
  }
});

// ── Initialize category card states on page load ──
document.addEventListener('DOMContentLoaded', updateCategoryCardStates);

/* ── Habit edit modal ────────────────────────────────────────────────────── */
async function openHabitEditor(habitId) {
  const overlay = document.getElementById('habit-edit-overlay');
  if (!overlay) return;
  // Get the current viewing date from the page
  const logDateInput = document.querySelector('input[name="log_date"]');
  const logDate = logDateInput ? logDateInput.value : '';
  const url = '/api/habits/' + habitId + (logDate ? '?log_date=' + logDate : '');
  const resp = await fetch(url);
  const data = await resp.json();
  // Set Alpine data on the panel
  const panel = overlay.querySelector('.habit-edit-panel');
  if (panel && panel.__x) {
    const d = panel.__x.$data;
    d.id = data.id;
    d.name = data.name;
    d.description = data.description;
    d.category_id = String(data.category_id || '');
    d.metric_enabled = data.metric_enabled;
    d.metric_unit = data.metric_unit;
    d.metric_default = data.metric_default;
    d.metric_max = data.metric_max;
    d.metric_step = data.metric_step;
  } else if (panel && panel._x_dataStack) {
    // Alpine v3
    const d = Alpine.$data(panel);
    d.id = data.id;
    d.name = data.name;
    d.description = data.description;
    d.category_id = String(data.category_id || '');
    d.metric_enabled = data.metric_enabled;
    d.metric_unit = data.metric_unit;
    d.metric_default = data.metric_default;
    d.metric_max = data.metric_max;
    d.metric_step = data.metric_step;
  }
  overlay.style.display = 'flex';
}

function closeHabitEditor() {
  const overlay = document.getElementById('habit-edit-overlay');
  if (overlay) overlay.style.display = 'none';
}

/* ── Category card drag-reorder (mouse-driven for "pick up" feel) ─────────── */
(function() {
  let dragCard = null;
  let clone = null;
  let placeholder = null;
  let indicator = null;
  let offsetX = 0, offsetY = 0;
  let dropTarget = null;
  let dropBefore = true;

  function getIndicator() {
    if (!indicator) {
      indicator = document.createElement('div');
      indicator.className = 'category-card-drop-indicator';
    }
    return indicator;
  }

  function removeIndicator() {
    if (indicator && indicator.parentNode) indicator.remove();
  }

  function cleanup() {
    if (clone) clone.remove();
    if (placeholder) {
      placeholder.style.transition = 'height 200ms ease';
      placeholder.style.height = '0';
      setTimeout(() => placeholder.remove(), 200);
    }
    removeIndicator();
    if (dragCard) {
      dragCard.style.display = '';
      dragCard.classList.remove('category-card-dragging');
    }
    clone = null;
    placeholder = null;
    dragCard = null;
    dropTarget = null;
    document.removeEventListener('mousemove', onMove);
    document.removeEventListener('mouseup', onUp);
  }

  function onMove(e) {
    if (!clone) return;
    clone.style.left = (e.clientX - offsetX) + 'px';
    clone.style.top = (e.clientY - offsetY) + 'px';

    // Find which card we're over
    // Temporarily hide clone so elementFromPoint hits the real cards
    clone.style.pointerEvents = 'none';
    const el = document.elementFromPoint(e.clientX, e.clientY);
    clone.style.pointerEvents = '';
    if (!el) return;
    const card = el.closest('.category-card');
    if (!card || card === dragCard || card === placeholder) {
      return;
    }

    const rect = card.getBoundingClientRect();
    const mid = rect.top + rect.height / 2;
    const ind = getIndicator();
    dropTarget = card;

    if (e.clientY < mid) {
      dropBefore = true;
      card.parentElement.insertBefore(ind, card);
    } else {
      dropBefore = false;
      if (card.nextSibling) {
        card.parentElement.insertBefore(ind, card.nextSibling);
      } else {
        card.parentElement.appendChild(ind);
      }
    }
  }

  function onUp(e) {
    if (!dragCard) { cleanup(); return; }

    removeIndicator();

    if (!dropTarget || dropTarget === dragCard) {
      // No valid drop — animate back
      const origRect = placeholder.getBoundingClientRect();
      clone.style.transition = 'top 250ms ease, left 250ms ease, transform 250ms ease, box-shadow 250ms ease';
      clone.style.top = origRect.top + 'px';
      clone.style.left = origRect.left + 'px';
      clone.style.transform = 'scale(1)';
      clone.style.boxShadow = 'none';
      setTimeout(cleanup, 260);
      return;
    }

    // Capture old positions of all cards for FLIP
    const parent = dragCard.parentElement;
    const allCards = Array.from(parent.querySelectorAll('.category-card[data-category-id]'));
    const oldRects = new Map();
    allCards.forEach(c => oldRects.set(c, c.getBoundingClientRect()));

    // Move in DOM
    if (dropBefore) {
      parent.insertBefore(dragCard, dropTarget);
    } else {
      if (dropTarget.nextSibling) {
        parent.insertBefore(dragCard, dropTarget.nextSibling);
      } else {
        parent.appendChild(dragCard);
      }
    }

    // Show the real card, get its landing rect
    dragCard.style.display = '';
    const landRect = dragCard.getBoundingClientRect();

    // Animate clone to the landing spot
    clone.style.transition = 'top 250ms ease, left 250ms ease, transform 250ms ease, box-shadow 250ms ease';
    clone.style.top = landRect.top + 'px';
    clone.style.left = landRect.left + 'px';
    clone.style.width = landRect.width + 'px';
    clone.style.transform = 'scale(1)';
    clone.style.boxShadow = 'none';

    // Hide real card until clone arrives
    dragCard.style.opacity = '0';

    // FLIP the other cards
    allCards.forEach(c => {
      if (c === dragCard) return;
      const oldRect = oldRects.get(c);
      if (!oldRect) return;
      const newRect = c.getBoundingClientRect();
      const dx = oldRect.left - newRect.left;
      const dy = oldRect.top - newRect.top;
      if (dx === 0 && dy === 0) return;
      c.style.transform = 'translate(' + dx + 'px, ' + dy + 'px)';
      c.style.transition = 'none';
      requestAnimationFrame(() => {
        c.style.transition = 'transform 250ms ease';
        c.style.transform = '';
        c.addEventListener('transitionend', function fn() {
          c.style.transition = '';
          c.style.transform = '';
          c.removeEventListener('transitionend', fn);
        });
      });
    });

    setTimeout(() => {
      dragCard.style.opacity = '';
      if (clone) clone.remove();
      if (placeholder) placeholder.remove();
      clone = null;
      placeholder = null;

      // Save order
      const updatedCards = parent.querySelectorAll('.category-card[data-category-id]');
      const orderedIds = [];
      updatedCards.forEach(c => {
        if (c.dataset.categoryId && c.dataset.categoryId !== 'none') {
          orderedIds.push(c.dataset.categoryId);
        }
      });
      const body = new URLSearchParams();
      orderedIds.forEach(id => body.append('order[]', id));
      fetch('/categories/reorder', { method: 'POST', body: body }).catch(() => {});

      dragCard = null;
      dropTarget = null;
    }, 260);

    document.removeEventListener('mousemove', onMove);
    document.removeEventListener('mouseup', onUp);
  }

  // Prevent native drag on handles (we use mouse events instead)
  document.addEventListener('dragstart', function(e) {
    if (e.target.closest('.category-card-drag-handle')) e.preventDefault();
  });

  document.addEventListener('mousedown', function(e) {
    const handle = e.target.closest('.category-card-drag-handle');
    if (!handle) return;
    const card = handle.closest('.category-card');
    if (!card || !card.dataset.categoryId || card.dataset.categoryId === 'none') return;
    e.preventDefault();

    dragCard = card;
    const rect = card.getBoundingClientRect();
    offsetX = e.clientX - rect.left;
    offsetY = e.clientY - rect.top;

    // Create floating clone
    clone = card.cloneNode(true);
    clone.style.position = 'fixed';
    clone.style.top = rect.top + 'px';
    clone.style.left = rect.left + 'px';
    clone.style.width = rect.width + 'px';
    clone.style.zIndex = '9999';
    clone.style.margin = '0';
    clone.style.pointerEvents = 'none';
    clone.style.transition = 'transform 150ms ease, box-shadow 150ms ease';
    clone.style.transform = 'scale(1.03)';
    clone.style.boxShadow = '0 12px 40px rgba(0,0,0,0.4)';
    clone.style.borderColor = 'var(--theme-dark)';
    // Strip interactivity
    clone.querySelectorAll('[hx-post],[hx-get],[hx-delete],[hx-target]').forEach(el => {
      ['hx-post','hx-get','hx-delete','hx-target','hx-swap','hx-include','hx-trigger','hx-vals'].forEach(a => el.removeAttribute(a));
    });
    document.body.appendChild(clone);

    // Leave a placeholder where the card was
    placeholder = document.createElement('div');
    placeholder.style.height = rect.height + 'px';
    placeholder.style.transition = 'height 200ms ease';
    placeholder.style.overflow = 'hidden';
    card.parentElement.insertBefore(placeholder, card);

    // Hide the real card
    card.style.display = 'none';

    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  });
})();

/* ── Habit row drag-reorder (within category cards) ──────────────────────── */
(function() {
  let dragRow = null;
  let clone = null;
  let placeholder = null;
  let offsetX = 0, offsetY = 0;
  let dropTarget = null;
  let dropBefore = true;
  let parentList = null;

  function cleanup() {
    if (clone) clone.remove();
    if (placeholder) placeholder.remove();
    if (dragRow) {
      dragRow.style.display = '';
      dragRow.style.opacity = '';
    }
    clone = null;
    placeholder = null;
    dragRow = null;
    dropTarget = null;
    parentList = null;
    document.removeEventListener('mousemove', onMove);
    document.removeEventListener('mouseup', onUp);
  }

  function onMove(e) {
    if (!clone) return;
    clone.style.left = (e.clientX - offsetX) + 'px';
    clone.style.top = (e.clientY - offsetY) + 'px';

    clone.style.pointerEvents = 'none';
    const el = document.elementFromPoint(e.clientX, e.clientY);
    clone.style.pointerEvents = '';
    if (!el) return;
    const row = el.closest('.habit-row');
    if (!row || row === dragRow || row === placeholder) return;
    // Only reorder within the same list
    if (!parentList || !parentList.contains(row)) return;

    const rect = row.getBoundingClientRect();
    const mid = rect.top + rect.height / 2;
    dropTarget = row;
    dropBefore = e.clientY < mid;
  }

  function onUp(e) {
    if (!dragRow) { cleanup(); return; }

    if (!dropTarget || dropTarget === dragRow) {
      const origRect = placeholder.getBoundingClientRect();
      clone.style.transition = 'top 200ms ease, left 200ms ease, transform 200ms ease, box-shadow 200ms ease';
      clone.style.top = origRect.top + 'px';
      clone.style.left = origRect.left + 'px';
      clone.style.transform = 'scale(1)';
      clone.style.boxShadow = 'none';
      setTimeout(cleanup, 210);
      return;
    }

    // FLIP: capture old positions
    const allRows = Array.from(parentList.querySelectorAll('.habit-row'));
    const oldRects = new Map();
    allRows.forEach(r => oldRects.set(r, r.getBoundingClientRect()));

    // Move in DOM
    if (dropBefore) {
      parentList.insertBefore(dragRow, dropTarget);
    } else {
      if (dropTarget.nextSibling) {
        parentList.insertBefore(dragRow, dropTarget.nextSibling);
      } else {
        parentList.appendChild(dragRow);
      }
    }

    dragRow.style.display = '';
    const landRect = dragRow.getBoundingClientRect();

    // Animate clone to landing
    clone.style.transition = 'top 200ms ease, left 200ms ease, transform 200ms ease, box-shadow 200ms ease';
    clone.style.top = landRect.top + 'px';
    clone.style.left = landRect.left + 'px';
    clone.style.width = landRect.width + 'px';
    clone.style.transform = 'scale(1)';
    clone.style.boxShadow = 'none';
    dragRow.style.opacity = '0';

    // FLIP other rows
    allRows.forEach(r => {
      if (r === dragRow) return;
      const oldRect = oldRects.get(r);
      if (!oldRect) return;
      const newRect = r.getBoundingClientRect();
      const dy = oldRect.top - newRect.top;
      if (dy === 0) return;
      r.animate([
        { transform: 'translateY(' + dy + 'px)' },
        { transform: 'translateY(0)' }
      ], { duration: 200, easing: 'ease' });
    });

    setTimeout(() => {
      dragRow.style.opacity = '';
      if (clone) clone.remove();
      if (placeholder) placeholder.remove();
      clone = null;
      placeholder = null;

      // Save order — collect all habit IDs across all lists on the page
      const orderedIds = [];
      document.querySelectorAll('.habits-list .habit-row, .habits-done-section .habit-row').forEach(r => {
        const m = r.id.match(/^habit-(\d+)$/);
        if (m) orderedIds.push(m[1]);
      });
      const body = new URLSearchParams();
      orderedIds.forEach(id => body.append('order[]', id));
      fetch('/habits/reorder', { method: 'POST', body }).catch(() => {});

      dragRow = null;
      dropTarget = null;
      parentList = null;
    }, 210);

    document.removeEventListener('mousemove', onMove);
    document.removeEventListener('mouseup', onUp);
  }

  document.addEventListener('dragstart', function(e) {
    if (e.target.closest('.habit-drag-handle')) e.preventDefault();
  });

  document.addEventListener('mousedown', function(e) {
    const handle = e.target.closest('.habit-drag-handle');
    if (!handle) return;
    const row = handle.closest('.habit-row');
    if (!row) return;
    const list = row.closest('.habits-list');
    if (!list) return;
    e.preventDefault();

    dragRow = row;
    parentList = list;
    const rect = row.getBoundingClientRect();
    offsetX = e.clientX - rect.left;
    offsetY = e.clientY - rect.top;

    clone = row.cloneNode(true);
    clone.style.position = 'fixed';
    clone.style.top = rect.top + 'px';
    clone.style.left = rect.left + 'px';
    clone.style.width = rect.width + 'px';
    clone.style.zIndex = '9999';
    clone.style.margin = '0';
    clone.style.pointerEvents = 'none';
    clone.style.transition = 'transform 150ms ease, box-shadow 150ms ease';
    clone.style.transform = 'scale(1.03)';
    clone.style.boxShadow = '0 8px 30px rgba(0,0,0,0.35)';
    clone.querySelectorAll('[hx-post],[hx-get],[hx-delete],[hx-target]').forEach(el => {
      ['hx-post','hx-get','hx-delete','hx-target','hx-swap','hx-include','hx-trigger','hx-vals'].forEach(a => el.removeAttribute(a));
    });
    document.body.appendChild(clone);

    placeholder = document.createElement('div');
    placeholder.style.height = rect.height + 'px';
    placeholder.style.transition = 'height 200ms ease';
    placeholder.style.overflow = 'hidden';
    list.insertBefore(placeholder, row);

    row.style.display = 'none';

    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  });
})();
