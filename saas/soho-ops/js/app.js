// js/app.js — SOHO SaaS 运营后台 主逻辑（路由 + 导航）
(function () {
  const { createApp } = Vue;
  const S = window.OpsShared;
  const V = window.OpsViews;

  const app = createApp({
    components: {
      "login-view": V.LoginView,
      "orgs-view": V.OrgsView,
      "org-detail-view": V.OrgDetailView,
      "invoices-view": V.InvoicesView,
      "usage-view": V.UsageView,
      "key-orders-view": V.KeyOrdersView,
    },
    data() {
      return {
        currentView: "",
        currentOrgId: null,
        loggedIn: !!S.getToken(),
        toast: { msg: "", type: "ok" },
        admin: S.getAdmin() || {},
        nav: [
          { view: "orgs", label: "机构", icon: S.ICONS.orgs },
          { view: "key-orders", label: "开源版订单", icon: S.ICONS.keyOrders },
          { view: "invoices", label: "账单", icon: S.ICONS.invoices },
          { view: "usage", label: "API 用量", icon: S.ICONS.usage },
        ],
      };
    },
    computed: {
      shared() { return S; },
      currentComponent() { return this.currentView + "-view"; },
      ctx() {
        return {
          shared: S,
          toast: this.showToast,
          go: this.go,
          params: { id: this.currentOrgId },
        };
      },
    },
    methods: {
      showToast(msg, type = "ok") {
        this.toast = { msg, type };
        clearTimeout(this._tt);
        this._tt = setTimeout(() => (this.toast.msg = ""), 3000);
      },
      go(view, orgId) {
        if (view === "org-detail") {
          this.currentOrgId = orgId;
          this.currentView = "org-detail";
          location.hash = "#/" + view + "/" + orgId;
        } else {
          this.currentOrgId = null;
          this.currentView = view;
          location.hash = "#/" + view;
        }
      },
      onLoggedIn() {
        this.admin = S.getAdmin() || {};
        this.loggedIn = true;
        this.go("orgs");
      },
      logout() {
        S.clearAuth();
        location.hash = "#/login";
        this.currentView = "";
        this.loggedIn = false;
        this.admin = {};
      },
    },
    mounted() {
      const hash = location.hash.replace(/^#\//, "");
      if (this.loggedIn) {
        const parts = hash.split("/");
        if (parts[0] === "org-detail" && parts[1]) {
          this.currentOrgId = parts[1];
          this.currentView = "org-detail";
        } else if (["orgs", "invoices", "usage", "key-orders"].includes(parts[0])) {
          this.currentView = parts[0];
        } else {
          this.currentView = "orgs";
        }
      }
      window.addEventListener("hashchange", () => {
        const h = location.hash.replace(/^#\//, "");
        const parts = h.split("/");
        if (parts[0] === "org-detail" && parts[1]) {
          this.currentOrgId = parts[1];
          this.currentView = "org-detail";
        } else if (["orgs", "invoices", "usage", "key-orders"].includes(parts[0])) {
          this.currentOrgId = null;
          this.currentView = parts[0];
        }
      });
    },
  });

  app.mount("#app");
})();
