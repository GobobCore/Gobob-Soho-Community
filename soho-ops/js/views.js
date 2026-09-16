// js/views.js — SOHO SaaS 运营后台 视图
(function () {
  const { defineComponent } = Vue;
  const S = () => window.OpsShared;

  // ── 共用小组件 ────────────────────────────────────────────────
  const Card = defineComponent({
    props: ["title"],
    template: `<div class="bg-white rounded-2xl border border-slate-200/70 shadow-sm p-5">
      <h3 v-if="title" class="font-semibold text-slate-700 mb-3">{{ title }}</h3>
      <slot></slot>
    </div>`,
  });
  const Stat = defineComponent({
    props: ["label", "value", "sub", "color"],
    template: `<div class="bg-white rounded-2xl border border-slate-200/70 shadow-sm p-5">
      <div class="text-xs text-slate-400">{{ label }}</div>
      <div class="text-2xl font-bold mt-1" :class="color||'text-slate-800'">{{ value }}</div>
      <div v-if="sub" class="text-xs text-slate-400 mt-1">{{ sub }}</div>
    </div>`,
  });

  // ── 登录 ──────────────────────────────────────────────────────
  const LoginView = defineComponent({
    data: () => ({ username: "", password: "", loading: false, error: "" }),
    template: `
    <div class="min-h-screen flex items-center justify-center p-4">
      <div class="w-full max-w-sm">
        <div class="text-center mb-8">
          <div class="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-br from-[#E08A44] to-[#C97636] shadow-[0_8px_24px_rgba(224,138,68,0.4)] mb-4">
            <img src="/logo.svg" class="w-8 h-8 brightness-0 invert" />
          </div>
          <h1 class="text-2xl font-bold tracking-tight">Gobob SOHO</h1>
          <p class="text-sm text-slate-500 mt-1">SaaS 运营后台</p>
        </div>
        <div class="bg-white rounded-2xl border border-slate-200/70 shadow-sm p-6">
          <div v-if="error" class="mb-4 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-3 py-2">{{ error }}</div>
          <label class="block text-sm font-medium text-slate-600 mb-1">用户名</label>
          <input v-model="username" @keyup.enter="submit" class="w-full border rounded-lg px-3 py-2 text-sm mb-4 focus:outline-none focus:ring-2 focus:ring-[#E08A44]" placeholder="运营账号" />
          <label class="block text-sm font-medium text-slate-600 mb-1">密码</label>
          <input v-model="password" type="password" @keyup.enter="submit" class="w-full border rounded-lg px-3 py-2 text-sm mb-5 focus:outline-none focus:ring-2 focus:ring-[#E08A44]" placeholder="••••••••" />
          <button @click="submit" :disabled="loading" class="btn-primary w-full py-2.5 disabled:opacity-50">
            {{ loading ? '登录中…' : '登录' }}
          </button>
        </div>
        <p class="text-center text-xs text-slate-400 mt-6">仅限 Gobob 运营方 · 机构用户请用服务平台</p>
      </div>
    </div>`,
    methods: {
      async submit() {
        if (!this.username || !this.password) { this.error = "请输入用户名和密码"; return; }
        this.loading = true; this.error = "";
        try {
          const d = await S().post("/api/saas/login", { username: this.username, password: this.password });
          S().setAuth(d.token, d.admin);
          this.$emit("logged-in");
        } catch (e) { this.error = e.message; }
        this.loading = false;
      },
    },
  });

  // ── 机构列表 ──────────────────────────────────────────────────
  const OrgsView = defineComponent({
    components: { Card, Stat },
    props: ["ctx"],
    data: () => ({ items: [], summary: {}, loading: true, q: "", status: "" }),
    template: `
    <div>
      <h1 class="text-xl font-bold mb-4">机构账户</h1>

      <div class="grid grid-cols-4 gap-4 mb-6">
        <stat label="机构总数" :value="summary.total_orgs||0"></stat>
        <stat label="付费机构" :value="summary.paid_orgs||0" color="text-emerald-600"></stat>
        <stat label="免费机构" :value="summary.free_orgs||0"></stat>
        <stat label="年费应收合计" :value="ctx.shared.fmtMoney(summary.total_annual_fee||0)" color="text-[#C97636]"></stat>
      </div>

      <card>
        <div class="flex gap-2 mb-4">
          <input v-model="q" @input="load" placeholder="搜索机构名…" class="border rounded-lg px-3 py-1.5 text-sm flex-1 max-w-xs focus:outline-none focus:ring-2 focus:ring-[#E08A44]" />
          <select v-model="status" @change="load" class="border rounded-lg px-3 py-1.5 text-sm">
            <option value="">全部状态</option>
            <option value="free">免费版</option>
            <option value="trial">试用</option>
            <option value="paid">付费版</option>
            <option value="suspended">已停用</option>
          </select>
        </div>

        <div v-if="loading" class="text-sm text-slate-400 py-8 text-center">加载中…</div>
        <div v-else-if="!items.length" class="text-sm text-slate-400 py-8 text-center">暂无机构</div>
        <table v-else class="w-full text-sm">
          <thead>
            <tr class="text-left text-xs text-slate-400 border-b">
              <th class="pb-2 font-medium">机构</th>
              <th class="pb-2 font-medium">状态</th>
              <th class="pb-2 font-medium text-right">协作账号</th>
              <th class="pb-2 font-medium text-right">学生/家长</th>
              <th class="pb-2 font-medium text-right">应收年费</th>
              <th class="pb-2 font-medium">有效期至</th>
              <th class="pb-2 font-medium"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="o in items" :key="o.id" class="border-b last:border-0 hover:bg-slate-50">
              <td class="py-3">
                <div class="font-medium">{{ o.name }}</div>
                <div class="text-xs text-slate-400">{{ o.contact_name || '—' }}</div>
              </td>
              <td>
                <span :class="'badge badge-'+o.plan_status">{{ ctx.shared.PLAN_LABEL[o.plan_status] }}</span>
                <span v-if="o.disabled" class="badge badge-suspended ml-1">已禁用</span>
              </td>
              <td class="text-right">
                <span :class="o.is_over_free?'font-bold text-[#C97636]':''">{{ o.seats_collab }}</span>
                <span class="text-xs text-slate-400">/ {{ o.seats_paid||0 }} 已付</span>
              </td>
              <td class="text-right text-slate-500">{{ o.seats_student }}/{{ o.seats_parent }}</td>
              <td class="text-right font-medium">{{ o.plan_status==='paid' ? ctx.shared.fmtMoney(o.annual_fee) : '—' }}</td>
              <td class="text-slate-500">{{ ctx.shared.fmtDate(o.paid_until) }}</td>
              <td>
                <button @click="ctx.go('org-detail', o.id)" class="text-[#C97636] hover:underline text-xs">详情</button>
              </td>
            </tr>
          </tbody>
        </table>
      </card>
    </div>`,
    async mounted() { this.load(); },
    methods: {
      async load() {
        this.loading = true;
        try {
          const params = new URLSearchParams();
          if (this.q) params.set("q", this.q);
          if (this.status) params.set("status", this.status);
          const d = await S().get("/api/saas/orgs?" + params);
          this.items = d.items; this.summary = d.summary;
        } catch (e) { this.ctx.toast(e.message, "error"); }
        this.loading = false;
      },
    },
  });

  // ── 机构详情 ──────────────────────────────────────────────────
  const OrgDetailView = defineComponent({
    components: { Card, Stat },
    props: ["ctx"],
    data: () => ({ org: null, invoices: [], usage: [], loading: true, editing: false, form: {}, newInv: null, showNewInv: false }),
    template: `
    <div>
      <button @click="ctx.go('orgs')" class="text-sm text-slate-500 hover:text-slate-800 mb-3">← 返回机构列表</button>
      <div v-if="loading" class="text-sm text-slate-400 py-8 text-center">加载中…</div>
      <template v-else-if="org">
        <div class="flex items-start justify-between mb-6">
          <div>
            <h1 class="text-xl font-bold">{{ org.name }}</h1>
            <div class="text-sm text-slate-400 mt-1">{{ org.id }}</div>
          </div>
          <div class="flex gap-2">
            <span :class="'badge badge-'+org.plan_status+' text-sm px-3 py-1'">{{ ctx.shared.PLAN_LABEL[org.plan_status] }}</span>
            <button v-if="!org.disabled" @click="toggleDisable(true)" class="text-xs text-red-500 border border-red-200 rounded-lg px-3 py-1.5 hover:bg-red-50">停用机构</button>
            <button v-else @click="toggleDisable(false)" class="text-xs text-emerald-600 border border-emerald-200 rounded-lg px-3 py-1.5 hover:bg-emerald-50">恢复机构</button>
          </div>
        </div>

        <div class="grid grid-cols-4 gap-4 mb-6">
          <stat label="协作账号 (owner+advisor)" :value="org.seats_collab" :sub="'已付费 '+org.seats_paid"></stat>
          <stat label="超免费席数" :value="org.seats_billable" :color="org.is_over_free?'text-[#C97636]':''"></stat>
          <stat label="应收年费" :value="ctx.shared.fmtMoney(org.annual_fee)" color="text-[#C97636]"></stat>
          <stat label="付费有效期至" :value="ctx.shared.fmtDate(org.paid_until)"></stat>
        </div>

        <div class="grid grid-cols-2 gap-4 mb-6">
          <card title="订阅信息">
            <div v-if="!editing">
              <dl class="text-sm space-y-2">
                <div class="flex justify-between"><dt class="text-slate-400">状态</dt><dd>{{ ctx.shared.PLAN_LABEL[org.plan_status] }}</dd></div>
                <div class="flex justify-between"><dt class="text-slate-400">已付席位</dt><dd>{{ org.seats_paid }}</dd></div>
                <div class="flex justify-between"><dt class="text-slate-400">有效期至</dt><dd>{{ ctx.shared.fmtDate(org.paid_until) }}</dd></div>
                <div class="flex justify-between"><dt class="text-slate-400">对接人</dt><dd>{{ org.contact_name || '—' }}</dd></div>
                <div class="flex justify-between"><dt class="text-slate-400">电话</dt><dd>{{ org.contact_phone || '—' }}</dd></div>
                <div class="flex justify-between"><dt class="text-slate-400">邮箱</dt><dd>{{ org.contact_email || '—' }}</dd></div>
              </dl>
              <button @click="startEdit" class="btn-primary mt-4 w-full">编辑订阅</button>
            </div>
            <div v-else class="space-y-3">
              <div>
                <label class="text-xs text-slate-500">状态</label>
                <select v-model="form.plan_status" class="w-full border rounded-lg px-2 py-1.5 text-sm">
                  <option value="free">免费版</option><option value="trial">试用</option>
                  <option value="paid">付费版</option><option value="suspended">已停用</option>
                </select>
              </div>
              <div class="grid grid-cols-2 gap-2">
                <div><label class="text-xs text-slate-500">已付席位</label>
                  <input v-model.number="form.seats_paid" type="number" class="w-full border rounded-lg px-2 py-1.5 text-sm" /></div>
                <div><label class="text-xs text-slate-500">有效期至</label>
                  <input v-model="form.paid_until" type="date" class="w-full border rounded-lg px-2 py-1.5 text-sm" /></div>
              </div>
              <div><label class="text-xs text-slate-500">对接人</label>
                <input v-model="form.contact_name" class="w-full border rounded-lg px-2 py-1.5 text-sm" /></div>
              <div><label class="text-xs text-slate-500">电话</label>
                <input v-model="form.contact_phone" class="w-full border rounded-lg px-2 py-1.5 text-sm" /></div>
              <div><label class="text-xs text-slate-500">邮箱</label>
                <input v-model="form.contact_email" class="w-full border rounded-lg px-2 py-1.5 text-sm" /></div>
              <div class="flex gap-2">
                <button @click="saveEdit" class="btn-primary flex-1">保存</button>
                <button @click="editing=false" class="px-4 py-2 text-sm text-slate-500 border rounded-lg">取消</button>
              </div>
            </div>
          </card>

          <card title="近 30 天 API 用量">
            <div v-if="!usage.length" class="text-sm text-slate-400 py-4 text-center">近 30 天无调用</div>
            <table v-else class="w-full text-sm">
              <thead><tr class="text-left text-xs text-slate-400 border-b">
                <th class="pb-2 font-medium">日期</th><th class="pb-2 font-medium">端点</th><th class="pb-2 font-medium text-right">次数</th>
              </tr></thead>
              <tbody>
                <tr v-for="(u,i) in usage.slice(0,15)" :key="i" class="border-b last:border-0">
                  <td class="py-2">{{ u.usage_date }}</td>
                  <td class="text-slate-500 text-xs">{{ u.endpoint }}</td>
                  <td class="text-right font-medium">{{ u.calls }}</td>
                </tr>
              </tbody>
            </table>
          </card>
        </div>

        <card>
          <template #default>
            <div class="flex items-center justify-between mb-3">
              <h3 class="font-semibold text-slate-700">账单</h3>
              <button @click="showNewInv=!showNewInv" class="btn-primary text-xs">+ 开账单</button>
            </div>
            <div v-if="showNewInv" class="mb-4 p-4 bg-slate-50 rounded-xl space-y-2">
              <div class="grid grid-cols-4 gap-2">
                <div><label class="text-xs text-slate-500">席位数</label>
                  <input v-model.number="newInv.seats" type="number" class="w-full border rounded-lg px-2 py-1.5 text-sm" /></div>
                <div><label class="text-xs text-slate-500">单价 ¥/席/年</label>
                  <input v-model.number="newInv.unit_price" type="number" class="w-full border rounded-lg px-2 py-1.5 text-sm" /></div>
                <div><label class="text-xs text-slate-500">服务期起</label>
                  <input v-model="newInv.period_start" type="date" class="w-full border rounded-lg px-2 py-1.5 text-sm" /></div>
                <div><label class="text-xs text-slate-500">服务期止</label>
                  <input v-model="newInv.period_end" type="date" class="w-full border rounded-lg px-2 py-1.5 text-sm" /></div>
              </div>
              <div class="flex items-center justify-between">
                <div class="text-sm">应收: <span class="font-bold text-[#C97636]">{{ ctx.shared.fmtMoney((newInv.seats||0)*(newInv.unit_price||0)) }}</span></div>
                <div class="flex gap-2">
                  <button @click="createInv" class="btn-primary text-xs">确认开单</button>
                  <button @click="showNewInv=false" class="text-xs text-slate-500 px-3">取消</button>
                </div>
              </div>
            </div>
            <div v-if="!invoices.length" class="text-sm text-slate-400 py-4 text-center">暂无账单</div>
            <table v-else class="w-full text-sm">
              <thead><tr class="text-left text-xs text-slate-400 border-b">
                <th class="pb-2 font-medium">单号</th><th class="pb-2 font-medium text-right">席位</th>
                <th class="pb-2 font-medium text-right">金额</th><th class="pb-2 font-medium">服务期</th>
                <th class="pb-2 font-medium">状态</th><th class="pb-2 font-medium"></th>
              </tr></thead>
              <tbody>
                <tr v-for="inv in invoices" :key="inv.id" class="border-b last:border-0">
                  <td class="py-2 font-mono text-xs">{{ inv.invoice_no }}</td>
                  <td class="text-right">{{ inv.seats }}</td>
                  <td class="text-right font-medium">{{ ctx.shared.fmtMoney(inv.amount) }}</td>
                  <td class="text-xs text-slate-500">{{ inv.period_start }} ~ {{ inv.period_end }}</td>
                  <td><span :class="'badge badge-'+inv.status">{{ ctx.shared.INV_STATUS_LABEL[inv.status] }}</span></td>
                  <td class="text-right">
                    <button v-if="inv.status==='pending'" @click="markPaid(inv)" class="text-xs text-emerald-600 hover:underline mr-2">标记已收</button>
                    <button v-if="inv.status==='pending'" @click="voidInv(inv)" class="text-xs text-slate-400 hover:underline">作废</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </template>
        </card>
      </template>
    </div>`,
    async mounted() { this.load(); },
    methods: {
      async load() {
        this.loading = true;
        try {
          const d = await S().get("/api/saas/orgs/" + this.ctx.params.id);
          this.org = d.org; this.invoices = d.invoices; this.usage = d.usage_30d;
        } catch (e) { this.ctx.toast(e.message, "error"); }
        this.loading = false;
      },
      startEdit() {
        this.form = {
          plan_status: this.org.plan_status, seats_paid: this.org.seats_paid,
          paid_until: this.org.paid_until || "", contact_name: this.org.contact_name || "",
          contact_phone: this.org.contact_phone || "", contact_email: this.org.contact_email || "",
        };
        this.editing = true;
      },
      async saveEdit() {
        try {
          await S().put("/api/saas/orgs/" + this.org.id, this.form);
          this.ctx.toast("已保存"); this.editing = false; this.load();
        } catch (e) { this.ctx.toast(e.message, "error"); }
      },
      async toggleDisable(disable) {
        if (disable && !confirm("确定停用该机构？全机构将登不进。")) return;
        try {
          await S().post(`/api/saas/orgs/${this.org.id}/${disable ? "disable" : "enable"}`);
          this.ctx.toast(disable ? "已停用" : "已恢复"); this.load();
        } catch (e) { this.ctx.toast(e.message, "error"); }
      },
      async createInv() {
        try {
          const d = await S().post("/api/saas/invoices", { org_id: this.org.id, ...this.newInv });
          this.ctx.toast("已开单 " + d.invoice_no);
          this.showNewInv = false; this.newInv = null; this.load();
        } catch (e) { this.ctx.toast(e.message, "error"); }
      },
      async markPaid(inv) {
        const method = prompt("收款方式 (如: 线下转账/支付宝/微信):", "线下转账");
        if (method === null) return;
        try {
          await S().post(`/api/saas/invoices/${inv.id}/pay`, { payment_method: method });
          this.ctx.toast("已标记收款"); this.load();
        } catch (e) { this.ctx.toast(e.message, "error"); }
      },
      async voidInv(inv) {
        if (!confirm("确定作废该账单？")) return;
        try { await S().post(`/api/saas/invoices/${inv.id}/void`); this.ctx.toast("已作废"); this.load(); }
        catch (e) { this.ctx.toast(e.message, "error"); }
      },
    },
    watch: {
      showNewInv(v) {
        if (v && !this.newInv) {
          const today = new Date();
          const nextYear = new Date(today); nextYear.setFullYear(today.getFullYear() + 1);
          this.newInv = {
            seats: Math.max(0, this.org.seats_collab - 2), unit_price: 1000,
            period_start: today.toISOString().slice(0, 10),
            period_end: nextYear.toISOString().slice(0, 10),
          };
        }
      },
    },
  });

  // ── 账单总览 ──────────────────────────────────────────────────
  const InvoicesView = defineComponent({
    components: { Card, Stat },
    props: ["ctx"],
    data: () => ({ items: [], summary: {}, loading: true, status: "" }),
    template: `
    <div>
      <h1 class="text-xl font-bold mb-4">账单流水</h1>
      <div class="grid grid-cols-3 gap-4 mb-6">
        <stat label="待收金额" :value="ctx.shared.fmtMoney(summary.pending_amount||0)" color="text-amber-600"></stat>
        <stat label="已收金额" :value="ctx.shared.fmtMoney(summary.paid_amount||0)" color="text-emerald-600"></stat>
        <stat label="账单数" :value="items.length"></stat>
      </div>
      <card>
        <div class="mb-4">
          <select v-model="status" @change="load" class="border rounded-lg px-3 py-1.5 text-sm">
            <option value="">全部状态</option>
            <option value="pending">待收</option>
            <option value="paid">已收</option>
            <option value="void">作废</option>
          </select>
        </div>
        <div v-if="loading" class="text-sm text-slate-400 py-8 text-center">加载中…</div>
        <div v-else-if="!items.length" class="text-sm text-slate-400 py-8 text-center">暂无账单</div>
        <table v-else class="w-full text-sm">
          <thead><tr class="text-left text-xs text-slate-400 border-b">
            <th class="pb-2 font-medium">单号</th><th class="pb-2 font-medium">机构</th>
            <th class="pb-2 font-medium text-right">席位</th><th class="pb-2 font-medium text-right">金额</th>
            <th class="pb-2 font-medium">服务期</th><th class="pb-2 font-medium">状态</th>
            <th class="pb-2 font-medium">收款方式</th>
          </tr></thead>
          <tbody>
            <tr v-for="inv in items" :key="inv.id" class="border-b last:border-0 hover:bg-slate-50">
              <td class="py-2 font-mono text-xs">{{ inv.invoice_no }}</td>
              <td>{{ inv.org_name }}</td>
              <td class="text-right">{{ inv.seats }}</td>
              <td class="text-right font-medium">{{ ctx.shared.fmtMoney(inv.amount) }}</td>
              <td class="text-xs text-slate-500">{{ inv.period_start }} ~ {{ inv.period_end }}</td>
              <td><span :class="'badge badge-'+inv.status">{{ ctx.shared.INV_STATUS_LABEL[inv.status] }}</span></td>
              <td class="text-xs text-slate-500">{{ inv.payment_method || '—' }}</td>
            </tr>
          </tbody>
        </table>
      </card>
    </div>`,
    async mounted() { this.load(); },
    methods: {
      async load() {
        this.loading = true;
        try {
          const d = await S().get("/api/saas/invoices?" + (this.status ? "status=" + this.status : ""));
          this.items = d.items; this.summary = d.summary;
        } catch (e) { this.ctx.toast(e.message, "error"); }
        this.loading = false;
      },
    },
  });

  // ── 用量总览 ──────────────────────────────────────────────────
  // ── 开源版按次购买订单 (机构在 portal 提交, 运营在这里开通 Key + 标记收款) ─
  const KeyOrdersView = defineComponent({
    components: { Card, Stat },
    props: ["ctx"],
    data: () => ({ items: [], summary: {}, loading: true, status: "pending", editId: null, form: {} }),
    template: `
    <div>
      <div class="flex items-center justify-between mb-4">
        <h1 class="text-xl font-bold">开源版订单</h1>
        <select v-model="status" @change="load" class="border rounded-lg px-3 py-1.5 text-sm">
          <option value="">全部</option>
          <option value="pending">待付款</option>
          <option value="paid">已付款待交付</option>
          <option value="delivered">已交付</option>
          <option value="cancelled">已取消</option>
        </select>
      </div>

      <div class="grid grid-cols-3 gap-4 mb-6">
        <stat label="待付款" :value="summary.pending||0" color="text-amber-600"></stat>
        <stat label="待收金额" :value="ctx.shared.fmtMoney(summary.pending_amount||0)" color="text-amber-600"></stat>
        <stat label="已收金额" :value="ctx.shared.fmtMoney(summary.paid_amount||0)" color="text-emerald-600"></stat>
      </div>

      <card>
        <div v-if="loading" class="text-sm text-slate-400 py-8 text-center">加载中…</div>
        <div v-else-if="!items.length" class="text-sm text-slate-400 py-8 text-center">暂无订单</div>
        <table v-else class="w-full text-sm">
          <thead><tr class="text-left text-xs text-slate-400 border-b">
            <th class="pb-2 font-medium">订单号</th>
            <th class="pb-2 font-medium">机构 / 联系人</th>
            <th class="pb-2 font-medium text-right">次数</th>
            <th class="pb-2 font-medium text-right">金额</th>
            <th class="pb-2 font-medium">状态</th>
            <th class="pb-2 font-medium">Key</th>
            <th class="pb-2 font-medium">操作</th>
          </tr></thead>
          <tbody>
            <tr v-for="o in items" :key="o.id" class="border-b last:border-0">
              <td class="py-3 font-mono text-xs">{{ o.order_no }}</td>
              <td class="py-3">
                <div class="font-medium">{{ o.org_name }}</div>
                <div class="text-xs text-slate-400">{{ o.contact_name }} · {{ o.contact_email }}</div>
              </td>
              <td class="text-right">{{ o.calls }}</td>
              <td class="text-right font-medium">¥{{ o.amount }}</td>
              <td>
                <span :class="'badge badge-' + (o.status==='pending' ? 'pending' : o.status==='paid' ? 'trial' : o.status==='delivered' ? 'paid' : 'void')">
                  {{ ({pending:'待付款', paid:'已付款', delivered:'已交付', cancelled:'已取消'})[o.status] }}
                </span>
              </td>
              <td class="font-mono text-xs text-slate-500">{{ o.api_key_prefix || '—' }}</td>
              <td class="text-right text-xs">
                <template v-if="o.status==='pending'">
                  <button @click="markPaid(o)" class="text-emerald-600 hover:underline">标记已收</button>
                  <button @click="cancel(o)" class="text-slate-400 hover:underline ml-2">取消</button>
                </template>
                <template v-else-if="o.status==='paid'">
                  <button @click="markDelivered(o)" class="text-primary-600 hover:underline">标记已交付</button>
                </template>
              </td>
            </tr>
          </tbody>
        </table>
      </card>
      <p class="text-xs text-slate-400 mt-3">
        流程: 机构在 portal /buy-key 下单 (台账) → 转账备注订单号 → 你点「标记已收」(可同时填 Gobob Key id) → 邮件/微信把 Key 发给机构 → 点「标记已交付」
      </p>
    </div>`,
    async mounted() { this.load(); },
    methods: {
      async load() {
        this.loading = true;
        try {
          const d = await S().get("/api/saas/key-orders" + (this.status ? "?status=" + this.status : ""));
          this.items = d.items; this.summary = d.summary;
        } catch (e) { this.ctx.toast(e.message, "error"); }
        this.loading = false;
      },
      async markPaid(o) {
        const keyIdStr = prompt(`已在 Gobob admin-portal /admin/soho-keys 开通了 Key?\n填 Key ID (数字), 或留空只标记已收:`, "");
        if (keyIdStr === null) return;
        const keyId = keyIdStr ? parseInt(keyIdStr) : null;
        const prefix = keyId ? prompt("Key prefix (gob_xxxx..., 用于在订单上展示):", "") : null;
        const method = prompt("收款方式:", "线下转账");
        if (method === null) return;
        try {
          await S().post(`/api/saas/key-orders/${o.id}/paid`, {
            api_key_id: keyId, api_key_prefix: prefix, payment_method: method,
          });
          this.ctx.toast("已标记收款"); this.load();
        } catch (e) { this.ctx.toast(e.message, "error"); }
      },
      async markDelivered(o) {
        if (!confirm("已把 Key 发给机构邮箱?")) return;
        try {
          await S().post(`/api/saas/key-orders/${o.id}/deliver`, {});
          this.ctx.toast("已标记交付"); this.load();
        } catch (e) { this.ctx.toast(e.message, "error"); }
      },
      async cancel(o) {
        if (!confirm("取消该订单?")) return;
        try {
          await S().post(`/api/saas/key-orders/${o.id}/cancel`, {});
          this.ctx.toast("已取消"); this.load();
        } catch (e) { this.ctx.toast(e.message, "error"); }
      },
    },
  });

  const UsageView = defineComponent({
    components: { Card, Stat },
    props: ["ctx"],
    data: () => ({ byOrg: [], byEndpoint: [], days: 30, loading: true }),
    template: `
    <div>
      <div class="flex items-center justify-between mb-4">
        <h1 class="text-xl font-bold">API 用量</h1>
        <select v-model.number="days" @change="load" class="border rounded-lg px-3 py-1.5 text-sm">
          <option :value="7">近 7 天</option>
          <option :value="30">近 30 天</option>
          <option :value="90">近 90 天</option>
        </select>
      </div>
      <div class="grid grid-cols-2 gap-4">
        <card title="按机构">
          <div v-if="loading" class="text-sm text-slate-400 py-8 text-center">加载中…</div>
          <div v-else-if="!byOrg.length" class="text-sm text-slate-400 py-8 text-center">近 {{ days }} 天无调用</div>
          <table v-else class="w-full text-sm">
            <thead><tr class="text-left text-xs text-slate-400 border-b">
              <th class="pb-2 font-medium">机构</th><th class="pb-2 font-medium text-right">调用次数</th>
              <th class="pb-2 font-medium text-right">活跃天数</th><th class="pb-2 font-medium">最近调用</th>
            </tr></thead>
            <tbody>
              <tr v-for="o in byOrg" :key="o.org_id" class="border-b last:border-0">
                <td class="py-2">{{ o.org_name }}</td>
                <td class="text-right font-medium">{{ o.total_calls }}</td>
                <td class="text-right text-slate-500">{{ o.active_days }}</td>
                <td class="text-xs text-slate-400">{{ o.last_date }}</td>
              </tr>
            </tbody>
          </table>
        </card>
        <card title="按端点">
          <div v-if="loading" class="text-sm text-slate-400 py-8 text-center">加载中…</div>
          <div v-else-if="!byEndpoint.length" class="text-sm text-slate-400 py-8 text-center">无数据</div>
          <table v-else class="w-full text-sm">
            <thead><tr class="text-left text-xs text-slate-400 border-b">
              <th class="pb-2 font-medium">端点</th><th class="pb-2 font-medium text-right">次数</th>
            </tr></thead>
            <tbody>
              <tr v-for="e in byEndpoint" :key="e.endpoint" class="border-b last:border-0">
                <td class="py-2 text-xs text-slate-600">{{ e.endpoint }}</td>
                <td class="text-right font-medium">{{ e.calls }}</td>
              </tr>
            </tbody>
          </table>
        </card>
      </div>
      <p class="text-xs text-slate-400 mt-4">
        SaaS 版机构调 Gobob Data API 走官方主 Key（不限次，成本运营方扛）。
        用量明细在 Gobob 主站 api_key_logs，按 org+day+endpoint 聚合回写到 saas_api_usage。
        开源版机构按次计费（¥1/次），在 Gobob 主站管理（后做）。
      </p>
    </div>`,
    async mounted() { this.load(); },
    methods: {
      async load() {
        this.loading = true;
        try {
          const d = await S().get("/api/saas/usage?days=" + this.days);
          this.byOrg = d.by_org; this.byEndpoint = d.by_endpoint;
        } catch (e) { this.ctx.toast(e.message, "error"); }
        this.loading = false;
      },
    },
  });

  window.OpsViews = { LoginView, OrgsView, OrgDetailView, InvoicesView, UsageView, KeyOrdersView };
})();
