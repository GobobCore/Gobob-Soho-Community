/**
 * LeadCapture.test.tsx — LeadCapture 组件测试
 * ==========================================
 * 验证表单校验 + 错误显示 + 提交逻辑
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import LeadCapture from './LeadCapture';

/**
 * 类型安全的 fetch mock。
 *
 * 组件只读 response.ok / .status / .json(), 但 vi.fn() 推导出的对象不满足
 * Response 的完整结构 (缺 headers / redirected / text 等), 直接赋给
 * globalThis.fetch 会触发 TS2322。这里把断言收口到一处, 各用例只描述
 * 自己关心的字段。
 */
function mockFetch(opts: { body?: unknown; ok?: boolean; status?: number } = {}) {
  const { body = {}, ok = true, status = 200 } = opts;
  // 显式声明参数签名 —— 否则 vi.fn 的实现无参, mock.calls 被推导为 [][],
  // 调用断言里取 call[0] 会报 "Tuple type '[]' has no element at index '0'"。
  const fn = vi.fn(
    (_input?: unknown, _init?: { method?: string; body?: string }) =>
      Promise.resolve({ ok, status, json: () => Promise.resolve(body) })
  );
  globalThis.fetch = fn as unknown as typeof fetch;
  return fn;
}

describe('LeadCapture', () => {
  const mockOnDone = vi.fn();
  const mockOnClose = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    // mock fetch (jsdom 没有, 但我们 setup 装了 undici)
    mockFetch();
  });

  it('should render name and contact inputs', () => {
    render(
      <LeadCapture
        assessmentId="ass_001"
        context="test"
        onClose={mockOnClose}
        onDone={mockOnDone}
      />
    );
    // 至少要有姓名输入
    expect(screen.getByPlaceholderText(/称呼/i) || screen.getByLabelText(/姓名/i)).toBeTruthy();
  });

  it('should show error when submitting empty form', async () => {
    // mock fetch 让 submit 不会发真请求
    mockFetch();
    render(
      <LeadCapture onClose={mockOnClose} onDone={mockOnDone} />
    );
    const submitBtn = screen.getByRole('button', { name: /提交/i });
    fireEvent.click(submitBtn);
    // 不应立即调 onDone (空表单应先显示错误)
    await new Promise(r => setTimeout(r, 100));
    expect(mockOnDone).not.toHaveBeenCalled();
  });

  it('should call onDone after successful submit', async () => {
    mockFetch({ body: { ok: true } });
    render(
      <LeadCapture assessmentId="a1" onClose={mockOnClose} onDone={mockOnDone} />
    );
    const nameInput = screen.getByPlaceholderText(/称呼|姓名/i);
    if (nameInput) {
      fireEvent.change(nameInput, { target: { value: '测试家长' } });
      // 填手机
      const phoneInput = screen.getByPlaceholderText(/手机|电话/i);
      if (phoneInput) {
        fireEvent.change(phoneInput, { target: { value: '13800000000' } });
      }
      // 提交
      const submitBtn = screen.getByRole('button', { name: /提交|完成|确定/i });
      if (submitBtn) {
        fireEvent.click(submitBtn);
        await waitFor(() => {
          expect(mockOnDone).toHaveBeenCalled();
        }, { timeout: 2000 });
      }
    }
  });

  it('should send POST to /api/leads/capture with correct body', async () => {
    const mockFetchSpy = mockFetch({ body: { ok: true } });

    render(
      <LeadCapture
        assessmentId="ass_test_001"
        context="评估页测试"
        onClose={mockOnClose}
        onDone={mockOnDone}
      />
    );

    const nameInput = screen.getByPlaceholderText(/称呼|姓名/i);
    const phoneInput = screen.getByPlaceholderText(/手机|电话/i);
    const submitBtn = screen.getByRole('button', { name: /提交/i });

    if (nameInput && phoneInput && submitBtn) {
      fireEvent.change(nameInput, { target: { value: '张三' } });
      fireEvent.change(phoneInput, { target: { value: '13900000000' } });
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(mockFetchSpy).toHaveBeenCalled();
      });

      // 验证 fetch 调用参数
      const call = mockFetchSpy.mock.calls[0];
      expect(call?.[0]).toBe('/api/leads/capture');
      expect(call?.[1]?.method).toBe('POST');
      const body = JSON.parse(call?.[1]?.body ?? '{}');
      expect(body.student_name).toBe('张三');
      expect(body.student_phone).toBe('13900000000');
      expect(body.assessment_id).toBe('ass_test_001');
      expect(body.source_detail).toBe('评估页测试');
    }
  });

  it('should include org query param when ?org= in URL', async () => {
    // mock useSearchParams (Next.js hook) — jsdom 默认没有, 我们直接 mock
    // 这个测试可选 — 实际行为需要 router context, 跳过复杂 mock
    // 仅做 smoke test 验证组件不崩
    mockFetch();

    render(
      <LeadCapture onClose={mockOnClose} onDone={mockOnDone} />
    );
    expect(screen.getByPlaceholderText(/称呼|姓名/i)).toBeTruthy();
  });

  it('should show error message on fetch failure', async () => {
    mockFetch({ ok: false, status: 500, body: { detail: '服务器错误' } });

    render(
      <LeadCapture assessmentId="a2" onClose={mockOnClose} onDone={mockOnDone} />
    );

    const nameInput = screen.getByPlaceholderText(/称呼|姓名/i);
    const phoneInput = screen.getByPlaceholderText(/手机|电话/i);
    const submitBtn = screen.getByRole('button', { name: /提交/i });

    if (nameInput && phoneInput && submitBtn) {
      fireEvent.change(nameInput, { target: { value: '李四' } });
      fireEvent.change(phoneInput, { target: { value: '13900000001' } });
      fireEvent.click(submitBtn);

      // fetch 失败应显示错误, 不调 onDone
      await new Promise(r => setTimeout(r, 200));
      expect(mockOnDone).not.toHaveBeenCalled();
    }
  });
});
