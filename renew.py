# renew.py - DigitalPlat 纯 API 自动续期与多通道通知版

import os
import sys
import json
import logging
import requests
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- 1. 从环境变量中读取配置 ---
DP_API_KEY = os.getenv("DP_API_KEY")  # 官方后台生成的 API 密钥 (dp_live_...)

# 通知配置：Telegram
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

# 通知配置：自定义微信 / PushPlus
WX_PUSH_URL = os.getenv("WX_PUSH_URL")          # 自定义微信推送接口地址
WX_PUSH_TOKEN = os.getenv("WX_PUSH_TOKEN")      # 自定义微信/PushPlus的Token

# --- 2. 官方 API 基础地址 ---
API_BASE_URL = "https://domain-api.digitalplat.org/api/v1"

def validate_config():
    """验证必需的环境变量是否已设置"""
    if not DP_API_KEY:
        logger.error("错误：缺少必需的环境变量 DP_API_KEY。请在 GitHub Secrets 中配置。")
        sys.exit(1)

def send_notifications(title, content):
    """同时推送通知到 Telegram 和 自定义微信"""
    # 1. 发送 Telegram 通知
    if TG_BOT_TOKEN and TG_CHAT_ID:
        try:
            tg_url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
            payload = {
                "chat_id": TG_CHAT_ID,
                "text": f"*{title}*\n\n{content}",
                "parse_mode": "Markdown"
            }
            res = requests.post(tg_url, json=payload, timeout=10)
            if res.status_code == 200:
                logger.info("Telegram 通知发送成功。")
            else:
                logger.warning(f"Telegram 通知发送失败: {res.text}")
        except Exception as e:
            logger.error(f"Telegram 通知异常: {e}")

    # 2. 发送自定义微信 / wxsend 通知
    if WX_PUSH_URL and WX_PUSH_TOKEN:
        try:
            headers = {
                "Authorization": f"Bearer {WX_PUSH_TOKEN}",
                "Content-Type": "application/json"
            }
            payload = {
                "token": WX_PUSH_TOKEN,
                "title": title,
                "text": content,
                "summary": title,
                "description": content,
                "content": content
            }
            res = requests.post(WX_PUSH_URL, json=payload, headers=headers, timeout=10)
            if res.status_code == 200:
                logger.info("微信通知发送成功。")
            else:
                logger.warning(f"微信通知发送失败: {res.status_code} - {res.text}")
        except Exception as e:
            logger.error(f"微信通知异常: {e}")

def get_headers():
    """构建官方 API 请求头"""
    return {
        "Authorization": f"Bearer {DP_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

def fetch_domains():
    """通过 API 获取域名列表"""
    url = f"{API_BASE_URL}/domains"
    logger.info("正在获取域名列表...")
    try:
        response = requests.get(url, headers=get_headers(), timeout=30)
        if response.status_code != 200:
            logger.error(f"获取域名列表失败，状态码: {response.status_code}, 响应: {response.text}")
            return []
        
        data = response.json()
        # 根据官方标准的 envelop 返回格式提取数据
        domains = data.get("data", [])
        if isinstance(domains, dict):
            domains = domains.get("domains", [])
        return domains
    except Exception as e:
        logger.error(f"获取域名列表异常: {e}")
        return []

def renew_domain(domain_name):
    """通过 API 续期指定域名"""
    url = f"{API_BASE_URL}/domains/{domain_name}/renew"
    headers = get_headers()
    headers["Idempotency-Key"] = f"renew-{domain_name}-{int(datetime.now().timestamp())}"
    
    payload = {
        "renewal_type": "free",
        "years": 1
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        return {
            "status": response.status_code,
            "body": response.text
        }
    except Exception as e:
        return {
            "status": 500,
            "body": str(e)
        }

def save_results(renewed_domains, failed_domains):
    """保存处理结果到 JSON 文件"""
    results = {
        "timestamp": datetime.now().isoformat(),
        "renewed_count": len(renewed_domains),
        "failed_count": len(failed_domains),
        "renewed_domains": renewed_domains,
        "failed_domains": failed_domains
    }
    try:
        with open("renewal_results.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        logger.info("处理结果已保存到 renewal_results.json")
    except Exception as e:
        logger.error(f"保存结果错误: {e}")

def main():
    validate_config()
    
    domains = fetch_domains()
    if not domains:
        logger.info("未找到任何域名或获取列表为空。")
        return

    logger.info(f"共获取到 {len(domains)} 个域名，开始检查续期状态...")
    renewed_domains = []
    failed_domains = []

    for d in domains:
        # 兼容不同字段名称
        name = d.get("name") or d.get("domain")
        can_renew = d.get("can_manual_renew", True) # 默认若无此字段则尝试请求
        
        if not name:
            continue

        logger.info(f"正在检查域名: {name}")

        # 发起续期请求
        result = renew_domain(name)
        if result["status"] in [200, 201]:
            logger.info(f"✅ 域名 {name} 续期成功！")
            renewed_domains.append(name)
        else:
            msg = result["body"]
            # 常见提示：距到期时间超过 120 天暂时无法续期
            if "more than 120 days" in msg or "cannot renew" in msg.lower():
                logger.info(f"ℹ️ 域名 {name} 距离到期时间尚早，暂无需续期。")
            else:
                logger.warning(f"❌ 域名 {name} 续期失败: {msg[:150]}")
                failed_domains.append(f"{name}: {msg[:100]}")

    # 汇总通知内容
    title = "DigitalPlat 自动续期报告"
    content_lines = []
    if renewed_domains:
        content_lines.append(f"✅ 成功续期 ({len(renewed_domains)}):")
        content_lines.extend([f"- {d}" for d in renewed_domains])
    if failed_domains:
        content_lines.append(f"\n❌ 失败或跳过 ({len(failed_domains)}):")
        content_lines.extend([f"- {f}" for f in failed_domains])
    
    if not content_lines:
        content_lines.append("所有域名检查完毕，本次无需要续期的域名。")

    final_content = "\n".join(content_lines)
    
    # 发送通知
    send_notifications(title, final_content)
    save_results(renewed_domains, failed_domains)
    logger.info("所有任务执行完毕。")

if __name__ == "__main__":
    main()
