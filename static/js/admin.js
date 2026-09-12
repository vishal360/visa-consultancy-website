/* =========================================================================
   Consultant dashboard behaviour.
   Shared by the overview, bookings and enquiries pages — each page only wires
   up the widgets that are actually present in its markup.
   ========================================================================= */
(function () {
  'use strict';

  const BOOT = (() => {
    const node = document.getElementById('bootData');
    if (!node) return {};
    try {
      return JSON.parse(node.textContent);
    } catch (err) {
      console.error('Bad boot data', err);
      return {};
    }
  })();

  const CSRF = BOOT.csrfToken || '';
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  function el(tag, attrs = {}, children = []) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs)) {
      if (value === null || value === undefined || value === false) continue;
      if (key === 'class') node.className = value;
      else if (key === 'text') node.textContent = value;
      else if (key.startsWith('on') && typeof value === 'function') {
        node.addEventListener(key.slice(2).toLowerCase(), value);
      } else if (value === true) node.setAttribute(key, '');
      else node.setAttribute(key, String(value));
    }
    for (const child of [].concat(children)) {
      if (child === null || child === undefined || child === false) continue;
      node.append(child instanceof Node ? child : document.createTextNode(child));
    }
    return node;
  }

  function debounce(fn, wait = 320) {
    let timer;
    return (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => fn(...args), wait);
    };
  }

  /* ------------------------------------------------------------------ *
   * HTTP helpers
   * ------------------------------------------------------------------ */
  async function apiGet(url) {
    try {
      const res = await fetch(url, {
        headers: { Accept: 'application/json', 'X-Requested-With': 'fetch' },
      });
      const data = await res.json().catch(() => ({}));
      if (res.status === 401) {
        Toast.error('Your session expired. Redirecting to sign in…');
        setTimeout(() => (window.location.href = '/admin/login'), 1400);
      }
      return { ok: res.ok, status: res.status, data };
    } catch (err) {
      return { ok: false, status: 0, data: { error: 'Network problem.' } };
    }
  }

  /** POST as form-encoded, with the CSRF token attached. */
  async function apiPost(url, fields = {}) {
    const body = new URLSearchParams();
    for (const [key, value] of Object.entries(fields)) {
      body.set(key, value === true ? 'true' : value === false ? '' : String(value));
    }
    body.set('csrf_token', CSRF);
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/x-www-form-urlencoded',
          'X-CSRF-Token': CSRF,
          'X-Requested-With': 'fetch',
        },
        body: body.toString(),
      });
      const data = await res.json().catch(() => ({}));
      if (res.status === 401) {
        Toast.error('Your session expired. Redirecting to sign in…');
        setTimeout(() => (window.location.href = '/admin/login'), 1400);
      }
      return { ok: res.ok, status: res.status, data };
    } catch (err) {
      return { ok: false, status: 0, data: { error: 'Network problem.' } };
    }
  }

  /* ------------------------------------------------------------------ *
   * Toasts
   * ------------------------------------------------------------------ */
  const Toast = (() => {
    const host = $('#toasts');
    const ICONS = { success: '✓', error: '!', info: 'i' };
    function show(message, kind = 'info', ttl = 5000) {
      if (!host) {
        console.log(`[${kind}] ${message}`);
        return;
      }
      const node = el('div', { class: `toast toast--${kind}` }, [
        el('span', { class: 'toast__icon', 'aria-hidden': 'true', text: ICONS[kind] }),
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
   * Theme
   * ------------------------------------------------------------------ */
  (function theme() {
    const KEY = 'vc-theme';
    const root = document.documentElement;
    let stored = null;
    try {
      stored = localStorage.getItem(KEY);
    } catch (_) {}
    if (stored === 'light' || stored === 'dark') root.dataset.theme = stored;

    $('#themeToggle')?.addEventListener('click', () => {
      const next = root.dataset.theme === 'light' ? 'dark' : 'light';
      root.dataset.theme = next;
      try {
        localStorage.setItem(KEY, next);
      } catch (_) {}
    });
  })();

  /* ------------------------------------------------------------------ *
   * Formatting helpers
   * ------------------------------------------------------------------ */
  function fmtDateTime(iso) {
    if (!iso) return '—';
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return iso;
    return date.toLocaleString(undefined, {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  function prettyDate(iso) {
    if (!iso) return '—';
    const [y, m, d] = iso.split('-').map(Number);
    if (!y || !m || !d) return iso;
    return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString(undefined, {
      weekday: 'short',
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      timeZone: 'UTC',
    });
  }

  function initials(name) {
    return (name || '?')
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0].toUpperCase())
      .join('');
  }

  /* ------------------------------------------------------------------ *
   * Booking detail drawer
   * ------------------------------------------------------------------ */
  const Drawer = (function drawer() {
    const root = $('#drawer');
    if (!root) return { open: () => {} };

    const body = $('#drawerBody');
    const refLabel = $('#drawerRef');
    const title = $('#drawerTitle');
    const panel = $('.drawer__panel', root);
    let lastFocus = null;
    let currentId = null;

    function close() {
      root.hidden = true;
      document.body.style.overflow = '';
      lastFocus?.focus?.();
      currentId = null;
    }

    $$('[data-close-drawer]', root).forEach((node) =>
      node.addEventListener('click', close)
    );
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && !root.hidden) close();
    });

    async function open(bookingId) {
      lastFocus = document.activeElement;
      currentId = bookingId;
      root.hidden = false;
      document.body.style.overflow = 'hidden';
      body.replaceChildren(el('p', { class: 'table__loading', text: 'Loading…' }));
      panel?.focus();

      const { ok, data } = await apiGet(`/admin/api/bookings/${bookingId}`);
      if (!ok || !data.booking) {
        body.replaceChildren(
          el('p', { class: 'table__empty', text: data.error || 'Could not load this booking.' })
        );
        return;
      }
      render(data.booking, data.emails || []);
    }

    function render(booking, emails) {
      if (refLabel) refLabel.textContent = booking.reference;
      if (title) title.textContent = booking.full_name;

      const detail = (label, value, href) =>
        el('div', {}, [
          el('dt', { text: label }),
          el('dd', {}, [
            href ? el('a', { href, text: value }) : document.createTextNode(value || '—'),
          ]),
        ]);

      body.replaceChildren(
        // --- appointment ---
        el('section', { class: 'drawer-section' }, [
          el('h3', { class: 'drawer-section__title', text: 'Appointment' }),
          el('dl', { class: 'detail-list' }, [
            detail('Date', booking.pretty_date || prettyDate(booking.slot_date)),
            detail('Time', `${booking.slot_time} (${BOOT.timezone || ''})`),
            detail('Service', booking.service_name),
            detail('Format', booking.mode_name),
            detail('Applicants', String(booking.applicants || 1)),
            detail('Travel plan', booking.travel_timeline || '—'),
          ]),
        ]),

        // --- client ---
        el('section', { class: 'drawer-section' }, [
          el('h3', { class: 'drawer-section__title', text: 'Client' }),
          el('dl', { class: 'detail-list' }, [
            detail('Name', booking.full_name),
            detail('Email', booking.email, `mailto:${booking.email}`),
            detail('Phone', booking.phone, `tel:${booking.phone}`),
            detail('Nationality', booking.nationality || '—'),
            detail('Booked at', fmtDateTime(booking.created_at)),
            detail('Source', booking.source || 'website'),
          ]),
        ]),

        // --- their message ---
        el('section', { class: 'drawer-section' }, [
          el('h3', { class: 'drawer-section__title', text: 'Their message' }),
          el('div', {
            class: `detail-message${booking.message ? '' : ' detail-message--empty'}`,
            text: booking.message || 'No message provided.',
          }),
        ]),

        // --- status controls ---
        el('section', { class: 'drawer-section' }, [
          el('h3', { class: 'drawer-section__title', text: 'Status' }),
          el(
            'div',
            { class: 'status-buttons' },
            (BOOT.statuses || []).map((status) =>
              el('button', {
                class: `status-btn${status === booking.status ? ' is-current' : ''}`,
                type: 'button',
                text: status.replace('-', ' '),
                disabled: status === booking.status,
                onclick: () => setStatus(booking.id, status),
              })
            )
          ),
          el('label', { class: 'notify-row' }, [
            el('input', { type: 'checkbox', id: 'notifyClient', checked: true }),
            el('span', { text: 'Email the client about this change' }),
          ]),
        ]),

        // --- private notes ---
        el('section', { class: 'drawer-section' }, [
          el('h3', { class: 'drawer-section__title', text: 'Private notes' }),
          el('textarea', {
            class: 'notes-area',
            id: 'notesArea',
            placeholder: 'Case notes, documents still outstanding, quoted fee…',
            text: booking.admin_notes || '',
          }),
          el('div', { class: 'notes-foot' }, [
            el('small', { text: 'Only visible to consultants.' }),
            el('button', {
              class: 'btn btn--ghost btn--sm',
              type: 'button',
              text: 'Save notes',
              onclick: () => saveNotes(booking.id),
            }),
          ]),
        ]),

        // --- email history ---
        el('section', { class: 'drawer-section' }, [
          el('h3', { class: 'drawer-section__title', text: 'Emails for this booking' }),
          emails.length
            ? el(
                'ul',
                { class: 'email-log' },
                emails.map((entry) =>
                  el('li', {}, [
                    el('div', { class: 'email-log__top' }, [
                      el('span', { class: 'email-log__subject', text: entry.subject }),
                      el('span', {
                        class: `email-log__status email-log__status--${entry.status}`,
                        text: entry.status,
                      }),
                    ]),
                    el('span', {
                      class: 'email-log__meta',
                      text: `${entry.recipients} · ${fmtDateTime(entry.created_at)}`,
                    }),
                    entry.error
                      ? el('span', { class: 'email-log__meta', text: entry.error })
                      : null,
                    entry.outbox_file
                      ? el('span', { class: 'email-log__meta', text: entry.outbox_file })
                      : null,
                  ])
                )
              )
            : el('p', { class: 'card__note', text: 'No emails recorded yet.' }),
        ]),

        // --- danger zone ---
        el('section', { class: 'drawer-section' }, [
          el('h3', { class: 'drawer-section__title', text: 'Danger zone' }),
          el('div', { class: 'drawer-danger' }, [
            el('p', {
              text:
                'Deleting removes the record permanently. Prefer cancelling, ' +
                'which keeps the history and frees the slot.',
            }),
            el('button', {
              class: 'btn btn--danger btn--sm',
              type: 'button',
              text: 'Delete this booking',
              onclick: () => remove(booking.id, booking.reference),
            }),
          ]),
        ])
      );
    }

    async function setStatus(bookingId, status) {
      const notify = $('#notifyClient')?.checked ? 'true' : '';
      const { ok, data } = await apiPost(
        `/admin/api/bookings/${bookingId}/status`,
        { status, notify }
      );
      if (!ok) {
        Toast.error(data.error || 'Could not update the status.');
        return;
      }
      Toast.success(
        data.email_sent
          ? `Marked as ${status} — the client has been emailed.`
          : `Marked as ${status}.`
      );
      open(bookingId); // re-render with fresh data
      window.AdminList?.refresh();
      refreshStatsIfPresent();
    }

    async function saveNotes(bookingId) {
      const notes = $('#notesArea')?.value ?? '';
      const { ok, data } = await apiPost(
        `/admin/api/bookings/${bookingId}/notes`,
        { notes }
      );
      Toast[ok ? 'success' : 'error'](
        ok ? 'Notes saved.' : data.error || 'Could not save the notes.'
      );
    }

    async function remove(bookingId, reference) {
      if (
        !window.confirm(
          `Permanently delete booking ${reference}? This cannot be undone.`
        )
      ) {
        return;
      }
      const { ok, data } = await apiPost(`/admin/api/bookings/${bookingId}/delete`);
      if (!ok) {
        Toast.error(data.error || 'Could not delete the booking.');
        return;
      }
      Toast.success(`Deleted ${reference}.`);
      close();
      window.AdminList?.refresh();
      refreshStatsIfPresent();
    }

    return { open, close };
  })();

  // Any element with data-open-booking opens the drawer.
  document.addEventListener('click', (event) => {
    const trigger = event.target.closest('[data-open-booking]');
    if (!trigger) return;
    Drawer.open(trigger.dataset.openBooking);
  });

  /* ------------------------------------------------------------------ *
   * Live stat refresh (overview page)
   * ------------------------------------------------------------------ */
  async function refreshStatsIfPresent() {
    if (!$('.stat-grid')) return;
    const { ok, data } = await apiGet('/admin/api/stats');
    if (!ok || !data.stats) return;
    const stats = data.stats;
    const map = {
      today: stats.today,
      pending: stats.pending,
      confirmed: stats.confirmed,
      upcoming: stats.upcoming,
      enquiries: stats.new_enquiries,
      recent: stats.new_last_7_days,
    };
    for (const [key, value] of Object.entries(map)) {
      const node = $(`.stat-card--${key} .stat-card__value`);
      if (node) node.textContent = String(value);
    }
  }

  /* ------------------------------------------------------------------ *
   * Bookings list (bookings page)
   * ------------------------------------------------------------------ */
  (function bookingsList() {
    const tbody = $('#bookingRows');
    if (!tbody) return;

    const filters = $('#filters');
    const pager = $('#pager');
    const countLabel = $('#resultCount');
    const exportLink = $('#exportLink');
    let page = 1;

    // Seed the controls from whatever the server put in the boot payload.
    if (BOOT.initialQuery) $('#q').value = BOOT.initialQuery;
    if (BOOT.initialStatus && $('#statusFilter')) {
      $('#statusFilter').value = BOOT.initialStatus;
    }

    function params() {
      const search = new URLSearchParams();
      const q = $('#q')?.value.trim();
      if (q) search.set('q', q);
      const status = $('#statusFilter')?.value;
      if (status && status !== 'all') search.set('status', status);
      const service = $('#serviceFilter')?.value;
      if (service && service !== 'all') search.set('service', service);
      const from = $('#fromDate')?.value;
      if (from) search.set('from', from);
      const to = $('#toDate')?.value;
      if (to) search.set('to', to);
      const order = $('#orderBy')?.value;
      if (order) search.set('order', order);
      return search;
    }

    function syncExportLink(search) {
      if (exportLink) exportLink.href = `/admin/export.csv?${search.toString()}`;
    }

    async function load() {
      const search = params();
      syncExportLink(search);
      search.set('page', String(page));
      search.set('per_page', '25');

      tbody.replaceChildren(
        el('tr', {}, [
          el('td', { colspan: '7', class: 'table__loading', text: 'Loading…' }),
        ])
      );

      const { ok, data } = await apiGet(`/admin/api/bookings?${search.toString()}`);
      if (!ok) {
        tbody.replaceChildren(
          el('tr', {}, [
            el('td', {
              colspan: '7',
              class: 'table__empty',
              text: data.error || 'Could not load bookings.',
            }),
          ])
        );
        return;
      }

      const rows = data.bookings || [];
      if (countLabel) {
        countLabel.textContent = data.total
          ? `${data.total} booking${data.total === 1 ? '' : 's'} match your filters`
          : 'No bookings match your filters';
      }

      if (!rows.length) {
        tbody.replaceChildren(
          el('tr', {}, [
            el('td', { colspan: '7' }, [
              el('div', { class: 'empty' }, [
                el('p', { class: 'empty__icon', 'aria-hidden': 'true', text: '🔍' }),
                el('p', {}, [el('strong', { text: 'Nothing here.' })]),
                el('p', { text: 'Try widening your filters or clearing the search.' }),
              ]),
            ]),
          ])
        );
        renderPager(data);
        return;
      }

      tbody.replaceChildren(
        ...rows.map((booking) =>
          el(
            'tr',
            {
              class: booking.is_past ? 'is-past' : '',
              'data-booking-id': booking.id,
            },
            [
              el('td', {}, [el('span', { class: 'cell-ref', text: booking.reference })]),
              el('td', {}, [
                el('span', {
                  class: 'cell-date',
                  text: booking.pretty_date || prettyDate(booking.slot_date),
                }),
                el('span', { class: 'cell-time', text: booking.slot_time }),
              ]),
              el('td', {}, [
                el('strong', { text: booking.full_name }),
                el('span', { class: 'cell-sub', text: booking.email }),
                el('span', { class: 'cell-sub', text: booking.phone }),
              ]),
              el('td', {}, [
                booking.service_name,
                booking.applicants > 1
                  ? el('span', {
                      class: 'cell-sub',
                      text: `${booking.applicants} applicants`,
                    })
                  : null,
              ]),
              el('td', { text: booking.mode_name }),
              el('td', {}, [
                el('span', {
                  class: `badge badge--${booking.status}`,
                  text: booking.status,
                }),
              ]),
              el('td', { class: 'cell-actions' }, [
                el('button', {
                  class: 'btn-mini',
                  type: 'button',
                  'data-open-booking': booking.id,
                  text: 'Manage',
                }),
              ]),
            ]
          )
        )
      );
      renderPager(data);
    }

    function renderPager(data) {
      if (!pager) return;
      const pages = data.pages || 1;
      if (pages <= 1) {
        pager.replaceChildren();
        return;
      }
      const buttons = [];
      buttons.push(
        el('button', {
          type: 'button',
          text: '‹ Prev',
          disabled: page <= 1,
          onclick: () => {
            page -= 1;
            load();
          },
        })
      );

      // Show a compact window of page numbers around the current one.
      const window_ = 2;
      const start = Math.max(1, page - window_);
      const end = Math.min(pages, page + window_);
      if (start > 1) buttons.push(el('span', { class: 'pager__info', text: '…' }));
      for (let i = start; i <= end; i += 1) {
        buttons.push(
          el('button', {
            type: 'button',
            class: i === page ? 'is-current' : '',
            text: String(i),
            onclick: () => {
              page = i;
              load();
            },
          })
        );
      }
      if (end < pages) buttons.push(el('span', { class: 'pager__info', text: '…' }));

      buttons.push(
        el('button', {
          type: 'button',
          text: 'Next ›',
          disabled: page >= pages,
          onclick: () => {
            page += 1;
            load();
          },
        })
      );
      buttons.push(
        el('span', { class: 'pager__info', text: `Page ${page} of ${pages}` })
      );
      pager.replaceChildren(...buttons);
    }

    const reload = () => {
      page = 1;
      load();
    };
    $('#q')?.addEventListener('input', debounce(reload, 350));
    ['statusFilter', 'serviceFilter', 'fromDate', 'toDate', 'orderBy'].forEach((id) => {
      $(`#${id}`)?.addEventListener('change', reload);
    });
    filters?.addEventListener('submit', (event) => {
      event.preventDefault();
      reload();
    });
    filters?.addEventListener('reset', () => setTimeout(reload, 0));

    window.AdminList = { refresh: load };
    load();
  })();

  /* ------------------------------------------------------------------ *
   * Enquiries list (enquiries page)
   * ------------------------------------------------------------------ */
  (function enquiriesList() {
    const host = $('#enquiryList');
    if (!host) return;

    const filters = $('#filters');
    const pager = $('#pager');
    const countLabel = $('#resultCount');
    const STATUSES = BOOT.statuses || ['new', 'in-progress', 'answered', 'closed'];
    let page = 1;

    async function load() {
      const search = new URLSearchParams();
      const q = $('#q')?.value.trim();
      if (q) search.set('q', q);
      const status = $('#statusFilter')?.value;
      if (status && status !== 'all') search.set('status', status);
      search.set('page', String(page));
      search.set('per_page', '20');

      host.replaceChildren(
        el('p', { class: 'table__loading', text: 'Loading enquiries…' })
      );

      const { ok, data } = await apiGet(`/admin/api/enquiries?${search.toString()}`);
      if (!ok) {
        host.replaceChildren(
          el('p', {
            class: 'table__empty',
            text: data.error || 'Could not load enquiries.',
          })
        );
        return;
      }

      const rows = data.enquiries || [];
      if (countLabel) {
        countLabel.textContent = data.total
          ? `${data.total} enquir${data.total === 1 ? 'y' : 'ies'}`
          : 'No enquiries yet';
      }

      if (!rows.length) {
        host.replaceChildren(
          el('div', { class: 'empty' }, [
            el('p', { class: 'empty__icon', 'aria-hidden': 'true', text: '📭' }),
            el('p', {}, [el('strong', { text: 'No enquiries to show.' })]),
            el('p', {
              text: 'Messages sent from the website contact form land here.',
            }),
          ])
        );
        renderPager(data);
        return;
      }

      host.replaceChildren(
        ...rows.map((enquiry) =>
          el('article', { class: 'enquiry', 'data-enquiry-id': enquiry.id }, [
            el('div', { class: 'enquiry__head' }, [
              el('div', { class: 'enquiry__who' }, [
                el('span', {
                  class: 'enquiry__avatar',
                  'aria-hidden': 'true',
                  text: initials(enquiry.full_name),
                }),
                el('div', {}, [
                  el('p', { class: 'enquiry__name', text: enquiry.full_name }),
                  el('p', { class: 'enquiry__contact' }, [
                    el('a', {
                      href: `mailto:${enquiry.email}`,
                      text: enquiry.email,
                    }),
                    enquiry.phone ? ` · ${enquiry.phone}` : '',
                  ]),
                ]),
              ]),
              el('div', { class: 'enquiry__tags' }, [
                enquiry.topic
                  ? el('span', { class: 'enquiry__topic', text: enquiry.topic })
                  : null,
                el('span', {
                  class: `badge badge--${enquiry.status}`,
                  text: enquiry.status.replace('-', ' '),
                }),
                el('span', { class: 'enquiry__ref', text: enquiry.reference }),
              ]),
            ]),

            el('div', { class: 'enquiry__message', text: enquiry.message }),

            el('div', { class: 'enquiry__foot' }, [
              el('span', {
                class: 'enquiry__time',
                text: `Received ${fmtDateTime(enquiry.created_at)}`,
              }),
              el('div', { class: 'enquiry__actions' }, [
                el('a', {
                  class: 'btn-mini',
                  href: `mailto:${enquiry.email}?subject=Re: your enquiry (${enquiry.reference})`,
                  text: 'Reply by email',
                }),
                ...STATUSES.filter((s) => s !== enquiry.status).map((status) =>
                  el('button', {
                    class: 'btn-mini',
                    type: 'button',
                    text: `Mark ${status.replace('-', ' ')}`,
                    onclick: () => setStatus(enquiry.id, status),
                  })
                ),
              ]),
            ]),
          ])
        )
      );
      renderPager(data);
    }

    async function setStatus(enquiryId, status) {
      const { ok, data } = await apiPost(
        `/admin/api/enquiries/${enquiryId}/status`,
        { status }
      );
      if (!ok) {
        Toast.error(data.error || 'Could not update the enquiry.');
        return;
      }
      Toast.success(`Marked as ${status.replace('-', ' ')}.`);
      load();
    }

    function renderPager(data) {
      if (!pager) return;
      const pages = data.pages || 1;
      if (pages <= 1) {
        pager.replaceChildren();
        return;
      }
      pager.replaceChildren(
        el('button', {
          type: 'button',
          text: '‹ Prev',
          disabled: page <= 1,
          onclick: () => {
            page -= 1;
            load();
          },
        }),
        el('span', { class: 'pager__info', text: `Page ${page} of ${pages}` }),
        el('button', {
          type: 'button',
          text: 'Next ›',
          disabled: page >= pages,
          onclick: () => {
            page += 1;
            load();
          },
        })
      );
    }

    const reload = () => {
      page = 1;
      load();
    };
    $('#q')?.addEventListener('input', debounce(reload, 350));
    $('#statusFilter')?.addEventListener('change', reload);
    filters?.addEventListener('submit', (event) => {
      event.preventDefault();
      reload();
    });
    filters?.addEventListener('reset', () => setTimeout(reload, 0));

    load();
  })();

  /* ------------------------------------------------------------------ *
   * Blocked slots (overview page)
   * ------------------------------------------------------------------ */
  (function blockedSlots() {
    const form = $('#blockForm');
    const list = $('#blockedList');
    if (!form || !list) return;

    // Don't offer dates in the past.
    const dateInput = $('#blockDate');
    if (dateInput) dateInput.min = new Date().toISOString().slice(0, 10);

    function render(blocked) {
      if (!blocked.length) {
        list.replaceChildren(
          el('li', {}, [
            el('span', { class: 'card__note', text: 'Nothing blocked right now.' }),
          ])
        );
        return;
      }
      list.replaceChildren(
        ...blocked.map((entry) =>
          el('li', {}, [
            el('span', { class: 'blocked-list__meta' }, [
              el('strong', {
                text: `${prettyDate(entry.slot_date)}${
                  entry.slot_time ? ` · ${entry.slot_time}` : ' · all day'
                }`,
              }),
              entry.reason ? el('small', { text: entry.reason }) : null,
            ]),
            el('button', {
              class: 'blocked-list__remove',
              type: 'button',
              text: 'Unblock',
              onclick: async () => {
                const { ok, data } = await apiPost('/admin/api/slots/unblock', {
                  date: entry.slot_date,
                  time: entry.slot_time || '',
                });
                if (!ok) {
                  Toast.error(data.error || 'Could not unblock that time.');
                  return;
                }
                Toast.success('Time unblocked — the website can offer it again.');
                render(data.blocked || []);
              },
            }),
          ])
        )
      );
    }

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const date = $('#blockDate')?.value;
      if (!date) {
        Toast.error('Pick a date to block.');
        return;
      }
      const { ok, data } = await apiPost('/admin/api/slots/block', {
        date,
        time: $('#blockTime')?.value || '',
        reason: $('#blockReason')?.value || '',
      });
      if (!ok) {
        Toast.error(data.error || 'Could not block that time.');
        return;
      }
      Toast.success('Time blocked — the website will stop offering it.');
      form.reset();
      if (dateInput) dateInput.min = new Date().toISOString().slice(0, 10);
      render(data.blocked || []);
    });

    (async () => {
      const { ok, data } = await apiGet('/admin/api/slots');
      if (ok) render(data.blocked || []);
    })();
  })();

  /* ------------------------------------------------------------------ *
   * Test email button (overview page)
   * ------------------------------------------------------------------ */
  (function testEmail() {
    const button = $('#testEmailBtn');
    if (!button) return;
    button.addEventListener('click', async () => {
      const original = button.textContent;
      button.disabled = true;
      button.textContent = 'Sending…';
      const { ok, data } = await apiPost('/admin/api/test-email', {});
      button.disabled = false;
      button.textContent = original;

      const result = data.result || {};
      if (!ok || result.status === 'failed') {
        Toast.error(`Test email failed: ${result.error || data.error || 'unknown error'}`);
        return;
      }
      if (result.status === 'queued') {
        Toast.info(
          `Offline mode — message written to ${result.outbox_file}. Set SMTP_HOST to send real email.`,
          9000
        );
      } else {
        Toast.success('Test email sent. Check your inbox.');
      }
      refreshStatsIfPresent();
    });
  })();
})();
