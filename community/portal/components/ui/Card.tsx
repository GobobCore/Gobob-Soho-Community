/**
 * Card - 通用卡片容器
 *
 * 白色背景 + rounded-2xl + shadow-sm 的基础卡片。
 * 子组件 CardHeader / CardBody / CardFooter 用于内容分组。
 * 严格使用 Gobob design-system token (gray-100 / gray-200 等)。
 */
import { forwardRef, HTMLAttributes, ElementType, ReactNode } from 'react';
import clsx from 'clsx';

export type CardPadding = 'none' | 'sm' | 'md' | 'lg';

const paddingClasses: Record<CardPadding, string> = {
  none: '',
  sm: 'p-3',
  md: 'p-5',
  lg: 'p-6',
};

export type CardProps = HTMLAttributes<HTMLElement> & {
  padding?: CardPadding;
  hoverable?: boolean;
  as?: ElementType;
};

export const Card = forwardRef<HTMLElement, CardProps>(function Card(
  { padding = 'md', hoverable = false, as, className, children, ...rest },
  ref,
) {
  const Component = (as ?? 'div') as ElementType;
  return (
    <Component
      ref={ref}
      className={clsx(
        'bg-white rounded-2xl shadow-sm border border-gray-100',
        paddingClasses[padding],
        hoverable && 'hover:shadow-md transition-shadow',
        className,
      )}
      {...rest}
    >
      {children}
    </Component>
  );
});

type DivProps = HTMLAttributes<HTMLDivElement> & { children?: ReactNode };

export function CardHeader({ className, children, ...rest }: DivProps) {
  return (
    <div className={clsx('mb-3', className)} {...rest}>
      {children}
    </div>
  );
}

export function CardBody({ className, children, ...rest }: DivProps) {
  return (
    <div className={clsx('text-sm text-gray-600', className)} {...rest}>
      {children}
    </div>
  );
}

export function CardFooter({ className, children, ...rest }: DivProps) {
  return (
    <div
      className={clsx('mt-4 pt-4 border-t border-gray-100', className)}
      {...rest}
    >
      {children}
    </div>
  );
}
