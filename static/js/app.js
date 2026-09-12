/* =========================================================================
   Dnipro Visa Partners — public site behaviour
   Vanilla ES2020. No dependencies, no build step.
   ========================================================================= */
(function () {
  'use strict';

  /* ------------------------------------------------------------------ *
   * Boot data & tiny helpers
   * ------------------------------------------------------------------ */
  const BOOT = (() => {
    const node = document.getElementById('bootData');
    if (!node) return {};
    try {
      return JSON.parse(node.textContent);
    } catch (err) {
      console.error('Could not parse boot data', err);
      return {};
    }
  })();

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  const REDUCED_MOTION = window.matchMedia(
    '(prefers-reduced-motion: reduce)'
  ).matches;

  /** Build a DOM element in one call. */
  function el(tag, attrs = {}, children = []) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs)) {
      if (value === null || value === undefined || value === false) continue;
      if (key === 'class') node.className = value;
      else if (key === 'text') node.textContent = value;
      else if (key === 'html') node.innerHTML = value;
      else if (key.startsWith('on') && typeof value === 'function') {
        node.addEventListener(key.slice(2).toLowerCase(), value);
      } else if (value === true) node.setAttribute(key, '');
      else node.setAttribute(key, String(value));
    }
    for (const child of [].concat(children)) {
      if (child === null || child === undefined) continue;
      node.append(child instanceof Node ? child : document.createTextNode(child));
    }
    return node;
  }

  function debounce(fn, wait = 250) {
    let timer;
    return (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => fn(...args), wait);
    };
  }

  /** fetch() wrapper that always resolves to { ok, status, data }. */
  async function api(url, options = {}) {
    const config = {
      headers: { Accept: 'application/json', 'X-Requested-With': 'fetch' },
      ...options,
    };
    if (config.body && typeof config.body !== 'string') {
      config.headers['Content-Type'] = 'application/json';
      config.body = JSON.stringify(config.body);
    }
    try {
      const response = await fetch(url, config);
      let data = null;
      try {
        data = await response.json();
      } catch (_) {
        data = null;
      }
      return { ok: response.ok, status: response.status, data: data || {} };
    } catch (err) {
      console.error('Network error', url, err);
      return {
        ok: false,
        status: 0,
        data: { error: 'Network problem — please check your connection.' },
      };
    }
  }

  /* ------------------------------------------------------------------ *
   * Toasts
   * ------------------------------------------------------------------ */
  const Toast = (() => {
    const host = $('#toasts');
    const ICONS = { success: '✓', error: '!', info: 'i' };

    function show(message, kind = 'info', ttl = 5200) {
      if (!host) return;
      const node = el('div', { class: `toast toast--${kind}` }, [
        el('span', { class: 'toast__icon', 'aria-hidden': 'true', text: ICONS[kind] || 'i' }),
        el('span', { text: message }),
      ]);
      host.append(node);
      const remove = () => {
        node.classList.add('is-leaving');
        setTimeout(() => node.remove(), 320);
      };
      const timer = setTimeout(remove, ttl);
      node.addEventListener('click', () => {
        clearTimeout(timer);
        remove();
      });
    }

    return {
      success: (m, t) => show(m, 'success', t),
      error: (m, t) => show(m, 'error', t || 7000),
      info: (m, t) => show(m, 'info', t),
    };
  })();

  /* ------------------------------------------------------------------ *
   * Theme toggle
   * ------------------------------------------------------------------ */
  (function theme() {
    const KEY = 'vc-theme';
    const root = document.documentElement;
    const toggle = $('#themeToggle');

    const stored = (() => {
      try {
        return localStorage.getItem(KEY);
      } catch (_) {
        return null;
      }
    })();

    if (stored === 'light' || stored === 'dark') {
      root.dataset.theme = stored;
    } else if (window.matchMedia('(prefers-color-scheme: light)').matches) {
      root.dataset.theme = 'light';
    }

    toggle?.addEventListener('click', () => {
      const next = root.dataset.theme === 'light' ? 'dark' : 'light';
      root.dataset.theme = next;
      try {
        localStorage.setItem(KEY, next);
      } catch (_) {
        /* private browsing — ignore */
      }
    });
  })();

  /* ------------------------------------------------------------------ *
   * Header: sticky state, scroll progress, mobile nav, active link
   * ------------------------------------------------------------------ */
  (function header() {
    const bar = $('#siteHeader');
    const progress = $('#scrollProgress');
    const nav = $('#primaryNav');
    const burger = $('#burger');

    const onScroll = () => {
      const y = window.scrollY;
      bar?.classList.toggle('is-stuck', y > 8);
      if (progress) {
        const max = document.body.scrollHeight - window.innerHeight;
        progress.style.width = `${max > 0 ? Math.min((y / max) * 100, 100) : 0}%`;
      }
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();

    // Mobile menu
    const closeNav = () => {
      nav?.classList.remove('is-open');
      burger?.setAttribute('aria-expanded', 'false');
      burger?.setAttribute('aria-label', 'Open menu');
    };
    burger?.addEventListener('click', () => {
      const open = nav?.classList.toggle('is-open');
      burger.setAttribute('aria-expanded', String(!!open));
      burger.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
    });
    nav?.addEventListener('click', (e) => {
      if (e.target.closest('a')) closeNav();
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') closeNav();
    });
    window.addEventListener('resize', debounce(() => {
      if (window.innerWidth > 900) closeNav();
    }, 200));

    // Highlight the section currently in view.
    const links = $$('#primaryNav a[href^="#"]');
    const sections = links
      .map((link) => {
        const id = link.getAttribute('href').slice(1);
        const section = document.getElementById(id);
        return section ? { link, section } : null;
      })
      .filter(Boolean);

    if (sections.length && 'IntersectionObserver' in window) {
      const spy = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (!entry.isIntersecting) return;
            const match = sections.find((s) => s.section === entry.target);
            if (!match) return;
            links.forEach((l) => l.classList.remove('is-current'));
            match.link.classList.add('is-current');
          });
        },
        { rootMargin: '-45% 0px -50% 0px' }
      );
      sections.forEach(({ section }) => spy.observe(section));
    }
  })();

  /* ------------------------------------------------------------------ *
   * Scroll reveal
   * ------------------------------------------------------------------ */
  (function reveal() {
    const targets = $$('.reveal');
    if (!targets.length) return;
    if (REDUCED_MOTION || !('IntersectionObserver' in window)) {
      targets.forEach((t) => t.classList.add('is-visible'));
      return;
    }
    const observer = new IntersectionObserver(
      (entries, obs) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          entry.target.classList.add('is-visible');
          obs.unobserve(entry.target);
        });
      },
      { threshold: 0.12, rootMargin: '0px 0px -8% 0px' }
    );
    targets.forEach((t) => observer.observe(t));
  })();

  /* ------------------------------------------------------------------ *
   * Animated stat counters
   * ------------------------------------------------------------------ */
  (function counters() {
    const nodes = $$('[data-count-to]');
    if (!nodes.length) return;

    const run = (node) => {
      const target = parseFloat(node.dataset.countTo) || 0;
      const suffix = node.dataset.suffix || '';
      if (REDUCED_MOTION) {
        node.textContent = `${target.toLocaleString()}${suffix}`;
        return;
      }
      const duration = 1500;
      const start = performance.now();
      const tick = (now) => {
        const progress = Math.min((now - start) / duration, 1);
        // easeOutExpo keeps the motion lively but settles precisely.
        const eased = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress);
        node.textContent =
          Math.round(target * eased).toLocaleString() + suffix;
        if (progress < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    };

    if (!('IntersectionObserver' in window)) {
      nodes.forEach(run);
      return;
    }
    const observer = new IntersectionObserver(
      (entries, obs) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          run(entry.target);
          obs.unobserve(entry.target);
        });
      },
      { threshold: 0.5 }
    );
    nodes.forEach((n) => observer.observe(n));
  })();

  /* ------------------------------------------------------------------ *
   * Visa card pointer glow
   * ------------------------------------------------------------------ */
  (function cardGlow() {
    if (REDUCED_MOTION || !window.matchMedia('(hover: hover)').matches) return;
    $$('.visa-card').forEach((card) => {
      const inner = $('.visa-card__inner', card);
      if (!inner) return;
      card.addEventListener('pointermove', (e) => {
        const rect = card.getBoundingClientRect();
        inner.style.setProperty('--mx', `${e.clientX - rect.left}px`);
        inner.style.setProperty('--my', `${e.clientY - rect.top}px`);
      });
    });
  })();

  /* ------------------------------------------------------------------ *
   * Testimonial carousel
   * ------------------------------------------------------------------ */
  (function carousel() {
    const root = $('#carousel');
    const track = $('#carouselTrack');
    const dotsHost = $('#carouselDots');
    if (!root || !track) return;

    const slides = $$('.quote', track);
    if (slides.length <= 1) {
      $('.carousel__controls', root)?.remove();
      return;
    }

    let index = 0;
    let timer = null;
    const AUTOPLAY = 6500;

    const dots = slides.map((_, i) =>
      el('button', {
        class: 'carousel__dot',
        type: 'button',
        role: 'tab',
        'aria-label': `Testimonial ${i + 1}`,
        onclick: () => {
          go(i);
          restart();
        },
      })
    );
    dots.forEach((d) => dotsHost?.append(d));

    function go(next) {
      index = (next + slides.length) % slides.length;
      track.style.transform = `translateX(-${index * 100}%)`;
      dots.forEach((dot, i) => {
        const active = i === index;
        dot.classList.toggle('is-active', active);
        dot.setAttribute('aria-selected', String(active));
      });
      slides.forEach((slide, i) => {
        // Keep off-screen slides out of the tab order.
        slide.toggleAttribute('inert', i !== index);
      });
    }

    function stop() {
      if (timer) clearInterval(timer);
      timer = null;
    }
    function restart() {
      stop();
      if (REDUCED_MOTION) return;
      timer = setInterval(() => go(index + 1), AUTOPLAY);
    }

    $('#carouselNext')?.addEventListener('click', () => {
      go(index + 1);
      restart();
    });
    $('#carouselPrev')?.addEventListener('click', () => {
      go(index - 1);
      restart();
    });

    root.addEventListener('pointerenter', stop);
    root.addEventListener('pointerleave', restart);
    root.addEventListener('focusin', stop);

    root.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowRight') {
        go(index + 1);
        restart();
      } else if (e.key === 'ArrowLeft') {
        go(index - 1);
        restart();
      }
    });

    // Touch swipe
    let startX = null;
    const viewport = $('#carouselViewport');
    viewport?.addEventListener(
      'touchstart',
      (e) => {
        startX = e.touches[0].clientX;
        stop();
      },
      { passive: true }
    );
    viewport?.addEventListener(
      'touchend',
      (e) => {
        if (startX === null) return;
        const delta = e.changedTouches[0].clientX - startX;
        if (Math.abs(delta) > 45) go(index + (delta < 0 ? 1 : -1));
        startX = null;
        restart();
      },
      { passive: true }
    );

    // Pause when scrolled out of view.
    if ('IntersectionObserver' in window) {
      new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => (entry.isIntersecting ? restart() : stop()));
        },
        { threshold: 0.25 }
      ).observe(root);
    } else {
      restart();
    }

    go(0);
  })();

  /* ------------------------------------------------------------------ *
   * Eligibility wizard
   * ------------------------------------------------------------------ */
  (function wizard() {
    const config = BOOT.wizard;
    const stage = $('#wizardStage');
    if (!config || !stage || !Array.isArray(config.questions)) return;

    const bar = $('#wizardBar');
    const counter = $('#wizardCounter');
    const backBtn = $('#wizardBack');
    const restartBtn = $('#wizardRestart');
    const intro = $('#wizardIntro');
    if (intro) intro.textContent = config.intro || '';

    const questions = config.questions;
    let step = 0;
    const answers = []; // { label, question, scores }

    function scoreboard() {
      const totals = {};
      answers.forEach((answer) => {
        for (const [serviceId, weight] of Object.entries(answer.scores || {})) {
          totals[serviceId] = (totals[serviceId] || 0) + weight;
        }
      });
      return totals;
    }

    function bestService() {
      const totals = scoreboard();
      let winner = 'other';
      let top = -1;
      for (const [serviceId, total] of Object.entries(totals)) {
        if (total > top) {
          top = total;
          winner = serviceId;
        }
      }
      return winner;
    }

    function updateChrome() {
      const total = questions.length;
      const done = Math.min(step, total);
      if (bar) bar.style.width = `${(done / total) * 100}%`;
      if (counter) {
        counter.textContent =
          step >= total ? 'Your result' : `Question ${step + 1} of ${total}`;
      }
      backBtn.hidden = step === 0 || step >= total;
      restartBtn.hidden = step === 0;
    }

    function renderQuestion() {
      const question = questions[step];
      stage.replaceChildren(
        el('div', { class: 'wizard__question' }, [
          el('h3', { text: question.label }),
          el(
            'div',
            { class: 'wizard__options' },
            question.options.map((option, i) =>
              el(
                'button',
                {
                  class: 'wizard__option',
                  type: 'button',
                  onclick: () => {
                    answers[step] = {
                      question: question.label,
                      label: option.label,
                      scores: option.scores || {},
                    };
                    step += 1;
                    render();
                  },
                },
                [
                  el('span', {
                    class: 'wizard__option-key',
                    'aria-hidden': 'true',
                    text: String.fromCharCode(65 + i),
                  }),
                  el('span', { text: option.label }),
                ]
              )
            )
          ),
        ])
      );
      // Move focus to the new question for keyboard/screen-reader users.
      $('.wizard__question h3', stage)?.setAttribute('tabindex', '-1');
      if (step > 0) $('.wizard__question h3', stage)?.focus({ preventScroll: true });
    }

    function renderResult() {
      const serviceId = bestService();
      const outcome =
        (config.outcomes && config.outcomes[serviceId]) ||
        config.outcomes?.other || { title: 'Free orientation call', text: '' };
      const service = (BOOT.services || []).find((s) => s.id === serviceId);

      stage.replaceChildren(
        el('div', { class: 'wizard__result' }, [
          el('span', { class: 'wizard__result-badge', text: 'Recommended route' }),
          el('h3', { text: outcome.title }),
          el('p', { text: outcome.text }),
          el(
            'dl',
            { class: 'wizard__result-answers' },
            answers.map((answer) =>
              el('div', {}, [
                el('dt', { text: answer.question }),
                el('dd', { text: answer.label }),
              ])
            )
          ),
          service
            ? el('p', { class: 'muted', style: 'margin-bottom:20px' }, [
                `Suggested consultation: ${service.name} · ${service.duration} minutes · ${service.price}`,
              ])
            : null,
          el('div', { class: 'wizard__result-actions' }, [
            el('button', {
              class: 'btn btn--primary btn--lg',
              type: 'button',
              text: 'Book this consultation',
              onclick: () => window.Booking?.startWith(serviceId),
            }),
            el('button', {
              class: 'btn btn--ghost',
              type: 'button',
              text: 'Start again',
              onclick: reset,
            }),
          ]),
        ])
      );
      $('.wizard__result h3', stage)?.setAttribute('tabindex', '-1');
      $('.wizard__result h3', stage)?.focus({ preventScroll: true });
    }

    function render() {
      if (step >= questions.length) renderResult();
      else renderQuestion();
      updateChrome();
    }

    function reset() {
      step = 0;
      answers.length = 0;
      render();
    }

    backBtn?.addEventListener('click', () => {
      if (step > 0) step -= 1;
      render();
    });
    restartBtn?.addEventListener('click', reset);

    render();
  })();

  /* ------------------------------------------------------------------ *
   * Booking flow: calendar, slots, multi-step form, submission
   * ------------------------------------------------------------------ */
  const Booking = (function booking() {
    const form = $('#bookingForm');
    if (!form) return {};

    const panels = $$('.booking__panel', form);
    const stepItems = $$('#bookingSteps li');
    const calGrid = $('#calGrid');
    const calTitle = $('#calTitle');
    const calPrev = $('#calPrev');
    const calNext = $('#calNext');
    const slotsList = $('#slotsList');
    const slotsTitle = $('#slotsTitle');
    const summaryStrip = $('#summaryStrip');
    const submitBtn = $('#bookingSubmit');
    const formError = $('#bookingFormError');
    const successPane = $('#bookingSuccess');

    const state = {
      step: 1,
      serviceId: '',
      date: '',
      time: '',
      month: null, // { year, month }
      monthCache: new Map(),
      dayCache: new Map(),
    };

    /* ---------- error display ---------- */
    function clearErrors() {
      $$('.field-error', form).forEach((node) => {
        node.classList.remove('is-visible');
        node.textContent = '';
      });
      $$('.has-error', form).forEach((node) => node.classList.remove('has-error'));
      formError?.classList.remove('is-visible');
      if (formError) formError.textContent = '';
    }

    function showFieldError(field, message) {
      const node = $(`.field-error[data-error-for="${field}"]`, form);
      if (node) {
        node.textContent = message;
        node.classList.add('is-visible');
        node.closest('.field')?.classList.add('has-error');
      }
      return node;
    }

    function showErrors(errors = {}, fallback = '') {
      clearErrors();
      let firstNode = null;
      for (const [field, message] of Object.entries(errors)) {
        const node = showFieldError(field, message);
        if (!firstNode) firstNode = node;
      }
      if (fallback && formError) {
        formError.textContent = fallback;
        formError.classList.add('is-visible');
      }
      // Jump to whichever panel holds the first problem.
      if (firstNode) {
        const panel = firstNode.closest('.booking__panel');
        const panelNo = panel ? Number(panel.dataset.panel) : state.step;
        if (panelNo && panelNo !== state.step) goToStep(panelNo, { silent: true });
        firstNode.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }

    /* ---------- step navigation ---------- */
    function goToStep(next, { silent = false } = {}) {
      state.step = next;
      panels.forEach((panel) =>
        panel.classList.toggle('is-active', Number(panel.dataset.panel) === next)
      );
      stepItems.forEach((item) => {
        const number = Number(item.dataset.step);
        item.classList.toggle('is-active', number === next);
        item.classList.toggle('is-done', number < next);
      });
      if (next === 3) renderSummary();
      if (!silent) {
        const anchor = $('#booking');
        if (anchor) {
          const top = anchor.getBoundingClientRect().top + window.scrollY - 84;
          window.scrollTo({ top, behavior: REDUCED_MOTION ? 'auto' : 'smooth' });
        }
      }
    }

    function validateStep(step) {
      clearErrors();
      if (step === 1) {
        if (!state.serviceId) {
          showFieldError('service_id', 'Please choose the service you need.');
          return false;
        }
        return true;
      }
      if (step === 2) {
        if (!state.date) {
          showFieldError('slot_date', 'Please choose a date for your consultation.');
          return false;
        }
        if (!state.time) {
          showFieldError('slot_time', 'Please choose a time slot.');
          return false;
        }
        return true;
      }
      return true;
    }

    form.addEventListener('click', (event) => {
      const nextBtn = event.target.closest('[data-next]');
      if (nextBtn) {
        const target = Number(nextBtn.dataset.next);
        if (validateStep(target - 1)) goToStep(target);
        return;
      }
      const prevBtn = event.target.closest('[data-prev]');
      if (prevBtn) goToStep(Number(prevBtn.dataset.prev));
    });

    // Let visitors click the step indicator to move backwards.
    stepItems.forEach((item) => {
      item.addEventListener('click', () => {
        const target = Number(item.dataset.step);
        if (target < state.step) goToStep(target);
      });
    });

    /* ---------- service selection ---------- */
    $$('input[name="service_id"]', form).forEach((input) => {
      input.addEventListener('change', () => {
        state.serviceId = input.value;
        clearErrors();
      });
    });

    /* ---------- summary chips on step 3 ---------- */
    function serviceName(id) {
      return (BOOT.services || []).find((s) => s.id === id)?.name || '';
    }

    function prettyDate(iso) {
      if (!iso) return '';
      const [y, m, d] = iso.split('-').map(Number);
      const date = new Date(Date.UTC(y, m - 1, d));
      return date.toLocaleDateString(undefined, {
        weekday: 'long',
        day: 'numeric',
        month: 'long',
        year: 'numeric',
        timeZone: 'UTC',
      });
    }

    function renderSummary() {
      if (!summaryStrip) return;
      const chips = [];
      if (state.serviceId) {
        chips.push(['📋', serviceName(state.serviceId)]);
      }
      if (state.date) chips.push(['📅', prettyDate(state.date)]);
      if (state.time) {
        chips.push(['🕑', `${state.time} ${BOOT.timezone || ''}`.trim()]);
      }
      summaryStrip.replaceChildren(
        ...chips.map(([icon, label]) =>
          el('span', { class: 'summary-chip' }, [
            el('span', { 'aria-hidden': 'true', text: icon }),
            el('span', { text: label }),
          ])
        )
      );
    }

    /* ---------- calendar ---------- */
    async function loadMonth(year, month) {
      const key = `${year}-${month}`;
      if (state.monthCache.has(key)) return state.monthCache.get(key);
      const { ok, data } = await api(
        `/api/availability/month?year=${year}&month=${month}`
      );
      if (!ok) {
        Toast.error(data.error || 'Could not load the calendar.');
        return null;
      }
      state.monthCache.set(key, data);
      return data;
    }

    async function renderMonth(year, month) {
      if (!calGrid) return;
      calGrid.setAttribute('aria-busy', 'true');
      const data = await loadMonth(year, month);
      calGrid.setAttribute('aria-busy', 'false');
      if (!data) return;

      state.month = { year: data.year, month: data.month };
      if (calTitle) calTitle.textContent = data.month_label;
      if (calPrev) calPrev.disabled = !data.can_go_prev;
      if (calNext) calNext.disabled = !data.can_go_next;

      const todayIso = new Date().toISOString().slice(0, 10);
      const cells = [];

      // Leading blanks so the 1st lands under the right weekday.
      for (let i = 0; i < data.first_weekday; i += 1) {
        cells.push(el('span', { class: 'cal-day cal-day--blank', 'aria-hidden': 'true' }));
      }

      data.days.forEach((day) => {
        const classes = ['cal-day', `cal-day--${day.status}`];
        if (day.date === todayIso) classes.push('cal-day--today');
        if (day.date === state.date) classes.push('is-selected');

        if (!day.selectable) {
          cells.push(
            el('span', {
              class: classes.join(' '),
              title: `${day.pretty} — ${
                day.status === 'full'
                  ? 'fully booked'
                  : day.status === 'closed'
                  ? 'closed'
                  : 'not available'
              }`,
              'aria-disabled': 'true',
              text: String(day.day_number),
            })
          );
          return;
        }

        cells.push(
          el('button', {
            class: classes.join(' '),
            type: 'button',
            title: `${day.pretty} — ${day.open_count} slot${
              day.open_count === 1 ? '' : 's'
            } free`,
            'aria-label': `${day.pretty}, ${day.open_count} slots available`,
            'data-date': day.date,
            text: String(day.day_number),
            onclick: () => selectDate(day.date),
          })
        );
      });

      calGrid.replaceChildren(...cells);
    }

    calPrev?.addEventListener('click', () => {
      if (!state.month) return;
      const { year, month } = state.month;
      const prev = month === 1 ? { year: year - 1, month: 12 } : { year, month: month - 1 };
      renderMonth(prev.year, prev.month);
    });

    calNext?.addEventListener('click', () => {
      if (!state.month) return;
      const { year, month } = state.month;
      const next = month === 12 ? { year: year + 1, month: 1 } : { year, month: month + 1 };
      renderMonth(next.year, next.month);
    });

    /* ---------- slots ---------- */
    async function loadDay(iso, { force = false } = {}) {
      if (!force && state.dayCache.has(iso)) return state.dayCache.get(iso);
      const { ok, data } = await api(`/api/availability?date=${iso}`);
      if (!ok || !data.day) {
        Toast.error(data.error || 'Could not load times for that date.');
        return null;
      }
      state.dayCache.set(iso, data.day);
      return data.day;
    }

    function renderSlots(day) {
      if (!slotsList) return;
      if (slotsTitle) slotsTitle.textContent = day.pretty || 'Available times';

      const available = (day.slots || []).filter((s) => s.available);
      if (!day.slots?.length || !available.length) {
        slotsList.replaceChildren(
          el('p', {
            class: 'slots__placeholder',
            text: day.is_open
              ? 'Every slot on this date is taken. Please pick another day.'
              : 'We are closed on this date. Please pick another day.',
          })
        );
        return;
      }

      slotsList.replaceChildren(
        ...day.slots.map((slot) => {
          const reason = {
            booked: 'Already booked',
            'too-soon': 'Too soon to book',
            unavailable: 'Not available',
            closed: 'Closed',
          }[slot.reason];
          return el(
            'button',
            {
              class: `slot-btn${slot.time === state.time ? ' is-selected' : ''}`,
              type: 'button',
              disabled: !slot.available,
              title: slot.available
                ? `${slot.time}–${slot.end}`
                : `${slot.time} — ${reason || 'unavailable'}`,
              'aria-pressed': String(slot.time === state.time),
              onclick: () => selectTime(slot.time),
            },
            [
              document.createTextNode(slot.time),
              slot.end ? el('small', { text: `to ${slot.end}` }) : null,
            ]
          );
        })
      );
    }

    async function selectDate(iso, { silent = false } = {}) {
      state.date = iso;
      state.time = '';
      clearErrors();

      $$('.cal-day', calGrid).forEach((node) =>
        node.classList.toggle('is-selected', node.dataset.date === iso)
      );

      if (slotsList) {
        slotsList.replaceChildren(
          el('p', { class: 'slots__placeholder', text: 'Loading times…' })
        );
      }
      const day = await loadDay(iso);
      if (day) renderSlots(day);
      if (!silent && window.innerWidth <= 900) {
        $('.slots')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
    }

    function selectTime(time) {
      state.time = time;
      clearErrors();
      $$('.slot-btn', slotsList).forEach((node) => {
        const active = node.textContent.startsWith(time);
        node.classList.toggle('is-selected', active);
        node.setAttribute('aria-pressed', String(active));
      });
      renderSummary();
    }

    /* ---------- quick slots in the hero ---------- */
    async function renderQuickSlots() {
      const host = $('#quickSlots');
      if (!host) return;
      const { ok, data } = await api('/api/availability?limit=3');
      host.dataset.loading = 'false';
      if (!ok || !Array.isArray(data.days) || !data.days.length) {
        host.replaceChildren(
          el('p', {
            class: 'slots__placeholder',
            text: 'No slots open right now — send us an enquiry and we will find you a time.',
          })
        );
        return;
      }
      host.replaceChildren(
        ...data.days.slice(0, 3).map((day) => {
          const first = day.slots.find((s) => s.available);
          return el(
            'button',
            {
              class: 'quick-slot',
              type: 'button',
              onclick: () => startWith(state.serviceId || '', day.date, first?.time),
            },
            [
              el('span', {}, [
                el('span', { class: 'quick-slot__day', text: day.weekday }),
                el('br'),
                el('span', {
                  class: 'quick-slot__meta',
                  text: `${day.pretty.replace(`${day.weekday} `, '')}${
                    first ? ` · from ${first.time}` : ''
                  }`,
                }),
              ]),
              el('span', {
                class: 'quick-slot__count',
                text: `${day.open_count} free`,
              }),
            ]
          );
        })
      );
    }

    $('#quickSlotsCta')?.addEventListener('click', () => startWith(''));

    /* ---------- deep entry points ---------- */
    async function startWith(serviceId, date, time) {
      if (successPane && !successPane.hidden) resetForm();

      if (serviceId) {
        const input = $(`input[name="service_id"][value="${serviceId}"]`, form);
        if (input) {
          input.checked = true;
          state.serviceId = serviceId;
        }
      }

      const target = serviceId ? (date && time ? 3 : 2) : 1;

      if (date) {
        // Make sure the calendar is showing the right month before selecting.
        const [year, month] = date.split('-').map(Number);
        if (!state.month || state.month.year !== year || state.month.month !== month) {
          await renderMonth(year, month);
        }
        await selectDate(date, { silent: true });
        if (time) selectTime(time);
      }

      goToStep(target);
      if (target === 1) {
        $('#serviceOptions input')?.focus({ preventScroll: true });
      }
    }

    $$('[data-book-service]').forEach((button) => {
      button.addEventListener('click', () => startWith(button.dataset.bookService));
    });

    /* ---------- character counter ---------- */
    const message = $('#message');
    const messageCount = $('#messageCount');
    message?.addEventListener('input', () => {
      if (messageCount) messageCount.textContent = String(message.value.length);
    });

    /* ---------- nationality suggestions ---------- */
    (function nationalities() {
      const list = $('#nationalityList');
      if (!list) return;
      const common = [
        'Algerian', 'Argentinian', 'Bangladeshi', 'Brazilian', 'British',
        'Canadian', 'Chinese', 'Colombian', 'Egyptian', 'Ethiopian', 'French',
        'German', 'Ghanaian', 'Indian', 'Indonesian', 'Iranian', 'Iraqi',
        'Italian', 'Japanese', 'Jordanian', 'Kazakh', 'Kenyan', 'Lebanese',
        'Malaysian', 'Mexican', 'Moldovan', 'Moroccan', 'Nepalese', 'Nigerian',
        'Pakistani', 'Filipino', 'Polish', 'Romanian', 'Saudi', 'Serbian',
        'South African', 'South Korean', 'Spanish', 'Sri Lankan', 'Sudanese',
        'Syrian', 'Tunisian', 'Turkish', 'Ugandan', 'American', 'Uzbek',
        'Vietnamese', 'Zimbabwean',
      ];
      list.replaceChildren(...common.map((name) => el('option', { value: name })));
    })();

    /* ---------- submission ---------- */
    function collect() {
      const data = Object.fromEntries(new FormData(form).entries());
      data.service_id = state.serviceId;
      data.slot_date = state.date;
      data.slot_time = state.time;
      data.consent = $('#consent')?.checked ? 'true' : '';
      return data;
    }

    function busy(on) {
      submitBtn?.classList.toggle('is-busy', on);
      if (submitBtn) submitBtn.disabled = on;
    }

    async function submit(event) {
      event.preventDefault();
      if (!validateStep(1) || !validateStep(2)) return;
      clearErrors();
      busy(true);

      const payload = collect();
      const { ok, status, data } = await api('/api/bookings', {
        method: 'POST',
        body: payload,
      });
      busy(false);

      if (ok && data.ok) {
        showSuccess(data);
        return;
      }

      // Slot was claimed while the visitor was filling the form.
      if (status === 409) {
        state.time = '';
        state.monthCache.clear();
        state.dayCache.delete(payload.slot_date);
        if (data.day) {
          state.dayCache.set(payload.slot_date, data.day);
          renderSlots(data.day);
        } else if (state.date) {
          const day = await loadDay(state.date, { force: true });
          if (day) renderSlots(day);
        }
        if (state.month) {
          state.monthCache.delete(`${state.month.year}-${state.month.month}`);
          renderMonth(state.month.year, state.month.month);
        }
        showErrors(data.errors || {}, data.error || 'That slot has just been taken.');
        Toast.error(data.error || 'That slot has just been taken. Please pick another.');
        goToStep(2, { silent: false });
        return;
      }

      if (status === 429) {
        const msg = data.error || 'Too many attempts. Please try again shortly.';
        if (formError) {
          formError.textContent = msg;
          formError.classList.add('is-visible');
        }
        Toast.error(msg);
        return;
      }

      showErrors(data.errors || {}, data.error || 'Something went wrong. Please try again.');
      Toast.error(data.error || 'Please check the highlighted fields.');
    }

    form.addEventListener('submit', submit);

    /* ---------- success view ---------- */
    function showSuccess(data) {
      const booking = data.booking || {};
      $('#successRef') && ($('#successRef').textContent = data.reference || '—');

      const detail = $('#successDetail');
      if (detail) {
        const rows = [
          ['Date', booking.pretty_date || prettyDate(booking.slot_date)],
          ['Time', `${booking.slot_time || ''} ${booking.timezone || ''}`.trim()],
          ['Service', booking.service_name || ''],
          ['Format', booking.mode_name || ''],
        ].filter(([, value]) => value);
        detail.replaceChildren(
          ...rows.map(([label, value]) =>
            el('div', {}, [el('dt', { text: label }), el('dd', { text: value })])
          )
        );
      }

      const note = $('#successNote');
      if (note) {
        note.textContent = booking.email
          ? `We've emailed the details to ${booking.email}. A consultant will confirm your slot shortly.`
          : 'A consultant will confirm your slot shortly.';
      }

      const link = $('#successThanksLink');
      if (link && data.redirect) link.href = data.redirect;

      form.hidden = true;
      $('#bookingSteps')?.setAttribute('hidden', '');
      if (successPane) {
        successPane.hidden = false;
        successPane.scrollIntoView({
          behavior: REDUCED_MOTION ? 'auto' : 'smooth',
          block: 'center',
        });
      }
      Toast.success(`Booking confirmed — reference ${data.reference}`, 8000);

      // The slot is gone now, so drop cached availability.
      state.monthCache.clear();
      state.dayCache.clear();
      renderQuickSlots();
    }

    function resetForm() {
      form.reset();
      form.hidden = false;
      $('#bookingSteps')?.removeAttribute('hidden');
      if (successPane) successPane.hidden = true;
      state.serviceId = '';
      state.date = '';
      state.time = '';
      if (messageCount) messageCount.textContent = '0';
      clearErrors();
      if (slotsList) {
        slotsList.replaceChildren(
          el('p', {
            class: 'slots__placeholder',
            text: 'Choose a highlighted date on the calendar to see open times.',
          })
        );
      }
      if (slotsTitle) slotsTitle.textContent = 'Select a date first';
      if (state.month) renderMonth(state.month.year, state.month.month);
      goToStep(1, { silent: true });
    }

    $('#bookAnother')?.addEventListener('click', () => {
      resetForm();
      $('#booking')?.scrollIntoView({
        behavior: REDUCED_MOTION ? 'auto' : 'smooth',
        block: 'start',
      });
    });

    /* ---------- init ---------- */
    const now = new Date();
    renderMonth(now.getFullYear(), now.getMonth() + 1);
    renderQuickSlots();

    return { startWith, resetForm };
  })();

  window.Booking = Booking;

  /* ------------------------------------------------------------------ *
   * Enquiry form
   * ------------------------------------------------------------------ */
  (function enquiry() {
    const form = $('#enquiryForm');
    if (!form) return;
    const submitBtn = $('#enquirySubmit');
    const formError = $('#enquiryFormError');

    function clearErrors() {
      $$('.field-error', form).forEach((node) => {
        node.classList.remove('is-visible');
        node.textContent = '';
      });
      $$('.has-error', form).forEach((node) => node.classList.remove('has-error'));
      formError?.classList.remove('is-visible');
      if (formError) formError.textContent = '';
    }

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      clearErrors();
      submitBtn?.classList.add('is-busy');
      if (submitBtn) submitBtn.disabled = true;

      const payload = Object.fromEntries(new FormData(form).entries());
      const { ok, data } = await api('/api/enquiries', {
        method: 'POST',
        body: payload,
      });

      submitBtn?.classList.remove('is-busy');
      if (submitBtn) submitBtn.disabled = false;

      if (ok && data.ok) {
        form.reset();
        Toast.success(
          data.reference
            ? `Message sent — reference ${data.reference}. We'll reply within one business day.`
            : 'Message sent. We will reply within one business day.',
          8000
        );
        return;
      }

      let firstNode = null;
      for (const [field, message] of Object.entries(data.errors || {})) {
        const node = $(`.field-error[data-error-for="${field}"]`, form);
        if (!node) continue;
        node.textContent = message;
        node.classList.add('is-visible');
        node.closest('.field')?.classList.add('has-error');
        if (!firstNode) firstNode = node;
      }
      const fallback = data.error || 'Could not send your message. Please try again.';
      if (formError) {
        formError.textContent = fallback;
        formError.classList.add('is-visible');
      }
      Toast.error(fallback);
      firstNode?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
  })();

  /* ------------------------------------------------------------------ *
   * Booking status lookup
   * ------------------------------------------------------------------ */
  (function lookup() {
    const form = $('#lookupForm');
    const input = $('#lookupRef');
    const result = $('#lookupResult');
    if (!form || !input || !result) return;

    const STATUS_COPY = {
      pending: 'Awaiting confirmation from a consultant.',
      confirmed: 'Confirmed — we look forward to speaking with you.',
      completed: 'This consultation has taken place.',
      cancelled: 'This booking was cancelled.',
      'no-show': 'Recorded as a missed appointment.',
    };

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const reference = input.value.trim().toUpperCase();
      if (!reference) {
        result.className = 'lookup__result lookup__result--error';
        result.textContent = 'Please enter your booking reference.';
        return;
      }

      result.className = 'lookup__result';
      result.textContent = 'Checking…';

      const { ok, data } = await api(
        `/api/bookings/${encodeURIComponent(reference)}`
      );

      if (!ok || !data.ok) {
        result.className = 'lookup__result lookup__result--error';
        result.textContent =
          data.error || 'No booking found with that reference.';
        return;
      }

      const booking = data.booking;
      result.className = 'lookup__result';
      result.replaceChildren(
        el('p', {}, [
          el('strong', { text: booking.status.toUpperCase() }),
          document.createTextNode(
            ` — ${STATUS_COPY[booking.status] || ''}`
          ),
        ]),
        el('dl', {}, [
          el('div', {}, [
            el('dt', { text: 'Reference' }),
            el('dd', { text: booking.reference }),
          ]),
          el('div', {}, [
            el('dt', { text: 'Date' }),
            el('dd', { text: booking.pretty_date }),
          ]),
          el('div', {}, [
            el('dt', { text: 'Time' }),
            el('dd', { text: `${booking.slot_time} ${booking.timezone}` }),
          ]),
          el('div', {}, [
            el('dt', { text: 'Service' }),
            el('dd', { text: booking.service_name }),
          ]),
          el('div', {}, [
            el('dt', { text: 'Format' }),
            el('dd', { text: booking.mode_name }),
          ]),
          el('div', {}, [
            el('dt', { text: 'Confirmation sent to' }),
            el('dd', { text: booking.email_masked }),
          ]),
        ])
      );
    });

    // Format as the user types: VC-XXXX-XXXX
    input.addEventListener('input', () => {
      const raw = input.value.toUpperCase().replace(/[^A-Z0-9]/g, '');
      const parts = [raw.slice(0, 2), raw.slice(2, 6), raw.slice(6, 10)].filter(Boolean);
      input.value = parts.join('-');
    });
  })();

  /* ------------------------------------------------------------------ *
   * Smooth in-page navigation for browsers without CSS smooth scroll
   * ------------------------------------------------------------------ */
  (function anchors() {
    if (REDUCED_MOTION) return;
    document.addEventListener('click', (event) => {
      const link = event.target.closest('a[href^="#"]');
      if (!link) return;
      const id = link.getAttribute('href').slice(1);
      if (!id) return;
      const target = document.getElementById(id);
      if (!target) return;
      event.preventDefault();
      const top = target.getBoundingClientRect().top + window.scrollY - 84;
      window.scrollTo({ top, behavior: 'smooth' });
      history.replaceState(null, '', `#${id}`);
    });
  })();
})();
