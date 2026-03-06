"""Minimal HTML browse UI served at GET /."""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(include_in_schema=False)

_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Attendable</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f7; color: #1d1d1f; }

    /* ── Header ── */
    header {
      background: #1d1d1f; color: white;
      padding: 0.875rem 2rem;
      display: flex; justify-content: space-between; align-items: center;
    }
    .header-left { display: flex; align-items: center; gap: 0.75rem; }
    header h1 { font-size: 1.1rem; font-weight: 600; }
    .header-right { display: flex; align-items: center; gap: 0.75rem; }
    #runStatus { font-size: 0.8rem; color: #aaa; min-width: 180px; text-align: right; }
    #runStatus.running { color: #60a5fa; }
    #runStatus.ok  { color: #4ade80; }
    #runStatus.err { color: #f87171; }
    #nextRun { font-size: 0.78rem; color: #666; white-space: nowrap; }
    #btnRun {
      padding: 0.375rem 0.875rem; border: 1px solid #444; border-radius: 6px;
      background: transparent; color: white; cursor: pointer; font-size: 0.8rem; white-space: nowrap;
    }
    #btnRun:hover:not(:disabled) { background: #333; }
    #btnRun:disabled { opacity: 0.45; cursor: default; }

    /* ── Filters ── */
    .filters {
      background: white; border-bottom: 1px solid #e0e0e0;
      padding: 0.75rem 2rem; display: flex; gap: 0.625rem; align-items: center; flex-wrap: wrap;
    }
    .filters input[type=text], .filters input[type=number], .filters select {
      padding: 0.35rem 0.6rem; border: 1px solid #ccc; border-radius: 6px;
      font-size: 0.825rem; background: white;
    }
    #fSearch { width: 190px; }
    #fDist   { width: 145px; }
    .filters label { display: flex; align-items: center; gap: 0.35rem; font-size: 0.825rem; cursor: pointer; }
    .filter-sep { width: 1px; height: 20px; background: #e0e0e0; }
    .filters button {
      padding: 0.35rem 0.8rem; border: none; border-radius: 6px;
      cursor: pointer; font-size: 0.825rem;
    }
    #btnApply { background: #0071e3; color: white; }
    #btnApply:hover { background: #005ecb; }
    #btnReset { background: #e5e5ea; color: #333; }
    #btnReset:hover { background: #d8d8de; }

    /* View toggle */
    .view-toggle { display: flex; gap: 0; border: 1px solid #ccc; border-radius: 6px; overflow: hidden; margin-left: auto; }
    .toggle-btn { padding: 0.35rem 0.7rem; border: none; background: white; cursor: pointer; font-size: 0.8rem; color: #555; white-space: nowrap; }
    .toggle-btn.active { background: #0071e3; color: white; }
    .toggle-btn:hover:not(.active) { background: #f0f0f5; }

    #activeTagWrap { display: none; align-items: center; gap: 0.3rem; }
    #activeTagWrap.visible { display: flex; }
    .active-tag-chip {
      display: flex; align-items: center; gap: 0.3rem;
      background: #e8f4fd; color: #0071e3;
      padding: 0.2rem 0.55rem; border-radius: 100px; font-size: 0.78rem; font-weight: 500;
    }
    .active-tag-chip button {
      background: none; border: none; padding: 0; cursor: pointer;
      font-size: 0.9rem; line-height: 1; color: #0071e3; opacity: 0.7;
    }
    .active-tag-chip button:hover { opacity: 1; }

    /* ── Legend ── */
    .legend {
      background: #fffbee; border-bottom: 1px solid #f0e8c0;
      padding: 0.45rem 2rem;
      display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap;
      font-size: 0.775rem; color: #666;
    }
    .legend-label { font-weight: 600; color: #444; white-space: nowrap; }
    .legend-item { display: flex; align-items: center; gap: 0.3rem; white-space: nowrap; }
    .li-none     { color: #ccc; font-size: 1rem; }
    .li-int      { color: #0071e3; font-size: 1rem; }
    .li-att      { color: #1a8a4a; font-size: 1rem; }
    .li-noted    { color: #aaa; font-size: 1rem; }
    .legend-hint { color: #aaa; font-style: italic; margin-left: 0.25rem; }

    /* ── Page body (sidebar + main) ── */
    .page-body { display: flex; align-items: flex-start; }

    /* ── KPI Sidebar ── */
    .sidebar {
      width: 200px; flex-shrink: 0;
      position: sticky; top: 0; max-height: 100vh; overflow-y: auto;
      border-right: 1px solid #e0e0e0; background: white;
      padding: 0.875rem 0.75rem;
    }
    .main-col { flex: 1; min-width: 0; }
    .kpi-section { margin-bottom: 1rem; }
    .kpi-title {
      font-size: 0.68rem; font-weight: 700; text-transform: uppercase;
      letter-spacing: 0.06em; color: #aaa; margin-bottom: 0.4rem;
    }
    .kpi-row {
      display: flex; align-items: center; gap: 0.35rem;
      font-size: 0.76rem; color: #444; padding: 0.18rem 0;
    }
    .kpi-dot { font-size: 0.6rem; flex-shrink: 0; }
    .kpi-ok   .kpi-dot { color: #16a34a; }
    .kpi-warn .kpi-dot { color: #d97706; }
    .kpi-err  .kpi-dot { color: #dc2626; }
    .kpi-name { flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .kpi-count {
      font-size: 0.7rem; font-weight: 600; color: #888;
      background: #f0f0f5; border-radius: 10px;
      padding: 0.05rem 0.4rem; white-space: nowrap;
    }
    .kpi-meta { font-size: 0.72rem; color: #888; line-height: 1.5; }
    .kpi-sep { height: 1px; background: #f0f0f0; margin: 0.6rem 0; }

    /* ── Status bar ── */
    .status { padding: 0.5rem 1.25rem; font-size: 0.78rem; color: #999; }

    /* ── List view ── */
    .events {
      padding: 1rem 1.25rem;
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(290px, 1fr));
      gap: 0.875rem;
    }

    .card {
      background: white; border-radius: 10px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.07);
      padding: 1rem; cursor: pointer;
      transition: box-shadow 0.15s, transform 0.1s;
      text-decoration: none; color: inherit;
      display: flex; flex-direction: column;
      position: relative;
    }
    .card:hover { box-shadow: 0 4px 14px rgba(0,0,0,0.11); transform: translateY(-1px); }

    /* ── Top row: flag | title | dismiss ── */
    .card-top { display: flex; align-items: flex-start; gap: 0.4rem; margin-bottom: 0.45rem; }
    .card-title { flex: 1; font-weight: 600; font-size: 0.875rem; line-height: 1.35; }

    .card-flag-btn, .card-dismiss-btn {
      flex-shrink: 0; background: none; border: none; cursor: pointer;
      width: 26px; height: 26px; padding: 0; border-radius: 5px;
      display: flex; align-items: center; justify-content: center;
      font-size: 0.85rem; transition: background 0.12s, color 0.12s;
    }
    .card-flag-btn    { color: #ccc; }
    .card-dismiss-btn { color: #ccc; }
    .card-flag-btn:hover    { background: #fef9c3; color: #ca8a04; }
    .card-dismiss-btn:hover { background: #fee2e2; color: #dc2626; }
    .card-flag-btn.active    { color: #ca8a04; background: #fef9c3; }
    .card-dismiss-btn.active { color: #dc2626; background: #fee2e2; }

    .badges { display: flex; gap: 0.25rem; flex-wrap: wrap; margin-bottom: 0.45rem; }
    .badge { font-size: 0.66rem; font-weight: 500; padding: 0.16rem 0.45rem; border-radius: 100px; white-space: nowrap; }
    .b-virtual  { background: #e8f4fd; color: #0071e3; }
    .b-physical { background: #e8faf0; color: #1a8a4a; }
    .b-hybrid   { background: #fef3e8; color: #bf6900; }
    .b-free     { background: #f0fdf4; color: #15803d; }
    .b-paid     { background: #fef9ec; color: #b45309; }

    .card-meta { font-size: 0.78rem; color: #555; display: flex; flex-direction: column; gap: 0.25rem; }
    .meta-row  { display: flex; align-items: center; gap: 0.4rem; }
    .meta-icon { opacity: 0.4; flex-shrink: 0; }

    .card-tags { display: flex; flex-wrap: wrap; gap: 0.25rem; margin-top: 0.55rem; }
    .tag-chip {
      font-size: 0.65rem; padding: 0.15rem 0.45rem;
      background: #f0f0f5; color: #555; border-radius: 100px;
      cursor: pointer; border: none; font-family: inherit;
      transition: background 0.1s, color 0.1s;
    }
    .tag-chip:hover { background: #e8f4fd; color: #0071e3; }

    /* ── Footer row: source | attending ── */
    .card-footer {
      display: flex; justify-content: space-between; align-items: center;
      margin-top: auto; padding-top: 0.55rem;
    }
    .card-source { font-size: 0.66rem; color: #c0c0c0; text-transform: uppercase; letter-spacing: 0.05em; }
    .card-attend-btn {
      background: none; border: 1px solid #e0e0e0; cursor: pointer;
      border-radius: 5px; padding: 0.2rem 0.55rem;
      font-size: 0.7rem; font-family: inherit; color: #aaa;
      display: flex; align-items: center; gap: 0.3rem;
      transition: border-color 0.12s, color 0.12s, background 0.12s;
    }
    .card-attend-btn:hover { border-color: #1a8a4a; color: #1a8a4a; }
    .card-attend-btn.active { border-color: #1a8a4a; color: #1a8a4a; background: #f0fdf4; }

    .empty, .loading { text-align: center; padding: 4rem 2rem; color: #bbb; grid-column: 1/-1; font-size: 0.9rem; }

    .pagination {
      display: flex; justify-content: center; align-items: center;
      gap: 1rem; padding: 1.25rem; font-size: 0.825rem; color: #666;
    }
    .pagination button {
      padding: 0.35rem 0.7rem; border: 1px solid #ccc;
      border-radius: 6px; background: white; cursor: pointer; font-size: 0.825rem;
    }
    .pagination button:hover:not(:disabled) { background: #f0f0f5; }
    .pagination button:disabled { opacity: 0.35; cursor: default; }

    /* ── Calendar view ── */
    .cal-nav {
      display: flex; justify-content: space-between; align-items: center;
      padding: 1rem 1.25rem 0.75rem;
    }
    .cal-month-title { font-size: 1.05rem; font-weight: 600; }
    .cal-nav-btn {
      padding: 0.3rem 0.75rem; border: 1px solid #ccc; border-radius: 6px;
      background: white; cursor: pointer; font-size: 0.825rem;
    }
    .cal-nav-btn:hover { background: #f0f0f5; }

    .cal-grid {
      display: grid; grid-template-columns: repeat(7, 1fr);
      gap: 4px; padding: 0 1.25rem 0.5rem;
    }
    .cal-dow { text-align: center; font-size: 0.72rem; font-weight: 600; color: #888; padding: 0.4rem 0; }
    .cal-cell {
      min-height: 76px; background: white; border-radius: 8px;
      padding: 0.4rem 0.5rem; cursor: default;
      border: 1px solid #f0f0f0; transition: border-color 0.1s, background 0.1s;
    }
    .cal-cell.empty { background: transparent; border-color: transparent; }
    .cal-cell.has-events { cursor: pointer; }
    .cal-cell.has-events:hover { background: #f0f7ff; border-color: #93c5fd; }
    .cal-cell.selected { border-color: #0071e3 !important; background: #eef5ff !important; }
    .cal-cell.today .cal-day-num {
      background: #0071e3; color: white; border-radius: 50%;
      width: 22px; height: 22px; display: inline-flex; align-items: center; justify-content: center;
    }
    .cal-day-num { font-size: 0.8rem; font-weight: 500; color: #333; }
    .cal-dots { display: flex; flex-wrap: wrap; gap: 3px; margin-top: 5px; }
    .cal-dot {
      background: #0071e3; color: white; border-radius: 100px;
      font-size: 0.62rem; padding: 0.07rem 0.38rem; font-weight: 600; white-space: nowrap;
    }
    .cal-dot.dot-physical { background: #1a8a4a; }
    .cal-dot.dot-virtual  { background: #0071e3; }
    .cal-dot.dot-mixed    { background: #bf6900; }

    .cal-day-panel { padding: 0 1.25rem 2rem; }
    .cal-day-title {
      font-size: 0.95rem; font-weight: 600; color: #333;
      padding: 0.875rem 0 0.625rem; border-top: 1px solid #e0e0e0; margin-top: 0.25rem;
    }
    .cal-day-events {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(290px, 1fr));
      gap: 0.875rem;
    }

    /* ── This Week urgency strip ── */
    #thisWeekSection {
      background: white; border-bottom: 1px solid #e0e0e0;
    }
    .tw-header {
      display: flex; align-items: center; gap: 0.5rem;
      padding: 0.55rem 2rem 0.5rem; cursor: pointer; user-select: none;
    }
    .tw-header:hover { background: #f9f9fb; }
    .tw-title { font-size: 0.82rem; font-weight: 600; color: #333; }
    .tw-count { font-size: 0.75rem; color: #999; }
    .tw-toggle { margin-left: auto; background: none; border: none; cursor: pointer; color: #aaa; font-size: 0.85rem; padding: 0; }
    .tw-body {
      display: flex; gap: 0.5rem; flex-wrap: wrap;
      padding: 0 2rem 0.75rem; overflow-x: auto;
    }
    .tw-body.collapsed { display: none; }
    .uc {
      display: flex; flex-direction: column; gap: 0.2rem;
      padding: 0.45rem 0.7rem; border-radius: 8px; border: 1px solid #e0e0e0;
      text-decoration: none; color: inherit;
      min-width: 160px; max-width: 240px; flex-shrink: 0;
      transition: box-shadow 0.12s;
    }
    .uc:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
    .uc.uc-today    { border-color: #fca5a5; background: #fff5f5; }
    .uc.uc-tomorrow { border-color: #fcd34d; background: #fffbeb; }
    .uc.uc-soon     { border-color: #86efac; background: #f0fdf4; }
    .uc.uc-virtual  { border-color: #93c5fd; background: #eff6ff; opacity: 0.8; }
    .ub {
      font-size: 0.62rem; font-weight: 700; padding: 0.1rem 0.4rem;
      border-radius: 100px; display: inline-block; width: fit-content; white-space: nowrap;
    }
    .ub-today    { background: #ef4444; color: white; }
    .ub-tomorrow { background: #f59e0b; color: white; }
    .ub-soon     { background: #10b981; color: white; }
    .ub-virtual  { background: #3b82f6; color: white; }
    .uc-title {
      font-size: 0.78rem; font-weight: 600; line-height: 1.3;
      display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
    }
    .uc-meta { font-size: 0.68rem; color: #888; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

    /* ── Detail Drawer ── */
    #drawerOverlay {
      position: fixed; inset: 0; background: rgba(0,0,0,0.35); z-index: 100;
    }
    .drawer {
      position: fixed; top: 0; right: 0; bottom: 0;
      width: 500px; max-width: 100vw;
      background: white; z-index: 101;
      display: flex; flex-direction: column;
      box-shadow: -4px 0 28px rgba(0,0,0,0.15);
      transform: translateX(100%); transition: transform 0.25s cubic-bezier(.4,0,.2,1);
    }
    .drawer.open { transform: translateX(0); }
    .drawer-header {
      display: flex; align-items: flex-start; gap: 0.75rem;
      padding: 1.125rem 1.25rem 0.875rem; border-bottom: 1px solid #e0e0e0; flex-shrink: 0;
    }
    .drawer-title { flex: 1; font-size: 1rem; font-weight: 600; line-height: 1.4; color: #1d1d1f; }
    .drawer-close {
      flex-shrink: 0; background: none; border: none; cursor: pointer;
      color: #aaa; font-size: 1rem; padding: 0.2rem 0.4rem; border-radius: 4px; line-height: 1;
      transition: background 0.1s, color 0.1s;
    }
    .drawer-close:hover { background: #f0f0f5; color: #333; }
    .drawer-body { flex: 1; overflow-y: auto; padding: 1.25rem; }
    .drawer-section { margin-bottom: 1.25rem; }
    .drawer-section-title {
      font-size: 0.69rem; font-weight: 700; text-transform: uppercase;
      letter-spacing: 0.06em; color: #bbb; margin-bottom: 0.45rem;
    }
    .drawer-meta-row {
      display: flex; align-items: flex-start; gap: 0.5rem;
      font-size: 0.825rem; color: #444; margin-bottom: 0.3rem; line-height: 1.4;
    }
    .drawer-meta-icon { opacity: 0.4; flex-shrink: 0; margin-top: 1px; }
    .drawer-desc {
      font-size: 0.825rem; color: #444; line-height: 1.65;
      white-space: pre-wrap; word-break: break-word;
      max-height: 300px; overflow-y: auto;
    }
    .drawer-org {
      font-size: 0.8rem; color: #444; padding: 0.25rem 0;
      display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;
    }
    .drawer-org a { color: #0071e3; text-decoration: none; font-size: 0.75rem; }
    .drawer-org a:hover { text-decoration: underline; }
    .drawer-footer {
      padding: 0.875rem 1.25rem; border-top: 1px solid #e0e0e0;
      display: flex; align-items: center; gap: 0.5rem;
      flex-shrink: 0; flex-wrap: wrap;
    }
    .btn-visit {
      flex: 1; min-width: 120px; padding: 0.5rem 1rem;
      background: #0071e3; color: white; border: none; border-radius: 8px;
      cursor: pointer; font-size: 0.825rem; font-family: inherit;
      text-decoration: none; text-align: center; display: inline-block;
      transition: background 0.12s; white-space: nowrap;
    }
    .btn-visit:hover { background: #005ecb; }
    .drawer-actions { display: flex; gap: 0.35rem; }
    .drawer-action-btn {
      padding: 0.375rem 0.65rem; border: 1px solid #e0e0e0; border-radius: 6px;
      background: white; cursor: pointer; font-size: 0.75rem; font-family: inherit;
      display: flex; align-items: center; gap: 0.25rem; color: #666;
      transition: border-color 0.12s, color 0.12s, background 0.12s; white-space: nowrap;
    }
    .dab-flag:hover,    .dab-flag.active    { border-color: #ca8a04; color: #ca8a04; background: #fef9c3; }
    .dab-attend:hover,  .dab-attend.active  { border-color: #1a8a4a; color: #1a8a4a; background: #f0fdf4; }
    .dab-dismiss:hover, .dab-dismiss.active { border-color: #dc2626; color: #dc2626; background: #fee2e2; }

    /* ── Gear button ── */
    #btnGear {
      padding: 0.375rem 0.625rem; border: 1px solid #444; border-radius: 6px;
      background: transparent; color: white; cursor: pointer; font-size: 0.9rem;
    }
    #btnGear:hover { background: #333; }

    /* ── Setup Wizard Overlay ── */
    #setupOverlay {
      position: fixed; inset: 0; background: rgba(0,0,0,0.55);
      z-index: 200; display: flex; align-items: center; justify-content: center;
    }
    #setupCard {
      background: white; border-radius: 14px;
      width: 560px; max-width: calc(100vw - 2rem);
      max-height: 90vh; display: flex; flex-direction: column;
      box-shadow: 0 20px 60px rgba(0,0,0,0.25);
    }
    #setupCardHeader {
      padding: 1.25rem 1.5rem 0.75rem;
      border-bottom: 1px solid #f0f0f0;
      display: flex; align-items: flex-start; gap: 0.75rem; flex-shrink: 0;
    }
    #setupCardHeader h2 { flex: 1; font-size: 1.05rem; font-weight: 700; color: #1d1d1f; margin: 0; }
    #btnSetupClose {
      background: none; border: none; cursor: pointer; color: #aaa;
      font-size: 1.1rem; padding: 0.15rem 0.35rem; border-radius: 4px; line-height: 1;
    }
    #btnSetupClose:hover { background: #f0f0f5; color: #333; }
    .setup-steps {
      display: flex; align-items: center; gap: 0; padding: 0.75rem 1.5rem 0;
      flex-shrink: 0;
    }
    .setup-step {
      display: flex; align-items: center; gap: 0.35rem; font-size: 0.78rem;
      color: #bbb; font-weight: 500; white-space: nowrap;
    }
    .setup-step.active { color: #0071e3; }
    .setup-step.done   { color: #16a34a; }
    .setup-step-num {
      width: 20px; height: 20px; border-radius: 50%;
      background: #e5e5ea; color: #888;
      display: inline-flex; align-items: center; justify-content: center;
      font-size: 0.68rem; font-weight: 700; flex-shrink: 0;
    }
    .setup-step.active .setup-step-num { background: #0071e3; color: white; }
    .setup-step.done   .setup-step-num { background: #16a34a; color: white; }
    .setup-step-line { flex: 1; height: 1px; background: #e5e5ea; min-width: 12px; }
    #setupBody { flex: 1; overflow-y: auto; padding: 1.25rem 1.5rem; }
    #setupFooter {
      padding: 0.875rem 1.5rem; border-top: 1px solid #f0f0f0;
      display: flex; align-items: center; gap: 0.5rem; flex-shrink: 0; flex-wrap: wrap;
    }
    .setup-btn-next {
      padding: 0.45rem 1.1rem; background: #0071e3; color: white; border: none;
      border-radius: 8px; cursor: pointer; font-size: 0.85rem; font-family: inherit; font-weight: 500;
    }
    .setup-btn-next:hover { background: #005ecb; }
    .setup-btn-back {
      padding: 0.45rem 0.9rem; background: #e5e5ea; color: #333; border: none;
      border-radius: 8px; cursor: pointer; font-size: 0.85rem; font-family: inherit;
    }
    .setup-btn-back:hover { background: #d1d1d6; }
    .setup-btn-skip {
      margin-left: auto; background: none; border: none; cursor: pointer;
      color: #aaa; font-size: 0.78rem; font-family: inherit;
    }
    .setup-btn-skip:hover { color: #666; text-decoration: underline; }
    .setup-field-label {
      display: block; font-size: 0.8rem; font-weight: 600; color: #333;
      margin-bottom: 0.3rem; margin-top: 0.85rem;
    }
    .setup-field-label:first-child { margin-top: 0; }
    .setup-input, .setup-select {
      width: 100%; padding: 0.45rem 0.7rem;
      border: 1px solid #ccc; border-radius: 8px;
      font-size: 0.85rem; font-family: inherit; background: white;
    }
    .setup-input:focus, .setup-select:focus { outline: none; border-color: #0071e3; }
    .setup-hint { font-size: 0.75rem; color: #888; margin-top: 0.25rem; }
    .provider-pills { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.5rem; }
    .provider-pill {
      padding: 0.4rem 0.8rem; border: 1.5px solid #e0e0e0; border-radius: 8px;
      background: white; cursor: pointer; font-size: 0.8rem; font-family: inherit;
      display: flex; align-items: center; gap: 0.4rem; color: #444;
      transition: border-color 0.12s, background 0.12s;
    }
    .provider-pill:hover { border-color: #93c5fd; }
    .provider-pill.active { border-color: #0071e3; background: #eef5ff; color: #0071e3; }
    .cost-badge {
      font-size: 0.65rem; font-weight: 600; padding: 0.1rem 0.35rem;
      border-radius: 100px; white-space: nowrap;
    }
    .cost-free { background: #dcfce7; color: #15803d; }
    .cost-paid { background: #fef3c7; color: #b45309; }
    .cost-mixed { background: #ede9fe; color: #7c3aed; }
    .provider-detail { margin-top: 0.85rem; }
    .setup-link { font-size: 0.75rem; color: #0071e3; }
    .setup-link:hover { text-decoration: underline; }
    .source-check-row {
      display: flex; align-items: flex-start; gap: 0.6rem;
      padding: 0.6rem 0.75rem; border: 1px solid #e5e5ea; border-radius: 8px;
      margin-bottom: 0.5rem; cursor: pointer;
    }
    .source-check-row:hover { border-color: #93c5fd; background: #f8fbff; }
    .source-check-row input { margin-top: 2px; flex-shrink: 0; }
    .source-name { font-size: 0.85rem; font-weight: 600; color: #1d1d1f; }
    .source-desc { font-size: 0.78rem; color: #666; margin-top: 0.15rem; }
    .done-icon { font-size: 2.5rem; text-align: center; margin-bottom: 0.5rem; }
    .done-title { font-size: 1.1rem; font-weight: 700; text-align: center; margin-bottom: 0.5rem; }
    .done-sub { font-size: 0.85rem; color: #666; text-align: center; margin-bottom: 1rem; }
    .backup-row {
      display: flex; gap: 0.75rem; justify-content: center; margin-top: 1rem;
      padding-top: 1rem; border-top: 1px solid #f0f0f0;
    }
    .backup-btn {
      padding: 0.4rem 0.85rem; border: 1px solid #ccc; border-radius: 8px;
      background: white; cursor: pointer; font-size: 0.8rem; font-family: inherit;
      display: flex; align-items: center; gap: 0.35rem; color: #444;
    }
    .backup-btn:hover { border-color: #0071e3; color: #0071e3; }
    #restoreFileInput { display: none; }
    #setupMsg { font-size: 0.78rem; text-align: center; margin-top: 0.5rem; min-height: 1em; }
    #setupMsg.ok  { color: #16a34a; }
    #setupMsg.err { color: #dc2626; }

    /* ── Tags button ── */
    #tagsPopoutBtn {
      padding: 0.35rem 0.7rem; border: 1px solid #ccc; border-radius: 6px;
      background: white; cursor: pointer; font-size: 0.825rem; white-space: nowrap;
    }
    #tagsPopoutBtn:hover { border-color: #93c5fd; }
    #tagsPopoutBtn.has-active { background: #e8f4fd; color: #0071e3; border-color: #93c5fd; }

    /* ── Tags popout ── */
    #tagsPopout {
      position: fixed; z-index: 150;
      background: white; border: 1px solid #e0e0e0; border-radius: 10px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.14);
      width: 280px; max-height: 420px; display: flex; flex-direction: column;
      overflow: hidden;
    }
    .tp-search { padding: 0.5rem 0.6rem; border-bottom: 1px solid #f0f0f0; flex-shrink: 0; }
    .tp-search input {
      width: 100%; padding: 0.3rem 0.55rem; border: 1px solid #ccc;
      border-radius: 6px; font-size: 0.8rem; font-family: inherit;
    }
    .tp-list { flex: 1; overflow-y: auto; padding: 0.2rem 0; min-height: 0; }
    .tp-tag {
      display: flex; align-items: center; gap: 0.4rem;
      padding: 0.3rem 0.75rem; cursor: pointer; font-size: 0.8rem; color: #333;
      user-select: none;
    }
    .tp-tag:hover { background: #f5f5f7; }
    .tp-tag.active { color: #0071e3; background: #eef5ff; }
    .tp-count {
      margin-left: auto; font-size: 0.7rem; color: #999;
      background: #f0f0f5; border-radius: 10px; padding: 0.05rem 0.4rem;
    }
    .tp-zero-toggle {
      font-size: 0.75rem; color: #bbb; padding: 0.3rem 0.75rem;
      cursor: pointer; flex-shrink: 0; user-select: none;
    }
    .tp-zero-toggle:hover { color: #888; }
    .tp-zero-list { border-top: 1px solid #f5f5f5; padding: 0.2rem 0; flex-shrink: 0; }
    .tp-zero-item {
      display: flex; align-items: center; gap: 0.35rem;
      padding: 0.25rem 0.75rem; font-size: 0.78rem; color: #bbb; cursor: pointer;
    }
    .tp-zero-item:hover { color: #888; }
    .tp-zero-item.kw-pending { color: #999; cursor: default; }
    .tp-add {
      padding: 0.5rem 0.6rem; border-top: 1px solid #f0f0f0;
      display: flex; gap: 0.4rem; flex-shrink: 0;
    }
    .tp-add input {
      flex: 1; padding: 0.3rem 0.5rem; border: 1px solid #ccc;
      border-radius: 6px; font-size: 0.78rem; font-family: inherit;
    }
    .tp-add-btn {
      padding: 0.3rem 0.65rem; background: #0071e3; color: white;
      border: none; border-radius: 6px; cursor: pointer; font-size: 0.85rem;
    }

    /* ── Welcome Banner ── */
    #welcomeBanner {
      background: #eef5ff; border-bottom: 1px solid #bfdbfe;
      padding: 0.55rem 2rem; display: flex; align-items: center; gap: 0.75rem;
      font-size: 0.82rem; color: #1d4ed8;
    }
    #welcomeBanner span { flex: 1; }
    #welcomeBanner button { padding: 0.3rem 0.7rem; border: 1px solid #93c5fd; border-radius: 6px; background: white; cursor: pointer; color: #1d4ed8; font-size: 0.8rem; font-family: inherit; }
    #welcomeBanner button:last-child { border: none; background: none; color: #60a5fa; font-size: 1rem; padding: 0 0.25rem; }

    /* ── Settings Panel ── */
    #settingsOverlay {
      position: fixed; inset: 0; background: rgba(0,0,0,0.55);
      z-index: 200; display: flex; align-items: center; justify-content: center;
    }
    #settingsCard {
      background: white; border-radius: 14px;
      width: 560px; max-width: calc(100vw - 2rem);
      max-height: 90vh; display: flex; flex-direction: column;
      box-shadow: 0 20px 60px rgba(0,0,0,0.25);
    }
    #settingsCardHeader {
      padding: 1.25rem 1.5rem 0.875rem; border-bottom: 1px solid #f0f0f0;
      display: flex; align-items: center; gap: 0.75rem; flex-shrink: 0;
    }
    #settingsCardHeader h2 { flex:1; font-size:1.05rem; font-weight:700; color:#1d1d1f; margin:0; }
    #settingsCardHeader button { background:none; border:none; cursor:pointer; color:#aaa; font-size:1.1rem; padding:.15rem .35rem; border-radius:4px; }
    #settingsCardHeader button:hover { background:#f0f0f5; color:#333; }
    #settingsBody { flex:1; overflow-y:auto; padding:1.25rem 1.5rem; }
    #settingsFooter { padding:.875rem 1.5rem; border-top:1px solid #f0f0f0; display:flex; align-items:center; gap:.5rem; flex-shrink:0; flex-wrap:wrap; }
    .sett-section { margin-bottom:1.25rem; }
    .sett-section-title { font-size:.72rem; font-weight:700; text-transform:uppercase; letter-spacing:.06em; color:#aaa; margin-bottom:.6rem; }
    .sett-row { display:flex; align-items:center; gap:.5rem; margin-bottom:.5rem; flex-wrap:wrap; }
    .sett-row label { font-size:.82rem; color:#444; min-width:90px; }
    .sett-hint { font-size:.72rem; color:#aaa; margin-top:.15rem; margin-bottom:.5rem; }

    /* ── iCal Modal ── */
    #icalModal {
      position: fixed; inset: 0; background: rgba(0,0,0,0.4); z-index: 250;
      display: flex; align-items: center; justify-content: center;
    }
    #icalCard {
      background: white; border-radius: 12px; padding: 1.25rem 1.5rem;
      width: 320px; max-width: calc(100vw - 2rem);
      box-shadow: 0 16px 48px rgba(0,0,0,0.2);
    }

    /* ── Wizard tabs ── */
    .wizard-tabs { display:flex; border-bottom:1px solid #e5e5ea; margin-bottom:.875rem; }
    .wizard-tab { padding:.4rem .9rem; border:none; background:none; cursor:pointer; font-size:.82rem; color:#666; border-bottom:2px solid transparent; margin-bottom:-1px; font-family:inherit; }
    .wizard-tab.active { color:#0071e3; border-bottom-color:#0071e3; font-weight:600; }

    /* ── Keyword chips ── */
    .kw-tag-wrap { display:flex; flex-wrap:wrap; gap:.35rem; min-height:28px; margin-bottom:.4rem; padding:.25rem 0; }
    .kw-chip { display:flex; align-items:center; gap:.25rem; background:#f0f0f5; border-radius:100px; padding:.15rem .5rem; font-size:.75rem; color:#444; }
    .kw-chip-rm { background:none; border:none; cursor:pointer; color:#aaa; font-size:.9rem; line-height:1; padding:0; }
    .kw-chip-rm:hover { color:#dc2626; }
    .kw-add-row { display:flex; gap:.4rem; align-items:center; margin-bottom:.5rem; }
    .kw-add-row .setup-input { flex:1; }
    .kw-add-btn { padding:.4rem .7rem; background:#0071e3; color:white; border:none; border-radius:8px; cursor:pointer; font-size:.85rem; white-space:nowrap; }

    /* ── Test connection ── */
    .test-conn-btn { margin-top:.5rem; padding:.3rem .75rem; border:1px solid #ccc; border-radius:6px; background:white; cursor:pointer; font-size:.78rem; font-family:inherit; display:inline-flex; align-items:center; gap:.3rem; }
    .test-conn-btn:hover { border-color:#0071e3; color:#0071e3; }
    .test-conn-result { font-size:.78rem; vertical-align:middle; margin-left:.35rem; }
    .test-conn-result.ok  { color:#16a34a; }
    .test-conn-result.err { color:#dc2626; }
  </style>
</head>
<body>

<header>
  <div class="header-left">
    <svg width="28" height="29" viewBox="0 0 40 42" fill="none" xmlns="http://www.w3.org/2000/svg" style="flex-shrink:0">
      <defs>
        <linearGradient id="n-header" x1="0" y1="2" x2="40" y2="42" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stop-color="#6366f1"/>
          <stop offset="100%" stop-color="#7c3aed"/>
        </linearGradient>
        <linearGradient id="n-dot" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="#fbbf24"/>
          <stop offset="100%" stop-color="#f97316"/>
        </linearGradient>
      </defs>
      <rect x="0" y="2" width="40" height="40" rx="9" fill="white" stroke="#e2e5ef" stroke-width="1.5"/>
      <rect x="0" y="2" width="40" height="14" rx="9" fill="url(#n-header)"/>
      <rect x="0" y="10" width="40" height="6" fill="url(#n-header)"/>
      <rect x="10" y="0" width="4" height="8" rx="2" fill="#818cf8"/>
      <rect x="26" y="0" width="4" height="8" rx="2" fill="#818cf8"/>
      <rect x="6"  y="22" width="5" height="5" rx="1.5" fill="#dde2ef"/>
      <rect x="14" y="22" width="5" height="5" rx="1.5" fill="#dde2ef"/>
      <rect x="22" y="22" width="5" height="5" rx="1.5" fill="#dde2ef"/>
      <rect x="30" y="22" width="5" height="5" rx="1.5" fill="#dde2ef"/>
      <rect x="6"  y="30" width="5" height="5" rx="1.5" fill="#dde2ef"/>
      <rect x="14" y="30" width="5" height="5" rx="1.5" fill="#dde2ef"/>
      <rect x="22" y="30" width="5" height="5" rx="1.5" fill="#dde2ef"/>
      <rect x="30" y="30" width="5" height="5" rx="1.5" fill="url(#n-dot)"/>
    </svg>
    <h1>Attendable</h1>
  </div>
  <div class="header-right">
    <span id="nextRun"></span>
    <span id="runStatus"></span>
    <button id="btnGear" onclick="showSettings()" title="Settings">⚙</button>
    <button id="btnRun" onclick="triggerRun()">Run Pipeline</button>
  </div>
</header>

<div id="welcomeBanner" style="display:none">
  <span>👋 Welcome to Attendable! Run the setup wizard to configure your location and API keys.</span>
  <button onclick="startWizardFromBanner()">Start Setup →</button>
  <button onclick="dismissBanner()" title="Dismiss">✕</button>
</div>

<div class="filters">
  <input type="text" id="fSearch" placeholder="Search events…">
  <select id="fSource">
    <option value="">All sources</option>
    <option value="luma">Luma</option>
    <option value="eventbrite">Eventbrite</option>
    <option value="meetup">Meetup</option>
    <option value="web_search">Web Search</option>
  </select>
  <select id="fType">
    <option value="">All types</option>
    <option value="physical">Physical</option>
    <option value="virtual">Virtual</option>
    <option value="hybrid">Hybrid</option>
  </select>
  <input type="number" id="fDist" placeholder="Max distance (mi)" min="1" max="500">
  <div class="filter-sep"></div>
  <label><input type="checkbox" id="fUpcoming" checked> Upcoming only</label>
  <label><input type="checkbox" id="fFree"> Free only</label>
  <label><input type="checkbox" id="fHideNoted" checked> Hide noted</label>
  <button id="tagsPopoutBtn" onclick="toggleTagsPopout(event)">🏷 Tags</button>
  <div id="activeTagWrap">
    <div class="active-tag-chip">
      <span id="activeTagLabel"></span>
      <button onclick="clearTag()" title="Remove tag filter">×</button>
    </div>
  </div>
  <div class="view-toggle">
    <button id="btnList" class="toggle-btn active" onclick="setView('list')">☰ List</button>
    <button id="btnCal"  class="toggle-btn"        onclick="setView('calendar')">📅 Calendar</button>
  </div>
  <button id="btnIcal" onclick="showIcalModal()" title="Export to calendar app"
     style="font-size:.78rem;color:#666;padding:0.3rem 0.5rem;
            border:1px solid #ccc;border-radius:6px;white-space:nowrap;background:white;cursor:pointer;font-family:inherit">📅 .ics</button>
  <button id="btnApply" onclick="applyFilters()">Apply</button>
  <button id="btnReset" onclick="resetFilters()">Reset</button>
</div>

<!-- Status legend — always visible below the filter bar -->
<div class="legend">
  <span class="legend-label">Card actions:</span>
  <span class="legend-item"><span class="li-int">🚩</span> Flag for review <em>(top-left)</em></span>
  <span class="legend-item"><span class="li-noted">✕</span> Dismiss / ignore <em>(top-right — hidden from default view)</em></span>
  <span class="legend-item"><span class="li-att">☑</span> Mark attending <em>(bottom-right)</em></span>
  <span class="legend-hint">— Click again to undo any action.</span>
</div>

<!-- This Week urgency strip (hidden until events load) -->
<div id="thisWeekSection" style="display:none">
  <div class="tw-header" onclick="toggleThisWeek()">
    <span class="tw-title">⚡ This Week</span>
    <span id="twCount" class="tw-count"></span>
    <button class="tw-toggle" id="twToggleBtn">▾</button>
  </div>
  <div id="twBody" class="tw-body"></div>
</div>

<div class="page-body">
  <!-- KPI Sidebar -->
  <aside class="sidebar" id="kpiSidebar">
    <div class="kpi-section">
      <div class="kpi-title">Last Run</div>
      <div class="kpi-meta" id="kpiRunAt">—</div>
      <div class="kpi-meta" id="kpiRunSummary"></div>
    </div>
    <div class="kpi-sep"></div>
    <div class="kpi-section">
      <div class="kpi-title">Sources</div>
      <div id="kpiSources"><div class="kpi-meta">No data yet</div></div>
    </div>
    <div class="kpi-sep"></div>
    <div class="kpi-section">
      <div class="kpi-title">API Keys</div>
      <div id="kpiApiKeys"><div class="kpi-meta">Loading…</div></div>
    </div>
  </aside>

  <!-- Main content -->
  <div class="main-col">
    <div class="status" id="status">&nbsp;</div>
    <div id="mainContent">
      <div class="events" id="events"><div class="loading">Loading events…</div></div>
    </div>
    <div class="pagination" id="pagination"></div>
  </div>
</div>

<!-- Tags Popout -->
<div id="tagsPopout" style="display:none">
  <div class="tp-search">
    <input type="text" id="tpSearch" placeholder="Search tags…" oninput="renderTagsPopout()">
  </div>
  <div class="tp-list" id="tpList"></div>
  <div class="tp-zero-toggle" id="tpZeroToggle" style="display:none" onclick="toggleZeroTags()"></div>
  <div class="tp-zero-list" id="tpZeroList" style="display:none"></div>
  <div class="tp-add">
    <input type="text" id="tpAddInput" placeholder="Add search term…"
           onkeydown="if(event.key==='Enter')addUserKeyword()">
    <button class="tp-add-btn" onclick="addUserKeyword()">+</button>
  </div>
</div>

<!-- iCal Export Modal -->
<div id="icalModal" style="display:none" onclick="if(event.target===this)closeIcalModal()">
  <div id="icalCard">
    <div style="font-weight:600;font-size:.9rem;margin-bottom:.75rem">📅 Export to Calendar</div>
    <p style="font-size:.78rem;color:#666;margin-bottom:.6rem">Include events:</p>
    <label style="display:flex;align-items:center;gap:.5rem;font-size:.82rem;margin-bottom:.4rem">
      <input type="radio" name="icalFilter" id="icalAll" value="all" checked> All upcoming
    </label>
    <label style="display:flex;align-items:center;gap:.5rem;font-size:.82rem;margin-bottom:.4rem">
      <input type="radio" name="icalFilter" id="icalInterested" value="interested"> 🚩 Flagged (interested)
    </label>
    <label style="display:flex;align-items:center;gap:.5rem;font-size:.82rem;margin-bottom:.4rem">
      <input type="radio" name="icalFilter" id="icalAttending" value="attending"> ☑ Attending
    </label>
    <label style="display:flex;align-items:center;gap:.5rem;font-size:.82rem;margin-bottom:.75rem">
      <input type="radio" name="icalFilter" id="icalBoth" value="interested,attending"> 🚩 + ☑ Flagged &amp; Attending
    </label>
    <div style="display:flex;gap:.5rem;justify-content:flex-end">
      <button onclick="closeIcalModal()" class="setup-btn-back" type="button">Cancel</button>
      <button onclick="doIcalExport()" class="setup-btn-next" type="button">Export .ics</button>
    </div>
  </div>
</div>

<!-- Settings Panel Overlay -->
<div id="settingsOverlay" style="display:none" onclick="handleSettingsOverlayClick(event)">
  <div id="settingsCard" onclick="event.stopPropagation()">
    <div id="settingsCardHeader">
      <h2>⚙ Settings</h2>
      <button onclick="closeSettings()" title="Close">✕</button>
    </div>
    <div id="settingsBody"></div>
    <div id="settingsFooter">
      <button class="setup-btn-back" onclick="closeSettings();showSetupWizard()">Run Setup Wizard</button>
      <span style="flex:1"></span>
      <span id="settingsMsg" style="font-size:.78rem"></span>
      <button class="setup-btn-next" onclick="saveSettings()">Save Settings</button>
    </div>
  </div>
</div>

<!-- Setup Wizard Overlay -->
<div id="setupOverlay" style="display:none" onclick="handleOverlayClick(event)">
  <div id="setupCard" onclick="event.stopPropagation()">
    <div id="setupCardHeader">
      <h2 id="setupCardTitle">Welcome to Attendable</h2>
      <button id="btnSetupClose" onclick="closeSetupWizard()" style="display:none" title="Close">✕</button>
    </div>
    <!-- Step indicator -->
    <div class="setup-steps" id="setupSteps">
      <div class="setup-step active" id="stepInd1"><span class="setup-step-num">1</span> Location</div>
      <div class="setup-step-line"></div>
      <div class="setup-step" id="stepInd2"><span class="setup-step-num">2</span> Sources</div>
      <div class="setup-step-line"></div>
      <div class="setup-step" id="stepInd3"><span class="setup-step-num">3</span> LLM</div>
      <div class="setup-step-line"></div>
      <div class="setup-step" id="stepInd4"><span class="setup-step-num">4</span> Search</div>
      <div class="setup-step-line"></div>
      <div class="setup-step" id="stepInd5"><span class="setup-step-num">5</span> Done</div>
    </div>
    <div id="setupBody"></div>
    <div id="setupFooter"></div>
  </div>
</div>
<input type="file" id="restoreFileInput" accept=".zip" onchange="doRestore(this)">

<!-- Event Detail Drawer -->
<div id="drawerOverlay" onclick="closeDrawer()" style="display:none"></div>
<aside id="eventDrawer" class="drawer" role="dialog" aria-modal="true" aria-labelledby="drawerTitle">
  <div class="drawer-header">
    <h2 class="drawer-title" id="drawerTitle">Loading…</h2>
    <button class="drawer-close" onclick="closeDrawer()" aria-label="Close">✕</button>
  </div>
  <div class="drawer-body" id="drawerBody"><div class="loading">Loading…</div></div>
  <div class="drawer-footer" id="drawerFooter"></div>
</aside>

<script>
  const LIMIT = 24;
  let page = 1;
  let activeTag = '';
  let viewMode = 'list';

  // Calendar state
  const _now = new Date();
  let calMonth = _now.getMonth();
  let calYear  = _now.getFullYear();
  let calAllEvents   = [];
  let calSelectedDate = null;

  // No more interest cycle — three independent toggle buttons per card.

  const calIcon = `<svg class="meta-icon" width="12" height="12" viewBox="0 0 16 16" fill="currentColor">
    <path d="M3.5 0a.5.5 0 0 1 .5.5V1h8V.5a.5.5 0 0 1 1 0V1h1a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2V3a2 2 0 0 1 2-2h1V.5a.5.5 0 0 1 .5-.5zM1 4v10a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V4H1z"/>
  </svg>`;
  const pinIcon = `<svg class="meta-icon" width="12" height="12" viewBox="0 0 16 16" fill="currentColor">
    <path d="M8 16s6-5.686 6-10A6 6 0 0 0 2 6c0 4.314 6 10 6 10zm0-7a3 3 0 1 1 0-6 3 3 0 0 1 0 6z"/>
  </svg>`;

  // ── Filters ──────────────────────────────────────────────────────────────
  function getFilters() {
    return {
      search:    document.getElementById('fSearch').value.trim(),
      source:    document.getElementById('fSource').value,
      eventType: document.getElementById('fType').value,
      dist:      document.getElementById('fDist').value,
      upcoming:  document.getElementById('fUpcoming').checked,
      free:      document.getElementById('fFree').checked,
      hideNoted: document.getElementById('fHideNoted').checked,
    };
  }

  function setTag(name) {
    activeTag = name;
    document.getElementById('activeTagLabel').textContent = name;
    document.getElementById('activeTagWrap').classList.toggle('visible', !!name);
  }
  function clearTag() {
    setTag('');
    document.getElementById('tagsPopoutBtn').classList.remove('has-active');
    page = 1; load();
  }
  function filterByTag(name) {
    setTag(name);
    document.getElementById('tagsPopoutBtn').classList.toggle('has-active', !!name);
    page = 1; load();
  }

  function applyFilters() { page = 1; load(); }
  function resetFilters() {
    document.getElementById('fSearch').value      = '';
    document.getElementById('fSource').value      = '';
    document.getElementById('fType').value        = '';
    document.getElementById('fDist').value        = '';
    document.getElementById('fUpcoming').checked  = true;
    document.getElementById('fFree').checked      = false;
    document.getElementById('fHideNoted').checked = true;
    setTag('');
    document.getElementById('tagsPopoutBtn').classList.remove('has-active');
    page = 1; load();
  }

  // ── Tags Popout ──────────────────────────────────────────────────────────
  let _allTags = [];
  let _userKeywords = [];
  let _tagsPopoutOpen = false;
  let _tagsZeroOpen = false;

  async function loadTagsData() {
    try {
      const [tags, cfg] = await Promise.all([
        fetch('/tags').then(r => r.json()),
        fetch('/config').then(r => r.json()),
      ]);
      _allTags = tags || [];
      _userKeywords = cfg.user_keywords || [];
    } catch (_) {}
  }

  function toggleTagsPopout(ev) {
    ev.stopPropagation();
    if (_tagsPopoutOpen) { closeTagsPopout(); return; }
    _tagsPopoutOpen = true;
    const btn = document.getElementById('tagsPopoutBtn');
    const pop = document.getElementById('tagsPopout');
    const r   = btn.getBoundingClientRect();
    pop.style.top  = (r.bottom + 6) + 'px';
    pop.style.left = r.left + 'px';
    pop.style.display = 'flex';
    pop.style.flexDirection = 'column';
    document.getElementById('tpSearch').value = '';
    renderTagsPopout();
    document.getElementById('tpSearch').focus();
  }

  function closeTagsPopout() {
    _tagsPopoutOpen = false;
    document.getElementById('tagsPopout').style.display = 'none';
  }

  function renderTagsPopout() {
    const q = (document.getElementById('tpSearch')?.value || '').toLowerCase();
    const withCount = _allTags.filter(t => t.count > 0 && (!q || t.name.toLowerCase().includes(q)));
    const zeroDB    = _allTags.filter(t => t.count === 0 && (!q || t.name.toLowerCase().includes(q)));
    const zeroPend  = _userKeywords.filter(k => !q || k.toLowerCase().includes(q));

    document.getElementById('tpList').innerHTML = withCount.map(t => `
      <div class="tp-tag ${t.name === activeTag ? 'active' : ''}"
           onclick="filterByTag(${JSON.stringify(t.name)});closeTagsPopout()">
        🏷 ${t.name}<span class="tp-count">${t.count}</span>
      </div>`).join('') ||
      '<div style="padding:.5rem .75rem;font-size:.78rem;color:#bbb">No tags yet — run the pipeline first.</div>';

    const zeroTotal = zeroDB.length + zeroPend.length;
    const toggle    = document.getElementById('tpZeroToggle');
    const zeroList  = document.getElementById('tpZeroList');
    if (zeroTotal) {
      toggle.style.display = '';
      toggle.textContent = (_tagsZeroOpen ? '▾' : '▸') + ` No events yet (${zeroTotal})`;
      if (_tagsZeroOpen) {
        zeroList.style.display = '';
        zeroList.innerHTML =
          zeroDB.map(t => `<div class="tp-zero-item" onclick="filterByTag(${JSON.stringify(t.name)});closeTagsPopout()">🏷 ${t.name}</div>`).join('') +
          zeroPend.map(k => `<div class="tp-zero-item kw-pending" title="Pending search term — will be searched next pipeline run">🔍 ${k}</div>`).join('');
      } else {
        zeroList.style.display = 'none';
      }
    } else {
      toggle.style.display = 'none';
    }
  }

  function toggleZeroTags() {
    _tagsZeroOpen = !_tagsZeroOpen;
    renderTagsPopout();
  }

  async function addUserKeyword() {
    const input = document.getElementById('tpAddInput');
    const term  = input.value.trim();
    if (!term || _userKeywords.includes(term)) { input.value = ''; return; }
    _userKeywords = [..._userKeywords, term];
    input.value = '';
    await fetch('/config', {
      method: 'PATCH',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({user_keywords: _userKeywords}),
    });
    renderTagsPopout();
  }

  document.addEventListener('click', ev => {
    if (_tagsPopoutOpen && !document.getElementById('tagsPopout').contains(ev.target))
      closeTagsPopout();
  });

  document.getElementById('fSearch').addEventListener('keydown', e => {
    if (e.key === 'Enter') applyFilters();
  });

  // ── View toggle ───────────────────────────────────────────────────────────
  function setView(mode) {
    viewMode = mode;
    document.getElementById('btnList').classList.toggle('active', mode === 'list');
    document.getElementById('btnCal').classList.toggle('active', mode === 'calendar');
    document.getElementById('pagination').innerHTML = '';
    // Show/hide the urgency strip based on view
    const tw = document.getElementById('thisWeekSection');
    if (tw) tw.style.display = mode === 'list' ? '' : 'none';
    page = 1;
    if (mode === 'list') {
      load();
    } else {
      loadCalendar();
    }
  }

  // ── Helpers ───────────────────────────────────────────────────────────────
  function fmtDate(iso) {
    if (!iso) return '—';
    return new Date(iso).toLocaleDateString('en-US', {
      weekday: 'short', month: 'short', day: 'numeric', year: 'numeric'
    });
  }
  function fmtTime(iso) {
    if (!iso) return '';
    return new Date(iso).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
  }

  // ── Card action buttons ───────────────────────────────────────────────────
  // Each button maps to one status. Clicking when already active clears it.
  async function toggleStatus(evt, eventId, targetStatus, btnEl) {
    evt.preventDefault();
    evt.stopPropagation();

    const card    = btnEl.closest('.card');
    const current = card.dataset.status || null;
    const next    = (current === targetStatus) ? null : targetStatus;

    await fetch('/events/' + eventId + '/interest', {
      method:  'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ status: next }),
    });

    card.dataset.status = next || '';
    _syncCardButtons(card, next);

    // If dismissed with hide-noted on, fade the card out
    if (next === 'noted' && document.getElementById('fHideNoted').checked) {
      card.style.transition = 'opacity 0.4s';
      card.style.opacity = '0';
      setTimeout(() => card.remove(), 450);
    }

    // Keep in-memory calendar list in sync
    const cached = calAllEvents.find(e => e.id === eventId);
    if (cached) cached.interest_status = next;
  }

  function _syncCardButtons(card, status) {
    const flagBtn    = card.querySelector('.card-flag-btn');
    const dismissBtn = card.querySelector('.card-dismiss-btn');
    const attendBtn  = card.querySelector('.card-attend-btn');
    if (!flagBtn) return;

    const isFlagged   = status === 'interested';
    const isDismissed = status === 'noted';
    const isAttending = status === 'attending';

    flagBtn.classList.toggle('active', isFlagged);
    flagBtn.title = isFlagged ? 'Flagged for review — click to unflag' : 'Flag for review';

    dismissBtn.classList.toggle('active', isDismissed);
    dismissBtn.title = isDismissed ? 'Dismissed — click to restore' : 'Dismiss this event';

    attendBtn.classList.toggle('active', isAttending);
    attendBtn.querySelector('span').textContent = isAttending ? '☑' : '☐';
    attendBtn.title = isAttending ? 'Attending — click to unmark' : 'Mark as attending';
  }

  // ── Card renderer ─────────────────────────────────────────────────────────
  function renderCard(e) {
    const loc      = [e.city, e.state].filter(Boolean).join(', ') || (e.event_type === 'virtual' ? 'Online' : '—');
    const dist     = e.distance_miles != null ? ` · ${e.distance_miles} mi` : '';
    const typeClass = { virtual: 'b-virtual', hybrid: 'b-hybrid' }[e.event_type] || 'b-physical';
    const typeBadge = e.event_type ? `<span class="badge ${typeClass}">${e.event_type}</span>` : '';
    const costBadge = e.cost_type === 'free'
      ? '<span class="badge b-free">Free</span>'
      : (e.cost_type ? '<span class="badge b-paid">Paid</span>' : '');

    const status      = e.interest_status || null;
    const isFlagged   = status === 'interested';
    const isDismissed = status === 'noted';
    const isAttending = status === 'attending';

    const tagChips = (e.tag_names || []).map(t =>
      `<button class="tag-chip" onclick="event.stopPropagation();filterByTag('${t.replace(/'/g,"\\'")}');">${t}</button>`
    ).join('');

    return `
      <div class="card" onclick="openDrawer('${e.id}')"
           data-id="${e.id}" data-status="${status || ''}">
        <div class="card-top">
          <button class="card-flag-btn ${isFlagged ? 'active' : ''}"
            title="${isFlagged ? 'Flagged for review — click to unflag' : 'Flag for review'}"
            onclick="toggleStatus(event, '${e.id}', 'interested', this)">🚩</button>
          <div class="card-title">${e.title}</div>
          <button class="card-dismiss-btn ${isDismissed ? 'active' : ''}"
            title="${isDismissed ? 'Dismissed — click to restore' : 'Dismiss this event'}"
            onclick="toggleStatus(event, '${e.id}', 'noted', this)">✕</button>
        </div>
        <div class="badges">${typeBadge}${costBadge}</div>
        <div class="card-meta">
          <div class="meta-row">${calIcon}${fmtDate(e.start_datetime)}${fmtTime(e.start_datetime) ? ' · ' + fmtTime(e.start_datetime) : ''}</div>
          <div class="meta-row">${pinIcon}${loc}${dist}</div>
        </div>
        ${tagChips ? `<div class="card-tags">${tagChips}</div>` : ''}
        <div class="card-footer">
          <span class="card-source">${e.source}</span>
          <button class="card-attend-btn ${isAttending ? 'active' : ''}"
            title="${isAttending ? 'Attending — click to unmark' : 'Mark as attending'}"
            onclick="toggleStatus(event, '${e.id}', 'attending', this)">
            <span>${isAttending ? '☑' : '☐'}</span> Attending
          </button>
        </div>
      </div>`;
  }

  // ── List view ─────────────────────────────────────────────────────────────
  async function load() {
    const container = document.getElementById('mainContent');
    container.innerHTML = '<div class="events"><div class="loading">Loading…</div></div>';
    document.getElementById('pagination').innerHTML = '';
    document.getElementById('status').textContent = '';

    const f = getFilters();
    const p = new URLSearchParams({ page, limit: LIMIT });
    if (f.search)    p.set('q', f.search);
    if (f.source)    p.set('source', f.source);
    if (f.eventType) p.set('event_type', f.eventType);
    if (f.dist)      p.set('max_distance_miles', f.dist);
    if (f.upcoming)  p.set('from_date', new Date().toISOString());
    if (f.free)      p.set('free_only', 'true');
    if (!f.hideNoted) p.set('hide_noted', 'false');
    if (activeTag)   p.set('tag', activeTag);

    try {
      const [eventsRes, countRes] = await Promise.all([
        fetch('/events?' + p),
        fetch('/events/count?' + p),
      ]);
      if (!eventsRes.ok) throw new Error(eventsRes.statusText);
      const events = await eventsRes.json();
      const total  = countRes.ok ? (await countRes.json()).total : null;

      if (!events.length) {
        container.innerHTML = '<div class="events"><div class="empty">No events found. Try adjusting filters or run the pipeline.</div></div>';
        document.getElementById('status').textContent = '0 events';
        return;
      }

      container.innerHTML = `<div class="events" id="events">${events.map(renderCard).join('')}</div>`;
      const from    = (page - 1) * LIMIT + 1;
      const to      = (page - 1) * LIMIT + events.length;
      const totalStr = total !== null ? ` of ${total}` : '';
      document.getElementById('status').textContent =
        `Showing ${from}–${to}${totalStr} events${activeTag ? ' · tag: ' + activeTag : ''}`;

      const pag  = document.getElementById('pagination');
      const prev = Object.assign(document.createElement('button'), { textContent: '← Prev', disabled: page === 1 });
      prev.onclick = () => { page--; load(); scrollTo(0, 0); };
      const info = Object.assign(document.createElement('span'), { textContent: `Page ${page}` });
      const next = Object.assign(document.createElement('button'), { textContent: 'Next →', disabled: events.length < LIMIT });
      next.onclick = () => { page++; load(); scrollTo(0, 0); };
      pag.append(prev, info, next);

    } catch (err) {
      container.innerHTML = '<div class="events"><div class="empty">Failed to load events. Is the server running?</div></div>';
    }
  }

  // ── Calendar view ─────────────────────────────────────────────────────────
  const CAL_MONTHS = ['January','February','March','April','May','June',
                      'July','August','September','October','November','December'];
  const CAL_DAYS   = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];

  async function loadCalendar() {
    document.getElementById('mainContent').innerHTML =
      '<div class="events"><div class="loading">Loading calendar…</div></div>';
    document.getElementById('status').textContent = '';

    const f = getFilters();
    const p = new URLSearchParams({ page: 1, limit: 200 });
    if (f.search)     p.set('q', f.search);
    if (f.source)     p.set('source', f.source);
    if (f.eventType)  p.set('event_type', f.eventType);
    if (f.dist)       p.set('max_distance_miles', f.dist);
    if (f.free)       p.set('free_only', 'true');
    if (!f.hideNoted) p.set('hide_noted', 'false');
    if (activeTag)    p.set('tag', activeTag);
    // Calendar always scopes to upcoming events
    p.set('from_date', new Date().toISOString());

    try {
      const res = await fetch('/events?' + p);
      if (!res.ok) throw new Error(res.statusText);
      calAllEvents = await res.json();
      calSelectedDate = null;
      renderCalendar();
    } catch (err) {
      document.getElementById('mainContent').innerHTML =
        '<div class="events"><div class="empty">Failed to load events.</div></div>';
    }
  }

  function _byDate(month, year) {
    const map = {};
    for (const e of calAllEvents) {
      if (!e.start_datetime) continue;
      const d = new Date(e.start_datetime);
      if (d.getMonth() === month && d.getFullYear() === year) {
        const key = d.toDateString();
        if (!map[key]) map[key] = [];
        map[key].push(e);
      }
    }
    return map;
  }

  function renderCalendar() {
    const byDate   = _byDate(calMonth, calYear);
    const firstDay = new Date(calYear, calMonth, 1);
    const lastDay  = new Date(calYear, calMonth + 1, 0);
    const todayStr = new Date().toDateString();

    let html = `
      <div class="cal-nav">
        <button class="cal-nav-btn" onclick="calPrev()">← Prev</button>
        <span class="cal-month-title">${CAL_MONTHS[calMonth]} ${calYear}</span>
        <button class="cal-nav-btn" onclick="calNext()">Next →</button>
      </div>
      <div class="cal-grid">`;

    for (const d of CAL_DAYS) html += `<div class="cal-dow">${d}</div>`;

    // Leading empty cells
    for (let i = 0; i < firstDay.getDay(); i++) html += '<div class="cal-cell empty"></div>';

    for (let d = 1; d <= lastDay.getDate(); d++) {
      const dateStr  = new Date(calYear, calMonth, d).toDateString();
      const dayEvts  = byDate[dateStr] || [];
      const isToday  = dateStr === todayStr;
      const isSel    = dateStr === calSelectedDate;
      const classes  = ['cal-cell',
        dayEvts.length ? 'has-events' : '',
        isToday ? 'today' : '',
        isSel   ? 'selected' : '',
      ].filter(Boolean).join(' ');

      // Dot shows count; color by majority event type
      let dotHtml = '';
      if (dayEvts.length) {
        const types = dayEvts.map(e => e.event_type || 'physical');
        const dotClass = types.every(t => t === 'virtual') ? 'dot-virtual'
                       : types.every(t => t === 'physical') ? 'dot-physical'
                       : 'dot-mixed';
        dotHtml = `<div class="cal-dots"><span class="cal-dot ${dotClass}">${dayEvts.length} event${dayEvts.length > 1 ? 's' : ''}</span></div>`;
      }

      const clickAttr = dayEvts.length ? `onclick="selectCalDay('${dateStr}')"` : '';
      html += `<div class="${classes}" ${clickAttr}><div class="cal-day-num">${d}</div>${dotHtml}</div>`;
    }

    html += '</div><div class="cal-day-panel" id="calDayPanel"></div>';

    const total = Object.values(byDate).flat().length;
    document.getElementById('mainContent').innerHTML = html;
    document.getElementById('status').textContent =
      `${total} event${total !== 1 ? 's' : ''} in ${CAL_MONTHS[calMonth]} ${calYear}${activeTag ? ' · tag: ' + activeTag : ''}`;

    if (calSelectedDate) selectCalDay(calSelectedDate);
  }

  function selectCalDay(dateStr) {
    calSelectedDate = dateStr;

    // Update selected styling
    document.querySelectorAll('.cal-cell.selected').forEach(el => el.classList.remove('selected'));
    document.querySelectorAll('.cal-cell').forEach(el => {
      if (el.onclick && el.onclick.toString().includes(dateStr)) el.classList.add('selected');
    });

    const dayEvts = calAllEvents.filter(e =>
      e.start_datetime && new Date(e.start_datetime).toDateString() === dateStr
    );

    const panel = document.getElementById('calDayPanel');
    if (!panel || !dayEvts.length) return;

    const d = new Date(dateStr);
    const label = d.toLocaleDateString('en-US', {
      weekday: 'long', month: 'long', day: 'numeric', year: 'numeric'
    });

    panel.innerHTML = `
      <div class="cal-day-title">${label} — ${dayEvts.length} event${dayEvts.length !== 1 ? 's' : ''}</div>
      <div class="cal-day-events">${dayEvts.map(renderCard).join('')}</div>
    `;
    panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function calPrev() {
    if (calMonth === 0) { calMonth = 11; calYear--; } else calMonth--;
    calSelectedDate = null;
    renderCalendar();
  }
  function calNext() {
    if (calMonth === 11) { calMonth = 0; calYear++; } else calMonth++;
    calSelectedDate = null;
    renderCalendar();
  }

  // ── Run pipeline ──────────────────────────────────────────────────────────
  let _pollTimer = null;
  let _runStart  = null;

  function setRunStatus(cls, text) {
    const el = document.getElementById('runStatus');
    el.className = cls;
    el.textContent = text;
  }

  async function triggerRun() {
    const btn = document.getElementById('btnRun');
    btn.disabled = true;
    _runStart = Date.now();
    setRunStatus('running', '● Starting…');

    try {
      const res  = await fetch('/run', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
      const data = await res.json();
      const runId = data.summary?.run_id;
      if (!runId) throw new Error('No run ID returned');
      pollRun(runId);
    } catch (err) {
      setRunStatus('err', '✕ ' + err.message);
      btn.disabled = false;
    }
  }

  function pollRun(runId) {
    _pollTimer = setInterval(async () => {
      const elapsed = Math.round((Date.now() - _runStart) / 1000);
      try {
        const res  = await fetch('/run/' + runId);
        const data = await res.json();
        if (data.status === 'complete') {
          clearInterval(_pollTimer);
          const s = data.summary || {};
          const newlyClassified = s.newly_classified ?? s.classified ?? '?';
          const alreadyKnown = s.already_classified ?? 0;
          const detail = alreadyKnown > 0
            ? `${newlyClassified} new · ${alreadyKnown} updated`
            : `${newlyClassified} events saved`;
          setRunStatus('ok', `✓ Done — ${detail}`);
          document.getElementById('btnRun').disabled = false;
          if (viewMode === 'list') { load(); loadThisWeek(); } else loadCalendar();
          loadStats();
          loadTagsData();
          setTimeout(() => setRunStatus('', ''), 12000);
        } else if (data.status === 'error') {
          clearInterval(_pollTimer);
          setRunStatus('err', '✕ ' + (data.summary?.error || 'unknown error'));
          document.getElementById('btnRun').disabled = false;
        } else {
          const step = data.step || 'Running…';
          setRunStatus('running', `● ${step} (${elapsed}s)`);
        }
      } catch (_) { /* network blip */ }
    }, 3000);
  }

  async function loadNextRun() {
    try {
      const cfg = await fetch('/config').then(r => r.json());
      const el  = document.getElementById('nextRun');
      if (cfg.next_run_at) {
        const d      = new Date(cfg.next_run_at);
        const isToday = d.toDateString() === new Date().toDateString();
        const isTomorrow = d.toDateString() === new Date(Date.now() + 86400000).toDateString();
        const dateStr = isToday ? 'Today'
                      : isTomorrow ? 'Tomorrow'
                      : d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        const timeStr = d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
        el.textContent = `⏱ Next run: ${dateStr} at ${timeStr}`;
      } else {
        el.textContent = 'Schedule off';
      }
    } catch (_) {}
  }

  // ── This Week urgency strip ───────────────────────────────────────────────
  let _twCollapsed = false;

  function toggleThisWeek() {
    _twCollapsed = !_twCollapsed;
    document.getElementById('twBody').classList.toggle('collapsed', _twCollapsed);
    document.getElementById('twToggleBtn').textContent = _twCollapsed ? '▸' : '▾';
  }

  function _urgencyInfo(isoDate, eventType) {
    const now      = new Date();
    const evtDate  = new Date(isoDate);
    const diffDays = Math.floor((evtDate - now) / 864e5);
    if (diffDays < 0) return null;
    if (eventType === 'virtual')
      return { cardCls: 'uc-virtual', badgeCls: 'ub-virtual', label: 'Virtual' };
    if (diffDays === 0)
      return { cardCls: 'uc-today',    badgeCls: 'ub-today',    label: 'Today' };
    if (diffDays === 1)
      return { cardCls: 'uc-tomorrow', badgeCls: 'ub-tomorrow', label: 'Tomorrow' };
    const dayName = evtDate.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
    return { cardCls: 'uc-soon', badgeCls: 'ub-soon', label: dayName };
  }

  async function loadThisWeek() {
    const now = new Date();
    const end = new Date(now.getTime() + 7 * 864e5);
    const p = new URLSearchParams({
      from_date: now.toISOString(), to_date: end.toISOString(),
      limit: 40, page: 1, hide_noted: 'true',
    });
    try {
      const res = await fetch('/events?' + p);
      if (!res.ok) return;
      renderThisWeek(await res.json());
    } catch (_) {}
  }

  function renderThisWeek(events) {
    const section = document.getElementById('thisWeekSection');
    const body    = document.getElementById('twBody');
    const countEl = document.getElementById('twCount');

    if (!events.length) { section.style.display = 'none'; return; }

    // Physical/hybrid first (sorted by date), then virtual
    const sorted = [...events].sort((a, b) => {
      const av = a.event_type === 'virtual', bv = b.event_type === 'virtual';
      if (av !== bv) return av ? 1 : -1;
      return new Date(a.start_datetime) - new Date(b.start_datetime);
    });

    const cards = sorted.map(e => {
      if (!e.start_datetime) return '';
      const info = _urgencyInfo(e.start_datetime, e.event_type);
      if (!info) return '';
      const loc  = [e.city, e.state].filter(Boolean).join(', ') || (e.event_type === 'virtual' ? 'Online' : '');
      const time = fmtTime(e.start_datetime);
      const meta = [time, loc].filter(Boolean).join(' · ');
      return `<div class="uc ${info.cardCls}" onclick="openDrawer('${e.id}')" style="cursor:pointer">
        <span class="ub ${info.badgeCls}">${info.label}</span>
        <span class="uc-title">${e.title}</span>
        ${meta ? `<span class="uc-meta">${meta}</span>` : ''}
      </div>`;
    }).join('');

    body.innerHTML = cards;
    countEl.textContent = `${events.length} event${events.length !== 1 ? 's' : ''}`;
    section.style.display = '';
  }

  // ── KPI Sidebar ──────────────────────────────────────────────────────────
  async function loadStats() {
    try {
      const data = await fetch('/stats').then(r => r.json());
      renderSidebar(data);
    } catch (_) {}
  }

  function renderSidebar(data) {
    // Last run
    const runAtEl      = document.getElementById('kpiRunAt');
    const runSummaryEl = document.getElementById('kpiRunSummary');
    if (data.last_run_at) {
      const d       = new Date(data.last_run_at);
      const isToday = d.toDateString() === new Date().toDateString();
      runAtEl.textContent = isToday
        ? d.toLocaleTimeString('en-US', {hour:'numeric', minute:'2-digit'}) + ' today'
        : d.toLocaleDateString('en-US', {month:'short', day:'numeric'})
          + ' ' + d.toLocaleTimeString('en-US', {hour:'numeric', minute:'2-digit'});
      const newC = data.newly_classified ?? 0;
      const updC = data.already_classified ?? 0;
      const errC = data.errors ?? 0;
      const parts = [];
      if (newC) parts.push(`${newC} new`);
      if (updC) parts.push(`${updC} updated`);
      if (errC) parts.push(`${errC} err`);
      runSummaryEl.textContent = parts.join(' · ') || 'no changes';
    } else {
      runAtEl.textContent = 'No runs yet';
    }

    // Sources
    const sourcesEl   = document.getElementById('kpiSources');
    const srcCounts   = data.source_counts || {};
    const srcEntries  = Object.entries(srcCounts);
    if (srcEntries.length) {
      const labels = { eventbrite:'Eventbrite', meetup:'Meetup', luma:'Lu.ma', web_search:'Web Search' };
      sourcesEl.innerHTML = srcEntries.map(([src, count]) => {
        const ok    = count > 0;
        const label = labels[src] || src;
        return `<div class="kpi-row ${ok ? 'kpi-ok' : 'kpi-warn'}">
          <span class="kpi-dot">●</span>
          <span class="kpi-name">${label}</span>
          <span class="kpi-count">${count}</span>
        </div>`;
      }).join('');
    } else {
      sourcesEl.innerHTML = '<div class="kpi-meta">No data yet</div>';
    }

    // API keys
    const keysEl  = document.getElementById('kpiApiKeys');
    const apiStat = data.api_status || {};
    if (Object.keys(apiStat).length) {
      keysEl.innerHTML = Object.entries(apiStat).map(([name, status]) => {
        const ok = status === 'configured';
        return `<div class="kpi-row ${ok ? 'kpi-ok' : 'kpi-err'}">
          <span class="kpi-dot">●</span>
          <span class="kpi-name">${name}</span>
          ${!ok ? '<span class="kpi-count" style="background:#fee2e2;color:#dc2626">!</span>' : ''}
        </div>`;
      }).join('');
    }
  }

  // ── Event Detail Drawer ───────────────────────────────────────────────────
  let _drawerEventId = null;
  let _drawerStatus  = null;

  async function openDrawer(eventId) {
    _drawerEventId = eventId;
    const overlay = document.getElementById('drawerOverlay');
    const drawer  = document.getElementById('eventDrawer');
    const body    = document.getElementById('drawerBody');
    const footer  = document.getElementById('drawerFooter');
    document.getElementById('drawerTitle').textContent = 'Loading…';
    body.innerHTML   = '<div class="loading">Loading event details…</div>';
    footer.innerHTML = '';
    overlay.style.display = '';
    drawer.getBoundingClientRect(); // force reflow before transition
    drawer.classList.add('open');
    document.body.style.overflow = 'hidden';
    try {
      const res = await fetch('/events/' + eventId);
      if (!res.ok) throw new Error(res.statusText);
      const e = await res.json();
      _drawerStatus = e.interest_status || null;
      drawer.dataset.eventUrl = e.event_url || '#';
      drawer.dataset.regUrl   = e.registration_url || '';
      _renderDrawer(e);
    } catch (err) {
      body.innerHTML = '<div class="empty">Failed to load event details.</div>';
    }
  }

  function closeDrawer() {
    const drawer = document.getElementById('eventDrawer');
    drawer.classList.remove('open');
    document.body.style.overflow = '';
    setTimeout(() => { document.getElementById('drawerOverlay').style.display = 'none'; }, 260);
    _drawerEventId = null;
  }

  function _sanitizeText(str) {
    const d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
  }

  function _renderDrawer(e) {
    document.getElementById('drawerTitle').textContent = e.title;

    const typeClass = { virtual: 'b-virtual', hybrid: 'b-hybrid' }[e.event_type] || 'b-physical';
    const typeBadge = e.event_type ? `<span class="badge ${typeClass}">${e.event_type}</span>` : '';
    const costBadge = e.cost_type === 'free'
      ? '<span class="badge b-free">Free</span>'
      : (e.cost_type ? '<span class="badge b-paid">Paid</span>' : '');
    const costAmt = (e.cost_type === 'paid' && e.cost_amount)
      ? ` ($${e.cost_amount.toFixed(2)})` : '';

    const dateStr = [fmtDate(e.start_datetime), fmtTime(e.start_datetime)].filter(Boolean).join(' · ');
    const endStr  = (e.end_datetime && fmtTime(e.end_datetime)) ? ` → ${fmtTime(e.end_datetime)}` : '';

    const locParts = [e.venue_name, e.address, [e.city, e.state].filter(Boolean).join(', ')].filter(Boolean);
    const locStr  = locParts.join(' · ') || (e.event_type === 'virtual' ? 'Online' : '—');
    const distStr = e.distance_miles != null ? ` · ${e.distance_miles} mi` : '';

    const tagChips = (e.tag_names || []).map(t =>
      `<button class="tag-chip" onclick="closeDrawer();filterByTag('${t.replace(/'/g,"\\'")}');">${t}</button>`
    ).join('');

    const orgList = (e.organizers || []).map(o => `
      <div class="drawer-org">
        <span>${_sanitizeText(o.name)}</span>
        ${o.website      ? `<a href="${o.website}" target="_blank" rel="noopener">Website ↗</a>` : ''}
        ${o.linkedin_url ? `<a href="${o.linkedin_url}" target="_blank" rel="noopener">LinkedIn ↗</a>` : ''}
      </div>`).join('');

    const sponsorList = (e.sponsors || []).map(s => `
      <div class="drawer-org">
        <span>${_sanitizeText(s.name)}</span>
        ${s.website ? `<a href="${s.website}" target="_blank" rel="noopener">Website ↗</a>` : ''}
      </div>`).join('');

    document.getElementById('drawerBody').innerHTML = `
      <div class="drawer-section">
        <div style="display:flex;gap:.3rem;flex-wrap:wrap;margin-bottom:.75rem">${typeBadge}${costBadge}</div>
        <div class="drawer-meta-row">${calIcon}<span>${dateStr}${endStr}</span></div>
        <div class="drawer-meta-row">${pinIcon}<span>${locStr}${distStr}</span></div>
        ${e.timezone ? `<div class="drawer-meta-row"><span class="drawer-meta-icon">🕐</span><span>${e.timezone}</span></div>` : ''}
        ${costAmt    ? `<div class="drawer-meta-row"><span class="drawer-meta-icon">💳</span><span>Paid${costAmt}</span></div>` : ''}
      </div>
      ${e.description ? `
      <div class="drawer-section">
        <div class="drawer-section-title">About</div>
        <div class="drawer-desc">${_sanitizeText(e.description)}</div>
      </div>` : ''}
      ${tagChips ? `
      <div class="drawer-section">
        <div class="drawer-section-title">Tags</div>
        <div style="display:flex;flex-wrap:wrap;gap:.25rem">${tagChips}</div>
      </div>` : ''}
      ${orgList ? `
      <div class="drawer-section">
        <div class="drawer-section-title">Organizers</div>
        ${orgList}
      </div>` : ''}
      ${sponsorList ? `
      <div class="drawer-section">
        <div class="drawer-section-title">Sponsors</div>
        ${sponsorList}
      </div>` : ''}
    `;
    _syncDrawerFooter();
  }

  function _syncDrawerFooter() {
    if (!_drawerEventId) return;
    const drawer     = document.getElementById('eventDrawer');
    const visitHref  = drawer.dataset.regUrl || drawer.dataset.eventUrl || '#';
    const visitLabel = drawer.dataset.regUrl ? 'Register ↗' : 'Visit Event ↗';
    const status      = _drawerStatus;
    const isFlagged   = status === 'interested';
    const isDismissed = status === 'noted';
    const isAttending = status === 'attending';

    document.getElementById('drawerFooter').innerHTML = `
      <a class="btn-visit" href="${visitHref}" target="_blank" rel="noopener">${visitLabel}</a>
      <div class="drawer-actions">
        <button class="drawer-action-btn dab-flag ${isFlagged ? 'active' : ''}"
          id="dabFlag" onclick="drawerToggleStatus('interested')"
          title="${isFlagged ? 'Flagged — click to unflag' : 'Flag for review'}">🚩</button>
        <button class="drawer-action-btn dab-attend ${isAttending ? 'active' : ''}"
          id="dabAttend" onclick="drawerToggleStatus('attending')"
          title="${isAttending ? 'Attending — click to unmark' : 'Mark attending'}">
          <span>${isAttending ? '☑' : '☐'}</span> Attending
        </button>
        <button class="drawer-action-btn dab-dismiss ${isDismissed ? 'active' : ''}"
          id="dabDismiss" onclick="drawerToggleStatus('noted')"
          title="${isDismissed ? 'Dismissed — click to restore' : 'Dismiss'}">✕ Dismiss</button>
      </div>
    `;
  }

  async function drawerToggleStatus(targetStatus) {
    if (!_drawerEventId) return;
    const next = (_drawerStatus === targetStatus) ? null : targetStatus;

    await fetch('/events/' + _drawerEventId + '/interest', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: next }),
    });

    _drawerStatus = next;
    _syncDrawerFooter();

    // Sync the matching card in the list/calendar views
    const card = document.querySelector(`.card[data-id="${_drawerEventId}"]`);
    if (card) {
      card.dataset.status = next || '';
      _syncCardButtons(card, next);
      if (next === 'noted' && document.getElementById('fHideNoted').checked) {
        card.style.transition = 'opacity 0.4s';
        card.style.opacity = '0';
        setTimeout(() => card.remove(), 450);
      }
    }
    const cached = calAllEvents.find(ev => ev.id === _drawerEventId);
    if (cached) cached.interest_status = next;
  }

  document.addEventListener('keydown', ev => {
    if (ev.key === 'Escape') {
      closeDrawer();
      if (document.getElementById('settingsOverlay').style.display !== 'none') closeSettings();
      if (_wizardOpenedViaGear) closeSetupWizard();
    }
  });

  // ── Setup Wizard ──────────────────────────────────────────────────────────
  let _wizardStep = 1;
  let _wizardOpenedViaGear = false;
  let _wizardEnvVars   = {};
  let _wizardConfigVars = {};

  // Step content builders
  const _SOURCES = [
    { id: 'eventbrite', label: 'Eventbrite', desc: 'Large event platform. Scrapes via browser — no API key needed.' },
    { id: 'meetup',     label: 'Meetup',     desc: 'Community meetups. Browser-based scraper.' },
    { id: 'luma',       label: 'Luma',       desc: 'Modern event platform popular with tech communities. REST API, no key needed.' },
    { id: 'web_search', label: 'Web Search', desc: 'AI-guided search for events not on the above platforms. Requires LLM + search provider.' },
  ];

  const _LLM_PROVIDERS = [
    { id: 'anthropic', label: 'Anthropic', cost: '💳 Pay-per-use', costCls: 'cost-paid',  note: 'Best accuracy. ~$0.01–0.05/run' },
    { id: 'openai',    label: 'OpenAI',    cost: '💳 Pay-per-use', costCls: 'cost-paid',  note: 'Strong accuracy. ~$0.01–0.05/run' },
    { id: 'google',    label: 'Google',    cost: '🆓/💳 Free tier', costCls: 'cost-mixed', note: 'Gemini Flash — generous free tier' },
    { id: 'lmstudio',  label: 'LM Studio', cost: '🆓 Free local',  costCls: 'cost-free',  note: 'Requires LM Studio running with a loaded model' },
    { id: 'ollama',    label: 'Ollama',    cost: '🆓 Free local',  costCls: 'cost-free',  note: 'Requires Ollama running locally' },
  ];

  const _SEARCH_PROVIDERS = [
    { id: 'brave',   label: 'Brave Search', cost: '🆓/💳 Free tier', costCls: 'cost-mixed', note: '2,000 free queries/month. Best quality free option.' },
    { id: 'serpapi', label: 'SerpAPI',       cost: '💳 Paid',         costCls: 'cost-paid',  note: '100 free searches then paid. Google results.' },
    { id: 'searxng', label: 'SearXNG',       cost: '🆓 Self-hosted',  costCls: 'cost-free',  note: 'Run locally via Docker. No quota.' },
    { id: 'ddg',     label: 'DuckDuckGo',    cost: '🆓 Always free',  costCls: 'cost-free',  note: 'No key needed. Lower result quality. Automatic fallback.' },
  ];

  function _pillsHtml(providers, selectedId, onclickFn) {
    return providers.map(p => `
      <button class="provider-pill ${p.id === selectedId ? 'active' : ''}"
              onclick="${onclickFn}('${p.id}')" type="button">
        ${p.label}
        <span class="cost-badge ${p.costCls}">${p.cost}</span>
      </button>`).join('');
  }

  function _stepHtml(step, cfg) {
    if (step === 1) {
      const zip = cfg.center_zip || '';
      const rad = cfg.radius_miles || 120;
      const lat = cfg.center_lat != null ? cfg.center_lat : '';
      const lon = cfg.center_lon != null ? cfg.center_lon : '';
      return `<label class="setup-field-label">ZIP Code</label>
        <input class="setup-input" id="wizZip" type="text" maxlength="10" placeholder="e.g. 10001" value="${zip}">
        <p class="setup-hint">Used to find events near you.</p>
        <label class="setup-field-label">Search radius</label>
        <select class="setup-select" id="wizRadius">
          ${[25,50,100,120,150,200].map(v => `<option value="${v}" ${v==rad?'selected':''}>${v} miles</option>`).join('')}
        </select>
        <div style="margin-top:.875rem;padding-top:.875rem;border-top:1px solid #f0f0f0">
          <label class="setup-field-label" style="margin-top:0">Latitude <span style="font-weight:400;color:#aaa">(optional)</span></label>
          <input class="setup-input" id="wizLat" type="number" step="any" placeholder="e.g. 40.7128"
                 value="${lat}" style="margin-bottom:.35rem">
          <label class="setup-field-label" style="margin-top:0">Longitude <span style="font-weight:400;color:#aaa">(optional)</span></label>
          <input class="setup-input" id="wizLon" type="number" step="any" placeholder="e.g. -74.0060"
                 value="${lon}">
          <p class="setup-hint">If set, overrides the ZIP centroid for distance calculations. ZIP still used for scraper URLs.</p>
        </div>`;
    }
    if (step === 2) {
      const enabled = cfg.enabled_sources || ['eventbrite','meetup','luma','web_search'];
      const sourcesHtml = _SOURCES.map(s => `
        <label class="source-check-row">
          <input type="checkbox" id="wizSrc_${s.id}" ${enabled.includes(s.id)?'checked':''}>
          <div><div class="source-name">${s.label}</div><div class="source-desc">${s.desc}</div></div>
        </label>`).join('');
      const keywordsHtml = `
        <p class="setup-hint">Geo-targeted terms (searched near your ZIP):</p>
        <div id="wizKwTags" class="kw-tag-wrap"></div>
        <div class="kw-add-row">
          <input class="setup-input" id="wizKwInput" type="text" placeholder="e.g. robotics conference"
                 onkeydown="if(event.key==='Enter')addWizKw()">
          <button class="kw-add-btn" onclick="addWizKw()" type="button">+ Add</button>
        </div>
        <p class="setup-hint" style="margin-top:.875rem">Virtual/vendor terms (searched globally, no ZIP):</p>
        <div id="wizVkTags" class="kw-tag-wrap"></div>
        <div class="kw-add-row">
          <input class="setup-input" id="wizVkInput" type="text" placeholder="e.g. Snowflake Summit"
                 onkeydown="if(event.key==='Enter')addWizVk()">
          <button class="kw-add-btn" onclick="addWizVk()" type="button">+ Add</button>
        </div>`;
      return `
        <div class="wizard-tabs">
          <button class="wizard-tab active" id="wtabSrc" onclick="switchWizTab('sources')" type="button">Sources</button>
          <button class="wizard-tab" id="wtabKw" onclick="switchWizTab('keywords')" type="button">Keywords</button>
        </div>
        <div id="wizTabSources">${sourcesHtml}</div>
        <div id="wizTabKeywords" style="display:none">${keywordsHtml}</div>`;
    }
    if (step === 3) {
      const activeProvider = _detectLlmProvider(cfg, _wizardEnvVars);
      return `<p style="font-size:.82rem;color:#555;margin-bottom:.75rem">
        Choose your AI provider. The LLM classifies events and powers web search.</p>
        <div class="provider-pills">${_pillsHtml(_LLM_PROVIDERS, activeProvider, 'selectLlmProvider')}</div>
        <div class="provider-detail" id="llmDetail">${_llmDetailHtml(activeProvider, cfg, 'wiz')}</div>`;
    }
    if (step === 4) {
      const activeSearch = _detectSearchProvider(cfg, _wizardEnvVars);
      return `<p style="font-size:.82rem;color:#555;margin-bottom:.75rem">
        Choose your search provider for web event discovery. DuckDuckGo always works as a free fallback.</p>
        <div class="provider-pills">${_pillsHtml(_SEARCH_PROVIDERS, activeSearch, 'selectSearchProvider')}</div>
        <div class="provider-detail" id="searchDetail">${_searchDetailHtml(activeSearch, cfg, 'wiz')}</div>`;
    }
    if (step === 5) {
      const sched = cfg.schedule_enabled !== false;
      const hour  = cfg.schedule_hour ?? 6;
      const min   = cfg.schedule_minute ?? 0;
      const clean = cfg.cleanup_schedule_enabled !== false;
      const cDay  = cfg.cleanup_day_of_week ?? 6;
      const days  = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];
      return `<div class="done-icon">✅</div>
        <div class="done-title">Attendable is ready!</div>
        <div class="done-sub" id="doneNextRun">Your events will be discovered automatically.</div>

        <div style="border:1px solid #e5e5ea;border-radius:10px;padding:.875rem;margin:.75rem 0">
          <div style="font-size:.72rem;font-weight:700;text-transform:uppercase;color:#aaa;margin-bottom:.6rem;letter-spacing:.05em">Schedule</div>
          <label style="display:flex;align-items:center;gap:.5rem;font-size:.82rem;margin-bottom:.5rem;flex-wrap:wrap">
            <input type="checkbox" id="wizSchedEnabled" ${sched?'checked':''}>
            Auto-run daily at
            <input class="setup-input" id="wizSchedHour" type="number" min="0" max="23" value="${hour}" style="width:56px;text-align:center">
            :
            <input class="setup-input" id="wizSchedMin" type="number" min="0" max="59" value="${String(min).padStart(2,'0')}" style="width:56px;text-align:center">
          </label>
          <label style="display:flex;align-items:center;gap:.5rem;font-size:.82rem;flex-wrap:wrap">
            <input type="checkbox" id="wizCleanEnabled" ${clean?'checked':''}>
            Auto-cleanup expired events every
            <select class="setup-select" id="wizCleanDay" style="width:auto">
              ${days.map((d,i)=>`<option value="${i}" ${i===cDay?'selected':''}>${d}</option>`).join('')}
            </select>
          </label>
        </div>

        <div class="backup-row">
          <button class="backup-btn" onclick="doBackup()" type="button">⬇ Download Backup</button>
          <button class="backup-btn" onclick="document.getElementById('restoreFileInput').click()" type="button">⬆ Restore from Backup</button>
        </div>
        <div id="setupMsg"></div>
        <p style="font-size:.72rem;color:#aaa;text-align:center;margin-top:.75rem">
          Data is auto-backed up before each Pinokio update.</p>`;
    }
    return '';
  }

  function _detectLlmProvider(cfg, evars) {
    evars = evars || {};
    if (evars.ANTHROPIC_API_KEY || (cfg._anthropic_set)) return 'anthropic';
    if (evars.OPENAI_API_KEY    || (cfg._openai_set))    return 'openai';
    if (evars.GEMINI_API_KEY    || (cfg._gemini_set))    return 'google';
    const base = evars.LLM_API_BASE || cfg.llm_api_base || '';
    if (base.includes('1234')) return 'lmstudio';
    if (base.includes('11434')) return 'ollama';
    return null;
  }

  function _detectSearchProvider(cfg, evars) {
    evars = evars || {};
    if (evars.BRAVE_API_KEY || cfg._brave_set)  return 'brave';
    if (evars.SERP_API_KEY  || cfg._serp_set)   return 'serpapi';
    if (evars.SEARXNG_URL   || cfg.searxng_url) return 'searxng';
    return 'ddg';
  }

  function _llmDetailHtml(provider, cfg, pfx='wiz') {
    if (!provider) return '<p class="setup-hint" style="margin-top:.5rem">Select a provider above.</p>';
    const evars = pfx === 'sett' ? _settingsEnvVars : _wizardEnvVars;
    const testFn = pfx === 'sett' ? 'testLlmConnSett' : 'testLlmConn';
    const _testConnBtn = `<div style="margin-top:.4rem">
      <button class="test-conn-btn" onclick="${testFn}()" type="button">⚡ Test Connection</button>
      <span class="test-conn-result" id="llmTestResult_${pfx}"></span>
    </div>`;
    if (provider === 'anthropic') return `
      <label class="setup-field-label">Anthropic API Key</label>
      <input class="setup-input" id="${pfx}AnthKey" type="password" placeholder="${cfg._anthropic_set ? '••••••••' : 'sk-ant-...'}"
             value="${evars.ANTHROPIC_API_KEY || ''}">
      <a class="setup-link" href="https://console.anthropic.com/settings/keys" target="_blank" rel="noopener">Get API key ↗</a>
      ${_testConnBtn}`;
    if (provider === 'openai') return `
      <label class="setup-field-label">OpenAI API Key</label>
      <input class="setup-input" id="${pfx}OpenaiKey" type="password" placeholder="${cfg._openai_set ? '••••••••' : 'sk-...'}"
             value="${evars.OPENAI_API_KEY || ''}">
      <a class="setup-link" href="https://platform.openai.com/api-keys" target="_blank" rel="noopener">Get API key ↗</a>
      <label class="setup-field-label" style="margin-top:.75rem">Model (optional)</label>
      <input class="setup-input" id="${pfx}LlmModel" type="text" placeholder="gpt-4o"
             value="${evars.LLM_MODEL || (cfg.llm_model && cfg.llm_model.startsWith('gpt') ? cfg.llm_model : '')}">
      ${_testConnBtn}`;
    if (provider === 'google') return `
      <label class="setup-field-label">Google Gemini API Key</label>
      <input class="setup-input" id="${pfx}GeminiKey" type="password" placeholder="${cfg._gemini_set ? '••••••••' : 'AIza...'}"
             value="${evars.GEMINI_API_KEY || ''}">
      <p class="setup-hint">Gemini 2.0 Flash has a generous free tier.</p>
      <a class="setup-link" href="https://aistudio.google.com/app/apikey" target="_blank" rel="noopener">Get API key ↗</a>
      ${_testConnBtn}`;
    if (provider === 'lmstudio') return `
      <label class="setup-field-label">LM Studio API Base URL</label>
      <input class="setup-input" id="${pfx}ApiBase" type="text" placeholder="http://localhost:1234/v1"
             value="${evars.LLM_API_BASE || cfg.llm_api_base || 'http://localhost:1234/v1'}">
      <p class="setup-hint">Start LM Studio, load a model, and enable the local server.</p>
      ${_testConnBtn}`;
    if (provider === 'ollama') return `
      <label class="setup-field-label">Ollama API Base URL</label>
      <input class="setup-input" id="${pfx}ApiBase" type="text" placeholder="http://localhost:11434"
             value="${evars.LLM_API_BASE || cfg.llm_api_base || 'http://localhost:11434'}">
      <label class="setup-field-label">Model</label>
      <input class="setup-input" id="${pfx}LlmModel" type="text" placeholder="ollama/llama3"
             value="${evars.LLM_MODEL || (cfg.llm_model && cfg.llm_model.startsWith('ollama') ? cfg.llm_model : 'ollama/llama3')}">
      ${_testConnBtn}`;
    return '';
  }

  function _searchDetailHtml(provider, cfg, pfx='wiz') {
    const evars = pfx === 'sett' ? _settingsEnvVars : _wizardEnvVars;
    const testFn = pfx === 'sett' ? 'testSearchConnSett' : 'testSearchConn';
    const _testConnBtn = `<div style="margin-top:.4rem">
      <button class="test-conn-btn" onclick="${testFn}()" type="button">⚡ Test Connection</button>
      <span class="test-conn-result" id="searchTestResult_${pfx}"></span>
    </div>`;
    if (provider === 'brave') return `
      <label class="setup-field-label">Brave Search API Key</label>
      <input class="setup-input" id="${pfx}BraveKey" type="password" placeholder="${cfg._brave_set ? '••••••••' : 'BSA...'}"
             value="${evars.BRAVE_API_KEY || ''}">
      <a class="setup-link" href="https://brave.com/search/api/" target="_blank" rel="noopener">Get API key ↗</a>
      ${_testConnBtn}`;
    if (provider === 'serpapi') return `
      <label class="setup-field-label">SerpAPI Key</label>
      <input class="setup-input" id="${pfx}SerpKey" type="password" placeholder="${cfg._serp_set ? '••••••••' : 'your key...'}"
             value="${evars.SERP_API_KEY || ''}">
      <a class="setup-link" href="https://serpapi.com/manage-api-key" target="_blank" rel="noopener">Get API key ↗</a>
      ${_testConnBtn}`;
    if (provider === 'searxng') return `
      <label class="setup-field-label">SearXNG URL</label>
      <input class="setup-input" id="${pfx}SearxUrl" type="text" placeholder="http://localhost:8080"
             value="${evars.SEARXNG_URL || cfg.searxng_url || 'http://localhost:8080'}">
      <p class="setup-hint">Run locally: <code>docker run -p 8080:8080 searxng/searxng</code></p>
      ${_testConnBtn}`;
    if (provider === 'ddg') return `
      <p class="setup-hint" style="margin-top:.5rem">
        DuckDuckGo requires no configuration. It will be used automatically as a fallback.</p>`;
    return '';
  }

  function _collectStep3() {
    const active = document.querySelector('#setupBody .provider-pill.active');
    if (!active) return;
    const p = active.textContent.trim().split(/\\s/)[0].toLowerCase();
    const val = id => { const el = document.getElementById(id); return el ? el.value.trim() : ''; };
    if (p === 'anthropic' && val('wizAnthKey'))   _wizardEnvVars.ANTHROPIC_API_KEY = val('wizAnthKey');
    if (p === 'openai'    && val('wizOpenaiKey')) _wizardEnvVars.OPENAI_API_KEY = val('wizOpenaiKey');
    if (p === 'google'    && val('wizGeminiKey')) _wizardEnvVars.GEMINI_API_KEY = val('wizGeminiKey');
    if ((p === 'lmstudio' || p === 'ollama') && val('wizApiBase')) _wizardEnvVars.LLM_API_BASE = val('wizApiBase');
    if (val('wizLlmModel')) _wizardEnvVars.LLM_MODEL = val('wizLlmModel');
  }

  function _collectStep4() {
    const active = document.querySelector('#setupBody .provider-pill.active');
    if (!active) return;
    const p = active.textContent.trim().split(/\\s/)[0].toLowerCase();
    const val = id => { const el = document.getElementById(id); return el ? el.value.trim() : ''; };
    if (p === 'brave'   && val('wizBraveKey')) _wizardEnvVars.BRAVE_API_KEY = val('wizBraveKey');
    if (p === 'serpapi' && val('wizSerpKey'))  _wizardEnvVars.SERP_API_KEY  = val('wizSerpKey');
    if (p === 'searxng' && val('wizSearxUrl')) {
      _wizardEnvVars.SEARXNG_URL = val('wizSearxUrl');
      _wizardConfigVars.searxng_url = val('wizSearxUrl');
    }
  }

  function _collectStep1() {
    const zip = document.getElementById('wizZip');
    const rad = document.getElementById('wizRadius');
    const lat = document.getElementById('wizLat');
    const lon = document.getElementById('wizLon');
    if (zip && zip.value.trim()) _wizardConfigVars.center_zip   = zip.value.trim();
    if (rad && rad.value)        _wizardConfigVars.radius_miles = parseInt(rad.value, 10);
    if (lat && lat.value.trim()) _wizardConfigVars.center_lat = parseFloat(lat.value);
    else if (lat && !lat.value.trim()) _wizardConfigVars.center_lat = null;
    if (lon && lon.value.trim()) _wizardConfigVars.center_lon = parseFloat(lon.value);
    else if (lon && !lon.value.trim()) _wizardConfigVars.center_lon = null;
  }

  let _wizKw = [];
  let _wizVk = [];

  function switchWizTab(tab) {
    document.getElementById('wizTabSources').style.display  = tab === 'sources'  ? '' : 'none';
    document.getElementById('wizTabKeywords').style.display = tab === 'keywords' ? '' : 'none';
    document.getElementById('wtabSrc').classList.toggle('active', tab === 'sources');
    document.getElementById('wtabKw').classList.toggle('active', tab === 'keywords');
    if (tab === 'keywords') renderWizKwChips();
  }

  function renderWizKwChips() {
    const kw = document.getElementById('wizKwTags');
    const vk = document.getElementById('wizVkTags');
    if (kw) kw.innerHTML = _wizKw.map((k,i) =>
      `<span class="kw-chip">${k}<button class="kw-chip-rm" onclick="removeWizKw(${i})" type="button">×</button></span>`).join('');
    if (vk) vk.innerHTML = _wizVk.map((k,i) =>
      `<span class="kw-chip">${k}<button class="kw-chip-rm" onclick="removeWizVk(${i})" type="button">×</button></span>`).join('');
  }

  function addWizKw() {
    const el = document.getElementById('wizKwInput');
    const v = el?.value.trim();
    if (v && !_wizKw.includes(v)) { _wizKw.push(v); renderWizKwChips(); }
    if (el) el.value = '';
  }
  function addWizVk() {
    const el = document.getElementById('wizVkInput');
    const v = el?.value.trim();
    if (v && !_wizVk.includes(v)) { _wizVk.push(v); renderWizKwChips(); }
    if (el) el.value = '';
  }
  function removeWizKw(i) { _wizKw.splice(i, 1); renderWizKwChips(); }
  function removeWizVk(i) { _wizVk.splice(i, 1); renderWizKwChips(); }

  function _collectStep2() {
    const enabled = _SOURCES.filter(s => {
      const el = document.getElementById('wizSrc_' + s.id);
      return el && el.checked;
    }).map(s => s.id);
    _wizardConfigVars.enabled_sources = enabled;
    _wizardConfigVars.user_keywords = _wizKw;
    _wizardConfigVars.vendor_virtual_keywords = _wizVk;
  }

  let _wizardCfg = {};

  async function showSetupWizard() {
    _wizardOpenedViaGear = (document.getElementById('setupOverlay').style.display === 'none');
    _wizardEnvVars = {};
    _wizardConfigVars = {};
    _wizardStep = 1;

    // Fetch current config for pre-population
    try {
      const [cfgRes, statusRes] = await Promise.all([
        fetch('/config').then(r => r.json()),
        fetch('/setup/status').then(r => r.json()),
      ]);
      _wizardCfg = cfgRes;
      // Annotate what keys are already set (without showing actual values)
      const status = statusRes;
      _wizardCfg._anthropic_set = status.configured?.llm && !cfgRes.llm_api_base;
      _wizardCfg._openai_set    = false;
      _wizardCfg._gemini_set    = false;
      _wizardCfg._brave_set     = false;
      _wizardCfg._serp_set      = false;
      _wizKw = [...(cfgRes.user_keywords || [])];
      _wizVk = [...(cfgRes.vendor_virtual_keywords || [])];
    } catch (_) { _wizardCfg = {}; }

    document.getElementById('btnSetupClose').style.display = _wizardOpenedViaGear ? '' : 'none';
    document.getElementById('setupCardTitle').textContent = _wizardOpenedViaGear ? 'Settings' : 'Welcome to Attendable';
    document.getElementById('setupOverlay').style.display = 'flex';
    document.body.style.overflow = 'hidden';
    _renderWizardStep();
  }

  function closeSetupWizard() {
    document.getElementById('setupOverlay').style.display = 'none';
    document.body.style.overflow = '';
  }

  function handleOverlayClick(ev) {
    if (ev.target === document.getElementById('setupOverlay') && _wizardOpenedViaGear) {
      closeSetupWizard();
    }
  }

  function _renderWizardStep() {
    const step = _wizardStep;
    document.getElementById('setupBody').innerHTML = _stepHtml(step, _wizardCfg);

    // Update step indicators
    for (let i = 1; i <= 5; i++) {
      const el = document.getElementById('stepInd' + i);
      el.className = 'setup-step' + (i < step ? ' done' : i === step ? ' active' : '');
      const num = el.querySelector('.setup-step-num');
      num.textContent = i < step ? '✓' : i;
    }

    const isFirst = step === 1;
    const isLast  = step === 5;
    const skipLabel = (isFirst && !_wizardOpenedViaGear) ? 'Configure later' : 'Skip';

    let footerHtml = '';
    if (!isFirst) footerHtml += `<button class="setup-btn-back" onclick="wizBack()">← Back</button>`;
    if (!isLast)  footerHtml += `<button class="setup-btn-next" onclick="wizNext()">Continue →</button>`;
    if (isLast)   footerHtml += `<button class="setup-btn-next" onclick="wizFinish(false)">Save Settings</button>
                                  <button class="setup-btn-next" style="background:#16a34a" onclick="wizFinish(true)">Save &amp; Start Discovering</button>`;
    footerHtml += `<button class="setup-btn-skip" onclick="closeSetupWizard()">${skipLabel}</button>`;
    document.getElementById('setupFooter').innerHTML = footerHtml;

    // Load next run time for step 5
    if (step === 5) {
      fetch('/config').then(r => r.json()).then(cfg => {
        const el = document.getElementById('doneNextRun');
        if (!el) return;
        if (cfg.next_run_at) {
          const d = new Date(cfg.next_run_at);
          el.textContent = `Next scheduled run: ${d.toLocaleDateString('en-US',{month:'short',day:'numeric'})} at ${d.toLocaleTimeString('en-US',{hour:'numeric',minute:'2-digit'})}`;
        } else {
          el.textContent = 'Scheduled daily run is disabled — use Run Pipeline to discover events.';
        }
      }).catch(() => {});
    }
  }

  async function wizNext() {
    if (_wizardStep === 1) _collectStep1();
    if (_wizardStep === 2) _collectStep2();
    if (_wizardStep === 3) _collectStep3();
    if (_wizardStep === 4) _collectStep4();
    if (_wizardStep < 5) { _wizardStep++; _renderWizardStep(); }
  }

  function wizBack() {
    if (_wizardStep > 1) { _wizardStep--; _renderWizardStep(); }
  }

  function _collectDone() {
    const sched = document.getElementById('wizSchedEnabled');
    const hour  = document.getElementById('wizSchedHour');
    const min   = document.getElementById('wizSchedMin');
    const clean = document.getElementById('wizCleanEnabled');
    const cday  = document.getElementById('wizCleanDay');
    if (sched) _wizardConfigVars.schedule_enabled           = sched.checked;
    if (hour)  _wizardConfigVars.schedule_hour              = parseInt(hour.value, 10);
    if (min)   _wizardConfigVars.schedule_minute            = parseInt(min.value, 10);
    if (clean) _wizardConfigVars.cleanup_schedule_enabled   = clean.checked;
    if (cday)  _wizardConfigVars.cleanup_day_of_week        = parseInt(cday.value, 10);
  }

  async function wizFinish(triggerRun_) {
    _collectStep1();
    _collectStep2();
    _collectStep3();
    _collectStep4();
    _collectDone();
    _wizardConfigVars.wizard_completed = true;

    try {
      const res = await fetch('/setup/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ env_vars: _wizardEnvVars, config_vars: _wizardConfigVars }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
    } catch (err) {
      const msg = document.getElementById('setupMsg');
      if (msg) { msg.textContent = '✕ ' + err.message; msg.className = 'err'; }
      return;
    }

    closeSetupWizard();
    loadNextRun();
    loadStats();
    if (triggerRun_) triggerRun();
  }

  async function testLlmConn() {
    const resultEl = document.getElementById('llmTestResult_wiz');
    if (!resultEl) return;
    resultEl.textContent = '…'; resultEl.className = 'test-conn-result';
    _collectStep3();
    const active = document.querySelector('#setupBody .provider-pill.active');
    const p = active ? active.textContent.trim().split(/\\s/)[0].toLowerCase() : '';
    const payload = {
      provider: p,
      api_key:  _wizardEnvVars.ANTHROPIC_API_KEY || _wizardEnvVars.OPENAI_API_KEY || _wizardEnvVars.GEMINI_API_KEY || '',
      model:    _wizardEnvVars.LLM_MODEL || '',
      api_base: _wizardEnvVars.LLM_API_BASE || '',
    };
    try {
      const res  = await fetch('/setup/test-llm', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      const data = await res.json();
      if (res.ok) { resultEl.textContent = '✓ Connected'; resultEl.className = 'test-conn-result ok'; }
      else { resultEl.textContent = '✕ ' + (data.detail || 'Failed'); resultEl.className = 'test-conn-result err'; }
    } catch(e) { resultEl.textContent = '✕ ' + e.message; resultEl.className = 'test-conn-result err'; }
  }

  async function testLlmConnSett() {
    const resultEl = document.getElementById('llmTestResult_sett');
    if (!resultEl) return;
    resultEl.textContent = '…'; resultEl.className = 'test-conn-result';
    const active = document.querySelector('#settingsBody .provider-pill.active');
    const p = active ? active.textContent.trim().split(/\\s/)[0].toLowerCase() : '';
    const val = id => { const el = document.getElementById(id); return el ? el.value.trim() : ''; };
    const payload = {
      provider: p,
      api_key:  val('settAnthKey') || val('settOpenaiKey') || val('settGeminiKey') || '',
      model:    val('settLlmModel') || '',
      api_base: val('settApiBase') || '',
    };
    try {
      const res  = await fetch('/setup/test-llm', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      const data = await res.json();
      if (res.ok) { resultEl.textContent = '✓ Connected'; resultEl.className = 'test-conn-result ok'; }
      else { resultEl.textContent = '✕ ' + (data.detail || 'Failed'); resultEl.className = 'test-conn-result err'; }
    } catch(e) { resultEl.textContent = '✕ ' + e.message; resultEl.className = 'test-conn-result err'; }
  }

  async function testSearchConn() {
    const resultEl = document.getElementById('searchTestResult_wiz');
    if (!resultEl) return;
    resultEl.textContent = '…'; resultEl.className = 'test-conn-result';
    _collectStep4();
    const active = document.querySelector('#setupBody .provider-pill.active');
    const p = active ? active.textContent.trim().split(/\\s/)[0].toLowerCase() : '';
    const payload = {
      provider: p,
      api_key:  _wizardEnvVars.BRAVE_API_KEY || _wizardEnvVars.SERP_API_KEY || '',
      url:      _wizardEnvVars.SEARXNG_URL || _wizardConfigVars.searxng_url || '',
    };
    try {
      const res  = await fetch('/setup/test-search', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      const data = await res.json();
      if (res.ok) { resultEl.textContent = '✓ Connected'; resultEl.className = 'test-conn-result ok'; }
      else { resultEl.textContent = '✕ ' + (data.detail || 'Failed'); resultEl.className = 'test-conn-result err'; }
    } catch(e) { resultEl.textContent = '✕ ' + e.message; resultEl.className = 'test-conn-result err'; }
  }

  async function testSearchConnSett() {
    const resultEl = document.getElementById('searchTestResult_sett');
    if (!resultEl) return;
    resultEl.textContent = '…'; resultEl.className = 'test-conn-result';
    const active = document.querySelector('#settingsBody .provider-pill.active');
    const p = active ? active.textContent.trim().split(/\\s/)[0].toLowerCase() : '';
    const val = id => { const el = document.getElementById(id); return el ? el.value.trim() : ''; };
    const payload = {
      provider: p,
      api_key:  val('settBraveKey') || val('settSerpKey') || '',
      url:      val('settSearxUrl') || '',
    };
    try {
      const res  = await fetch('/setup/test-search', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      const data = await res.json();
      if (res.ok) { resultEl.textContent = '✓ Connected'; resultEl.className = 'test-conn-result ok'; }
      else { resultEl.textContent = '✕ ' + (data.detail || 'Failed'); resultEl.className = 'test-conn-result err'; }
    } catch(e) { resultEl.textContent = '✕ ' + e.message; resultEl.className = 'test-conn-result err'; }
  }

  function selectLlmProvider(id) {
    _collectStep3();
    document.querySelectorAll('#setupBody .provider-pill').forEach(el => el.classList.remove('active'));
    event.currentTarget.classList.add('active');
    document.getElementById('llmDetail').innerHTML = _llmDetailHtml(id, _wizardCfg, 'wiz');
  }

  function selectSearchProvider(id) {
    _collectStep4();
    document.querySelectorAll('#setupBody .provider-pill').forEach(el => el.classList.remove('active'));
    event.currentTarget.classList.add('active');
    document.getElementById('searchDetail').innerHTML = _searchDetailHtml(id, _wizardCfg, 'wiz');
  }

  function selectLlmProviderSett(id) {
    document.querySelectorAll('#settingsBody .provider-pill').forEach(el => el.classList.remove('active'));
    event.currentTarget.classList.add('active');
    document.getElementById('settLlmDetail').innerHTML = _llmDetailHtml(id, _settingsCfg, 'sett');
  }

  function selectSearchProviderSett(id) {
    document.querySelectorAll('#settingsBody .provider-pill').forEach(el => el.classList.remove('active'));
    event.currentTarget.classList.add('active');
    document.getElementById('settSearchDetail').innerHTML = _searchDetailHtml(id, _settingsCfg, 'sett');
  }

  // Backup / restore
  async function doBackup() {
    const msg = document.getElementById('setupMsg');
    try {
      const res = await fetch('/backup', { method: 'POST' });
      if (!res.ok) throw new Error(await res.text());
      const blob = await res.blob();
      const cd   = res.headers.get('Content-Disposition') || '';
      const name = cd.match(/filename=([^;]+)/)?.[1] || 'attendable_backup.zip';
      const a    = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = name;
      a.click();
      if (msg) { msg.textContent = '✓ Backup downloaded'; msg.className = 'ok'; }
    } catch (err) {
      if (msg) { msg.textContent = '✕ Backup failed: ' + err.message; msg.className = 'err'; }
    }
  }

  async function doRestore(input) {
    const msg = document.getElementById('setupMsg');
    if (!input.files?.length) return;
    const fd = new FormData();
    fd.append('file', input.files[0]);
    input.value = '';
    try {
      const res = await fetch('/backup/restore', { method: 'POST', body: fd });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || res.statusText);
      if (msg) { msg.textContent = `✓ Restored: ${data.restored.join(', ')}. Reloading…`; msg.className = 'ok'; }
      setTimeout(() => location.reload(), 1500);
    } catch (err) {
      if (msg) { msg.textContent = '✕ Restore failed: ' + err.message; msg.className = 'err'; }
    }
  }

  // ── Welcome Banner ────────────────────────────────────────────────────────
  function showBanner() { document.getElementById('welcomeBanner').style.display = 'flex'; }
  async function dismissBanner() {
    document.getElementById('welcomeBanner').style.display = 'none';
    await fetch('/config', { method:'PATCH', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({wizard_completed: true}) });
  }
  function startWizardFromBanner() {
    document.getElementById('welcomeBanner').style.display = 'none';
    showSetupWizard();
  }

  // ── iCal Modal ────────────────────────────────────────────────────────────
  function showIcalModal() {
    document.getElementById('icalAll').checked = true;
    document.getElementById('icalModal').style.display = 'flex';
  }
  function closeIcalModal() {
    document.getElementById('icalModal').style.display = 'none';
  }
  function doIcalExport() {
    const sel = document.querySelector('input[name="icalFilter"]:checked');
    const filter = sel ? sel.value : 'all';
    const f = getFilters();
    const p = new URLSearchParams();
    p.set('from_date', new Date().toISOString());
    if (f.source)    p.set('source', f.source);
    if (f.eventType) p.set('event_type', f.eventType);
    if (activeTag)   p.set('tag', activeTag);
    if (filter !== 'all') p.set('interest_statuses', filter);
    const a = document.createElement('a');
    a.href = '/events/export.ics?' + p;
    a.download = 'attendable.ics';
    a.click();
    closeIcalModal();
  }

  // ── Settings Panel ────────────────────────────────────────────────────────
  let _settingsCfg = {};
  let _settingsEnvVars = {};

  function _renderSettingsBody(cfg) {
    const zip = cfg.center_zip || '';
    const rad = cfg.radius_miles || 120;
    const lat = cfg.center_lat != null ? cfg.center_lat : '';
    const lon = cfg.center_lon != null ? cfg.center_lon : '';
    const enabled = cfg.enabled_sources || ['eventbrite','meetup','luma','web_search'];
    const sourcesHtml = _SOURCES.map(s => `
      <label class="source-check-row">
        <input type="checkbox" id="settSrc_${s.id}" ${enabled.includes(s.id)?'checked':''}>
        <div><div class="source-name">${s.label}</div><div class="source-desc">${s.desc}</div></div>
      </label>`).join('');
    const activeLlm    = _detectLlmProvider(cfg, {});
    const activeSearch = _detectSearchProvider(cfg, {});
    const sched  = cfg.schedule_enabled !== false;
    const hour   = cfg.schedule_hour ?? 6;
    const min    = cfg.schedule_minute ?? 0;
    const clean  = cfg.cleanup_schedule_enabled !== false;
    const cDay   = cfg.cleanup_day_of_week ?? 6;
    const days   = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];
    return `
      <div class="sett-section">
        <div class="sett-section-title">Location</div>
        <div class="sett-row">
          <label for="settZip">ZIP Code</label>
          <input class="setup-input" id="settZip" type="text" maxlength="10" placeholder="e.g. 10001" value="${zip}" style="width:110px">
          <label for="settRadius" style="margin-left:.5rem">Radius</label>
          <select class="setup-select" id="settRadius" style="width:auto">
            ${[25,50,100,120,150,200].map(v => `<option value="${v}" ${v==rad?'selected':''}>${v} mi</option>`).join('')}
          </select>
        </div>
        <div class="sett-row">
          <label for="settLat">Lat <span style="font-weight:400;color:#aaa">(opt.)</span></label>
          <input class="setup-input" id="settLat" type="number" step="any" placeholder="e.g. 40.7128" value="${lat}" style="width:130px">
          <label for="settLon">Lon <span style="font-weight:400;color:#aaa">(opt.)</span></label>
          <input class="setup-input" id="settLon" type="number" step="any" placeholder="e.g. -74.0060" value="${lon}" style="width:130px">
        </div>
        <p class="sett-hint">Lat/Lon overrides ZIP centroid for distance calculations. ZIP still used for scraper URLs.</p>
      </div>
      <div class="sett-section">
        <div class="sett-section-title">Sources</div>
        ${sourcesHtml}
      </div>
      <div class="sett-section">
        <div class="sett-section-title">AI Provider</div>
        <div class="provider-pills">${_pillsHtml(_LLM_PROVIDERS, activeLlm, 'selectLlmProviderSett')}</div>
        <div class="provider-detail" id="settLlmDetail">${_llmDetailHtml(activeLlm, cfg, 'sett')}</div>
      </div>
      <div class="sett-section">
        <div class="sett-section-title">Search Provider</div>
        <div class="provider-pills">${_pillsHtml(_SEARCH_PROVIDERS, activeSearch, 'selectSearchProviderSett')}</div>
        <div class="provider-detail" id="settSearchDetail">${_searchDetailHtml(activeSearch, cfg, 'sett')}</div>
      </div>
      <div class="sett-section">
        <div class="sett-section-title">Schedule</div>
        <label style="display:flex;align-items:center;gap:.5rem;font-size:.82rem;margin-bottom:.5rem;flex-wrap:wrap">
          <input type="checkbox" id="settSchedEnabled" ${sched?'checked':''}>
          Auto-run daily at
          <input class="setup-input" id="settSchedHour" type="number" min="0" max="23" value="${hour}" style="width:56px;text-align:center">
          :
          <input class="setup-input" id="settSchedMin" type="number" min="0" max="59" value="${String(min).padStart(2,'0')}" style="width:56px;text-align:center">
        </label>
        <label style="display:flex;align-items:center;gap:.5rem;font-size:.82rem;flex-wrap:wrap">
          <input type="checkbox" id="settCleanEnabled" ${clean?'checked':''}>
          Auto-cleanup expired events every
          <select class="setup-select" id="settCleanDay" style="width:auto">
            ${days.map((d,i)=>`<option value="${i}" ${i===cDay?'selected':''}>${d}</option>`).join('')}
          </select>
        </label>
      </div>`;
  }

  function _collectSettingsConfig() {
    const val = id => { const el = document.getElementById(id); return el ? el.value.trim() : ''; };
    const chk = id => { const el = document.getElementById(id); return el ? el.checked : null; };
    const cfg = {};
    if (val('settZip'))    cfg.center_zip    = val('settZip');
    const rad = document.getElementById('settRadius');
    if (rad)               cfg.radius_miles  = parseInt(rad.value, 10);
    const lat = val('settLat'); const lon = val('settLon');
    cfg.center_lat = lat ? parseFloat(lat) : null;
    cfg.center_lon = lon ? parseFloat(lon) : null;
    cfg.enabled_sources = _SOURCES.filter(s => {
      const el = document.getElementById('settSrc_' + s.id); return el && el.checked;
    }).map(s => s.id);
    // LLM config vars
    const apiBase = val('settApiBase');
    if (apiBase) cfg.llm_api_base = apiBase;
    const llmModel = val('settLlmModel');
    if (llmModel) cfg.llm_model = llmModel;
    // Search config vars
    const searxUrl = val('settSearxUrl');
    if (searxUrl) cfg.searxng_url = searxUrl;
    // Schedule
    if (chk('settSchedEnabled') !== null) cfg.schedule_enabled = chk('settSchedEnabled');
    const sh = val('settSchedHour'); if (sh !== '') cfg.schedule_hour = parseInt(sh, 10);
    const sm = val('settSchedMin');  if (sm !== '') cfg.schedule_minute = parseInt(sm, 10);
    if (chk('settCleanEnabled') !== null) cfg.cleanup_schedule_enabled = chk('settCleanEnabled');
    const cd = document.getElementById('settCleanDay');
    if (cd) cfg.cleanup_day_of_week = parseInt(cd.value, 10);
    return cfg;
  }

  function _collectSettingsEnv() {
    const val = id => { const el = document.getElementById(id); return el ? el.value.trim() : ''; };
    const env = {};
    const active = document.querySelector('#settingsBody .provider-pill.active');
    const p = active ? active.textContent.trim().split(/\\s/)[0].toLowerCase() : '';
    if (p === 'anthropic' && val('settAnthKey'))   env.ANTHROPIC_API_KEY = val('settAnthKey');
    if (p === 'openai'    && val('settOpenaiKey')) env.OPENAI_API_KEY    = val('settOpenaiKey');
    if (p === 'google'    && val('settGeminiKey')) env.GEMINI_API_KEY    = val('settGeminiKey');
    if ((p === 'lmstudio' || p === 'ollama') && val('settApiBase')) env.LLM_API_BASE = val('settApiBase');
    if (val('settLlmModel')) env.LLM_MODEL = val('settLlmModel');
    if (val('settBraveKey')) env.BRAVE_API_KEY = val('settBraveKey');
    if (val('settSerpKey'))  env.SERP_API_KEY  = val('settSerpKey');
    if (val('settSearxUrl')) env.SEARXNG_URL   = val('settSearxUrl');
    return env;
  }

  async function showSettings() {
    try {
      const [cfgRes, statusRes] = await Promise.all([
        fetch('/config').then(r => r.json()),
        fetch('/setup/status').then(r => r.json()),
      ]);
      _settingsCfg = cfgRes;
      _settingsCfg._anthropic_set = statusRes.configured?.llm && !cfgRes.llm_api_base;
    } catch(_) { _settingsCfg = {}; }
    _settingsEnvVars = {};
    document.getElementById('settingsBody').innerHTML = _renderSettingsBody(_settingsCfg);
    document.getElementById('settingsMsg').textContent = '';
    document.getElementById('settingsOverlay').style.display = 'flex';
    document.body.style.overflow = 'hidden';
  }

  function closeSettings() {
    document.getElementById('settingsOverlay').style.display = 'none';
    document.body.style.overflow = '';
  }

  function handleSettingsOverlayClick(ev) {
    if (ev.target === document.getElementById('settingsOverlay')) closeSettings();
  }

  async function saveSettings() {
    const configVars = _collectSettingsConfig();
    const envVars    = _collectSettingsEnv();
    const msg = document.getElementById('settingsMsg');
    try {
      if (Object.keys(configVars).length)
        await fetch('/config', {method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify(configVars)});
      if (Object.keys(envVars).length)
        await fetch('/setup/', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({env_vars:envVars, config_vars:{}})});
      msg.textContent = '✓ Saved'; msg.style.color = '#16a34a';
      setTimeout(() => { msg.textContent = ''; }, 2500);
      loadNextRun(); loadStats();
    } catch(err) {
      msg.textContent = '✕ ' + err.message; msg.style.color = '#dc2626';
    }
  }

  // ── First-run banner IIFE ─────────────────────────────────────────────────
  (async () => {
    try {
      const status = await fetch('/setup/status').then(r => r.json());
      if (!status.wizard_completed) showBanner();
    } catch (_) {}
  })();

  load();
  loadThisWeek();
  loadNextRun();
  loadStats();
  loadTagsData();
</script>
</body>
</html>"""


@router.get("/")
async def browse_ui():
    return HTMLResponse(_HTML)
