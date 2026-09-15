# 获取 Gobob Data API Key

Gobob SOHO 的**智能评估**与**院校/专业/排名数据**由 Gobob Data API 远程提供。你的业务数据（线索、学生、合同）100% 存在自己的数据库，不上传到 Gobob。

## 申请步骤

1. 在 Gobob 平台注册账号并登录
2. 进入「个人资料 → API Keys」
3. 创建 Key，勾选所需 scope：

   | scope | 用途 |
   |---|---|
   | `smb:meta` | 评估表单元数据（国家/学位/学科/国内校分层）|
   | `smb:schools` | 院校库查询 |
   | `smb:programs` | 专业/项目查询 |
   | `smb:rankings` | 综合与学科排名 |
   | `smb:match` | 智能匹配（评估核心）|
   | `smb:cities` | 城市数据 |

4. 复制生成的 `gob_...` Key（**只显示一次**）
5. 填入 SOHO 的 `.env`：

   ```
   GOBOB_API_BASE=https://api.gobob.cn
   GOBOB_API_KEY=gob_你的key
   ```

6. 重启 backend（`docker compose restart backend`）

## 验证

```
curl http://localhost:19001/api/health
# "gobob_data_api": "configured" 即配置成功
```

## 没有 Key 也能用

核心业务（线索 / 签约 / 进程 / 员工 / 换师）不依赖 Gobob。仅：
- 获客门户的「智能评估」结果不可用（返回 503 提示）
- 院校 / 专业联想下拉为空

配好 Key 后即自动恢复。
