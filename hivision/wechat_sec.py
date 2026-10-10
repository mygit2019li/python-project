"""
微信服务端安全能力封装
- access_token 获取与缓存（供 msgSecCheck 使用）
- code2Session（code 换 openid，msgSecCheck 2.0 必传 openid）
- msgSecCheck 文本内容安全检测

说明：本模块仅使用标准库 urllib，避免引入额外依赖。
调用方需保证在线程池中执行（本模块为同步阻塞实现）。
"""

import json
import os
import threading
import time
import urllib.parse
import urllib.request

# 凭据一律从环境变量读取，禁止硬编码明文
# 兼容两种变量名：WX_APPID / WX_APP_ID
WX_APPID = os.getenv("WX_APPID") or os.getenv("WX_APP_ID", "")
WX_SECRET = os.getenv("WX_SECRET", "")

WX_API_BASE = "https://api.weixin.qq.com"
HTTP_TIMEOUT = 5

# access_token 缓存：微信侧有效期 7200s，提前 300s 刷新
_token_lock = threading.Lock()
_token_cache = {"value": None, "expire_at": 0.0}


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _post_json(url: str, body: dict) -> dict:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_access_token(force: bool = False) -> str:
    """获取 access_token（带进程内缓存）。force=True 时强制刷新。"""
    if not WX_APPID or not WX_SECRET:
        raise RuntimeError("WX_APPID / WX_SECRET 未配置，请在环境变量中设置")

    now = time.time()
    with _token_lock:
        if not force and _token_cache["value"] and _token_cache["expire_at"] > now:
            return _token_cache["value"]

        query = urllib.parse.urlencode(
            {
                "grant_type": "client_credential",
                "appid": WX_APPID,
                "secret": WX_SECRET,
            }
        )
        data = _get_json(f"{WX_API_BASE}/cgi-bin/token?{query}")

        token = data.get("access_token")
        if not token:
            # 常见错误：40001/40013 appid 或 secret 错误
            raise RuntimeError(f"获取 access_token 失败: {data}")

        _token_cache["value"] = token
        _token_cache["expire_at"] = now + int(data.get("expires_in", 7200)) - 300
        return token


def code2session(code: str) -> dict:
    """
    code 换 openid / session_key。
    官方文档：https://developers.weixin.qq.com/miniprogram/dev/OpenApiDoc/user-login/code2Session.html
    """
    if not WX_APPID or not WX_SECRET:
        raise RuntimeError("WX_APPID / WX_SECRET 未配置，请在环境变量中设置")

    query = urllib.parse.urlencode(
        {
            "appid": WX_APPID,
            "secret": WX_SECRET,
            "js_code": code,
            "grant_type": "authorization_code",
        }
    )
    data = _get_json(f"{WX_API_BASE}/sns/jscode2session?{query}")

    if data.get("errcode"):
        raise RuntimeError(f"code2Session 失败: {data}")

    return {
        "openid": data.get("openid"),
        "session_key": data.get("session_key"),
        "unionid": data.get("unionid"),
    }


def msg_sec_check(content: str, openid: str, scene: int = 2) -> dict:
    """
    文本内容安全检测（msgSecCheck 2.0）。
    官方文档：https://developers.weixin.qq.com/miniprogram/dev/OpenApiDoc/sec-center/sec-check/msgSecCheck.html

    :param content: 待检测文本（UTF-8，上限 2500 字）
    :param openid:  用户 openid（要求用户近两小时内访问过小程序）
    :param scene:   场景枚举：1 资料 / 2 评论 / 3 论坛 / 4 社交日志
    :return: 微信原始返回 dict（含 errcode / result.suggest / result.label / detail）
    """
    body = {
        "version": 2,
        "openid": openid,
        "scene": scene,
        "content": content,
    }

    def _call(force_token: bool) -> dict:
        token = get_access_token(force=force_token)
        url = f"{WX_API_BASE}/wxa/msg_sec_check?access_token={token}"
        return _post_json(url, body)

    result = _call(force_token=False)

    # access_token 失效时强制刷新并重试一次
    if result.get("errcode") in (40001, 40014, 42001):
        result = _call(force_token=True)

    return result


def is_token_error(result: dict) -> bool:
    return result.get("errcode") in (40001, 40014, 42001)
