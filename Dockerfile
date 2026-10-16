FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 libglx-mesa0 libglu1-mesa \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt requirements-app.txt ./

RUN pip install --no-cache-dir -r requirements.txt -r requirements-app.txt

COPY . .

# 微信小程序凭证：用于 wx.login code2Session 换 openid 与 msgSecCheck 内容安全检测
ENV WX_APPID=wx2839e4f9b66968f0
ENV WX_SECRET=fed00aa9847998ea375c7a4019bc229d

EXPOSE 8087

CMD ["python3", "-u", "deploy_api.py"]