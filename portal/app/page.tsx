import Link from 'next/link';

export default function Home() {
  return (
    <div>
      {/* Hero */}
      <section className="bg-gradient-to-b from-blue-600 to-blue-700 text-white py-24 px-4">
        <div className="max-w-3xl mx-auto text-center">
          <h1 className="text-4xl md:text-5xl font-bold leading-tight">
            3 分钟，找到最适合你的<br className="hidden md:block" />留学院校
          </h1>
          <p className="mt-6 text-lg text-blue-100">
            基于真实录取数据的智能匹配 —— 告诉你哪些是冲刺、哪些是稳妥、哪些是保底
          </p>
          <Link
            href="/assessment"
            className="inline-block mt-8 bg-white text-blue-700 font-semibold px-8 py-4 rounded-xl text-lg hover:bg-blue-50 shadow-lg"
          >
            免费开始智能评估 →
          </Link>
          <p className="mt-4 text-sm text-blue-200">无需注册 · 立即出结果</p>
        </div>
      </section>

      {/* 卖点 */}
      <section className="max-w-5xl mx-auto py-16 px-4 grid md:grid-cols-3 gap-8">
        {[
          { icon: '🎯', title: '精准匹配', desc: 'GPA / 语言 / 背景 / 预算 7 维加权，按冲刺-匹配-保底分层' },
          { icon: '📊', title: '真实数据', desc: '院校库 + 历年录取数据校准，给出可信的录取概率' },
          { icon: '🤝', title: '顾问跟进', desc: '评估后可一键留资，专业顾问为你定制完整申请方案' },
        ].map((f) => (
          <div key={f.title} className="bg-white rounded-2xl border border-slate-200 p-6 text-center">
            <div className="text-4xl">{f.icon}</div>
            <h3 className="mt-3 font-semibold text-lg">{f.title}</h3>
            <p className="mt-2 text-sm text-slate-500">{f.desc}</p>
          </div>
        ))}
      </section>

      {/* CTA */}
      <section className="max-w-3xl mx-auto text-center pb-20 px-4">
        <div className="bg-white rounded-2xl border border-slate-200 p-10">
          <h2 className="text-2xl font-bold">开始你的留学规划</h2>
          <p className="mt-3 text-slate-500">填写你的背景，30 秒出匹配结果</p>
          <Link href="/assessment" className="inline-block mt-6 bg-blue-600 text-white px-8 py-3 rounded-xl font-medium hover:bg-blue-700">
            免费智能评估
          </Link>
        </div>
      </section>
    </div>
  );
}
