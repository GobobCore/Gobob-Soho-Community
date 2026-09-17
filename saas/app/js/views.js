// js/views.js — 所有视图组件（Vue 3，浏览器内模板编译）
// 每个视图接收 props: ['ctx']；ctx = { shared, api, toast, go, refreshUser }
(function () {
  const S = () => window.SohoShared;
  const { defineComponent } = Vue;

  // ── 通用小组件 ────────────────────────────────────────────────
  const Card = {
    props: ["title"],
    template: `<div class="bg-white rounded-xl border border-slate-200 p-5">
      <h3 v-if="title" class="font-semibold mb-3 text-slate-700">{{ title }}</h3><slot></slot></div>`,
  };
  const Empty = {
    props: ["text"],
    template: `<div class="text-center py-10 text-slate-400 text-sm">{{ text || '暂无数据' }}</div>`,
  };
  const Tag = {
    props: ["label", "color"],
    template: `<span class="inline-block px-2 py-0.5 rounded text-xs font-medium" :class="cls">{{ label }}</span>`,
    computed: {
      cls() {
        return ({ blue: "bg-blue-50 text-blue-600", green: "bg-emerald-50 text-emerald-600",
          amber: "bg-amber-50 text-amber-600", red: "bg-red-50 text-red-600",
          slate: "bg-slate-100 text-slate-500", purple: "bg-purple-50 text-purple-600" })[this.color] || "bg-slate-100 text-slate-500";
      },
    },
  };
  const Stat = {
    props: ["label", "value", "sub"],
    template: `<div class="bg-white rounded-xl border border-slate-200 p-5">
      <div class="text-sm text-slate-400">{{ label }}</div>
      <div class="text-3xl font-bold mt-1">{{ value }}</div>
      <div v-if="sub" class="text-xs text-slate-400 mt-1">{{ sub }}</div></div>`,
  };

  // ════════════════════════════════════════════════════════════
  // 登录
  // ════════════════════════════════════════════════════════════
  const LoginView = defineComponent({
    emits: ["logged-in"],
    data: () => ({ username: "", password: "", loading: false, err: "" }),
    // R-Refactor 2026-09-17: SaaS 正式版登录页 (去掉 demo 提示 + 一键填入)
    template: `
    <div class="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-slate-100 p-4">
      <div class="w-full max-w-md bg-white rounded-2xl shadow-lg p-8">
        <div class="flex items-center gap-2 mb-1">
          <img src="https://gobob-img.oss-cn-beijing.aliyuncs.com/static/img/gobob_logo_en.svg" class="w-[72px] h-[72px]" />
          <span class="ml-auto text-[10px] uppercase tracking-wider px-2 py-0.5 bg-blue-100 text-blue-700 rounded">Gobob Soho</span>
        </div>
        <div class="text-sm text-slate-400 mb-6">留学服务业务协作系统</div>

        <div class="space-y-3">
          <input v-model="username" placeholder="用户名" @keyup.enter="doLogin"
                 class="w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
          <input v-model="password" type="password" placeholder="密码" @keyup.enter="doLogin"
                 class="w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
          <div v-if="err" class="text-sm text-red-500">{{ err }}</div>
          <button @click="doLogin" :disabled="loading"
                  class="w-full bg-blue-600 hover:bg-blue-700 text-white rounded-lg py-2.5 text-sm font-medium disabled:opacity-50">
            {{ loading ? '登录中…' : '登 录' }}
          </button>
          <div class="text-center text-xs text-slate-400 pt-1">
            还没有账号？
            <a href="#/register" class="text-blue-600 hover:underline">自助注册机构</a>
          </div>
          <div class="text-center text-[11px] text-slate-400 pt-0.5">
            Gobob workspace for small office home office
          </div>
        </div>
      </div>
    </div>`,
    methods: {
      async doLogin() {
        if (!this.username || !this.password) { this.err = "请输入用户名和密码"; return; }
        this.loading = true; this.err = "";
        try {
          const d = await S().post("/api/login", { username: this.username, password: this.password });
          S().setAuth(d.token, d.user);
          this.$emit("logged-in");
        } catch (e) { this.err = e.message; }
        this.loading = false;
      },
    },
  });

  // ════════════════════════════════════════════════════════════
  // 自助注册机构 (SaaS Gobob Soho 注册入口)
  // ════════════════════════════════════════════════════════════
  const RegisterView = defineComponent({
    emits: ["registered", "goto-login"],
    data: () => ({
      org_name: "", owner_name: "",
      username: "", password: "",
      contact_phone: "", contact_email: "",
      loading: false, err: "", ok: false,
    }),
    template: `
    <div class="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-slate-100 p-4">
      <div class="w-full max-w-md bg-white rounded-2xl shadow-lg p-8">
        <div class="flex items-center gap-2 mb-1">
          <img src="https://gobob-img.oss-cn-beijing.aliyuncs.com/static/img/gobob_logo_en.svg" class="w-[72px] h-[72px]" />
          <span class="ml-auto text-[10px] uppercase tracking-wider px-2 py-0.5 bg-blue-100 text-blue-700 rounded">Gobob Soho</span>
        </div>
        <div class="text-sm text-slate-400 mb-6">留学服务业务协作系统</div>

        <div v-if="ok" class="text-center py-8">
          <div class="text-emerald-600 text-lg font-semibold mb-2">✓ 注册成功</div>
          <div class="text-sm text-slate-500 mb-4">机构已创建, 即将跳转到登录页</div>
        </div>

        <template v-else>
        <div class="space-y-3">
          <input v-model="org_name" placeholder="机构名称 (例: 我的留学工作室)" maxlength="100"
                 class="w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
          <input v-model="owner_name" placeholder="老板/主管姓名" maxlength="50"
                 class="w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
          <input v-model="username" placeholder="登录用户名 (3-32 位字母/数字)" maxlength="32" pattern="[a-zA-Z0-9_.-]+"
                 class="w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm font-mono focus:ring-2 focus:ring-blue-500 outline-none" />
          <input v-model="password" type="password" placeholder="密码 (≥ 8 位)" maxlength="64"
                 class="w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
          <div class="grid grid-cols-2 gap-3">
            <input v-model="contact_phone" placeholder="手机 (选填)" maxlength="50"
                   class="w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
            <input v-model="contact_email" type="email" placeholder="邮箱 (选填)" maxlength="200"
                   class="w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
          </div>
          <div v-if="err" class="text-sm text-red-500">{{ err }}</div>
          <button @click="doRegister" :disabled="loading || !canSubmit"
                  class="w-full bg-blue-600 hover:bg-blue-700 text-white rounded-lg py-2.5 text-sm font-medium disabled:opacity-50">
            {{ loading ? '注册中…' : '创建机构账号' }}
          </button>
          <div class="text-center text-xs text-slate-400 pt-1">
            已有账号？
            <a href="#/login" class="text-blue-600 hover:underline">去登录</a>
          </div>
        </div>
        </template>
      </div>
    </div>`,
    computed: {
      canSubmit() {
        return this.org_name.length >= 2 && this.owner_name.length >= 1
          && /^[a-zA-Z0-9_.-]{3,32}$/.test(this.username) && this.password.length >= 8;
      },
    },
    methods: {
      async doRegister() {
        if (!this.canSubmit) { this.err = "请填写完整 (机构名/姓名/用户名≥3位/密码≥8位)"; return; }
        this.loading = true; this.err = "";
        try {
          await S().post("/api/register", {
            org_name: this.org_name,
            username: this.username,
            password: this.password,
            owner_name: this.owner_name,
            contact_phone: this.contact_phone || undefined,
            contact_email: this.contact_email || undefined,
          });
          this.ok = true;
          setTimeout(() => { location.hash = "#/login"; location.reload(); }, 1200);
        } catch (e) { this.err = e.message; }
        this.loading = false;
      },
    },
  });

  // ════════════════════════════════════════════════════════════
  // 机构端 — 驾驶舱
  // ════════════════════════════════════════════════════════════
  const DashboardView = defineComponent({
    components: { Card, Stat, Tag, Empty },
    props: ["ctx"],
    data: () => ({ ov: null, progress: [], loading: true }),
    template: `
    <div>
      <h1 class="text-xl font-bold mb-4">{{ ov && ov.is_owner ? '机构驾驶舱' : '我的工作台' }}</h1>
      <div v-if="loading" class="text-slate-400 text-sm">加载中…</div>
      <template v-else>
        <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <stat label="在读学生" :value="ov.student_count"></stat>
          <stat label="本月签约" :value="ov.month_contract_count" :sub="ctx.shared.fmtMoney(ov.month_contract_amount)"></stat>
          <stat label="待跟进线索" :value="openLeads"></stat>
          <stat label="已签约线索" :value="ov.lead_funnel.converted || 0"></stat>
        </div>

        <div class="grid lg:grid-cols-3 gap-4">
          <!-- 学生进度总览 -->
          <card title="学生进度总览" class="lg:col-span-2">
            <empty v-if="!progress.length" text="还没有学生"></empty>
            <div v-for="s in progress" :key="s.student_id"
                 class="border-b border-slate-100 py-3 last:border-0">
              <div class="flex items-center justify-between">
                <div class="font-medium">{{ s.student_name }}</div>
                <div class="flex gap-1">
                  <tag v-for="(name, phase) in s.advisors" :key="phase" color="blue"
                       :label="ctx.shared.PHASE_LABEL[phase]+':'+name"></tag>
                </div>
              </div>
              <div class="flex gap-4 text-xs text-slate-500 mt-1.5">
                <span class="text-emerald-600 inline-flex items-center gap-1">
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="w-3.5 h-3.5"><path d="M20 6 9 17l-5-5"/></svg>
                  已完成 {{ s.task_stats.done }}
                </span>
                <span class="text-amber-600">● 进行中 {{ s.task_stats.doing }}</span>
                <span class="text-slate-400">○ 待办 {{ s.task_stats.todo }}</span>
              </div>
              <div v-if="s.next_tasks.length" class="text-xs text-slate-400 mt-1">
                接下来：{{ s.next_tasks.map(t=>t.title).join('、') }}
              </div>
            </div>
          </card>

          <!-- 老师负载 -->
          <card title="老师负载">
            <empty v-if="!ov.advisor_load.length"></empty>
            <div v-for="a in ov.advisor_load" :key="a.id" class="flex items-center justify-between py-2 border-b border-slate-100 last:border-0">
              <div class="text-sm font-medium">{{ a.name }}</div>
              <div class="text-xs text-slate-500">{{ a.active_students }} 学生 · {{ a.open_leads }} 线索</div>
            </div>
          </card>
        </div>
      </template>
    </div>`,
    computed: {
      openLeads() {
        const f = this.ov.lead_funnel || {};
        return (f.new || 0) + (f.contacted || 0) + (f.qualified || 0) + (f.proposal || 0) + (f.negotiation || 0);
      },
    },
    async mounted() {
      try {
        this.ov = await S().get("/api/dashboard/overview");
        const p = await S().get("/api/dashboard/students-progress");
        this.progress = p.items;
      } catch (e) { this.ctx.toast(e.message, "error"); }
      this.loading = false;
    },
  });

  // ════════════════════════════════════════════════════════════
  // 机构端 — 线索池（列表 + 看板 + 详情抽屉）
  // ════════════════════════════════════════════════════════════
  const LeadsView = defineComponent({
    components: { Card, Tag, Empty },
    props: ["ctx"],
    data: () => ({
      mode: "board", board: null, list: [], stages: [],
      selected: null, detail: null, showNew: false,
      newLead: { student_name: "", student_phone: "", parent_name: "", parent_phone: "", source: "转介绍", notes: "" },
      duplicates: [],  // Phase 5 录入查重
      openExisting: null,  // Phase 5 疑似重复后跳到已有线索
      saving: false,
    }),
    template: `
    <div>
      <div class="flex items-center justify-between mb-4">
        <h1 class="text-xl font-bold">线索池</h1>
        <div class="flex gap-2">
          <div class="bg-white border border-slate-200 rounded-lg p-0.5 flex text-sm">
            <button @click="mode='board'" :class="['px-3 py-1 rounded-md', mode==='board'?'bg-blue-600 text-white':'text-slate-600']">看板</button>
            <button @click="mode='list'" :class="['px-3 py-1 rounded-md', mode==='list'?'bg-blue-600 text-white':'text-slate-600']">列表</button>
          </div>
          <button @click="showNew=true" class="bg-blue-600 text-white px-4 py-1.5 rounded-lg text-sm">+ 录入线索</button>
        </div>
      </div>

      <!-- 看板 -->
      <div v-if="mode==='board' && board" class="flex gap-3 overflow-x-auto pb-4">
        <div v-for="st in stages" :key="st.stage_id" class="w-60 flex-shrink-0">
          <div class="text-sm font-semibold text-slate-600 mb-2 flex items-center justify-between">
            <span>{{ st.name }}</span>
            <span class="text-xs text-slate-400">{{ (board[st.status]||{leads:[]}).leads.length }}</span>
          </div>
          <div class="bg-slate-200/60 rounded-xl p-2 min-h-[300px] space-y-2">
            <div v-for="l in (board[st.status]||{leads:[]}).leads" :key="l.lead_id"
                 @click="openDetail(l)"
                 class="kanban-card bg-white rounded-lg p-3 cursor-pointer">
              <div class="font-medium text-sm">{{ l.student_name || '未命名' }}</div>
              <div class="text-xs text-slate-400 mt-1 flex justify-between">
                <span>{{ l.advisor_name || '未分配' }}</span>
                <span>{{ l.source || '' }}</span>
              </div>
            </div>
            <empty v-if="!(board[st.status]||{leads:[]}).leads.length" text=""></empty>
          </div>
        </div>
        <!-- Phase 5: 公海列 -->
        <div class="w-60 flex-shrink-0">
          <div class="text-sm font-semibold text-slate-600 mb-2 flex items-center justify-between">
            <span>公海 <span class="text-xs text-amber-600">(回收)</span></span>
            <span class="text-xs text-slate-400">{{ (board['recycled']||{leads:[]}).leads.length }}</span>
          </div>
          <div class="bg-amber-50 border border-amber-200 rounded-xl p-2 min-h-[300px] space-y-2">
            <div v-for="l in (board['recycled']||{leads:[]}).leads" :key="l.lead_id"
                 @click="openDetail(l)"
                 class="kanban-card bg-white rounded-lg p-3 cursor-pointer border-l-4 border-amber-300">
              <div class="font-medium text-sm">{{ l.student_name || '未命名' }}</div>
              <div class="text-xs text-slate-400 mt-1 flex justify-between items-center">
                <span>{{ l.advisor_name || '公海' }}</span>
                <button @click.stop="claimLead(l)" class="text-xs text-blue-600 hover:underline">认领</button>
              </div>
            </div>
            <empty v-if="!(board['recycled']||{leads:[]}).leads.length" text=""></empty>
          </div>
        </div>
      </div>

      <!-- 列表 -->
      <card v-else>
        <empty v-if="!list.length"></empty>
        <table v-else class="w-full text-sm">
          <thead><tr class="text-left text-slate-400 text-xs border-b border-slate-100">
            <th class="py-2">学生</th><th>联系方式</th><th>意向</th><th>阶段</th><th>负责人</th><th>来源</th>
          </tr></thead>
          <tbody>
            <tr v-for="l in list" :key="l.lead_id" @click="openDetail(l)" class="border-b border-slate-50 hover:bg-slate-50 cursor-pointer">
              <td class="py-2.5 font-medium">{{ l.student_name }}</td>
              <td class="text-slate-500">{{ l.student_phone || l.student_wechat || '—' }}</td>
              <td class="text-slate-500">{{ (l.target_countries||[]).join('/') || '—' }}</td>
              <td><tag :label="ctx.shared.LEAD_STATUS_LABEL[l.status]||l.status" :color="statusColor(l.status)"></tag></td>
              <td class="text-slate-500">{{ l.advisor_name || '未分配' }}</td>
              <td class="text-slate-400 text-xs">{{ l.source || '' }}</td>
            </tr>
          </tbody>
        </table>
      </card>

      <!-- 新建线索弹窗 -->
      <div v-if="showNew" class="fixed inset-0 bg-black/40 flex items-center justify-center z-40 p-4" @click.self="showNew=false">
        <div class="bg-white rounded-2xl w-full max-w-md p-6 max-h-[85vh] overflow-y-auto">
          <h3 class="font-bold mb-4">录入线索</h3>
          <div class="space-y-3 text-sm">
            <input v-model="newLead.student_name" placeholder="学生姓名 *" class="w-full border rounded-lg px-3 py-2" />
            <input v-model="newLead.student_phone" placeholder="学生手机" class="w-full border rounded-lg px-3 py-2" />
            <input v-model="newLead.parent_name" placeholder="家长姓名" class="w-full border rounded-lg px-3 py-2" />
            <input v-model="newLead.parent_phone" placeholder="家长手机" class="w-full border rounded-lg px-3 py-2" />
            <select v-model="newLead.source" class="w-full border rounded-lg px-3 py-2">
              <option>转介绍</option><option>线上咨询</option><option>讲座</option><option>广告</option><option>地推</option><option>其他</option>
            </select>
            <textarea v-model="newLead.notes" placeholder="备注" class="w-full border rounded-lg px-3 py-2" rows="2"></textarea>
          </div>
          <div class="flex gap-2 mt-5">
            <button @click="showNew=false" class="flex-1 border rounded-lg py-2 text-sm">取消</button>
            <button @click="saveNew" :disabled="saving" class="flex-1 bg-blue-600 text-white rounded-lg py-2 text-sm disabled:opacity-50">{{ saving?'保存中…':'保存' }}</button>
          </div>
        </div>
      </div>

      <!-- Phase 5: 录入查重结果卡片 -->
      <div v-if="duplicates.length" class="mt-3 bg-amber-50 border border-amber-200 rounded-xl p-3">
        <div class="text-sm font-medium text-amber-800 mb-2">⚠ 发现 {{ duplicates.length }} 条疑似重复线索</div>
        <div v-for="d in duplicates" :key="d.lead_id" class="bg-white border rounded-lg p-2 mb-2 text-sm flex justify-between items-center">
          <div>
            <span class="font-medium">{{ d.student_name }}</span>
            <span class="text-xs text-slate-500 ml-2">{{ d._match_reason }} · 状态 {{ d.status }}</span>
            <span class="text-xs text-slate-400 ml-2">归属 {{ d.assigned_advisor_id || '未分配' }}</span>
          </div>
          <div class="flex gap-2">
            <button @click="openExisting = d; selected = d; showNew = false" class="text-xs text-blue-600">打开</button>
          </div>
        </div>
        <button @click="duplicates=[]" class="text-xs text-slate-500 underline">忽略，仍要新建</button>
      </div>

      <!-- 详情抽屉 -->
      <lead-detail v-if="selected" :lead-id="selected.lead_id" :ctx="ctx" @close="selected=null;load()" @changed="load"></lead-detail>
    </div>`,
    async mounted() { this.load(); },
    methods: {
      statusColor(s) { return { new: "blue", contacted: "slate", qualified: "purple", proposal: "amber", negotiation: "amber", converted: "green", lost: "red" }[s] || "slate"; },
      async load() {
        try {
          const b = await S().get("/api/leads/board");
          this.board = b.board; this.stages = b.stages;
          const l = await S().get("/api/leads?page_size=200");
          this.list = l.items;
        } catch (e) { this.ctx.toast(e.message, "error"); }
      },
      openDetail(l) { this.selected = l; },
      async claimLead(l) {
        try {
          // advisor 认领自己；owner 需传 advisor_id（这里简化：owner 先打开详情抽屉选顾问）
          if (this.ctx.shared.isStaff && !this.ctx.shared.isOwner) {
            await S().post(`/api/leads/${l.lead_id}/claim`, {});
            this.ctx.toast("已认领");
            this.load();
          } else {
            this.ctx.toast("请先打开详情，在'分配'里选目标顾问", "error");
            this.openDetail(l);
          }
        } catch (e) { this.ctx.toast(e.message, "error"); }
      },
      async saveNew() {
        if (!this.newLead.student_name) { this.ctx.toast("请填学生姓名", "error"); return; }
        this.saving = true;
        try {
          const r = await S().post("/api/leads", this.newLead);
          // Phase 5: 录入查重返回
          if (r.duplicates && r.duplicates.length) {
            this.duplicates = r.duplicates;
            this.ctx.toast(`已保存，但发现 ${r.duplicates.length} 条疑似重复`, "ok");
            this.load();
          } else {
            this.ctx.toast("线索已录入");
            this.showNew = false;
            this.newLead = { student_name: "", student_phone: "", parent_name: "", parent_phone: "", source: "转介绍", notes: "" };
            this.load();
          }
        } catch (e) { this.ctx.toast(e.message, "error"); }
        this.saving = false;
      },
    },
  });

  // 线索详情抽屉（含跟进/推进/转化/分配）
  const LeadDetail = defineComponent({
    components: { Tag, Empty },
    props: ["leadId", "ctx"],
    emits: ["close", "changed"],
    data: () => ({ lead: null, activities: [], advisors: [],
      act: { activity_type: "wechat", subject: "", content: "", contact_type: "student", outcome: "interested" },
      // Phase 5: 流失弹窗
      showLostModal: false, lostReason: "", lostDetail: "",
      saving: false }),
    template: `
    <div class="fixed inset-0 z-40" @click.self="$emit('close')">
      <div class="absolute inset-0 bg-black/30"></div>
      <div class="absolute right-0 top-0 h-full w-full max-w-lg bg-white shadow-2xl flex flex-col">
        <div class="flex items-center justify-between p-4 border-b">
          <h3 class="font-bold">{{ lead ? lead.student_name : '…' }}</h3>
          <button @click="$emit('close')" class="text-slate-400 hover:text-slate-600 text-xl">✕</button>
        </div>
        <div v-if="lead" class="flex-1 overflow-y-auto p-4 space-y-4">
          <div class="grid grid-cols-2 gap-3 text-sm">
            <div><span class="text-slate-400">阶段</span> <tag :label="ctx.shared.LEAD_STATUS_LABEL[lead.status]" :color="'blue'"></tag></div>
            <div><span class="text-slate-400">负责人</span> {{ lead.assigned_advisor_id ? (advisorName(lead.assigned_advisor_id)) : '未分配' }}</div>
            <div><span class="text-slate-400">学生手机</span> {{ lead.student_phone || '—' }}</div>
            <div><span class="text-slate-400">家长手机</span> {{ lead.parent_phone || '—' }}</div>
            <div class="col-span-2"><span class="text-slate-400">意向</span> {{ (lead.target_countries||[]).join('/') }} {{ (lead.target_majors||[]).join('/') }}</div>
            <div class="col-span-2" v-if="lead.notes"><span class="text-slate-400">备注</span> {{ lead.notes }}</div>
          </div>

          <!-- 操作 -->
          <div class="flex flex-wrap gap-2">
            <select @change="onStageChange($event.target.value)" :value="lead.status" class="border rounded-lg px-2 py-1.5 text-sm">
              <option v-for="(label,s) in ctx.shared.LEAD_STATUS_LABEL" :value="s" :disabled="s==='converted'||s==='lost'">{{ label }}</option>
            </select>
            <select v-if="ctx.shared.isOwner" @change="assignTo($event.target.value)" :value="lead.assigned_advisor_id||''" class="border rounded-lg px-2 py-1.5 text-sm">
              <option value="">分配给…</option>
              <option v-for="a in advisors" :value="a.id">{{ a.name }}</option>
            </select>
            <button v-if="lead.status!=='converted'" @click="convert" class="bg-emerald-600 text-white rounded-lg px-3 py-1.5 text-sm">转化为学生</button>
            <span v-else class="text-emerald-600 text-sm py-1.5 inline-flex items-center gap-1">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="w-3.5 h-3.5"><path d="M20 6 9 17l-5-5"/></svg>
              已转化
            </span>
          </div>

          <!-- Phase 5: 流失原因弹窗 -->
          <div v-if="showLostModal" class="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" @click.self="showLostModal=false">
            <div class="bg-white rounded-2xl w-full max-w-sm p-6">
              <h3 class="font-bold mb-1">标记为流失</h3>
              <div class="text-sm text-slate-500 mb-4">请填写流失原因（必填）+ 备注（≥10 字）</div>
              <div class="space-y-3 text-sm">
                <select v-model="lostReason" class="w-full border rounded-lg px-3 py-2">
                  <option value="">选流失原因</option>
                  <option v-for="(label, r) in ctx.shared.LOST_REASON_LABEL" :value="r">{{ label }}</option>
                </select>
                <textarea v-model="lostDetail" placeholder="详细原因（≥10 字）" class="w-full border rounded-lg px-3 py-2" rows="3"></textarea>
              </div>
              <div class="flex gap-2 mt-4">
                <button @click="showLostModal=false" class="flex-1 border rounded-lg py-2 text-sm">取消</button>
                <button @click="confirmLost" class="flex-1 bg-red-600 text-white rounded-lg py-2 text-sm">确认流失</button>
              </div>
            </div>
          </div>

          <!-- 跟进记录 -->
          <div>
            <div class="text-sm font-semibold mb-2">跟进记录</div>
            <div class="space-y-2 mb-3">
              <select v-model="act.activity_type" class="border rounded-lg px-2 py-1.5 text-sm w-full">
                <option value="wechat">微信</option><option value="call">电话</option><option value="meeting">面访</option><option value="email">邮件</option>
              </select>
              <input v-model="act.subject" placeholder="摘要（如：首次沟通）" class="w-full border rounded-lg px-3 py-2 text-sm" />
              <textarea v-model="act.content" placeholder="详细内容" class="w-full border rounded-lg px-3 py-2 text-sm" rows="2"></textarea>
              <button @click="addActivity" :disabled="saving" class="w-full bg-blue-600 text-white rounded-lg py-2 text-sm disabled:opacity-50">{{ saving?'…':'记一次跟进' }}</button>
            </div>
            <empty v-if="!activities.length" text="暂无跟进"></empty>
            <div v-for="a in activities" :key="a.activity_id" class="border-l-2 border-blue-200 pl-3 py-1.5 mb-1">
              <div class="text-sm font-medium">{{ a.subject || a.activity_type }}</div>
              <div v-if="a.content" class="text-xs text-slate-500">{{ a.content }}</div>
              <div class="text-xs text-slate-400">{{ a.actor_name }} · {{ ctx.shared.fmtDate(a.created_at) }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>`,
    async mounted() { this.load(); this.loadAdvisors(); },
    methods: {
      advisorName(id) { const a = this.advisors.find(x => x.id === id); return a ? a.name : "—"; },
      async loadAdvisors() {
        if (!this.ctx.shared.isOwner) return;
        try { const d = await S().get("/api/staff"); this.advisors = d.items.filter(x => x.role === "advisor"); } catch {}
      },
      async load() {
        try {
          const d = await S().get("/api/leads/" + this.leadId);
          this.lead = d.lead; this.activities = d.activities;
        } catch (e) { this.ctx.toast(e.message, "error"); }
      },
      onStageChange(status) {
        // 流失走弹窗（必填原因）
        if (status === "lost") { this.showLostModal = true; this.lostReason = ""; this.lostDetail = ""; return; }
        this.moveStage(status);
      },
      async moveStage(status) {
        try { await S().post(`/api/leads/${this.leadId}/move-stage`, { status }); this.load(); this.$emit("changed"); }
        catch (e) { this.ctx.toast(e.message, "error"); }
      },
      async confirmLost() {
        if (!this.lostReason) { this.ctx.toast("请选流失原因", "error"); return; }
        if (!this.lostDetail || this.lostDetail.trim().length < 10) { this.ctx.toast("备注至少 10 字", "error"); return; }
        try {
          await S().post(`/api/leads/${this.leadId}/move-stage`, {
            status: "lost", lost_reason: this.lostReason, lost_detail: this.lostDetail
          });
          this.ctx.toast("已标记流失"); this.showLostModal = false;
          this.load(); this.$emit("changed");
        } catch (e) { this.ctx.toast(e.message, "error"); }
      },
      async assignTo(advisor_id) {
        if (!advisor_id) return;
        try { await S().post(`/api/leads/${this.leadId}/assign`, { advisor_id }); this.load(); this.$emit("changed"); this.ctx.toast("已分配"); }
        catch (e) { this.ctx.toast(e.message, "error"); }
      },
      async addActivity() {
        if (!this.act.subject) { this.ctx.toast("请填摘要", "error"); return; }
        this.saving = true;
        try { await S().post(`/api/leads/${this.leadId}/activities`, this.act); this.act.subject = ""; this.act.content = ""; this.load(); }
        catch (e) { this.ctx.toast(e.message, "error"); }
        this.saving = false;
      },
      async convert() {
        if (!confirm("转化为正式学生？将创建学生（+家长）档案。")) return;
        try { await S().post(`/api/leads/${this.leadId}/convert`, { create_account: false }); this.ctx.toast("已转化为学生"); this.load(); this.$emit("changed"); }
        catch (e) { this.ctx.toast(e.message, "error"); }
      },
    },
  });

  // ════════════════════════════════════════════════════════════
  // 机构端 — 学生列表 + 学生详情（含换师）
  // ════════════════════════════════════════════════════════════
  const StudentsView = defineComponent({
    components: { Card, Tag, Empty },
    props: ["ctx"],
    data: () => ({ items: [], loading: true, selectedId: null }),
    methods: {
      openStudent(s) { this.selectedId = s.id; },
      closeDetail() { this.selectedId = null; },
    },
    template: `
    <div>
      <h1 class="text-xl font-bold mb-4">学生</h1>
      <card>
        <div v-if="loading" class="text-sm text-slate-400">加载中…</div>
        <empty v-else-if="!items.length" text="还没有学生，从线索池转化一个试试"></empty>
        <table v-else class="w-full text-sm">
          <thead><tr class="text-left text-slate-400 text-xs border-b border-slate-100">
            <th class="py-2">姓名</th><th>联系方式</th><th>负责老师</th><th>账号</th><th>创建</th>
          </tr></thead>
          <tbody>
            <tr v-for="s in items" :key="s.id" @click="openStudent(s)" class="border-b border-slate-50 hover:bg-slate-50 cursor-pointer">
              <td class="py-2.5 font-medium">{{ s.name }}</td>
              <td class="text-slate-500">{{ s.phone || s.wechat || '—' }}</td>
              <td class="text-slate-500">{{ s.advisors || '未分配' }}</td>
              <td><tag :label="s.is_virtual?'虚拟':'可登录'" :color="s.is_virtual?'slate':'green'"></tag></td>
              <td class="text-slate-400 text-xs">{{ ctx.shared.fmtDate(s.created_at) }}</td>
            </tr>
          </tbody>
        </table>
      </card>
      <student-detail v-if="selectedId" :student-id="selectedId" :ctx="ctx" @close="closeDetail"></student-detail>
    </div>`,
    async mounted() {
      try { const d = await S().get("/api/students?page_size=200"); this.items = d.items; }
      catch (e) { this.ctx.toast(e.message, "error"); }
      this.loading = false;
    },
  });

  const StudentDetail = defineComponent({
    components: { Tag, Empty, Card },
    props: ["studentId", "ctx"],
    emits: ["close"],
    data: () => ({
      stu: null, assignments: [], contracts: [], tasks: [], milestones: [], apps: [],
      advisors: [], tab: "overview",
      deliverables: [],  // Phase 5
      deliverableModal: null,  // {deliverable_id, title}
      newVersion: { content: "", submit: false },
      reviewModal: null,  // {version_id}
      review: { decision: "approve", content: "" },
      assignForm: { advisor_member_id: "", phase: "overall" },
      handoverTarget: null, handover: { new_advisor_id: "", handover_note: "" },
    }),
    template: `
    <div class="fixed inset-0 z-40">
      <div class="absolute inset-0 bg-black/30" @click="$emit('close')"></div>
      <div class="absolute right-0 top-0 h-full w-full max-w-2xl bg-slate-50 shadow-2xl flex flex-col">
        <div class="bg-white border-b p-4 flex items-center justify-between">
          <div>
            <h3 class="font-bold text-lg">{{ stu ? stu.name : '…' }}</h3>
            <div class="text-xs text-slate-400">{{ stu ? (stu.phone || '') : '' }}</div>
          </div>
          <button @click="$emit('close')" class="text-slate-400 hover:text-slate-600 text-xl">✕</button>
        </div>

        <!-- tabs -->
        <div class="bg-white border-b px-4 flex gap-1 text-sm">
          <button v-for="t in tabs" :key="t.id" @click="tab=t.id"
                  :class="['px-3 py-2 border-b-2 -mb-px', tab===t.id?'border-blue-600 text-blue-600 font-medium':'border-transparent text-slate-500']">{{ t.label }}</button>
        </div>

        <div v-if="stu" class="flex-1 overflow-y-auto p-4 space-y-4">
          <!-- 总览 -->
          <div v-show="tab==='overview'">
            <card title="负责老师（按环节）">
              <empty v-if="!assignments.length" text="尚未分配老师"></empty>
              <div v-for="a in assignments" :key="a.id" class="flex items-center justify-between py-2 border-b border-slate-100 last:border-0">
                <div><tag :label="ctx.shared.PHASE_LABEL[a.phase]" color="blue"></tag> <span class="ml-2 font-medium">{{ a.advisor_name }}</span></div>
                <button @click="handoverTarget=a; handover.new_advisor_id=''; handover.handover_note=''" class="text-xs text-amber-600 hover:underline">更换老师</button>
              </div>
              <div class="flex gap-2 mt-3 pt-3 border-t">
                <select v-model="assignForm.phase" class="border rounded-lg px-2 py-1.5 text-sm">
                  <option v-for="(l,p) in ctx.shared.PHASE_LABEL" :value="p">{{ l }}</option>
                </select>
                <select v-model="assignForm.advisor_member_id" class="border rounded-lg px-2 py-1.5 text-sm flex-1">
                  <option value="">选老师…</option>
                  <option v-for="a in advisors" :value="a.id">{{ a.name }}</option>
                </select>
                <button @click="assignTeacher" class="bg-blue-600 text-white rounded-lg px-3 py-1.5 text-sm">分配</button>
              </div>
            </card>
            <card title="签约">
              <empty v-if="!contracts.length" text="无合同"></empty>
              <div v-for="c in contracts" :key="c.id" class="py-2 border-b border-slate-100 last:border-0 text-sm">
                <div class="flex justify-between"><span class="font-medium">{{ c.contract_no }}</span><span class="text-slate-500">{{ ctx.shared.fmtMoney(c.total_amount) }}</span></div>
                <div class="text-xs text-slate-400 mt-0.5">{{ (c.modules||[]).length }} 个服务模块 · 已收 {{ ctx.shared.fmtMoney(c.paid_amount) }}</div>
              </div>
            </card>
          </div>

          <!-- 进程 -->
          <div v-show="tab==='progress'">
            <card title="里程碑">
              <empty v-if="!milestones.length"></empty>
              <div v-for="m in milestones" :key="m.id" class="flex items-center gap-2 py-2 border-b border-slate-100 last:border-0">
                <button @click="toggleMilestone(m)" class="w-5 h-5 rounded-full border-2 transition-all" :class="m.status==='done'?'bg-emerald-500 border-emerald-500':(m.status==='in_progress'?'bg-blue-500 border-blue-500':'bg-white border-slate-300 hover:border-slate-400')"></button>
                <div class="flex-1 text-sm" :class="m.status==='done'?'line-through text-slate-400':''">{{ m.title }}</div>
                <div class="text-xs text-slate-400">{{ ctx.shared.fmtDate(m.due_date) }}</div>
              </div>
            </card>
            <card title="任务">
              <empty v-if="!tasks.length"></empty>
              <div v-for="t in tasks" :key="t.id" class="flex items-center gap-2 py-2 border-b border-slate-100 last:border-0">
                <button @click="toggleTask(t)" class="w-5 h-5 rounded-full border-2 transition-all" :class="t.status==='done'?'bg-emerald-500 border-emerald-500':'bg-white border-slate-300 hover:border-slate-400'"></button>
                <div class="flex-1 text-sm" :class="t.status==='done'?'line-through text-slate-400':''">
                  {{ t.title }} <tag v-if="t.phase" :label="ctx.shared.PHASE_LABEL[t.phase]" color="slate"></tag>
                </div>
                <div class="text-xs text-slate-400">{{ ctx.shared.fmtDate(t.due_date) }}</div>
              </div>
            </card>
          </div>

          <!-- 申请 -->
          <div v-show="tab==='applications'">
            <card title="申请院校">
              <empty v-if="!apps.length"></empty>
              <div v-for="a in apps" :key="a.id" class="py-2 border-b border-slate-100 last:border-0 flex justify-between items-center">
                <div>
                  <div class="font-medium text-sm">{{ a.school_name }}</div>
                  <div class="text-xs text-slate-400">{{ a.program_name || '' }} {{ a.degree || '' }} · 截止 {{ ctx.shared.fmtDate(a.deadline) }}</div>
                </div>
                <tag :label="ctx.shared.APP_STATUS_LABEL[a.status]||a.status" :color="a.status==='offer'?'green':(a.status==='rejection'?'red':'blue')"></tag>
              </div>
            </card>
          </div>

          <!-- Phase 5: 交付物 -->
          <div v-show="tab==='deliverables'">
            <card title="交付物（多版本）">
              <empty v-if="!deliverables.length" text="暂无交付物"></empty>
              <div v-for="d in deliverables" :key="d.id" class="py-2.5 border-b border-slate-100 last:border-0">
                <div class="flex justify-between items-center">
                  <div>
                    <div class="font-medium text-sm">{{ d.title }}</div>
                    <div class="text-xs text-slate-400">{{ d.advisor_name }} · {{ d.module_code || '' }}</div>
                  </div>
                  <div class="flex items-center gap-2">
                    <tag :label="({draft:'草稿',in_review:'审阅中',accepted:'已通过'})[d.status]||d.status"
                          :color="({draft:'slate',in_review:'amber',accepted:'green'})[d.status]||'slate'"></tag>
                    <button @click="openDeliverableDetail(d)" class="text-xs text-blue-600">版本</button>
                  </div>
                </div>
              </div>
            </card>
          </div>

          <!-- Phase 5: 交付物版本/审阅弹窗 -->
          <div v-if="deliverableModal" class="absolute inset-0 bg-black/40 flex items-center justify-center p-4 z-50" @click.self="deliverableModal=null">
            <div class="bg-white rounded-2xl w-full max-w-2xl p-6 max-h-[85vh] overflow-y-auto">
              <div class="flex justify-between items-center mb-4">
                <h3 class="font-bold">{{ deliverableModal.title }}</h3>
                <button @click="deliverableModal=null" class="text-slate-400 text-xl">✕</button>
              </div>
              <div v-if="deliverableModal.loading" class="text-sm text-slate-400">加载中…</div>
              <template v-else-if="deliverableModal.data">
                <div v-for="v in deliverableModal.data.versions" :key="v.id" class="border rounded-lg p-3 mb-3">
                  <div class="flex justify-between items-center mb-2">
                    <div class="font-medium">v{{ v.version }} <span class="text-xs text-slate-400">{{ v.submitted_by_name }}</span></div>
                    <div class="flex gap-1">
                      <tag :label="({draft:'草稿',in_review:'审阅中',accepted:'已通过'})[v.status]||v.status" color="slate"></tag>
                    </div>
                  </div>
                  <div class="text-sm text-slate-600 whitespace-pre-wrap bg-slate-50 rounded p-2 mb-2">{{ v.content || '(无内容)' }}</div>
                  <!-- 审阅意见 -->
                  <div v-if="v.comments && v.comments.length" class="border-t pt-2 mt-2 space-y-1">
                    <div v-for="c in v.comments" :key="c.id" class="text-xs flex gap-2">
                      <span :class="c.decision==='approve'?'text-emerald-600':(c.decision==='reject'?'text-red-600':'text-slate-500')">
                        {{ ({approve:'通过',reject:'驳回',comment:'评论'})[c.decision] }}
                      </span>
                      <span class="text-slate-400">{{ c.reviewer_name }}:</span>
                      <span class="text-slate-600">{{ c.content }}</span>
                    </div>
                  </div>
                  <!-- 审阅操作（仅 in_review 状态且当前用户是 owner/advisor）-->
                  <div v-if="v.status==='in_review' && ctx.shared.isStaff" class="flex gap-2 mt-2 pt-2 border-t">
                    <button @click="openReview(v)" class="text-xs bg-emerald-50 text-emerald-600 rounded px-2 py-1">审阅</button>
                  </div>
                </div>
                <!-- 出新版本（草稿） -->
                <div v-if="ctx.shared.isStaff" class="border-t pt-3 mt-3">
                  <div class="text-sm font-semibold mb-2">出新版本</div>
                  <textarea v-model="newVersion.content" placeholder="新版本内容/说明" class="w-full border rounded-lg px-3 py-2 text-sm" rows="2"></textarea>
                  <div class="flex items-center gap-2 mt-2">
                    <label class="text-sm"><input type="checkbox" v-model="newVersion.submit" /> 提交审阅</label>
                    <button @click="submitNewVersion" class="ml-auto bg-blue-600 text-white rounded-lg px-4 py-1.5 text-sm">提交 v{{ (deliverableModal.data.versions.length||0)+1 }}</button>
                  </div>
                </div>
              </template>
            </div>
          </div>

          <!-- Phase 5: 审阅弹窗 -->
          <div v-if="reviewModal" class="absolute inset-0 bg-black/50 flex items-center justify-center p-4 z-50" @click.self="reviewModal=null">
            <div class="bg-white rounded-2xl w-full max-w-sm p-6">
              <h3 class="font-bold mb-3">审阅 v{{ reviewModal.version }}</h3>
              <div class="space-y-3 text-sm">
                <div class="flex gap-2">
                  <label><input type="radio" v-model="review.decision" value="approve" /> 通过</label>
                  <label><input type="radio" v-model="review.decision" value="reject" /> 驳回</label>
                  <label><input type="radio" v-model="review.decision" value="comment" /> 评论</label>
                </div>
                <textarea v-model="review.content" placeholder="审阅意见（必填）" class="w-full border rounded-lg px-3 py-2" rows="3"></textarea>
              </div>
              <div class="flex gap-2 mt-4">
                <button @click="reviewModal=null" class="flex-1 border rounded-lg py-2 text-sm">取消</button>
                <button @click="submitReview" class="flex-1 bg-emerald-600 text-white rounded-lg py-2 text-sm">提交审阅</button>
              </div>
            </div>
          </div>
        </div>

        <!-- 换师弹窗 -->
        <div v-if="handoverTarget" class="absolute inset-0 bg-black/40 flex items-center justify-center p-4" @click.self="handoverTarget=null">
          <div class="bg-white rounded-2xl w-full max-w-sm p-6">
            <h3 class="font-bold mb-1">更换老师</h3>
            <div class="text-sm text-slate-500 mb-4">{{ ctx.shared.PHASE_LABEL[handoverTarget.phase] }} 环节：{{ handoverTarget.advisor_name }} →</div>
            <select v-model="handover.new_advisor_id" class="w-full border rounded-lg px-3 py-2 text-sm mb-3">
              <option value="">选新老师…</option>
              <option v-for="a in advisors.filter(x=>x.id!==handoverTarget.advisor_id)" :value="a.id">{{ a.name }}</option>
            </select>
            <textarea v-model="handover.handover_note" placeholder="交接说明（必填，会通知新旧老师、学生、家长）" class="w-full border rounded-lg px-3 py-2 text-sm" rows="3"></textarea>
            <div class="flex gap-2 mt-4">
              <button @click="handoverTarget=null" class="flex-1 border rounded-lg py-2 text-sm">取消</button>
              <button @click="doHandover" class="flex-1 bg-amber-600 text-white rounded-lg py-2 text-sm">确认更换</button>
            </div>
          </div>
        </div>
      </div>
    </div>`,
    computed: {
      tabs() {
        return [
          { id: "overview", label: "总览" },
          { id: "progress", label: "服务进程" },
          { id: "applications", label: "申请" },
          { id: "deliverables", label: "交付物" },  // Phase 5
        ];
      },
    },
    async mounted() { this.loadAll(); },
    methods: {
      async loadAll() {
        try {
          this.stu = await S().get("/api/students/" + this.studentId);
          const [a, c, t, m, ap, dv] = await Promise.all([
            S().get("/api/assignments?student_id=" + this.studentId),
            S().get("/api/contracts?student_id=" + this.studentId),
            S().get("/api/workflow/tasks?student_id=" + this.studentId),
            S().get("/api/workflow/milestones?student_id=" + this.studentId),
            S().get("/api/workflow/applications?student_id=" + this.studentId),
            S().get("/api/assignments/deliverables?student_id=" + this.studentId),  // Phase 5
          ]);
          this.assignments = a.items.filter(x => x.status === "active");
          this.contracts = c.items;
          this.tasks = t.items; this.milestones = m.items; this.apps = ap.items;
          this.deliverables = dv.items;  // Phase 5
          if (this.ctx.shared.isStaff) {
            const st = await S().get("/api/staff").catch(() => ({ items: [] }));
            this.advisors = st.items.filter(x => x.role === "advisor");
          }
        } catch (e) { this.ctx.toast(e.message, "error"); }
      },
      async assignTeacher() {
        if (!this.assignForm.advisor_member_id) { this.ctx.toast("请选老师", "error"); return; }
        try {
          await S().post("/api/assignments", { student_member_id: this.studentId, ...this.assignForm });
          this.ctx.toast("已分配"); this.loadAll();
        } catch (e) { this.ctx.toast(e.message, "error"); }
      },
      async doHandover() {
        if (!this.handover.new_advisor_id || !this.handover.handover_note) { this.ctx.toast("请选老师并填交接说明", "error"); return; }
        try {
          await S().post(`/api/assignments/${this.handoverTarget.id}/handover`, this.handover);
          this.ctx.toast("换师完成，已通知相关方"); this.handoverTarget = null; this.loadAll();
        } catch (e) { this.ctx.toast(e.message, "error"); }
      },
      async toggleTask(t) {
        try { await S().post(`/api/workflow/tasks/${t.id}/status`, { status: t.status === "done" ? "pending" : "done" }); this.loadAll(); }
        catch (e) { this.ctx.toast(e.message, "error"); }
      },
      async toggleMilestone(m) {
        try { await S().post(`/api/workflow/milestones/${m.id}/status`, { status: m.status === "done" ? "pending" : "done" }); this.loadAll(); }
        catch (e) { this.ctx.toast(e.message, "error"); }
      },
      // Phase 5: 交付物多版本
      async openDeliverableDetail(d) {
        this.deliverableModal = { deliverable_id: d.id, title: d.title, loading: true, data: null };
        try {
          const r = await S().get("/api/assignments/deliverables/" + d.id);
          this.deliverableModal.data = r;
        } catch (e) { this.ctx.toast(e.message, "error"); }
        this.deliverableModal.loading = false;
      },
      async submitNewVersion() {
        if (!this.newVersion.content.trim()) { this.ctx.toast("请填内容", "error"); return; }
        try {
          await S().post(`/api/assignments/deliverables/${this.deliverableModal.deliverable_id}/versions`,
                         { content: this.newVersion.content, submit: this.newVersion.submit });
          this.ctx.toast("已出新版本");
          this.newVersion = { content: "", submit: false };
          this.openDeliverableDetail(this.deliverableModal);
          this.loadAll();
        } catch (e) { this.ctx.toast(e.message, "error"); }
      },
      openReview(v) {
        this.reviewModal = { version_id: v.id, version: v.version };
        this.review = { decision: "approve", content: "" };
      },
      async submitReview() {
        if (!this.review.content.trim()) { this.ctx.toast("请填审阅意见", "error"); return; }
        try {
          await S().post(`/api/assignments/deliverables/versions/${this.reviewModal.version_id}/review`,
                         { decision: this.review.decision, content: this.review.content });
          this.ctx.toast("审阅已提交"); this.reviewModal = null;
          this.openDeliverableDetail(this.deliverableModal);
          this.loadAll();
        } catch (e) { this.ctx.toast(e.message, "error"); }
      },
    },
  });

  // ════════════════════════════════════════════════════════════
  // 机构端 — 签约管理
  // ════════════════════════════════════════════════════════════
  const ContractsView = defineComponent({
    components: { Card, Tag, Empty },
    props: ["ctx"],
    data: () => ({
      items: [], modules: [], students: [], showNew: false, detail: null,
      // Phase 5: items 数组（每模块独立金额），不是 modules 字符串数组
      form: { student_member_id: "", items: [], signed_date: new Date().toISOString().slice(0, 10), notes: "" },
      pay: { amount: "", pay_type: "定金", pay_method: "微信", paid_at: new Date().toISOString().slice(0, 10) },
      saving: false,
      renew: { open: false, target: null, extend_months: 6, new_items: [] },  // Phase 5 续约
    }),
    template: `
    <div>
      <div class="flex items-center justify-between mb-4">
        <h1 class="text-xl font-bold">签约管理</h1>
        <button @click="showNew=true" class="bg-blue-600 text-white px-4 py-1.5 rounded-lg text-sm">+ 新建合同</button>
      </div>

      <card>
        <empty v-if="!items.length" text="暂无合同"></empty>
        <table v-else class="w-full text-sm">
          <thead><tr class="text-left text-slate-400 text-xs border-b border-slate-100">
            <th class="py-2">合同号</th><th>学生</th><th>金额</th><th>已收</th><th>状态</th><th>签约日期</th><th></th>
          </tr></thead>
          <tbody>
            <tr v-for="c in items" :key="c.id" @click="openDetail(c.id)" class="border-b border-slate-50 hover:bg-slate-50 cursor-pointer">
              <td class="py-2.5 font-mono text-xs">{{ c.contract_no }}</td>
              <td class="font-medium">{{ c.student_name }}</td>
              <td>{{ ctx.shared.fmtMoney(c.total_amount) }}</td>
              <td :class="c.paid_amount>=c.total_amount?'text-emerald-600':'text-amber-600'">{{ ctx.shared.fmtMoney(c.paid_amount) }}</td>
              <td><tag :label="ctx.shared.CONTRACT_STATUS_LABEL[c.status]" :color="c.status==='active'?'blue':(c.status==='completed'?'green':'red')"></tag></td>
              <td class="text-slate-400 text-xs">{{ ctx.shared.fmtDate(c.signed_date) }}</td>
              <td class="text-xs text-slate-400">{{ (c.items||[]).length }} 项</td>
            </tr>
          </tbody>
        </table>
      </card>

      <!-- 新建合同 -->
      <div v-if="showNew" class="fixed inset-0 bg-black/40 flex items-center justify-center z-40 p-4" @click.self="showNew=false">
        <div class="bg-white rounded-2xl w-full max-w-lg p-6 max-h-[85vh] overflow-y-auto">
          <h3 class="font-bold mb-4">新建合同</h3>
          <div class="space-y-3 text-sm">
            <select v-model="form.student_member_id" class="w-full border rounded-lg px-3 py-2">
              <option value="">选学生 *</option>
              <option v-for="s in students" :value="s.id">{{ s.name }}</option>
            </select>
            <div>
              <div class="text-xs text-slate-400 mb-1.5">服务包（每项独立填金额，合计=合同总额）*</div>
              <div class="space-y-1.5 max-h-64 overflow-y-auto border rounded-lg p-2">
                <div v-for="m in modules" :key="m.code" class="flex items-center gap-2">
                  <label class="flex items-center gap-1.5 text-sm flex-1 cursor-pointer">
                    <input type="checkbox" :value="m.code"
                           :checked="form.items.find(it=>it.module_code===m.code)"
                           @change="toggleItem(m.code, m.base_price||0, $event.target.checked)" />
                    {{ m.name_zh }}
                  </label>
                  <input v-if="form.items.find(it=>it.module_code===m.code)"
                         type="number" :value="form.items.find(it=>it.module_code===m.code).amount"
                         @input="updateItemAmount(m.code, $event.target.value)"
                         class="w-24 border rounded px-2 py-1 text-right" placeholder="¥" />
                </div>
              </div>
              <div class="text-xs text-slate-500 mt-1.5 flex justify-between">
                <span>已选 {{ form.items.length }} 项</span>
                <span>合计：<b class="text-blue-600">¥{{ form.items.reduce((s,i)=>s+(+i.amount||0),0).toLocaleString() }}</b></span>
              </div>
            </div>
            <div><div class="text-xs text-slate-400 mb-1">签约日期</div><input v-model="form.signed_date" type="date" class="w-full border rounded-lg px-3 py-2" /></div>
            <textarea v-model="form.notes" placeholder="备注" class="w-full border rounded-lg px-3 py-2" rows="2"></textarea>
          </div>
          <div class="flex gap-2 mt-5">
            <button @click="showNew=false" class="flex-1 border rounded-lg py-2 text-sm">取消</button>
            <button @click="saveNew" :disabled="saving" class="flex-1 bg-blue-600 text-white rounded-lg py-2 text-sm disabled:opacity-50">{{ saving?'…':'创建' }}</button>
          </div>
        </div>
      </div>

      <!-- Phase 5: 续约弹窗 -->
      <div v-if="renew.open" class="fixed inset-0 bg-black/40 flex items-center justify-center z-40 p-4" @click.self="renew.open=false">
        <div class="bg-white rounded-2xl w-full max-w-lg p-6 max-h-[85vh] overflow-y-auto">
          <h3 class="font-bold mb-1">续约</h3>
          <div class="text-xs text-slate-500 mb-4">基于原合同 {{ renew.target && renew.target.contract_no }} 创建新合同</div>
          <div class="text-sm space-y-3">
            <div class="flex items-center gap-2">
              <span class="text-xs text-slate-400 w-20">延期</span>
              <input v-model.number="renew.extend_months" type="number" min="1" max="36" class="w-20 border rounded px-2 py-1" />
              <span class="text-xs text-slate-500">月</span>
            </div>
            <div>
              <div class="text-xs text-slate-400 mb-1.5">服务包（可调整）</div>
              <div class="space-y-1.5 border rounded-lg p-2 max-h-48 overflow-y-auto">
                <div v-for="m in modules" :key="m.code" class="flex items-center gap-2">
                  <label class="flex items-center gap-1.5 text-sm flex-1">
                    <input type="checkbox" :checked="renew.new_items.find(it=>it.module_code===m.code)"
                           @change="toggleRenewItem(m.code, $event.target.checked)" />
                    {{ m.name_zh }}
                  </label>
                  <input v-if="renew.new_items.find(it=>it.module_code===m.code)"
                         type="number" :value="renew.new_items.find(it=>it.module_code===m.code).amount"
                         @input="updateRenewItemAmount(m.code, $event.target.value)"
                         class="w-24 border rounded px-2 py-1 text-right" />
                </div>
              </div>
              <div class="text-xs text-slate-500 mt-1.5 text-right">
                合计：<b class="text-blue-600">¥{{ renew.new_items.reduce((s,i)=>s+(+i.amount||0),0).toLocaleString() }}</b>
              </div>
            </div>
          </div>
          <div class="flex gap-2 mt-5">
            <button @click="renew.open=false" class="flex-1 border rounded-lg py-2 text-sm">取消</button>
            <button @click="doRenew" :disabled="saving" class="flex-1 bg-blue-600 text-white rounded-lg py-2 text-sm disabled:opacity-50">{{ saving?'…':'续约' }}</button>
          </div>
        </div>
      </div>

      <!-- 合同详情（收款）-->
      <div v-if="detail" class="fixed inset-0 z-40" @click.self="detail=null">
        <div class="absolute inset-0 bg-black/30"></div>
        <div class="absolute right-0 top-0 h-full w-full max-w-md bg-white shadow-2xl overflow-y-auto p-5">
          <div class="flex justify-between items-center mb-4">
            <h3 class="font-bold font-mono text-sm">{{ detail.contract_no }}</h3>
            <button @click="detail=null" class="text-slate-400 text-xl">✕</button>
          </div>
          <div class="grid grid-cols-2 gap-2 text-sm mb-4">
            <div><span class="text-slate-400">学生</span> {{ detail.student_name }}</div>
            <div><span class="text-slate-400">总额</span> {{ ctx.shared.fmtMoney(detail.total_amount) }}</div>
            <div><span class="text-slate-400">已收</span> <span class="text-emerald-600 font-medium">{{ ctx.shared.fmtMoney(detail.paid_amount) }}</span></div>
            <div><span class="text-slate-400">待收</span> <span class="text-amber-600">{{ ctx.shared.fmtMoney(detail.total_amount - detail.paid_amount) }}</span></div>
          </div>

          <!-- Phase 5: 服务项明细 -->
          <div v-if="detail.items && detail.items.length" class="mb-4">
            <div class="text-sm font-semibold mb-2">服务项（{{ detail.items.length }}）</div>
            <div class="space-y-1.5">
              <div v-for="it in detail.items" :key="it.id" class="flex items-center justify-between bg-slate-50 rounded-lg px-3 py-2 text-sm">
                <div>
                  <span class="font-medium">{{ (modules.find(m=>m.code===it.module_code)||{}).name_zh || it.module_code }}</span>
                  <span class="ml-2 text-xs text-slate-500">{{ ctx.shared.fmtMoney(it.amount) }}</span>
                </div>
                <tag :label="({pending:'待启动',in_progress:'进行中',delivered:'已交付',completed:'已完成',cancelled:'已取消',refunded:'已退'})[it.status]||it.status"
                      :color="({completed:'green',in_progress:'blue',delivered:'purple',refunded:'red',cancelled:'slate'})[it.status]||'amber'"></tag>
              </div>
            </div>
          </div>

          <!-- Phase 5: 续约按钮（活跃合同） -->
          <div v-if="detail.status==='active'" class="mb-4">
            <button @click="startRenew(detail)" class="w-full border border-blue-200 text-blue-600 rounded-lg py-2 text-sm hover:bg-blue-50">
              续约此合同
            </button>
          </div>
          <div class="text-sm font-semibold mb-2">收款登记</div>
          <div class="space-y-2 mb-4 text-sm">
            <input v-model.number="pay.amount" type="number" placeholder="金额（元）" class="w-full border rounded-lg px-3 py-2" />
            <div class="flex gap-2">
              <select v-model="pay.pay_type" class="flex-1 border rounded-lg px-2 py-2"><option>定金</option><option>中期</option><option>尾款</option><option>其他</option></select>
              <select v-model="pay.pay_method" class="flex-1 border rounded-lg px-2 py-2"><option>微信</option><option>支付宝</option><option>对公转账</option><option>现金</option></select>
            </div>
            <button @click="addPayment" class="w-full bg-emerald-600 text-white rounded-lg py-2 text-sm">记一笔收款</button>
          </div>
          <div class="text-sm font-semibold mb-2">收款记录</div>
          <empty v-if="!detail.payments || !detail.payments.length"></empty>
          <div v-for="p in detail.payments" :key="p.id" class="flex justify-between py-2 border-b border-slate-100 last:border-0 text-sm">
            <span>{{ p.pay_type }} · {{ p.pay_method }}</span>
            <span class="font-medium text-emerald-600">{{ ctx.shared.fmtMoney(p.amount) }}</span>
            <span class="text-xs text-slate-400">{{ ctx.shared.fmtDate(p.paid_at) }}</span>
          </div>
        </div>
      </div>
    </div>`,
    async mounted() { this.load(); },
    methods: {
      async load() {
        try {
          const [c, m, s] = await Promise.all([
            S().get("/api/contracts?page_size=200"), S().get("/api/contracts/modules"), S().get("/api/students?page_size=200"),
          ]);
          this.items = c.items; this.modules = m.modules; this.students = s.items;
        } catch (e) { this.ctx.toast(e.message, "error"); }
      },
      async saveNew() {
        if (!this.form.student_member_id || !this.form.items.length) {
          this.ctx.toast("请选学生 + 至少勾一个服务项", "error"); return;
        }
        this.saving = true;
        try {
          await S().post("/api/contracts", this.form);
          this.ctx.toast("合同已创建"); this.showNew = false;
          this.form = { student_member_id: "", items: [], signed_date: new Date().toISOString().slice(0, 10), notes: "" };
          this.load();
        } catch (e) { this.ctx.toast(e.message, "error"); }
        this.saving = false;
      },
      // Phase 5: 勾选/取消服务项
      toggleItem(code, defaultAmount, checked) {
        if (checked) {
          this.form.items.push({ module_code: code, amount: defaultAmount });
        } else {
          this.form.items = this.form.items.filter(it => it.module_code !== code);
        }
      },
      updateItemAmount(code, val) {
        const it = this.form.items.find(x => x.module_code === code);
        if (it) it.amount = +val || 0;
      },
      // Phase 5: 续约
      startRenew(c) {
        this.renew.target = c;
        this.renew.extend_months = 6;
        // 默认拷贝原合同服务项（带金额）
        this.renew.new_items = (c.items || []).map(it => ({ module_code: it.module_code, amount: it.amount }));
        this.renew.open = true;
      },
      toggleRenewItem(code, checked) {
        const has = this.renew.new_items.find(it => it.module_code === code);
        if (checked && !has) {
          const m = this.modules.find(x => x.code === code);
          this.renew.new_items.push({ module_code: code, amount: m ? m.base_price || 0 : 0 });
        } else if (!checked && has) {
          this.renew.new_items = this.renew.new_items.filter(it => it.module_code !== code);
        }
      },
      updateRenewItemAmount(code, val) {
        const it = this.renew.new_items.find(x => x.module_code === code);
        if (it) it.amount = +val || 0;
      },
      async doRenew() {
        if (!this.renew.new_items.length) { this.ctx.toast("请勾至少一项", "error"); return; }
        this.saving = true;
        try {
          const r = await S().post(`/api/contracts/${this.renew.target.id}/renew`,
                                    { extend_months: this.renew.extend_months,
                                      new_items: this.renew.new_items });
          this.ctx.toast("续约成功：" + r.new_contract_no);
          this.renew.open = false;
          this.load();
        } catch (e) { this.ctx.toast(e.message, "error"); }
        this.saving = false;
      },
      async openDetail(id) {
        try { this.detail = await S().get("/api/contracts/" + id); } catch (e) { this.ctx.toast(e.message, "error"); }
      },
      async addPayment() {
        if (!this.pay.amount) { this.ctx.toast("请填金额", "error"); return; }
        try { await S().post(`/api/contracts/${this.detail.id}/payments`, this.pay); this.ctx.toast("已登记"); this.pay.amount = ""; this.openDetail(this.detail.id); this.load(); }
        catch (e) { this.ctx.toast(e.message, "error"); }
      },
    },
  });

  // ════════════════════════════════════════════════════════════
  // 机构端 — 员工 / 报表 / 设置（精简）
  // ════════════════════════════════════════════════════════════
  const StaffView = defineComponent({
    components: { Card, Tag, Empty },
    props: ["ctx"],
    data: () => ({ items: [], showNew: false, form: { name: "", username: "", password: "", title: "", specialty: "" }, saving: false }),
    template: `
    <div>
      <div class="flex items-center justify-between mb-4">
        <h1 class="text-xl font-bold">员工管理</h1>
        <button @click="showNew=true" class="bg-blue-600 text-white px-4 py-1.5 rounded-lg text-sm">+ 添加员工</button>
      </div>
      <card>
        <empty v-if="!items.length"></empty>
        <table v-else class="w-full text-sm">
          <thead><tr class="text-left text-slate-400 text-xs border-b border-slate-100">
            <th class="py-2">姓名</th><th>角色</th><th>擅长</th><th>在读学生</th><th>本月交付</th><th>名下线索</th>
          </tr></thead>
          <tbody>
            <tr v-for="s in items" :key="s.id" class="border-b border-slate-50">
              <td class="py-2.5 font-medium">{{ s.name }} <span class="text-xs text-slate-400">{{ s.title||'' }}</span></td>
              <td><tag :label="s.role==='owner'?'主管':'顾问'" :color="s.role==='owner'?'purple':'blue'"></tag></td>
              <td class="text-slate-500 text-xs">{{ s.specialty || '—' }}</td>
              <td>{{ s.active_students }}</td><td>{{ s.month_deliverables }}</td><td>{{ s.leads_count }}</td>
            </tr>
          </tbody>
        </table>
      </card>

      <div v-if="showNew" class="fixed inset-0 bg-black/40 flex items-center justify-center z-40 p-4" @click.self="showNew=false">
        <div class="bg-white rounded-2xl w-full max-w-sm p-6">
          <h3 class="font-bold mb-4">添加员工</h3>
          <div class="space-y-3 text-sm">
            <input v-model="form.name" placeholder="姓名 *" class="w-full border rounded-lg px-3 py-2" />
            <input v-model="form.username" placeholder="登录用户名 *" class="w-full border rounded-lg px-3 py-2" />
            <input v-model="form.password" placeholder="初始密码 *（≥6位）" class="w-full border rounded-lg px-3 py-2" />
            <input v-model="form.title" placeholder="头衔（如 资深顾问）" class="w-full border rounded-lg px-3 py-2" />
            <input v-model="form.specialty" placeholder="擅长方向（如 美本申请）" class="w-full border rounded-lg px-3 py-2" />
          </div>
          <div class="flex gap-2 mt-5">
            <button @click="showNew=false" class="flex-1 border rounded-lg py-2 text-sm">取消</button>
            <button @click="saveNew" :disabled="saving" class="flex-1 bg-blue-600 text-white rounded-lg py-2 text-sm disabled:opacity-50">{{ saving?'…':'添加' }}</button>
          </div>
        </div>
      </div>
    </div>`,
    async mounted() { this.load(); },
    methods: {
      async load() { try { const d = await S().get("/api/staff"); this.items = d.items; } catch (e) { this.ctx.toast(e.message, "error"); } },
      async saveNew() {
        if (!this.form.name || !this.form.username || !this.form.password) { this.ctx.toast("请填姓名/用户名/密码", "error"); return; }
        this.saving = true;
        try { await S().post("/api/staff", this.form); this.ctx.toast("已添加"); this.showNew = false; this.form = { name: "", username: "", password: "", title: "", specialty: "" }; this.load(); }
        catch (e) { this.ctx.toast(e.message, "error"); }
        this.saving = false;
      },
    },
  });

  // Phase 5: 撞单工作台（owner）
  const CollisionsView = defineComponent({
    components: { Card, Tag, Empty },
    props: ["ctx"],
    data: () => ({ groups: [], loading: true, merging: null, mergeNote: "" }),
    template: `
    <div>
      <div class="flex items-center justify-between mb-4">
        <h1 class="text-xl font-bold">撞单工作台</h1>
        <div class="text-sm text-slate-400">同一手机号/微信的多条线索</div>
      </div>
      <empty v-if="!loading && !groups.length" text="暂无撞单"></empty>
      <div v-if="loading" class="text-sm text-slate-400">加载中…</div>
      <div v-for="g in groups" :key="g.key" class="bg-white rounded-xl border border-slate-200 p-5 mb-4">
        <div class="flex items-center justify-between mb-3">
          <div class="font-medium">📱 {{ g.key }}</div>
          <span class="text-xs text-slate-400">{{ g.leads.length }} 条重复</span>
        </div>
        <table class="w-full text-sm mb-3">
          <thead><tr class="text-left text-slate-400 text-xs border-b border-slate-100">
            <th class="py-2">学生</th><th>来源</th><th>归属顾问</th><th>状态</th><th>录入时间</th>
          </tr></thead>
          <tbody>
            <tr v-for="l in g.leads" :key="l.lead_id" class="border-b border-slate-50">
              <td class="py-2 font-medium">{{ l.student_name }}</td>
              <td class="text-slate-500 text-xs">{{ l.source || '—' }}</td>
              <td class="text-slate-500">{{ l.assigned_advisor_id || '未分配' }}</td>
              <td><tag :label="ctx.shared.LEAD_STATUS_LABEL[l.status]||l.status" color="blue"></tag></td>
              <td class="text-slate-400 text-xs">{{ ctx.shared.fmtDate(l.created_at) }}</td>
            </tr>
          </tbody>
        </table>
        <div class="flex items-center gap-2">
          <select v-model="g._keep" class="border rounded-lg px-2 py-1.5 text-sm flex-1">
            <option value="">保留哪条？</option>
            <option v-for="l in g.leads" :value="l.lead_id">保留 {{ l.student_name }} ({{ l.source }} · {{ ctx.shared.fmtDate(l.created_at) }})</option>
          </select>
          <input v-model="g._note" placeholder="合并原因（必填）" class="border rounded-lg px-3 py-1.5 text-sm flex-1" />
          <button @click="doMerge(g)" :disabled="merging===g.key" class="bg-amber-600 text-white rounded-lg px-4 py-1.5 text-sm disabled:opacity-50">
            {{ merging===g.key ? '合并中…' : '合并' }}
          </button>
        </div>
      </div>
    </div>`,
    async mounted() { this.load(); },
    methods: {
      async load() {
        try {
          const d = await S().get("/api/leads/collisions");
          this.groups = d.groups.map(g => ({...g, _keep: "", _note: ""}));
        } catch (e) { this.ctx.toast(e.message, "error"); }
        this.loading = false;
      },
      async doMerge(g) {
        if (!g._keep || !g._note) { this.ctx.toast("请选保留线索 + 填合并原因", "error"); return; }
        const others = g.leads.filter(l => l.lead_id !== g._keep).map(l => l.lead_id);
        if (!others.length) { this.ctx.toast("无需合并", "error"); return; }
        this.merging = g.key;
        try {
          await S().post("/api/leads/merge", {
            keep_lead_id: g._keep,
            merge_lead_ids: others,
            reason: g._note
          });
          this.ctx.toast("合并完成");
          this.load();
        } catch (e) { this.ctx.toast(e.message, "error"); }
        this.merging = null;
      },
    },
  });

  const ReportsView = defineComponent({
    components: { Card, Empty },
    props: ["ctx"],
    data: () => ({ funnel: {}, roi: [], loss: {} }),
    template: `
    <div>
      <h1 class="text-xl font-bold mb-4">报表</h1>
      <card title="线索漏斗">
        <empty v-if="!Object.keys(funnel.by_status||{}).length"></empty>
        <div v-for="(label, s) in ctx.shared.LEAD_STATUS_LABEL" :key="s" class="flex items-center gap-3 py-1.5">
          <div class="w-20 text-sm text-slate-500">{{ label }}</div>
          <div class="flex-1 bg-slate-100 rounded-full h-5 overflow-hidden">
            <div class="bg-blue-500 h-full rounded-full" :style="{width: pct(funnel.by_status[s])+'%'}"></div>
          </div>
          <div class="w-10 text-right text-sm font-medium">{{ funnel.by_status[s]||0 }}</div>
        </div>
      </card>

      <!-- Phase 5: 流失原因 -->
      <card title="流失原因分布" class="mt-4">
        <empty v-if="!(loss.by_reason||[]).length" text="暂无流失"></empty>
        <div v-for="r in loss.by_reason||[]" :key="r.reason" class="flex items-center gap-3 py-1.5">
          <div class="w-32 text-sm text-slate-500">{{ ctx.shared.LOST_REASON_LABEL[r.reason]||r.reason }}</div>
          <div class="flex-1 bg-slate-100 rounded-full h-5 overflow-hidden">
            <div class="bg-red-400 h-full rounded-full" :style="{width: r.pct+'%'}"></div>
          </div>
          <div class="w-16 text-right text-sm font-medium">{{ r.count }} <span class="text-xs text-slate-400">({{ r.pct }}%)</span></div>
        </div>
      </card>

      <!-- Phase 5: 来源 ROI -->
      <card title="来源 ROI" class="mt-4">
        <empty v-if="!roi.length" text="暂无数据"></empty>
        <table v-else class="w-full text-sm">
          <thead><tr class="text-left text-slate-400 text-xs border-b border-slate-100">
            <th class="py-2">来源</th><th>线索</th><th>转化</th><th>转化率</th><th>签约额</th><th>CPA</th><th>ROI</th>
          </tr></thead>
          <tbody>
            <tr v-for="r in roi" :key="r.source" class="border-b border-slate-50">
              <td class="py-2 font-medium">{{ r.source }}</td>
              <td>{{ r.leads }}</td>
              <td>{{ r.converted }}</td>
              <td :class="r.conv_rate>=30?'text-emerald-600':'text-slate-500'">{{ r.conv_rate }}%</td>
              <td>{{ ctx.shared.fmtMoney(r.revenue_cents/100) }}</td>
              <td>{{ r.cpa_cents===0?'—':ctx.shared.fmtMoney(r.cpa_cents/100) }}</td>
              <td :class="r.roi==='∞'?'text-blue-600':'text-slate-700'">{{ r.roi }}</td>
            </tr>
          </tbody>
        </table>
      </card>
    </div>`,
    async mounted() {
      try {
        this.funnel = await S().get("/api/leads/stats/funnel");
        if (this.ctx.shared.isOwner) {
          this.roi = (await S().get("/api/reports/source-roi")).items;
          this.loss = await S().get("/api/reports/loss-reasons");
        }
      } catch (e) { this.ctx.toast(e.message, "error"); }
    },
    methods: {
      pct(n) { const total = Object.values(this.funnel.by_status || {}).reduce((a, b) => a + b, 0); return total ? Math.round((n || 0) / total * 100) : 0; },
    },
  });

  const SettingsView = defineComponent({
    components: { Card },
    props: ["ctx"],
    data: () => ({
      user: null,
      org: null,
      isOwner: false,
      loading: true,
      saving: false,
      savingPwd: false,
      err: "",
      ok: "",
      profileForm: { name: "", phone: "", email: "", wechat: "" },
      pwdForm: { old_password: "", new_password: "", confirm: "" },
      form: { name: "", description: "", address: "", phone: "", email: "", website: "", logo_url: "" },
    }),
    template: `
    <div>
      <h1 class="text-xl font-bold mb-4">设置</h1>

      <!-- 个人信息 — 任何登录用户都能改自己的 -->
      <card title="个人信息">
        <div class="space-y-3">
          <div class="grid md:grid-cols-2 gap-3">
            <div>
              <label class="block text-xs text-slate-500 mb-1">姓名 <span class="text-red-500">*</span></label>
              <input v-model="profileForm.name" placeholder="您的姓名"
                     class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
            </div>
            <div>
              <label class="block text-xs text-slate-500 mb-1">个人手机</label>
              <input v-model="profileForm.phone" placeholder="13900000000"
                     class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
            </div>
          </div>
          <div class="grid md:grid-cols-2 gap-3">
            <div>
              <label class="block text-xs text-slate-500 mb-1">个人邮箱</label>
              <input v-model="profileForm.email" type="email" placeholder="you@example.com"
                     class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
            </div>
            <div>
              <label class="block text-xs text-slate-500 mb-1">微信号</label>
              <input v-model="profileForm.wechat" placeholder="可选"
                     class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
            </div>
          </div>
          <div v-if="profileErr" class="text-sm text-red-500">{{ profileErr }}</div>
          <div v-if="profileOk" class="text-sm text-emerald-600">{{ profileOk }}</div>
          <button @click="saveProfile" :disabled="saving || !profileForm.name.trim()"
                  class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium disabled:opacity-50">
            {{ saving ? '保存中…' : '保存个人信息' }}
          </button>
        </div>
      </card>

      <!-- 修改密码 — 任何登录用户都能改自己的 -->
      <card title="修改密码" class="mt-4">
        <div class="space-y-3">
          <div>
            <label class="block text-xs text-slate-500 mb-1">当前密码</label>
            <input v-model="pwdForm.old_password" type="password" placeholder="输入当前密码"
                   class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
          </div>
          <div>
            <label class="block text-xs text-slate-500 mb-1">新密码 (≥ 8 位)</label>
            <input v-model="pwdForm.new_password" type="password" placeholder="新密码"
                   class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
          </div>
          <div>
            <label class="block text-xs text-slate-500 mb-1">确认新密码</label>
            <input v-model="pwdForm.confirm" type="password" placeholder="再次输入新密码"
                   class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
          </div>
          <div v-if="pwdErr" class="text-sm text-red-500">{{ pwdErr }}</div>
          <div v-if="pwdOk" class="text-sm text-emerald-600">{{ pwdOk }}</div>
          <button @click="savePassword" :disabled="savingPwd || !canChangePwd"
                  class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium disabled:opacity-50">
            {{ savingPwd ? '修改中…' : '修改密码' }}
          </button>
        </div>
      </card>

      <!-- 机构信息 — owner 可编辑, 其他角色只读 -->
      <card title="机构信息" class="mt-4">
        <div v-if="loading" class="text-sm text-slate-400">加载中…</div>
        <template v-else>
          <div class="space-y-3">
            <div>
              <label class="block text-xs text-slate-500 mb-1">机构名称 <span class="text-red-500">*</span></label>
              <input v-model="form.name" :disabled="!isOwner" placeholder="例: 我的留学工作室"
                     class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none disabled:bg-slate-100 disabled:text-slate-500" />
            </div>
            <div>
              <label class="block text-xs text-slate-500 mb-1">机构简介</label>
              <textarea v-model="form.description" :disabled="!isOwner" rows="3" placeholder="机构业务范围、特色等"
                        class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none disabled:bg-slate-100 disabled:text-slate-500"></textarea>
            </div>
            <div class="grid md:grid-cols-2 gap-3">
              <div>
                <label class="block text-xs text-slate-500 mb-1">商务地址</label>
                <input v-model="form.address" :disabled="!isOwner" placeholder="例: 北京市朝阳区..."
                       class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none disabled:bg-slate-100 disabled:text-slate-500" />
              </div>
              <div>
                <label class="block text-xs text-slate-500 mb-1">公开联系电话</label>
                <input v-model="form.phone" :disabled="!isOwner" placeholder="010-xxxx-xxxx"
                       class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none disabled:bg-slate-100 disabled:text-slate-500" />
              </div>
            </div>
            <div class="grid md:grid-cols-2 gap-3">
              <div>
                <label class="block text-xs text-slate-500 mb-1">公开联系邮箱</label>
                <input v-model="form.email" :disabled="!isOwner" type="email" placeholder="contact@example.com"
                       class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none disabled:bg-slate-100 disabled:text-slate-500" />
              </div>
              <div>
                <label class="block text-xs text-slate-500 mb-1">官方网站</label>
                <input v-model="form.website" :disabled="!isOwner" placeholder="https://example.com"
                       class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none disabled:bg-slate-100 disabled:text-slate-500" />
              </div>
            </div>
            <div>
              <label class="block text-xs text-slate-500 mb-1">机构 Logo URL</label>
              <input v-model="form.logo_url" :disabled="!isOwner" placeholder="https://..."
                     class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none disabled:bg-slate-100 disabled:text-slate-500" />
            </div>
          </div>
          <div v-if="err" class="text-sm text-red-500 mt-3">{{ err }}</div>
          <div v-if="ok" class="text-sm text-emerald-600 mt-3">{{ ok }}</div>
          <div v-if="isOwner" class="mt-4 flex items-center gap-3">
            <button @click="save" :disabled="saving || !form.name.trim()"
                    class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium disabled:opacity-50">
              {{ saving ? '保存中…' : '保存机构信息' }}
            </button>
            <span v-if="!isOwner" class="text-xs text-slate-400">（只读, 非 owner）</span>
          </div>
          <div v-else class="text-xs text-slate-400 mt-2">仅 owner 可编辑机构信息</div>
        </template>
      </card>

      <!-- 当前账号 (只读) -->
      <card title="当前账号" class="mt-4">
        <div class="text-sm space-y-2">
          <div><span class="text-slate-400">账号</span> {{ user && user.name }}（{{ user && user.username }}）</div>
          <div><span class="text-slate-400">角色</span> {{ user && user.role }} <span v-if="!isOwner" class="text-xs text-slate-400">(只读)</span></div>
        </div>
      </card>

      <!-- Gobob 数据 API 说明 -->
      <card title="Gobob 数据 API" class="mt-4">
        <div class="text-sm text-slate-500">
          智能评估 / 院校数据由 Gobob Data API 提供。API Key 在后端环境变量 <code class="bg-slate-100 px-1 rounded">GOBOB_API_KEY</code> 配置，
          修改后重启后端生效。申请方式见仓库 <code class="bg-slate-100 px-1 rounded">docs/GETTING_GOBOB_API_KEY.md</code>。
        </div>
      </card>
    </div>`,
    computed: {
      canChangePwd() {
        return this.pwdForm.old_password
          && this.pwdForm.new_password.length >= 8
          && this.pwdForm.new_password === this.pwdForm.confirm;
      },
    },
    methods: {
      profileErr: "",
      profileOk: "",
      pwdErr: "",
      pwdOk: "",
      async load() {
        this.loading = true; this.err = "";
        try {
          const u = S().getUser();
          this.user = u;
          this.isOwner = u && u.role === "owner";
          // 加载个人信息
          this.profileForm = {
            name: u && u.name || "",
            phone: u && u.phone || "",
            email: u && u.email || "",
            wechat: u && u.wechat || "",
          };
          // 加载机构信息
          const data = await S().get("/api/orgs/me");
          this.org = data;
          this.form = {
            name: data.name || "",
            description: data.description || "",
            address: data.address || "",
            phone: data.phone || "",
            email: data.email || "",
            website: data.website || "",
            logo_url: data.logo_url || "",
          };
        } catch (e) { this.err = "加载失败: " + e.message; }
        this.loading = false;
      },
      async saveProfile() {
        this.saving = true; this.profileErr = ""; this.profileOk = "";
        try {
          const body = {};
          for (const k of Object.keys(this.profileForm)) {
            const v = this.profileForm[k];
            if (v && v.trim()) body[k] = v;
          }
          const r = await S().patch("/api/profile", body);
          this.profileOk = `已更新 ${r.updated} 项`;
          // 同步本地 user (name/phone/email/wechat) + 写回 localStorage
          const u = S().getUser() || {};
          Object.assign(u, this.profileForm);
          localStorage.setItem(S().USER_KEY || "soho_user", JSON.stringify(u));
          this.user = u;
        } catch (e) { this.profileErr = "保存失败: " + e.message; }
        this.saving = false;
      },
      async savePassword() {
        this.savingPwd = true; this.pwdErr = ""; this.pwdOk = "";
        try {
          await S().post("/api/change-password", {
            old_password: this.pwdForm.old_password,
            new_password: this.pwdForm.new_password,
          });
          this.pwdOk = "密码修改成功, 下次登录请用新密码";
          this.pwdForm = { old_password: "", new_password: "", confirm: "" };
        } catch (e) { this.pwdErr = e.message || "修改失败"; }
        this.savingPwd = false;
      },
      async save() {
        this.saving = true; this.err = ""; this.ok = "";
        try {
          // PUT 走 PATCH 语义 — 只发非空字段 (空字符串会被后端忽略)
          const body = {};
          for (const k of Object.keys(this.form)) {
            const v = this.form[k];
            if (v && v.trim()) body[k] = v;
          }
          const r = await S().put("/api/orgs/me", body);
          this.ok = `已更新 ${r.updated} 项`;
          await this.load();
        } catch (e) { this.err = "保存失败: " + e.message; }
        this.saving = false;
      },
    },
    mounted() { this.load(); },
  });

  // ════════════════════════════════════════════════════════════
  // 学生/家长端
  // ════════════════════════════════════════════════════════════
  const MyProgressView = defineComponent({
    components: { Card, Tag, Empty, Stat },
    props: ["ctx"],
    data: () => ({ stu: null, tasks: [], milestones: [], loading: true }),
    template: `
    <div>
      <h1 class="text-xl font-bold mb-4">我的进度</h1>
      <div v-if="loading" class="text-sm text-slate-400">加载中…</div>
      <template v-else>
        <div class="grid grid-cols-3 gap-4 mb-6">
          <stat label="已完成任务" :value="done"></stat>
          <stat label="进行中" :value="doing"></stat>
          <stat label="待办" :value="todo"></stat>
        </div>
        <card title="我的负责老师" v-if="stu && stu.advisors && stu.advisors.length">
          <div class="flex flex-wrap gap-2">
            <div v-for="a in stu.advisors" :key="a.id" class="bg-blue-50 border border-blue-100 rounded-lg px-3 py-2 text-sm">
              <tag :label="ctx.shared.PHASE_LABEL[a.phase]" color="blue"></tag> {{ a.advisor_name }}
            </div>
          </div>
        </card>
        <card title="里程碑" class="mt-4">
          <empty v-if="!milestones.length" text="老师还没有为你规划里程碑"></empty>
          <div v-for="m in milestones" :key="m.id" class="flex items-center gap-3 py-2.5 border-b border-slate-100 last:border-0">
            <span class="inline-flex items-center">
              <span v-if="m.status==='done'" class="w-5 h-5 rounded-full bg-emerald-500 inline-flex items-center justify-center">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="w-3 h-3"><path d="M20 6 9 17l-5-5"/></svg>
              </span>
              <span v-else-if="m.status==='in_progress'" class="w-5 h-5 rounded-full bg-blue-500 inline-block"></span>
              <span v-else class="w-5 h-5 rounded-full border-2 border-slate-300 bg-white inline-block"></span>
            </span>
            <div class="flex-1">
              <div class="text-sm font-medium" :class="m.status==='done'?'line-through text-slate-400':''">{{ m.title }}</div>
              <div class="text-xs text-slate-400">{{ m.phase?ctx.shared.PHASE_LABEL[m.phase]:'' }}</div>
            </div>
            <div class="text-xs text-slate-400">{{ ctx.shared.fmtDate(m.due_date) }}</div>
          </div>
        </card>
      </template>
    </div>`,
    computed: {
      done() { return this.tasks.filter(t => t.status === "done").length; },
      doing() { return this.tasks.filter(t => t.status === "in_progress").length; },
      todo() { return this.tasks.filter(t => t.status === "pending").length; },
    },
    async mounted() {
      try {
        const me = S().getUser();
        // Phase 5: 家长端带 activeStudentId
        const sid = this.ctx.activeStudentId || me.member_id;
        this.stu = await S().get("/api/students/" + sid).catch(() => null);
        const q = sid !== me.member_id ? "?student_id=" + sid : "";
        const [t, m] = await Promise.all([
          S().get("/api/workflow/tasks" + q),
          S().get("/api/workflow/milestones" + q)
        ]);
        this.tasks = t.items; this.milestones = m.items;
      } catch (e) { this.ctx.toast(e.message, "error"); }
      this.loading = false;
    },
  });

  const MyTasksView = defineComponent({
    components: { Card, Tag, Empty },
    props: ["ctx"],
    data: () => ({ tasks: [], loading: true }),
    template: `
    <div>
      <h1 class="text-xl font-bold mb-4">我的任务</h1>
      <card>
        <div v-if="loading" class="text-sm text-slate-400">加载中…</div>
        <empty v-else-if="!tasks.length"></empty>
        <div v-else v-for="t in tasks" :key="t.id" class="flex items-center gap-3 py-2.5 border-b border-slate-100 last:border-0">
          <button @click="toggle(t)" class="w-5 h-5 rounded-full border-2 transition-all inline-flex items-center justify-center" :class="t.status==='done'?'bg-emerald-500 border-emerald-500':'bg-white border-slate-300 hover:border-slate-400'">
            <svg v-if="t.status==='done'" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="w-3 h-3"><path d="M20 6 9 17l-5-5"/></svg>
          </button>
          <div class="flex-1">
            <div class="text-sm" :class="t.status==='done'?'line-through text-slate-400':'font-medium'">{{ t.title }}</div>
            <div v-if="t.description" class="text-xs text-slate-400">{{ t.description }}</div>
          </div>
          <tag v-if="t.phase" :label="ctx.shared.PHASE_LABEL[t.phase]" color="slate"></tag>
          <div class="text-xs text-slate-400 w-20 text-right">{{ ctx.shared.fmtDate(t.due_date) }}</div>
        </div>
      </card>
    </div>`,
    async mounted() { this.load(); },
    methods: {
      async load() {
        try {
          const q = this.ctx.activeStudentId ? "?student_id=" + this.ctx.activeStudentId : "";
          const d = await S().get("/api/workflow/tasks" + q);
          this.tasks = d.items;
        } catch (e) { this.ctx.toast(e.message, "error"); }
        this.loading = false;
      },
      async toggle(t) {
        try { await S().post(`/api/workflow/tasks/${t.id}/status`, { status: t.status === "done" ? "pending" : "done" }); this.load(); }
        catch (e) { this.ctx.toast(e.message, "error"); }
      },
    },
  });

  const MyContractView = defineComponent({
    components: { Card, Tag, Empty },
    props: ["ctx"],
    data: () => ({ items: [], loading: true }),
    template: `
    <div>
      <h1 class="text-xl font-bold mb-4">我的合同与服务</h1>
      <div v-if="loading" class="text-sm text-slate-400">加载中…</div>
      <empty v-else-if="!items.length" text="暂无合同"></empty>
      <card v-for="c in items" :key="c.id" class="mb-4">
        <div class="flex justify-between items-start mb-2">
          <div class="font-mono text-sm">{{ c.contract_no }}</div>
          <tag :label="ctx.shared.CONTRACT_STATUS_LABEL[c.status]" color="blue"></tag>
        </div>
        <div class="text-sm text-slate-500 mb-2">签约 {{ ctx.shared.fmtDate(c.signed_date) }} · 总额 {{ ctx.shared.fmtMoney(c.total_amount) }}</div>
        <div class="flex flex-wrap gap-1.5">
          <tag v-for="m in c.modules" :key="m" :label="moduleLabel(m)" color="blue"></tag>
        </div>
      </card>
    </div>`,
    async mounted() {
      try {
        const me = S().getUser();
        // Phase 5: 家长带 activeStudentId
        const sid = this.ctx.activeStudentId || me.member_id;
        const d = await S().get("/api/contracts?student_id=" + sid);
        this.items = d.items;
        const m = await S().get("/api/contracts/modules").catch(() => ({ modules: [] }));
        this._mods = Object.fromEntries(m.modules.map(x => [x.code, x.name_zh]));
      } catch (e) { this.ctx.toast(e.message, "error"); }
      this.loading = false;
    },
    methods: { moduleLabel(code) { return (this._mods && this._mods[code]) || code; } },
  });

  const MessagesView = defineComponent({
    components: { Card, Empty },
    props: ["ctx"],
    data: () => ({ convs: [], active: null, msgs: [], other: null, draft: "", sending: false }),
    template: `
    <div>
      <h1 class="text-xl font-bold mb-4">消息</h1>
      <div class="grid grid-cols-3 gap-4" style="height:70vh">
        <card class="col-span-1 overflow-y-auto">
          <empty v-if="!convs.length" text="暂无会话"></empty>
          <div v-for="c in convs" :key="c.conversation_id" @click="open(c)"
               :class="['p-3 rounded-lg cursor-pointer mb-1', active===c.conversation_id?'bg-blue-50':'hover:bg-slate-50']">
            <div class="flex justify-between">
              <span class="font-medium text-sm">{{ c.other_name }}</span>
              <span v-if="c.unread>0" class="bg-red-500 text-white text-xs rounded-full px-1.5">{{ c.unread }}</span>
            </div>
            <div class="text-xs text-slate-400 truncate">{{ c.last_msg }}</div>
          </div>
        </card>
        <card class="col-span-2 flex flex-col">
          <div v-if="!active" class="flex-1 flex items-center justify-center text-slate-300 text-sm">选择一个会话</div>
          <template v-else>
            <div class="flex-1 overflow-y-auto space-y-3 mb-3">
              <div v-for="m in msgs" :key="m.id" :class="['flex', m.sender_member_id===myId?'justify-end':'justify-start']">
                <div :class="['max-w-[70%] rounded-2xl px-4 py-2 text-sm', m.sender_member_id===myId?'bg-blue-600 text-white':'bg-slate-100']">
                  {{ m.content }}
                  <div :class="['text-xs mt-1', m.sender_member_id===myId?'text-blue-200':'text-slate-400']">{{ ctx.shared.fmtDate(m.created_at) }}</div>
                </div>
              </div>
            </div>
            <div class="flex gap-2 border-t pt-3">
              <input v-model="draft" @keyup.enter="send" placeholder="输入消息…" class="flex-1 border rounded-lg px-3 py-2 text-sm" />
              <button @click="send" :disabled="sending" class="bg-blue-600 text-white rounded-lg px-4 text-sm">发送</button>
            </div>
          </template>
        </card>
      </div>
    </div>`,
    computed: { myId() { const u = S().getUser(); return u && u.member_id; } },
    async mounted() { this.loadConvs(); },
    methods: {
      async loadConvs() { try { const d = await S().get("/api/messages/conversations"); this.convs = d.items; } catch {} },
      async open(c) {
        this.active = c.conversation_id;
        try {
          const d = await S().get("/api/messages/with/" + c.other_id);
          this.msgs = d.messages; this.other = d.other;
          this.loadConvs();
        } catch (e) { this.ctx.toast(e.message, "error"); }
      },
      async send() {
        if (!this.draft.trim() || !this.other) return;
        this.sending = true;
        try { await S().post("/api/messages", { to_member_id: this.other.id, content: this.draft }); this.draft = ""; this.open({ conversation_id: this.active, other_id: this.other.id }); }
        catch (e) { this.ctx.toast(e.message, "error"); }
        this.sending = false;
      },
    },
  });

  const NotificationsView = defineComponent({
    components: { Card, Tag, Empty },
    props: ["ctx"],
    data: () => ({ items: [], loading: true }),
    template: `
    <div>
      <h1 class="text-xl font-bold mb-4">通知</h1>
      <card>
        <div v-if="loading" class="text-sm text-slate-400">加载中…</div>
        <empty v-else-if="!items.length"></empty>
        <div v-for="n in items" :key="n.id" @click="markRead(n)" class="py-2.5 border-b border-slate-100 last:border-0 cursor-pointer" :class="n.is_read?'opacity-60':''">
          <div class="flex items-center gap-2">
            <span v-if="!n.is_read" class="w-2 h-2 bg-blue-500 rounded-full"></span>
            <span class="font-medium text-sm">{{ n.title }}</span>
            <tag :label="n.type" color="slate"></tag>
          </div>
          <div class="text-xs text-slate-500 mt-0.5">{{ n.content }}</div>
          <div class="text-xs text-slate-300 mt-0.5">{{ ctx.shared.fmtDate(n.created_at) }}</div>
        </div>
      </card>
    </div>`,
    async mounted() { this.load(); },
    methods: {
      async load() { try { const d = await S().get("/api/workflow/notifications"); this.items = d.items; } catch (e) { this.ctx.toast(e.message, "error"); } this.loading = false; },
      async markRead(n) { if (n.is_read) return; try { await S().post(`/api/workflow/notifications/${n.id}/read`, {}); n.is_read = 1; } catch {} },
    },
  });

  // 注册到全局
  window.SohoViews = {
    LoginView, RegisterView, DashboardView, LeadsView, LeadDetail, StudentsView, StudentDetail,
    ContractsView, StaffView, CollisionsView, ReportsView, SettingsView,
    MyProgressView, MyTasksView, MyContractView, MessagesView, NotificationsView,
  };
})();
