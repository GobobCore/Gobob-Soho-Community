import { Container } from '@/components/ui/Container';

/**
 * 服务条款页
 * ============================================================================
 * ⚠️ 上线前需法务定稿。骨架已按常见条款结构搭好, 标注「待法务确认」的条目
 * 需业务/法务给出真实答案 —— 定价、退款规则、责任限制等均无法由代码推断。
 *
 * 现状: 注册页曾以 "注册即表示同意" 链接到 href="#"(空占位), 即用户被告知
 * 同意了一份并不存在的条款。现改为指向本页。
 *
 * 定稿后请同步:
 *   1. 服务提供方全称 (应与 /privacy 一致)
 *   2. 定价与计费规则、试用期的具体口径
 *   3. 退款 / 取消政策
 *   4. 责任限制与免责范围
 *   5. 服务变更与终止条款
 * ============================================================================
 */

type Clause = {
  title: string;
  body: React.ReactNode;
  todo?: string;
};

const CLAUSES: Clause[] = [
  {
    title: '一、服务说明',
    body: (
      <p>
        Gobob SOHO 是面向中小型留学机构与语言培训工作室的业务管理系统，
        覆盖获客、线索管理、签约与留学进程服务。服务由
        <strong>【待法务确认：服务提供方全称】</strong>提供。
      </p>
    ),
    todo: '服务提供方全称',
  },
  {
    title: '二、账号与开通',
    body: (
      <>
        <p>机构自助注册后可获得 <strong>【待法务确认：试用席位数与试用天数】</strong>。
          试用期内可随时取消，逾期未续费的服务将
          <strong>【待法务确认：到期后的处理方式，如只读 / 停服 / 数据保留期】</strong>。</p>
        <p>账号所有权归注册机构；机构内的成员账号由机构管理员分配与回收。</p>
      </>
    ),
    todo: '试用期口径、席位数量、到期处理方式与数据保留期',
  },
  {
    title: '三、计费与续费',
    body: (
      <>
        <p>按
          <strong>【待法务确认：计费维度，如按席位 / 按 API 调用次数】</strong>
          计费。价格以下单页面展示为准。</p>
        <p><strong>【待法务确认：退款政策 —— 是否可退、可退比例、退款时限】</strong></p>
      </>
    ),
    todo: '计费维度、退款政策',
  },
  {
    title: '四、用户责任',
    body: (
      <p>机构应确保其录入的学生与家长信息已获得当事人授权，并对所提交数据的
        合法性负责。不得使用本服务存储、传播违法违规内容。</p>
    ),
  },
  {
    title: '五、知识产权',
    body: (
      <p>软件著作权及商标归
        <strong>【待法务确认：权利主体】</strong>所有。机构上传的业务数据归机构所有；
        我们不主张对该数据的任何权利。</p>
    ),
    todo: '知识产权权利主体',
  },
  {
    title: '六、服务变更与终止',
    body: (
      <p>我们可能不时更新功能。若变更影响机构核心使用，会提前
        <strong>【待法务确认：提前通知期限】</strong>通知。机构可随时停止使用并导出数据，
        <strong>【待法务确认：数据导出方式与期限】</strong>。</p>
    ),
    todo: '变更通知期限、数据导出方式与保留期限',
  },
  {
    title: '七、责任限制',
    body: (
      <p>
        <strong>【待法务确认：责任上限与免责范围】</strong>
        在法律允许的最大范围内，我们不对间接损失承担责任。
      </p>
    ),
    todo: '责任上限与免责范围（需法务拟定，勿自行填写）',
  },
];

export default function TermsPage() {
  return (
    <Container className="py-12" size="md">
      <h1 className="text-2xl font-bold mb-2">服务条款</h1>
      <p className="text-sm text-slate-400 mb-6">
        更新日期：【待法务确认】　|　生效日期：【待法务确认】
      </p>

      <nav className="mb-8 p-4 rounded-lg bg-amber-50 border border-amber-200">
        <p className="text-sm text-amber-900">
          <strong>本页尚未定稿。</strong>
          以下已按常见条款结构搭好，但定价、退款、责任限制等关键条款仍需
          法务确定（以「待法务确认」标注）。正式发布前请勿认为其已生效。
        </p>
      </nav>

      <div className="space-y-8">
        {CLAUSES.map((c) => (
          <section key={c.title}>
            <h2 className="text-lg font-semibold mb-2">{c.title}</h2>
            <div className="text-slate-600 space-y-2 text-sm leading-relaxed">
              {c.body}
            </div>
            {c.todo && (
              <p className="mt-2 text-xs text-amber-700 bg-amber-50 rounded px-2 py-1 inline-block">
                待法务确认：{c.todo}
              </p>
            )}
          </section>
        ))}
      </div>

      <div className="mt-10 pt-4 border-t text-sm text-slate-500">
        <p>
          联系我们：
          <strong>【待法务确认：联系邮箱 / 通讯地址】</strong>
        </p>
        <p className="mt-2">
          我们如何处理你的信息，见
          <a href="/privacy" className="text-primary-600 hover:underline">隐私政策</a>。
        </p>
      </div>
    </Container>
  );
}
