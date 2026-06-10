# Cloudflare Access 演示站部署说明

## 当前站点

| 系统 | GitHub private repo | Cloudflare Pages project | 发布目录 | 正式域名 |
| --- | --- | --- | --- | --- |
| GlobalAR | `Yiseut/GlobalAR` | `globalar` | `web` | `globalar.aestratmc.com` |
| ChinaAR | `Yiseut/Registration` | `chinaar` | `docs` | `chinaar.aestratmc.com` |

## 访问控制

Cloudflare One / Access application:

```text
globalar
```

Public hostnames:

```text
globalar.aestratmc.com
chinaar.aestratmc.com
```

Policy:

```text
datashow
Action: Allow
Include: Emails
Value: giselle.ding@gmail.com
```

不要添加 `Everyone`、`Bypass` 或 `*@gmail.com`。

## GlobalAR 更新

在 `E:\shared\Documents\data\global_aesthetics_dashboard` 里双击：

```text
Deploy-GlobalAR-Cloudflare.bat
```

或运行：

```powershell
npx wrangler pages deploy web --project-name globalar --branch main --commit-dirty=true
```

## ChinaAR 更新

在 `E:\shared\Documents\data\Registration` 里双击：

```text
Deploy-ChinaAR-Cloudflare.bat
```

或运行：

```powershell
npx wrangler pages deploy docs --project-name chinaar --branch main --commit-dirty=true
```

## 新增一个类似演示站

1. GitHub 仓库设为 private。
2. 确认静态发布目录，例如 `web` 或 `docs`。
3. 创建 Pages 项目：

```powershell
npx wrangler pages project create project-name --production-branch main
```

4. 上传静态目录：

```powershell
npx wrangler pages deploy publish-dir --project-name project-name --branch main --commit-dirty=true
```

5. Cloudflare Workers & Pages 里绑定正式子域名。
6. Cloudflare One / Access application 里添加该 hostname。
7. 用无痕窗口确认正式域名先进入 Cloudflare Access 登录页。
8. 处理 Pages 临时域名，避免绕过正式域名。

## iPad 使用

打开正式域名，通过邮箱验证码登录后，在 Safari 里选择“添加到主屏幕”。后续更新后刷新页面即可看到新版。
