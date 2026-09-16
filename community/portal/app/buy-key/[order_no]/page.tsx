'use client';

/**
 * /buy-key/[order_no] — 订单状态查询页
 * 机构用订单号查自己的购买状态
 */
import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { CheckCircle2, Clock, AlertCircle, Package } from 'lucide-react';
import { Container } from '@/components/ui/Container';

type OrderStatus = 'pending' | 'paid' | 'delivered' | 'cancelled';

const STATUS_META: Record<OrderStatus, { label: string; icon: any; color: string; bg: string; hint: string }> = {
  pending: {
    label: '待付款',
    icon: Clock,
    color: 'text-amber-600',
    bg: 'bg-amber-50 border-amber-200',
    hint: '请转账时备注订单号, 我们确认到账后会开通 Key',
  },
  paid: {
    label: '已付款, 开通中',
    icon: CheckCircle2,
    color: 'text-blue-600',
    bg: 'bg-blue-50 border-blue-200',
    hint: '款已收到, 我们正在为你开通 API Key, 会通过邮箱发送',
  },
  delivered: {
    label: '已交付',
    icon: Package,
    color: 'text-emerald-600',
    bg: 'bg-emerald-50 border-emerald-200',
    hint: 'API Key 已发送到你的邮箱, 请查收',
  },
  cancelled: {
    label: '已取消',
    icon: AlertCircle,
    color: 'text-slate-500',
    bg: 'bg-slate-50 border-slate-200',
    hint: '订单已取消, 如有疑问请联系我们',
  },
};

export default function OrderStatusPage() {
  const params = useParams();
  const orderNo = String(params.order_no || '');
  const [order, setOrder] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!orderNo) return;
    fetch(`/api/saas/buy-key/${orderNo}`)
      .then(r => r.ok ? r.json() : Promise.reject(new Error('订单不存在')))
      .then(setOrder)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [orderNo]);

  return (
    <Container className="py-12 md:py-20" size="sm">
      <div className="max-w-md mx-auto">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold">订单状态查询</h1>
          <p className="text-sm text-slate-500 mt-1">订单号 <code className="font-mono text-primary-600">{orderNo}</code></p>
        </div>

        {loading && <div className="text-center text-sm text-slate-400 py-8">加载中…</div>}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-center">
            <AlertCircle className="w-8 h-8 text-red-500 mx-auto mb-3" />
            <p className="text-red-700">{error}</p>
            <Link href="/buy-key" className="text-sm text-primary-600 hover:underline mt-3 inline-block">
              ← 返回购买页
            </Link>
          </div>
        )}

        {order && (
          <div className="space-y-4">
            <div className={`rounded-2xl border p-6 text-center ${STATUS_META[order.status as OrderStatus].bg}`}>
              {(() => {
                const meta = STATUS_META[order.status as OrderStatus];
                const Icon = meta.icon;
                return (
                  <>
                    <Icon className={`w-10 h-10 mx-auto mb-3 ${meta.color}`} />
                    <div className={`text-xl font-bold ${meta.color}`}>{meta.label}</div>
                    <p className="text-sm text-slate-600 mt-2">{meta.hint}</p>
                  </>
                );
              })()}
            </div>

            <div className="bg-white border border-slate-200 rounded-2xl p-5 space-y-2.5 text-sm">
              <div className="flex justify-between">
                <span className="text-slate-500">机构</span>
                <span className="font-medium">{order.org_name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">次数</span>
                <span className="font-medium">{order.calls} 次</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">金额</span>
                <span className="font-bold text-primary-700">¥{order.amount}</span>
              </div>
              {order.api_key_prefix && (
                <div className="flex justify-between">
                  <span className="text-slate-500">API Key</span>
                  <span className="font-mono text-primary-700">{order.api_key_prefix}…</span>
                </div>
              )}
              <div className="flex justify-between">
                <span className="text-slate-500">下单时间</span>
                <span className="text-slate-600">{order.created_at}</span>
              </div>
              {order.paid_at && (
                <div className="flex justify-between">
                  <span className="text-slate-500">付款时间</span>
                  <span className="text-slate-600">{order.paid_at}</span>
                </div>
              )}
            </div>

            <div className="text-center text-sm">
              <Link href="/buy-key" className="text-primary-600 hover:underline">再买一单 →</Link>
            </div>
          </div>
        )}
      </div>
    </Container>
  );
}
