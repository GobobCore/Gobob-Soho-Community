# Gobob SOHO 开机自启与常驻配置

> **R-Fix (2026-09-17)**: 本机 (192.168.1.5) 8 个 Gobob SOHO systemd --user service 全部 enable + linger=yes, 开机自启, 重启后自动恢复.

---

## 当前配置状态

| service | 端口 | enabled | active | 用途 |
|---|---|---|---|---|
| `gobob-soho-backend` | 19001 | ✅ enabled | active | SaaS dev 站 backend |
| `gobob-soho-portal` | 19002 | ✅ enabled | active | SaaS dev 站 portal |
| `gobob-soho-app` | 19003 | ✅ enabled | active | SaaS dev 站 服务平台 |
| `gobob-soho-ops` | 19004 | ✅ enabled | active | SaaS 运营后台 |
| `gobob-soho-aggregate-usage` | — | static | inactive (timer 触发) | SaaS daily cron (03:03) |
| `gobob-soho-community-backend` | 19011 | ✅ enabled | active | 社区版 dev 站 backend |
| `gobob-soho-community-portal` | 19012 | ✅ enabled | active | 社区版 dev 站 portal |
| `gobob-soho-community-app` | 19013 | ✅ enabled | active | 社区版 dev 站 服务平台 |

**Timer**:
- `gobob-soho-aggregate-usage.timer` → 每天 03:03 触发 `gobob-soho-aggregate-usage.service` (oneshot)

**User linger**:
- `loginctl show-user ricky | grep Linger` → `Linger=yes`
- 含义: 机器重启后, ricky 用户没登录时 systemd --user service 也能继续跑

---

## 开机自启原理

`systemd --user` service 默认不持久化, 用户登出后停. `enable` 只是建 symlink 写到 `default.target.wants/`, 真正持久化靠 `linger=yes`.

```
开机启动
   ↓
systemd --user 实例化 (因为 linger=yes)
   ↓
读 ~/.config/systemd/user/default.target.wants/*.service
   ↓
并行启动所有 enabled service
   ↓
RestartSec=3 (crash 后 3s 自动重启)
```

---

## 常用管理命令

```bash
# 一键看全部 SOHO service 状态
for svc in gobob-soho-backend gobob-soho-portal gobob-soho-app gobob-soho-ops \
           gobob-soho-aggregate-usage \
           gobob-soho-community-backend gobob-soho-community-portal gobob-soho-community-app; do
  echo "$svc: enabled=$(systemctl --user is-enabled $svc 2>/dev/null) active=$(systemctl --user is-active $svc 2>/dev/null)"
done

# 启/停/重起
systemctl --user start gobob-soho-community-backend
systemctl --user stop gobob-soho-community-portal
systemctl --user restart gobob-soho-community-app

# 启用/禁用开机自启
systemctl --user enable gobob-soho-community-backend     # 加入 default.target.wants
systemctl --user disable gobob-soho-community-backend    # 移除 soft link (但服务还在)

# 看日志
journalctl --user -u gobob-soho-community-backend -n 50 --no-pager
journalctl --user -u gobob-soho-community-backend -f  # follow

# 触发 aggregate-usage cron (默认 03:03 自动)
systemctl --user start gobob-soho-aggregate-usage.service

# 看 timer 下次跑时间
systemctl --user list-timers gobob-soho-aggregate-usage.timer
```

---

## 重启验证步骤

```bash
# 1. 软重启 (不重启 host)
sudo systemctl restart systemd-logind

# 2. 等 30s 后看 service 状态
sleep 30
for svc in gobob-soho-{backend,portal,app,ops,community-backend,community-portal,community-app}; do
  systemctl --user is-active $svc 2>/dev/null
done

# 3. hard reboot host 后验证
sudo reboot
# 登回后:
journalctl --user -u gobob-soho-community-backend -n 5 --no-pager
# 应该看到 "Started gobob-soho-community-backend.service" 在 boot 之后
```

---

## 故障排查

| 现象 | 可能原因 | 怎么查 |
|---|---|---|
| 重启后 service 没跑 | `Linger=no` | `loginctl show-user ricky \| grep Linger`, 应为 `yes`. 修: `sudo loginctl enable-linger ricky` |
| service 显示 enabled 但没起 | 缺依赖 (DB / Node 模块) | `journalctl --user -u <svc> -n 30` 看启动错误 |
| 端口冲突 000 | systemd 已 disable 但进程残留 | `ps -ef \| grep uvicorn`, kill 残留 PID, 再 `systemctl --user start` |
| portal 启动报 `npm error ENOENT` | community/portal/node_modules 没装 | `cd ~/.openclaw/workspace/gobob-soho/community/portal && npm install` |
| aggregate-usage CHDIR failed | WorkingDirectory 路径错 | 检查 service unit 的 WorkingDirectory 是否存在 |

---

## R-Fix 历史

- **2026-09-17**: 拆分后 backend/ 目录删除, aggregate-usage.service WorkingDirectory CHDIR failed → 恢复脚本到 `cloud/backend-saas/scripts/` + 修 service
- **2026-09-16**: R-Refactor SaaS/开源拆分, 加了 gobob-soho-community-* 三 service
- **(earlier)**: 已有 gobob-soho-{backend,portal,app,ops,aggregate-usage} 5 service 在跑

---

**Last updated**: 2026-09-17 (cecilia, 开机自启配置完整核查)