// js/app.js — Gobob SOHO 服务平台主逻辑（路由 + 导航）
(function () {
  const { createApp } = Vue;
  const S = window.SohoShared;
  const V = window.SohoViews;

  const app = createApp({
    components: {
      "login-view": V.LoginView,
      "dashboard-view": V.DashboardView,
      "leads-view": V.LeadsView,
      "lead-detail": V.LeadDetail,
      "students-view": V.StudentsView,
      "student-detail": V.StudentDetail,
      "contracts-view": V.ContractsView,
      "staff-view": V.StaffView,
      "reports-view": V.ReportsView,
      "settings-view": V.SettingsView,
      "my-progress-view": V.MyProgressView,
      "my-tasks-view": V.MyTasksView,
      "my-contract-view": V.MyContractView,
      "messages-view": V.MessagesView,
      "notifications-view": V.NotificationsView,
    },
    data() {
      return {
        currentView: "",
        loggedIn: !!S.getToken(),  // 响应式登录态（替代模板里直调 S.getToken() 不响应的问题）
        toast: { msg: "", type: "ok" },
        user: S.getUser() || {},
      };
    },
    computed: {
      shared() { return S; },
      roleLabel() {
        return { owner: "主管", advisor: "顾问", student: "学生", parent: "家长" }[this.user.role] || "";
      },
      ctx() {
        return { shared: S, toast: this.showToast, go: this.go };
      },
      // 导航按角色分组（即时计算当前角色，不用挂载期缓存的 S.isStaff）
      navGroups() {
        const role = this.user.role;
        const isStaff = role === "owner" || role === "advisor";
        const isOwner = role === "owner";
        if (isStaff) {
          const g = [
            { title: "总览", items: [{ view: "dashboard", label: "驾驶舱", icon: "📊" }] },
            { title: "业务", items: [
              { view: "leads", label: "线索池", icon: "🎯" },
              { view: "students", label: "学生", icon: "👨‍🎓" },
              { view: "contracts", label: "签约", icon: "📄" },
            ] },
          ];
          if (isOwner) {
            g.push({ title: "管理", items: [
              { view: "staff", label: "员工", icon: "👥" },
              { view: "reports", label: "报表", icon: "📈" },
              { view: "settings", label: "设置", icon: "⚙️" },
            ] });
          }
          g.push({ title: "沟通", items: [
            { view: "messages", label: "消息", icon: "💬" },
            { view: "notifications", label: "通知", icon: "🔔" },
          ] });
          return g;
        }
        // 学生/家长端
        return [
          { title: "我的", items: [
            { view: "my-progress", label: "我的进度", icon: "🗺️" },
            { view: "my-tasks", label: "我的任务", icon: "✅" },
            { view: "my-contract", label: "我的合同", icon: "📄" },
          ] },
          { title: "沟通", items: [
            { view: "messages", label: "消息", icon: "💬" },
            { view: "notifications", label: "通知", icon: "🔔" },
          ] },
        ];
      },
      isStaffNow() { const r = this.user.role; return r === "owner" || r === "advisor"; },
      currentComponent() { return this.currentView + "-view"; },
    },
    methods: {
      showToast(msg, type = "ok") {
        this.toast = { msg, type };
        clearTimeout(this._tt);
        this._tt = setTimeout(() => (this.toast.msg = ""), 3000);
      },
      go(view) {
        this.currentView = view;
        location.hash = "#/" + view;
      },
      onLoggedIn() {
        this.user = S.getUser() || {};
        this.loggedIn = true;
        this.go(this.isStaffNow ? "dashboard" : "my-progress");
      },
      logout() {
        S.clearAuth();
        location.hash = "#/login";
        this.currentView = "";
        this.loggedIn = false;
        this.user = {};
      },
    },
    mounted() {
      // hash 路由恢复
      const h = location.hash.replace(/^#\//, "");
      if (this.loggedIn) {
        this.user = S.getUser() || {};
        const allowed = this.navGroups.flatMap(g => g.items.map(i => i.view));
        this.currentView = allowed.includes(h) ? h : (this.isStaffNow ? "dashboard" : "my-progress");
      }
      window.addEventListener("hashchange", () => {
        const v = location.hash.replace(/^#\//, "");
        const allowed = this.navGroups.flatMap(g => g.items.map(i => i.view));
        if (this.loggedIn && allowed.includes(v)) this.currentView = v;
      });
    },
  });

  // 全局注册所有视图（含子组件 lead-detail / student-detail），
  // 解决 views.js 里"先用后定义"导致局部 components 快照为 undefined 的问题。
  app.component("login-view", V.LoginView);
  app.component("dashboard-view", V.DashboardView);
  app.component("leads-view", V.LeadsView);
  app.component("lead-detail", V.LeadDetail);
  app.component("students-view", V.StudentsView);
  app.component("student-detail", V.StudentDetail);
  app.component("contracts-view", V.ContractsView);
  app.component("staff-view", V.StaffView);
  app.component("reports-view", V.ReportsView);
  app.component("settings-view", V.SettingsView);
  app.component("my-progress-view", V.MyProgressView);
  app.component("my-tasks-view", V.MyTasksView);
  app.component("my-contract-view", V.MyContractView);
  app.component("messages-view", V.MessagesView);
  app.component("notifications-view", V.NotificationsView);

  app.mount("#app");
})();
