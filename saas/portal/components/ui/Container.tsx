/**
 * Container - 页面内容居中容器
 *
 * 横向居中 + 响应式内边距 (移动 16px / 平板 24px / 桌面 32px)。
 * 4 个 size 档 (sm/md/lg/full) 控制最大宽度。
 */
import { forwardRef, HTMLAttributes, ElementType } from 'react';
import clsx from 'clsx';

export type ContainerSize = 'sm' | 'md' | 'lg' | 'full';

const sizeClasses: Record<ContainerSize, string> = {
  sm: 'max-w-3xl',
  md: 'max-w-5xl',
  lg: 'max-w-7xl',
  full: 'max-w-none',
};

export type ContainerProps = HTMLAttributes<HTMLElement> & {
  size?: ContainerSize;
  as?: ElementType;
};

export const Container = forwardRef<HTMLElement, ContainerProps>(
  function Container({ size = 'lg', as, className, children, ...rest }, ref) {
    const Component = (as ?? 'div') as ElementType;
    return (
      <Component
        ref={ref}
        className={clsx(
          'mx-auto px-4 md:px-6 lg:px-8',
          sizeClasses[size],
          className,
        )}
        {...rest}
      >
        {children}
      </Component>
    );
  },
);
