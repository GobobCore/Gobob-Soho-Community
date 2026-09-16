import Link from 'next/link';

export default function Home() {
  return (
    <div>
      {/* Hero — R-Design 2026-09-16: 暖橙渐变 + 装饰光圈 + 更大字体层级 */}
      <section className="relative overflow-hidden bg-gradient-to-br from-primary-600 via-primary-500 to-primary-700 text-white py-24 md:py-32 px-4">
        {/* 装饰光圈 (暖橙 + 白 透明度) */}
        <div aria-hidden className="absolute -top-32 -right-32 w-96 h-96 rounded-full bg-white/10 blur-3xl" />
        <div aria-hidden className="absolute -bottom-40 -left-40 w-[28rem] h-[28rem] rounded-full bg-primary-300/30 blur-3xl" />
        <div aria-hidden className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[40rem] h-[40rem] rounded-full bg-gradient-to-tr from-primary-400/20 to-transparent blur-3xl" />

        <div className="relative max-w-3xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 bg-white/15 backdrop-blur-sm border border-white/25 rounded-full px-4 py-1.5 text-sm font-medium mb-6">
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-300 animate-pulse-soft" />
            免费 · 30 秒出结果 · 无需注册
          </div>

          <h1 className="text-4xl md:text-6xl font-bold leading-tight tracking-tight">
            3 分钟，找到
            <span className="bg-gradient-to-r from-yellow-200 to-amber-100 bg-clip-text text-transparent">
              最适合你
            </span>
            的<br className="hidden md:block" />留学院校
          </h1>

          <p className="mt-6 text-lg md:text-xl text-primary-50/90 max-w-2xl mx-auto">
            基于真实录取数据的智能匹配 —— 告诉你哪些是冲刺、哪些是稳妥、哪些是保底
          </p>

          <Link
            href="/assessment"
            className="inline-flex items-center gap-2 mt-10 bg-white text-primary-700 font-bold px-8 py-4 rounded-2xl text-lg shadow-lift hover:shadow-[0_12px_32px_rgba(0,0,0,0.2)] hover:-translate-y-1 transition-all"
          >
            免费开始智能评估
            <span aria-hidden className="text-xl">→</span>
          </Link>

          <p className="mt-5 text-sm text-primary-100/80">
            已被 <span className="font-semibold text-white">3,000+</span> 学生使用
          </p>
        </div>
      </section>

      {/* 卖点 — R-Design: 卡片 hover 浮起 + 图标包 gradient 背景 */}
      <section className="max-w-5xl mx-auto py-20 px-4">
        <div className="text-center mb-12">
          <h2 className="text-3xl font-bold tracking-tight">为什么选择 Gobob SOHO</h2>
          <p className="mt-3 text-slate-500">三个让选校更靠谱的理由</p>
        </div>
        <div className="grid md:grid-cols-3 gap-6">
          {[
            { icon: '🎯', title: '精准匹配', desc: 'GPA / 语言 / 背景 / 预算 7 维加权，按冲刺-匹配-保底分层', color: 'from-orange-400 to-amber-500' },
            { icon: '📊', title: '真实数据', desc: '院校库 + 历年录取数据校准，给出可信的录取概率', color: 'from-blue-400 to-indigo-500' },
            { icon: '🤝', title: '顾问跟进', desc: '评估后可一键留资，专业顾问为你定制完整申请方案', color: 'from-emerald-400 to-teal-500' },
          ].map((f) => (
            <div
              key={f.title}
              className="group bg-white rounded-2xl border border-slate-200/70 p-8 text-center shadow-soft hover:shadow-lift hover:-translate-y-1 hover:border-primary-200 transition-all duration-300"
            >
              <div className={`inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br ${f.color} text-white text-3xl shadow-md group-hover:scale-110 transition-transform`}>
                {f.icon}
              </div>
              <h3 className="mt-5 font-bold text-xl tracking-tight">{f.title}</h3>
              <p className="mt-2.5 text-sm text-slate-500 leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA — R-Design: 加渐变背景 + 装饰, 不再单调 */}
      <section className="max-w-3xl mx-auto text-center pb-24 px-4">
        <div className="relative overflow-hidden bg-gradient-to-br from-primary-50 via-white to-primary-100/50 rounded-3xl border border-primary-200/50 p-12 shadow-soft">
          <div aria-hidden className="absolute -top-20 -right-20 w-48 h-48 rounded-full bg-primary-200/40 blur-2xl" />
          <div className="relative">
            <h2 className="text-3xl font-bold tracking-tight">开始你的留学规划</h2>
            <p className="mt-3 text-slate-600">填写你的背景，30 秒出匹配结果</p>
            <Link
              href="/assessment"
              className="btn-primary mt-7 text-base px-8 py-3.5"
            >
              免费智能评估
              <span aria-hidden>→</span>
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
