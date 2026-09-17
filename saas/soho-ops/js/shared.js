// js/shared.js — SOHO SaaS 运营后台 共享层
window.OpsShared = (function () {
  const TOKEN_KEY = "soho_ops_token";
  const ADMIN_KEY = "soho_ops_admin";

  function getToken() { return localStorage.getItem(TOKEN_KEY) || ""; }
  function getAdmin() {
    try { return JSON.parse(localStorage.getItem(ADMIN_KEY) || "null"); } catch { return null; }
  }
  function setAuth(token, admin) {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(ADMIN_KEY, JSON.stringify(admin));
  }
  function clearAuth() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(ADMIN_KEY);
  }

  async function api(path, opts = {}) {
    let p = path;
    const m = (opts.method || "GET").toUpperCase();
    if (m !== "GET" && p.indexOf("?") === -1 && !p.endsWith("/")) p += "/";
    const headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
    const tok = getToken();
    if (tok) headers["Authorization"] = "Bearer " + tok;
    let res;
    try {
      res = await fetch(p, { ...opts, headers, redirect: "follow" });
    } catch (e) {
      throw new Error("网络错误：" + e.message);
    }
    if (res.status === 401) { clearAuth(); location.hash = "#/login"; throw new Error("登录已过期"); }
    let data = null;
    try { data = await res.json(); } catch { }
    if (!res.ok) {
      const msg = (data && (data.detail || data.message)) || ("请求失败 " + res.status);
      throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
    }
    return data;
  }
  const get = (p) => api(p);
  const post = (p, body) => api(p, { method: "POST", body: JSON.stringify(body || {}) });
  const put = (p, body) => api(p, { method: "PUT", body: JSON.stringify(body || {}) });

  function fmtDate(s) { if (!s) return "—"; return String(s).slice(0, 10); }
  function fmtMoney(n) { if (n == null) return "—"; return "¥" + Number(n).toLocaleString(); }
  const PLAN_LABEL = { free: "免费版", trial: "试用", paid: "付费版", suspended: "已停用" };
  const INV_STATUS_LABEL = { pending: "待收", paid: "已收", void: "作废" };

  // SVG 图标 (跟 SOHO app 同一套风格)
  function svg(paths) {
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="inline-block w-4 h-4 align-text-bottom">${paths}</svg>`;
  }
  const ICONS = {
    orgs: svg('<path d="M3 21h18"/><path d="M5 21V7l7-4 7 4v14"/><path d="M9 21v-6h6v6"/><path d="M9 10h.01"/><path d="M15 10h.01"/>'),
    invoices: svg('<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/>'),
    usage: svg('<path d="M3 3v16a2 2 0 0 0 2 2h16"/><path d="M7 13l3-3 4 4 5-6"/>'),
    dashboard: svg('<rect width="7" height="9" x="3" y="3" rx="1"/><rect width="7" height="5" x="14" y="3" rx="1"/><rect width="7" height="9" x="14" y="12" rx="1"/><rect width="7" height="5" x="3" y="16" rx="1"/>'),
    keyOrders: svg('<path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/>'),
  };

  return {
    getToken, getAdmin, setAuth, clearAuth,
    api, get, post, put,
    fmtDate, fmtMoney, PLAN_LABEL, INV_STATUS_LABEL, ICONS,
  };
})();
