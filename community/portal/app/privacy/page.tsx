import { Container } from '@/components/ui/Container';

/**
 * 隐私政策页
 * ============================================================================
 * ⚠️ 上线前需法务定稿。
 *
 * 下面按《个人信息保护法》《网络安全法》要求的告知要素搭好了骨架, 每个
 * 【待法务确认】都是需要业务/法务给出真实答案的条目 —— 我无法替机构决定
 * 收集范围、留存期限、第三方共享清单或联系方式, 凭空填写等于给出不实告知。
 *
 * 现状: 本页仅一句话, 但注册页 (/register) 已勾选"我已阅读并同意隐私政策",
 * 意味着用户点同意时看到的并不是完整政策。
 *
 * 定稿后请同步:
 *   1. 运营主体全称与统一社会信用代码
 *   2. 个人信息保护负责人的姓名与联系方式
 *   3. 实际调用的第三方 SDK / 数据接口清单 (当前已接 Gobob Data API)
 *   4. 各类数据的留存期限与删除方式
 * ============================================================================
 */

type Section = {
  id: string;
  title: string;
  body: React.ReactNode;
  /** 需要业务/法务确认才能定稿的条目 */
  todo?: string;
};

const SECTIONS: Section[] = [
  {
    id: 'operator',
    title: '一、我们是谁',
    body: (
      <>
        <p>本政策由 <strong>【待法务确认：运营主体全称】</strong>（统一社会信用代码
          【待法务确认】）运营，产品名称为 Gobob SOHO。</p>
        <p>我们持有的业务数据（线索、学生、合同等）存储在机构自行部署的数据库中；
          我们不代为持有机构业务数据。</p>
      </>
    ),
    todo: '运营主体全称、统一社会信用代码、注册地址、联系电话',
  },
  {
    id: 'collect',
    title: '二、我们收集哪些信息，以及为什么',
    body: (
      <>
        <p><strong>你主动提供：</strong>在使用智能选校评估时填写的姓名、联系方式、
          选校意向等信息；在机构自助注册时填写的机构名称与联系人信息。</p>
        <p><strong>自动收集：</strong>访问日志、浏览器与设备信息（用于排查故障与
          反滥用）。</p>
        <p><strong>我们不收集：</strong>与上述服务无关的信息；也不会收集你的
          通讯录、相册或位置信息。</p>
      </>
    ),
    todo: '逐项核对实际采集字段，确保与后端落库字段一一对应',
  },
  {
    id: 'thirdparty',
    title: '三、第三方共享',
    body: (
      <>
        <p>院校 / 专业 / 排名 / 智能匹配等数据能力由 <strong>Gobob Data API</strong>
          提供，提交评估时会把你在表单中填写的内容发送至该接口以完成匹配计算。</p>
        <p>我们<strong>不出售</strong>你的个人信息。除上述必需情形外，未经你另行同意，
          我们不会向第三方提供你的信息。</p>
        <p>【待法务确认：是否还有支付、短信、客服等其他第三方，逐一列明名称、
          处理目的与数据类型】</p>
      </>
    ),
    todo: '完整第三方清单（含支付 / 短信 / 客服），及其隐私政策链接',
  },
  {
    id: 'rights',
    title: '四、你的权利',
    body: (
      <>
        <p>你有权查阅、复制、更正、删除你的个人信息，以及撤回同意、注销账号。</p>
        <p>行使方式：发送邮件至 <strong>【待法务确认：个人信息保护负责人邮箱】</strong>，
          我们将在 15 个工作日内响应。撤回同意不影响此前基于同意已进行的处理活动。</p>
        <p>若机构为你的信息控制者，请同时向该机构提出请求。</p>
      </>
    ),
    todo: '个人信息保护负责人姓名、邮箱、响应时限的承诺口径',
  },
  {
    id: 'storage',
    title: '五、数据存储与安全',
    body: (
      <>
        <p>数据传输采用 HTTPS 加密；机构业务数据存储在机构自行部署的数据库中。</p>
        <p>我们采取访问控制、传输加密等措施保护信息安全。
          【待法务确认：数据存储地域、是否存在跨境传输、留存期限与到期处置方式】</p>
      </>
    ),
    todo: '数据存储地域、跨境情况、各类数据的留存期限',
  },
  {
    id: 'minors',
    title: '六、未成年人保护',
    body: (
      <p>本产品面向留学机构与学生家庭使用。若使用者为未满 14 周岁的未成年人，
        需在监护人同意下使用。若你是监护人并发现未成年人未经同意提交了信息，
        可通过下方方式联系我们删除。</p>
    ),
    todo: '是否需要监护人单独同意流程，以及具体实现方式',
  },
  {
    id: 'changes',
    title: '七、政策更新',
    body: (
      <p>本政策如有重大变更，我们会通过站内通知等方式向你提示。继续使用即表示
        你已阅读更新后的政策。</p>
    ),
  },
];

export default function PrivacyPage() {
  return (
    <Container className="py-12" size="md">
      <h1 className="text-2xl font-bold mb-2">隐私政策</h1>
      <p className="text-sm text-slate-400 mb-6">
        更新日期：【待法务确认】　|　生效日期：【待法务确认】
      </p>

      <p className="text-slate-600 mb-6">
        Gobob SOHO 重视你的隐私。我们仅在提供上述服务所必需的范围内收集和使用
        你的信息，不会出售你的个人信息。
      </p>

      <nav className="mb-8 p-4 rounded-lg bg-amber-50 border border-amber-200">
        <p className="text-sm text-amber-900">
          <strong>本页尚未定稿。</strong>
          以下已按法定要素搭好结构，但仍有若干条目需由业务与法务确认后填入
          （以「待法务确认」标注）。正式发布前请勿认为其已构成完整告知。
        </p>
      </nav>

      <div className="space-y-8">
        {SECTIONS.map((s) => (
          <section key={s.id} id={s.id}>
            <h2 className="text-lg font-semibold mb-2">{s.title}</h2>
            <div className="text-slate-600 space-y-2 text-sm leading-relaxed">
              {s.body}
            </div>
            {s.todo && (
              <p className="mt-2 text-xs text-amber-700 bg-amber-50 rounded px-2 py-1 inline-block">
                待法务确认：{s.todo}
              </p>
            )}
          </section>
        ))}
      </div>

      <div className="mt-10 pt-4 border-t text-sm text-slate-500">
        <p>
          联系我们：
          <strong>【待法务确认：个人信息保护负责人姓名 / 邮箱 / 通讯地址】</strong>
        </p>
      </div>
    </Container>
  );
}
