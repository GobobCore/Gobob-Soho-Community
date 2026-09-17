// ---------- QuotaView (R-Feat 2026-09-17: 智能评估用量 + 套餐购买) ----------
const QuotaView = {
  props: ['ctx'],
  template: `
  <div class="max-w-4xl">
    <h2 class="text-xl font-bold mb-1">智能评估用量</h2>
    <p class="text-sm text-slate-500 mb-6">免费套餐: 每年 120 次, 每月上限 10 次。超量请购买资源包。</p>

    <!-- 用量卡片 -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8" v-if="usage">
      <div class="bg-white rounded-xl border border-slate-200 p-5">
        <div class="text-xs text-slate-400 mb-1">本年度已用 / 总量</div>
        <div class="text-2xl font-bold" :class="usage.year_used >= 120 ? 'text-red-500' : 'text-slate-800'">
          {{ usage.year_used }} <span class="text-sm text-slate-400">/ 120</span>
        </div>
        <div class="mt-3 h-2 bg-slate-100 rounded-full overflow-hidden">
          <div class="h-full bg-gradient-to-r from-[#E08A44] to-[#C97636]"
               :style="{width: Math.min(100, usage.year_used/120*100) + '%'}"></div>
        </div>
      </div>
      <div class="bg-white rounded-xl border border-slate-200 p-5">
        <div class="text-xs text-slate-400 mb-1">本月已用 / 月上限</div>
        <div class="text-2xl font-bold" :class="usage.month_used >= 10 ? 'text-red-500' : 'text-slate-800'">
          {{ usage.month_used }} <span class="text-sm text-slate-400">/ 10</span>
        </div>
        <div class="mt-3 h-2 bg-slate-100 rounded-full overflow-hidden">
          <div class="h-full bg-gradient-to-r from-[#E08A44] to-[#C97636]"
               :style="{width: Math.min(100, usage.month_used/10*100) + '%'}"></div>
        </div>
      </div>
      <div class="bg-white rounded-xl border border-slate-200 p-5">
        <div class="text-xs text-slate-400 mb-1">已购资源包余额</div>
        <div class="text-2xl font-bold text-emerald-600">{{ usage.paid_quota }}</div>
        <div class="text-xs text-slate-400 mt-1">资源包次数不占用免费额度, 用完免费额度后自动扣减</div>
      </div>
    </div>

    <!-- 套餐购买 -->
    <h3 class="text-lg font-bold mb-4">购买更多用量</h3>
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
      <div v-for="p in usage ? usage.plans : []" :key="p.plan"
           class="bg-white rounded-xl border-2 p-6 cursor-pointer transition-all"
           :class="selected===p.plan ? 'border-[#E08A44] shadow-lg' : 'border-slate-200 hover:border-[#F4CC9A]'"
           @click="selected=p.plan">
        <div class="text-sm font-medium text-slate-500">{{ p.label }}</div>
        <div class="mt-2">
          <span class="text-3xl font-bold">¥{{ p.price }}</span>
        </div>
        <div class="mt-2 text-sm text-slate-500">{{ p.desc }}</div>
        <div v-if="selected===p.plan" class="mt-4 text-xs text-[#C97636] font-medium">✓ 已选择</div>
      </div>
    </div>

    <div class="flex items-center gap-4">
      <button @click="buy" :disabled="!selected || buying"
              class="btn-primary px-8 py-3 text-base disabled:opacity-50 disabled:cursor-not-allowed">
        {{ buying ? '创建订单中...' : '立即购买' }}
      </button>
      <span class="text-xs text-slate-400">微信扫码支付, 支付后额度立即到账</span>
    </div>

    <!-- 支付二维码弹层 -->
    <div v-if="order" class="fixed inset-0 bg-black/50 z-50 flex items-center justify-center" @click.self="order=null">
      <div class="bg-white rounded-2xl p-8 max-w-sm text-center">
        <h3 class="text-lg font-bold mb-2">微信扫码支付</h3>
        <p class="text-sm text-slate-500 mb-4">订单 {{ order.order_no }} · ¥{{ order.price }}</p>
        <img :src="'https://api.qrserver.com/v1/create-qr-code/?size=220x220&data=' + encodeURIComponent(order.code_url)"
             class="mx-auto rounded-lg border" alt="微信支付二维码"/>
        <p class="text-xs text-slate-400 mt-4">支付完成后额度自动到账, 可关闭此窗口</p>
        <button @click="checkPaid" class="mt-4 w-full btn-primary py-2">我已支付, 查询到账</button>
      </div>
    </div>
  </div>`,
  data() { return { usage: null, selected: null, buying: false, order: null }; },
  async mounted() { await this.load(); },
  methods: {
    async load() {
      try {
        const r = await this.ctx.api.get('/api/assessment/usage');
        this.usage = r;
      } catch (e) { this.ctx.toast('加载用量失败: ' + (e.detail || e.message), 'error'); }
    },
    async buy() {
      if (!this.selected) return;
      this.buying = true;
      try {
        const r = await this.ctx.api.post('/api/assessment/buy-quota', { plan: this.selected });
        this.order = { order_no: r.order_no, price: r.price, code_url: r.pay_url };
      } catch (e) {
        this.ctx.toast('下单失败: ' + (e.detail || e.message), 'error');
      } finally { this.buying = false; }
    },
    async checkPaid() {
      try {
        const r = await this.ctx.api.get('/api/assessment/usage');
        this.usage = r;
        if (r.paid_quota > (this.usage ? 0 : 0) || true) {
          this.ctx.toast('已刷新最新用量', 'success');
          this.order = null;
        }
      } catch (e) { this.ctx.toast('查询失败', 'error'); }
    }
  }
};

