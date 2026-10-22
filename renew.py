# renew.py - DigitalPlat 多账号纯 API 自动续期与邮箱标识版

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
# 支持多账号，多个 Key 用英文逗号隔开
DP_API_KEYS_RAW = os.getenv("DP_API_KEY", "")
DP_API_KEYS = [k.strip() for k in DP_API_KEYS_RAW.split(",") if k.strip()]

# 账号邮箱映射，用英文逗号隔开，例如: adjlevis@qq.com, liu687836@gmail.com, djbadboy.vip@qq.com
DP_ACCOUNT_EMAILS_RAW = os.getenv("DP_ACCOUNT_EMAILS", "")
DP_ACCOUNT_EMAILS = [e.strip() for e in DP_ACCOUNT_EMAILS_RAW.split(",") if e.strip()]

# 通知配置：Telegram
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

# 通知配置：自定义微信 / PushPlus
WX_PUSH_URL = os.getenv("WX_PUSH_URL")          
WX_PUSH_TOKEN = os.getenv("WX_PUSH_TOKEN")      

API_BASE_URL = "https://domain-api.digitalplat.org/api/v1"

def validate_config():
    """验证必需的环境变量是否已设置"""
    if not DP_API_KEYS:
        logger.error("错误：缺少必需的环境变量 DP_API_KEY。请在 GitHub Secrets 中配置。")
        sys.exit(1)

def get_account_label(index):
    """根据索引获取账号标识名称（优先显示邮箱，若无则显示账号数字）"""
    if index - 1 < len(DP_ACCOUNT_EMAILS) and DP_ACCOUNT_EMAILS[index - 1]:
        return DP_ACCOUNT_EMAILS[index - 1]
    return f"账号 {index}"

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
                "summary": title + "\n" + content[:100],  # 确保微信列表预览直接显示内容
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

def get_headers(api_key):
    """构建官方 API 请求头"""
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

def parse_expiry_days(expiry_str):
    """解析到期时间字符串并计算剩余天数（支持纯数字 20270412 格式）"""
    if not expiry_str:
        return None
    expiry_str = str(expiry_str).strip()
    
    formats = [
        "%Y%m%d",
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ"
    ]
    
    clean_str = expiry_str.split(".")[0].rstrip("Z")
    for fmt in formats:
        try:
            exp_dt = datetime.strptime(clean_str, fmt)
            remaining = (exp_dt - datetime.now()).days
            return remaining
        except ValueError:
            continue
    return None

def fetch_domains(api_key):
    """通过 API 获取域名列表"""
    url = f"{API_BASE_URL}/domains"
    try:
        response = requests.get(url, headers=get_headers(api_key), timeout=30)
        if response.status_code != 200:
            logger.error(f"获取域名列表失败，状态码: {response.status_code}, 响应: {response.text}")
            return []
        
        data = response.json()
        domains = data.get("data", [])
        if isinstance(domains, dict):
            domains = domains.get("domains", [])
        return domains
    except Exception as e:
        logger.error(f"获取域名列表异常: {e}")
        return []

def renew_domain(api_key, domain_identifier):
    """通过 API 续期指定域名"""
    url = f"{API_BASE_URL}/domains/{domain_identifier}/renew"
    headers = get_headers(api_key)
    headers["Idempotency-Key"] = f"renew-{domain_identifier}-{int(datetime.now().timestamp())}"
    
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

def process_account(api_key, index):
    """处理单个账号下的域名检查与续期"""
    account_name = get_account_label(index)
    logger.info(f"\n--- 开始处理账号: {account_name} ---")
    
    domains = fetch_domains(api_key)
    if not domains:
        logger.info(f"账号 {account_name} 未找到任何域名或获取列表为空。")
        return f"【账号: {account_name}】\n⚠️ 未找到有效域名或 API Key 无效"

    report_lines = [f"【账号: {account_name}】"]
    
    for d in domains:
        name = d.get("name") or d.get("domain")
        domain_id = d.get("id") or name
        if not name:
            continue
        
        expiry_raw = d.get("expires_at") or d.get("expiry_date") or d.get("expire_at") or d.get("expires")
        remaining_days = parse_expiry_days(expiry_raw)
        
        logger.info(f"检查域名: {name} (到期时间: {expiry_raw}, 剩余天数: {remaining_days})")

        # 判断：如果计算出剩余天数大于 120 天，自动跳过
        if remaining_days is not None and remaining_days > 120:
            logger.info(f"ℹ️ 域名 {name} 距离到期还有 {remaining_days} 天，暂无需续期，已跳过。")
            report_lines.append(f"⚪ {name}: 剩 {remaining_days} 天 (未到期)")
            continue

        # 处于 120 天内（或无法解析日期时），尝试进行续期
        result = renew_domain(api_key, domain_id)
        if result["status"] in [200, 201]:
            logger.info(f"✅ 域名 {name} 续期成功！")
            report_lines.append(f"✅ {name}: 续期成功 (+1年)")
        else:
            msg = result["body"]
            if "more than 120 days" in msg or "cannot renew" in msg.lower():
                days_str = f"剩 {remaining_days} 天" if remaining_days is not None else "未到期"
                logger.info(f"ℹ️ 域名 {name} 暂无需续期。")
                report_lines.append(f"⚪ {name}: {days_str} (暂无需续期)")
            else:
                logger.warning(f"❌ 域名 {name} 续期失败: {msg[:120]}")
                report_lines.append(f"❌ {name}: 失败 ({msg[:60]})")

    return "\n".join(report_lines)

def main():
    validate_config()
    
    all_reports = []
    for idx, key in enumerate(DP_API_KEYS, 1):
        account_report = process_account(key, idx)
        all_reports.append(account_report)

    final_content = "\n\n".join(all_reports)
    title = "DigitalPlat 自动续期汇总报告"
    
    # 发送通知
    send_notifications(title, final_content)
    logger.info("所有账号任务执行完毕。")

if __name__ == "__main__":
    main()
