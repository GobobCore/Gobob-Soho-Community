// js/app.js — Gobob SOHO 服务平台主逻辑（路由 + 导航）
(function () {
  const { createApp } = Vue;
  const S = window.SohoShared;
  const V = window.SohoViews;

  const app = createApp({
    components: {
      "login-view": V.LoginView,
      "register-view": V.RegisterView,
      "dashboard-view": V.DashboardView,
      "leads-view": V.LeadsView,
      "lead-detail": V.LeadDetail,
      "students-view": V.StudentsView,
      "student-detail": V.StudentDetail,
      "contracts-view": V.ContractsView,
      "staff-view": V.StaffView,
      "collisions-view": V.CollisionsView,
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
        loggedIn: !!S.getToken(),  // 响应式登录态
        toast: { msg: "", type: "ok" },
        user: S.getUser() || {},
        // R-Refactor 2026-09-17: 未登录态下显示 login 或 register (由 hash 决定)
        authView: (location.hash.replace(/^#\//, "") === "register") ? "register" : "login",
        // Phase 5: 家长多学生切换
        myStudents: [],          // 家长关联的所有学生
        activeStudentId: null,   // 当前选中的学生
      };
    },
    computed: {
      shared() { return S; },
      roleLabel() {
        return { owner: "主管", advisor: "顾问", student: "学生", parent: "家长" }[this.user.role] || "";
      },
      // Phase 5: 家长角色判断（用于学生切换器显隐）
      role() { return this.user.role; },
      ctx() {
        return {
          shared: S,
          toast: this.showToast,
          go: this.go,
          // Phase 5: 让家长端视图知道当前选中的学生
          activeStudentId: this.activeStudentId,
          myStudents: this.myStudents,
        };
      },
      // 导航按角色分组（即时计算当前角色，不用挂载期缓存的 S.isStaff）
      navGroups() {
        const role = this.user.role;
        const isStaff = role === "owner" || role === "advisor";
        const isOwner = role === "owner";
        const I = S.ICONS;  // R-Design 2026-09-16: 扁平化 SVG 图标 (替代 emoji)
        if (isStaff) {
          const g = [
            { title: "总览", items: [{ view: "dashboard", label: "驾驶舱", icon: I.dashboard }] },
            { title: "业务", items: [
              { view: "leads", label: "线索池", icon: I.leads },
              { view: "students", label: "学生", icon: I.students },
              { view: "contracts", label: "签约", icon: I.contracts },
            ] },
          ];
          if (isOwner) {
            g.push({ title: "管理", items: [
              { view: "staff", label: "员工", icon: I.staff },
              { view: "collisions", label: "撞单", icon: I.collisions },
              { view: "reports", label: "报表", icon: I.reports },
              { view: "settings", label: "设置", icon: I.settings },
            ] });
          }
          g.push({ title: "沟通", items: [
            { view: "messages", label: "消息", icon: I.messages },
            { view: "notifications", label: "通知", icon: I.notifications },
          ] });
          return g;
        }
        // 学生/家长端
        return [
          { title: "我的", items: [
            { view: "my-progress", label: "我的进度", icon: I.myProgress },
            { view: "my-tasks", label: "我的任务", icon: I.myTasks },
            { view: "my-contract", label: "我的合同", icon: I.myContract },
          ] },
          { title: "沟通", items: [
            { view: "messages", label: "消息", icon: I.messages },
            { view: "notifications", label: "通知", icon: I.notifications },
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
        this.loadMyStudents();
        this.go(this.isStaffNow ? "dashboard" : "my-progress");
      },
      logout() {
        S.clearAuth();
        location.hash = "#/login";
        this.currentView = "";
        this.loggedIn = false;
        this.user = {};
        this.myStudents = [];
        this.activeStudentId = null;
      },
      // Phase 5: 家长多学生
      async loadMyStudents() {
        if (this.user.role !== "parent") return;
        try {
          const d = await S.get(`/api/relationships/parent/${this.user.member_id}/students`);
          this.myStudents = d.students || [];
          if (this.myStudents.length) {
            // 默认选第一个（或 localStorage 记忆）
            const saved = localStorage.getItem("soho_active_student");
            const valid = this.myStudents.find(s => s.id === saved);
            this.activeStudentId = (valid || this.myStudents[0]).id;
          }
        } catch (e) { /* 家长可能还没关联，静默 */ }
      },
      switchStudent() {
        localStorage.setItem("soho_active_student", this.activeStudentId);
        // 强制当前视图重载
        this.currentView = "";
        this.$nextTick(() => {
          this.currentView = this.isStaffNow ? "dashboard" : "my-progress";
        });
      },
    },
    mounted() {
      // hash 路由恢复
      const h = location.hash.replace(/^#\//, "");
      if (this.loggedIn) {
        // R-Fix 2026-09-17 18:10: 如果 hash 是 #/login (用户主动登出或访问根 #/login) 但本地有 token, 清 token 重置为未登录态.
        if (h === "login" || h === "register") {
          S.clearAuth();
          this.loggedIn = false;
          this.user = {};
          this.authView = (h === "register") ? "register" : "login";
          return;
        }
        this.user = S.getUser() || {};
        this.loadMyStudents();  // Phase 5
        const allowed = this.navGroups.flatMap(g => g.items.map(i => i.view));
        this.currentView = allowed.includes(h) ? h : (this.isStaffNow ? "dashboard" : "my-progress");
      } else if (h === "register") {
        this.authView = "register";
      } else {
        this.authView = "login";
      }
      window.addEventListener("hashchange", () => {
        const v = location.hash.replace(/^#\//, "");
        if (this.loggedIn) {
          // 用户点登出 (hash=#/login) 或访问 register, 清 token
          if (v === "login" || v === "register") {
            S.clearAuth();
            this.loggedIn = false;
            this.user = {};
            this.myStudents = [];
            this.currentView = "";
            this.authView = (v === "register") ? "register" : "login";
            return;
          }
          const allowed = this.navGroups.flatMap(g => g.items.map(i => i.view));
          if (allowed.includes(v)) this.currentView = v;
        } else if (v === "register") {
          this.authView = "register";
        } else if (v === "login" || v === "") {
          this.authView = "login";
        }
      });
    },
  });

  // 全局注册所有视图（含子组件 lead-detail / student-detail），
  // 解决 views.js 里"先用后定义"导致局部 components 快照为 undefined 的问题。
  app.component("login-view", V.LoginView);
  app.component("register-view", V.RegisterView);
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
