# Gobob SOHO GitHub 仓库设置 (R-Fix 2026-09-17)

> **目的**: 拆分完成后, 给两个新 GitHub 仓库加 description / topics / visibility
>
> **触发**: Phase 9 后再统一做, 见下

---

## 1. Community 仓库加 description + topics

仓库 URL: https://github.com/GobobCore/Gobob-Soho-Community

### 1.1 Web 端(手动, 30 秒)

打开 → 右上角 ⚙ → General → "About" 区域右侧 ⚙ → 编辑:

| 字段 | 值 |
|---|---|
| **Description** | Open-source CRM + student management for small study-abroad agencies and language tutoring studios |
| **Website** | https://github.com/GobobCore |
| **Topics** (一个一个加) | `apache-2.0` `education` `gobob` `study-abroad` `study-abroad-agency` `crm` `fastapi` `nextjs` `vue` `mysql` `docker` |

点 "Save changes" 完成。

### 1.2 API 端(curl + GitHub PAT)

```bash
# 1. 先到 https://github.com/settings/tokens 生成 PAT (需要 repo scope)
# 2. 复制 token 替换下面的 YOUR_PAT
export GH_TOKEN="ghp_YOUR_PAT"

# 3. PATCH description + topics + homepage
curl -s --noproxy '*' -X PATCH \
  -H "Authorization: token $GH_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/GobobCore/Gobob-Soho-Community \
  -d '{
    "description": "Open-source CRM + student management for small study-abroad agencies and language tutoring studios",
    "homepage": "https://github.com/GobobCore",
    "topics": ["apache-2.0", "education", "gobob", "study-abroad", "study-abroad-agency", "crm", "fastapi", "nextjs", "vue", "mysql", "docker"]
  }'
```

预期返回 200 + 仓库 JSON。

---

## 2. SaaS 仓库改 Private

仓库 URL: https://github.com/GobobCore/Gobob-Soho-SaaS

### 2.1 Web 端(手动, 30 秒)

打开 → ⚙ Settings → 底部 **"Danger Zone"** → **"Change repository visibility"** → **"Make private"** → 确认。

⚠️ 注意: SaaS 仓库有商业闭源代码, **必须 private**, 否则会泄露 SaaS 计费/多机构/运营后台逻辑。

### 2.2 API 端

```bash
export GH_TOKEN="ghp_YOUR_PAT"

curl -s --noproxy '*' -X PATCH \
  -H "Authorization: token $GH_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/GobobCore/Gobob-Soho-SaaS \
  -d '{"private": true}'
```

预期返回 200 + `"private": true`。

### 2.3 验证

```bash
# 应该返回: 包含 "private": true
curl -s --noproxy '*' -H "Authorization: token $GH_TOKEN" \
  https://api.github.com/repos/GobobCore/Gobob-Soho-SaaS | jq .private
```

---

## 3. 完成后

把 PAT 销毁(若用临时 PAT):

```bash
# GitHub UI → Settings → Developer settings → Personal access tokens → Delete
```

---

## 4. 后续自动化(可选)

把这俩 PATCH 加进 GitHub Actions workflow, 自动在 README 推送后跑一遍 metadata sync。

需要 GitHub PAT 在 repo Settings → Secrets → `GH_REPO_TOKEN` (PAT with repo scope), workflow:

```yaml
# .github/workflows/sync-metadata.yml
name: Sync repo metadata
on:
  push:
    paths: ['README.md']
jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: |
          curl -s -X PATCH \
            -H "Authorization: token ${{ secrets.GH_REPO_TOKEN }}" \
            -H "Accept: application/vnd.github+json" \
            https://api.github.com/repos/${{ github.repository }} \
            -d @metadata.json
```

---

**Last updated**: 2026-09-17 (cecilia, 等 PM 拍 token 后执行或手动 Web 端操作)