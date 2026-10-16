FROM python:3.10-slim

# 1) 替换为腾讯云镜像源
#    新版 Debian(bookworm/trixie+) 的 APT 源是 debian.sources，
#    旧版才是 sources.list，这里做兼容处理。
RUN set -eux; \
    for f in /etc/apt/sources.list.d/debian.sources /etc/apt/sources.list; do \
        if [ -f "$f" ]; then \
            sed -i 's|deb.debian.org|mirrors.tencent.com|g; s|security.debian.org|mirrors.tencent.com|g' "$f"; \
        fi; \
    done

# 2) 关闭 Release 文件有效期校验，避免镜像站同步滞后导致构建失败
RUN echo 'Acquire::Check-Valid-Until "false";' > /etc/apt/apt.conf.d/99no-check-valid

# 3) 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libgl1 \
        libglx-mesa0 \
        libglu1-mesa \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 4) 先拷依赖文件，利用 Docker 层缓存
COPY requirements.txt requirements-app.txt ./

# 5) 安装 Python 依赖（清华源）
RUN pip install --no-cache-dir \
        -i https://pypi.tuna.tsinghua.edu.cn/simple \
        -r requirements.txt -r requirements-app.txt

# 6) 拷贝项目代码
COPY . .

# 微信小程序凭证：用于 wx.login code2Session 换 openid 与 msgSecCheck 内容安全检测
ENV WX_APPID=wx2839e4f9b66968f0
ENV WX_SECRET=fed00aa9847998ea375c7a4019bc229d

EXPOSE 8087

CMD ["python3", "-u", "deploy_api.py"]