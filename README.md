# DigitalPlat 多账号域名自动续期 GitHub Actions 脚本

本脚本用于通过 DigitalPlat API 实现多个账号下免费域名的自动检查与续期，支持计算剩余天数、精准跳过未到期域名、捕获运行异常并通过 Telegram 与微信推送详细报告。

---

## 🌟 功能特性

1. **精准剩余天数解析**：
   * 自动解析域名到期时间，计算距离到期的剩余天数。
   * 剩余天数 **> 120 天** 时，自动判定为暂无需续期并跳过请求，节省 API 调用。
2. **多账号独立绑定与隔离**：
   * 支持通过邮箱列表（`DP_ACCOUNT_EMAILS`）与 API 密钥列表（`DP_API_KEY`）按顺序严格 1 对 1 绑定。
   * 若某个账号未配置独立的 API 密钥，会自动跳过该账号，避免账号间域名数据混乱显示。
3. **完善的通知提醒与报错告警**：
   * 支持 **Telegram Bot** 与 **自定义微信 (wxsend/PushPlus)** 双通道推送。
   * 优化微信列表摘要预览（`summary` / `description` 字段），解决列表预览空白问题。
   * **全局异常捕获**：即便脚本运行时遇到错误或配置缺失，也会第一时间将具体报错原因推送至手机。

---

## 🛠️ GitHub Secrets 环境变量配置

请在 GitHub 仓库的 **Settings** -> **Secrets and variables** -> **Actions** 中添加以下密钥：

| 变量名 | 是否必填 | 示例 / 说明 |
| :--- | :---: | :--- |
| `DP_API_KEY` | **是** | `dp_live_xxx1, dp_live_xxx2, dp_live_xxx3`<br>*(多个账号 Key 用英文逗号分隔)* |
| `DP_ACCOUNT_EMAILS` | **是** | `adxxxx@qq.com, lixxxx@gmail.com, badboyxx@qq.com`<br>*(按顺序与 API Key 依次对应)* |
| `TG_BOT_TOKEN` | 选填 | `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ` |
| `TG_CHAT_ID` | 选填 | `987654321` |
| `WX_PUSH_URL` | 选填 | `https://wxsend.example.com/send` |
| `WX_PUSH_TOKEN` | 选填 | `your_wx_push_token` |


## 修改后的效果：

账号 1 (adjxxx@qq.com)：因为配置了对应的 DP_API_KEY，会正常查询并显示其名下的域名（如 axx.qd.je 和 axx6.qzz.io）。

账号 2 和 3：因为在 GitHub Secrets 的 DP_API_KEY 中没有配置第二个和第三个密钥，它们不会去复用第一个账号的 Key，而是会直接在报告中显示：

⚠️ 未配置对应的 API 密钥 (DP_API_KEY)，跳过检查。

这样各个账号就实现了严格隔离，互不干扰！

---

## ⚠️ 注意事项

* **安全性**: 您的账号密码存储在 GitHub 的加密 Secrets 中，脚本通过环境变量读取，不会暴露在代码或日志里，非常安全。
* **续期限制**: DigitalPlat 规定域名距到期 **超过 120 天**时不允许续期。脚本会跳过这类域名并正常结束。
* **脚本健壮性**: 本脚本依赖 DigitalPlat 的 API 结构。如果未来网站大幅改版，可能会导致脚本失效。届时需要根据新的接口更新脚本。
