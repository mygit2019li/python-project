from fastapi import FastAPI, UploadFile, Form, File
from hivision import IDCreator
from hivision.error import FaceError
from hivision.creator.layout_calculator import (
    generate_layout_array,
    generate_layout_image,
)
from hivision.creator.choose_handler import choose_handler
from hivision.utils import (
    add_background,
    resize_image_to_kb,
    bytes_2_base64,
    base64_2_numpy,
    hex_to_rgb,
    add_watermark,
    save_image_dpi_to_bytes,
)
import numpy as np
import cv2
from starlette.middleware.cors import CORSMiddleware
from starlette.formparsers import MultiPartParser
from fastapi import Header, HTTPException, Request
from hivision.security import verify_signature, decrypt_data
from hivision.nsfw_detector import get_nsfw_checker
import os

# 安全配置
APP_ID = "wx_123456789"
API_SECRET_KEY = "1234567890abcdef1234567890abcdef"

# 设置Starlette表单字段大小限制
MultiPartParser.max_part_size = 10 * 1024 * 1024  # 10MB
# 设置Starlette文件上传大小限制
MultiPartParser.max_file_size = 20 * 1024 * 1024   # 20MB

app = FastAPI()
creator = IDCreator()

# 添加 CORS 中间件 解决跨域问题
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许的请求来源
    allow_credentials=True,  # 允许携带 Cookie
    allow_methods=[
        "*"
    ],  # 允许的请求方法，例如：GET, POST 等，也可以指定 ["GET", "POST"]
    allow_headers=["*"],  # 允许的请求头，也可以指定具体的头部
)


# 图片鉴黄检测接口
@app.post("/nsfw_check")
async def nsfw_check(
    input_image: UploadFile = File(None),
    payload: str = Form(None),
    x_app_id: str = Header(None, alias="X-App-Id"),
    x_timestamp: str = Header(None, alias="X-Timestamp"),
    x_signature: str = Header(None, alias="X-Signature"),
):
    """
    图片鉴黄检测接口
    
    在图片上传后、处理前调用，用于检测图片是否包含不适当内容。
    
    返回:
    - status: bool - 请求是否成功
    - is_safe: bool - 图片是否安全
    - score: float - NSFW 综合得分 (0-1, 越高越不安全)
    - details: list - 检测到的不安全内容详情
    - message: str - 检测结果描述
    """
    # 1. 验证基础安全头
    if not all([x_app_id, x_timestamp, x_signature]):
        raise HTTPException(status_code=401, detail="Missing security headers")
    
    if x_app_id != APP_ID:
        raise HTTPException(status_code=401, detail="Invalid App ID")

    # 2. 解密参数
    try:
        data = decrypt_data(payload, API_SECRET_KEY)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Decryption failed: {str(e)}")

    # 3. 验证签名
    if not verify_signature(data, x_app_id, x_timestamp, x_signature, API_SECRET_KEY):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # 4. 提取参数
    input_image_base64 = data.get("input_image_base64")
    
    # 5. 获取图片数据
    try:
        if input_image_base64:
            img = base64_2_numpy(input_image_base64)
        elif input_image:
            image_bytes = await input_image.read()
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is not None:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        else:
            raise HTTPException(status_code=400, detail="No image provided")
        
        if img is None:
            raise HTTPException(status_code=400, detail="Failed to decode image")
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Image processing failed: {str(e)}")

    # 6. 进行 NSFW 检测
    try:
        checker = get_nsfw_checker()
        result = checker.check_image_from_numpy(img)
        
        return {
            "status": True,
            "is_safe": result["is_safe"],
            "score": result["score"],
            "details": result["details"],
            "message": result["message"]
        }
    except Exception as e:
        return {
            "status": False,
            "is_safe": False,
            "score": 1.0,
            "details": [],
            "message": f"检测失败: {str(e)}"
        }


# 证件照智能制作接口
@app.post("/idphoto")
async def idphoto_inference(
    input_image: UploadFile = File(None),
    payload: str = Form(None),
    x_app_id: str = Header(None, alias="X-App-Id"),
    x_timestamp: str = Header(None, alias="X-Timestamp"),
    x_signature: str = Header(None, alias="X-Signature"),
):
    # 1. 验证基础安全头
    if not all([x_app_id, x_timestamp, x_signature]):
        raise HTTPException(status_code=401, detail="Missing security headers")
    
    if x_app_id != APP_ID:
        raise HTTPException(status_code=401, detail="Invalid App ID")

    # 2. 解密参数
    try:
        data = decrypt_data(payload, API_SECRET_KEY)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Decryption failed: {str(e)}")

    # 3. 验证签名 (使用解密后的原始参数)
    if not verify_signature(data, x_app_id, x_timestamp, x_signature, API_SECRET_KEY):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # 4. 提取参数 (解密后的 data 是一个 dict)
    input_image_base64 = data.get("input_image_base64")
    height = int(data.get("height", 413))
    width = int(data.get("width", 295))
    human_matting_model = data.get("human_matting_model", "modnet_photographic_portrait_matting")
    face_detect_model = data.get("face_detect_model", "mtcnn")
    hd = str(data.get("hd", "true")).lower() == "true"
    dpi = int(data.get("dpi", 300))
    face_align = str(data.get("face_align", "false")).lower() == "true"
    whitening_strength = int(data.get("whitening_strength", 0))
    head_measure_ratio = float(data.get("head_measure_ratio", 0.2))
    head_height_ratio = float(data.get("head_height_ratio", 0.45))
    top_distance_max = float(data.get("top_distance_max", 0.12))
    top_distance_min = float(data.get("top_distance_min", 0.10))
    brightness_strength = float(data.get("brightness_strength", 0))
    contrast_strength = float(data.get("contrast_strength", 0))
    sharpen_strength = float(data.get("sharpen_strength", 0))
    saturation_strength = float(data.get("saturation_strength", 0))
    # 如果传入了base64，则直接使用base64解码
    if input_image_base64:
        img = base64_2_numpy(input_image_base64)
    # 否则使用上传的图片
    else:
        image_bytes = await input_image.read()
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        # 将BGR转换为RGB
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # ------------------- 选择抠图与人脸检测模型 -------------------
    choose_handler(creator, human_matting_model, face_detect_model)

    # 将字符串转为元组
    size = (int(height), int(width))
    try:
        result = creator(
            img,
            size=size,
            head_measure_ratio=head_measure_ratio,
            head_height_ratio=head_height_ratio,
            head_top_range=(top_distance_max, top_distance_min),
            face_alignment=face_align,
            whitening_strength=whitening_strength,
            brightness_strength=brightness_strength,
            contrast_strength=contrast_strength,
            sharpen_strength=sharpen_strength,
            saturation_strength=saturation_strength,
        )
    except FaceError:
        result_message = {"status": False}
    # 如果检测到人脸数量等于1, 则返回标准证和高清照结果（png 4通道图像）
    else:
        result_image_standard_bytes = save_image_dpi_to_bytes(result.standard, None, dpi)
        
        result_message = {
            "status": True,
            "image_base64_standard": bytes_2_base64(result_image_standard_bytes),
        }

        # 如果hd为True, 则增加高清照结果（png 4通道图像）
        if hd:
            result_image_hd_bytes = save_image_dpi_to_bytes(result.hd, None, dpi)
            result_message["image_base64_hd"] = bytes_2_base64(result_image_hd_bytes)

    return result_message


# 人像抠图接口
@app.post("/human_matting")
async def human_matting_inference(
    input_image: UploadFile = File(None),
    payload: str = Form(None),
    x_app_id: str = Header(None, alias="X-App-Id"),
    x_timestamp: str = Header(None, alias="X-Timestamp"),
    x_signature: str = Header(None, alias="X-Signature"),
):
    # 1. 验证基础安全头
    if not all([x_app_id, x_timestamp, x_signature]):
        raise HTTPException(status_code=401, detail="Missing security headers")
    
    if x_app_id != APP_ID:
        raise HTTPException(status_code=401, detail="Invalid App ID")

    # 2. 解密参数
    try:
        data = decrypt_data(payload, API_SECRET_KEY)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Decryption failed: {str(e)}")

    # 3. 验证签名
    if not verify_signature(data, x_app_id, x_timestamp, x_signature, API_SECRET_KEY):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # 4. 提取参数
    input_image_base64 = data.get("input_image_base64")
    human_matting_model = data.get("human_matting_model", "hivision_modnet")
    dpi = int(data.get("dpi", 300))
    whitening_strength = int(data.get("whitening_strength", 0))
    brightness_strength = float(data.get("brightness_strength", 0))
    contrast_strength = float(data.get("contrast_strength", 0))
    sharpen_strength = float(data.get("sharpen_strength", 0))
    saturation_strength = float(data.get("saturation_strength", 0))
    if input_image_base64:
        img = base64_2_numpy(input_image_base64)
    else:
        image_bytes = await input_image.read()
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    # ------------------- 选择抠图与人脸检测模型 -------------------
    choose_handler(creator, human_matting_model, None)

    try:
        result = creator(
            img,
            change_bg_only=True,
            whitening_strength=whitening_strength,
            brightness_strength=brightness_strength,
            contrast_strength=contrast_strength,
            sharpen_strength=sharpen_strength,
            saturation_strength=saturation_strength,
        )
    except FaceError:
        result_message = {"status": False}

    else:
        result_image_standard_bytes = save_image_dpi_to_bytes(cv2.cvtColor(result.standard, cv2.COLOR_RGBA2BGRA), None, dpi)
        result_message = {
            "status": True,
            "image_base64": bytes_2_base64(result_image_standard_bytes),
        }
    return result_message


# 透明图像添加纯色背景接口
@app.post("/add_background")
async def photo_add_background(
    request: Request,
    x_app_id: str = Header(None, alias="X-App-Id"),
    x_timestamp: str = Header(None, alias="X-Timestamp"),
    x_signature: str = Header(None, alias="X-Signature"),
):
    # 1. 验证基础安全头
    if not all([x_app_id, x_timestamp, x_signature]):
        raise HTTPException(status_code=401, detail="Missing security headers")
    
    if x_app_id != APP_ID:
        raise HTTPException(status_code=401, detail="Invalid App ID")

    # 2. 获取请求体并解密
    try:
        body = await request.json()
        payload = body.get("payload")
        data = decrypt_data(payload, API_SECRET_KEY)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid request body or decryption failed: {str(e)}")

    # 3. 验证签名
    if not verify_signature(data, x_app_id, x_timestamp, x_signature, API_SECRET_KEY):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # 4. 提取参数
    input_image_base64 = data.get("input_image_base64")
    color = data.get("color", "000000")
    kb = data.get("kb")
    dpi = int(data.get("dpi", 300))
    render = int(data.get("render", 0))
    render_choice = ["pure_color", "updown_gradient", "center_gradient"]

    if input_image_base64:
        img = base64_2_numpy(input_image_base64)
    else:
        image_bytes = await input_image.read()
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_UNCHANGED)

    color = hex_to_rgb(color)
    color = (color[2], color[1], color[0])

    result_image = add_background(
        img,
        bgr=color,
        mode=render_choice[render],
    ).astype(np.uint8)

    result_image = cv2.cvtColor(result_image, cv2.COLOR_RGB2BGR)
    if kb:
        result_image_bytes = resize_image_to_kb(result_image, None, int(kb), dpi=dpi)
    else:
        result_image_bytes = save_image_dpi_to_bytes(result_image, None, dpi=dpi)

    result_messgae = {
        "status": True,
        "image_base64": bytes_2_base64(result_image_bytes),
    }

    return result_messgae


# 六寸排版照生成接口
@app.post("/generate_layout_photos")
async def generate_layout_photos(
    input_image: UploadFile = File(None),
    input_image_base64: str = Form(None),
    height: int = Form(413),
    width: int = Form(295),
    kb: int = Form(None),
    dpi: int = Form(300),
):
    # try:
    if input_image_base64:
        img = base64_2_numpy(input_image_base64)
    else:
        image_bytes = await input_image.read()
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    size = (int(height), int(width))

    typography_arr, typography_rotate = generate_layout_array(
        input_height=size[0], input_width=size[1]
    )

    result_layout_image = generate_layout_image(
        img, typography_arr, typography_rotate, height=size[0], width=size[1]
    ).astype(np.uint8)

    result_layout_image = cv2.cvtColor(result_layout_image, cv2.COLOR_RGB2BGR)
    if kb:
        result_layout_image_bytes = resize_image_to_kb(
            result_layout_image, None, int(kb), dpi=dpi
        )
    else:
        result_layout_image_bytes = save_image_dpi_to_bytes(result_layout_image, None, dpi=dpi)
        
    result_layout_image_base64 = bytes_2_base64(result_layout_image_bytes)

    result_messgae = {
        "status": True,
        "image_base64": result_layout_image_base64,
    }

    return result_messgae


# 透明图像添加水印接口
@app.post("/watermark")
async def watermark(
    input_image: UploadFile = File(None),
    input_image_base64: str = Form(None),
    text: str = Form("Hello"),
    size: int = 20,
    opacity: float = 0.5,
    angle: int = 30,
    color: str = "#000000",
    space: int = 25,
    kb: int = Form(None),
    dpi: int = Form(300),
):
    if input_image_base64:
        img = base64_2_numpy(input_image_base64)
    else:
        image_bytes = await input_image.read()
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    try:
        result_image = add_watermark(img, text, size, opacity, angle, color, space)

        result_image = cv2.cvtColor(result_image, cv2.COLOR_RGB2BGR)
        if kb:
            result_image_bytes = resize_image_to_kb(result_image, None, int(kb), dpi=dpi)
        else:
            result_image_bytes = save_image_dpi_to_bytes(result_image, None, dpi=dpi)
        result_image_base64 = bytes_2_base64(result_image_bytes)

        result_messgae = {
            "status": True,
            "image_base64": result_image_base64,
        }
    except Exception as e:
        result_messgae = {
            "status": False,
            "error": str(e),
        }

    return result_messgae


# 设置照片KB值接口(RGB图)
@app.post("/set_kb")
async def set_kb(
    input_image: UploadFile = File(None),
    input_image_base64: str = Form(None),
    dpi: int = Form(300),
    kb: int = Form(50),
):
    if input_image_base64:
        img = base64_2_numpy(input_image_base64)
    else:
        image_bytes = await input_image.read()
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    try:
        result_image = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        result_image_bytes = resize_image_to_kb(result_image, None, int(kb), dpi=dpi)
        result_image_base64 = bytes_2_base64(result_image_bytes)

        result_messgae = {
            "status": True,
            "image_base64": result_image_base64,
        }
    except Exception as e:
        result_messgae = {
            "status": False,
            "error": e,
        }

    return result_messgae


# 证件照智能裁剪接口
@app.post("/idphoto_crop")
async def idphoto_crop_inference(
    input_image: UploadFile = File(None),
    input_image_base64: str = Form(None),
    height: int = Form(413),
    width: int = Form(295),
    face_detect_model: str = Form("mtcnn"),
    hd: bool = Form(True),
    dpi: int = Form(300),
    head_measure_ratio: float = Form(0.2),
    head_height_ratio: float = Form(0.45),
    top_distance_max: float = Form(0.12),
    top_distance_min: float = Form(0.10),
):
    if input_image_base64:
        img = base64_2_numpy(input_image_base64)
    else:
        image_bytes = await input_image.read()
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_UNCHANGED)  # 读取图像(4通道)

    # ------------------- 选择抠图与人脸检测模型 -------------------
    choose_handler(creator, face_detect_option=face_detect_model)

    # 将字符串转为元组
    size = (int(height), int(width))
    try:
        result = creator(
            img,
            size=size,
            head_measure_ratio=head_measure_ratio,
            head_height_ratio=head_height_ratio,
            head_top_range=(top_distance_max, top_distance_min),
            crop_only=True,
            whitening_strength=whitening_strength,
            brightness_strength=brightness_strength,
            contrast_strength=contrast_strength,
            sharpen_strength=sharpen_strength,
            saturation_strength=saturation_strength,
        )
    except FaceError:
        result_message = {"status": False}
    # 如果检测到人脸数量等于1, 则返回标准证和高清照结果（png 4通道图像）
    else:
        result_image_standard_bytes = save_image_dpi_to_bytes(cv2.cvtColor(result.standard, cv2.COLOR_RGBA2BGRA), None, dpi)
        
        result_message = {
            "status": True,
            "image_base64_standard": bytes_2_base64(result_image_standard_bytes),
        }

        # 如果hd为True, 则增加高清照结果（png 4通道图像）
        if hd:
            result_image_hd_bytes = save_image_dpi_to_bytes(cv2.cvtColor(result.hd, cv2.COLOR_RGBA2BGRA), None, dpi)
            result_message["image_base64_hd"] = bytes_2_base64(result_image_hd_bytes)

    return result_message


# PDF 转图片接口
@app.post("/pdf2img")
async def pdf2img(
    file: UploadFile = File(None),
    payload: str = Form(None),
    x_app_id: str = Header(None, alias="X-App-Id"),
    x_timestamp: str = Header(None, alias="X-Timestamp"),
    x_signature: str = Header(None, alias="X-Signature"),
):
    # 1. 验证基础安全头
    if not all([x_app_id, x_timestamp, x_signature]):
        raise HTTPException(status_code=401, detail="Missing security headers")

    if x_app_id != APP_ID:
        raise HTTPException(status_code=401, detail="Invalid App ID")

    # 2. 解密参数
    try:
        data = decrypt_data(payload, API_SECRET_KEY)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Decryption failed: {str(e)}")

    # 3. 验证签名
    if not verify_signature(data, x_app_id, x_timestamp, x_signature, API_SECRET_KEY):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # 4. 读取并校验 PDF
    if file is None:
        raise HTTPException(status_code=400, detail="Missing PDF file")

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Empty PDF file")
    if len(pdf_bytes) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="PDF file too large (max 20MB)")

    # 5. 逐页渲染为 PNG
    dpi = int(data.get("dpi", 150))
    dpi = max(72, min(dpi, 300))
    max_pages = 30

    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise HTTPException(status_code=500, detail="Server missing dependency: pymupdf")

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid PDF file: {str(e)}")

    page_count = doc.page_count
    images = []
    try:
        for page in doc:
            if len(images) >= max_pages:
                break
            pix = page.get_pixmap(dpi=dpi)
            images.append(bytes_2_base64(pix.tobytes("png")))
    finally:
        doc.close()

    return {
        "status": True,
        "page_count": page_count,
        "images": images,
    }


if __name__ == "__main__":
    import uvicorn

    # 在8081端口运行推理服务
    uvicorn.run(app, host="0.0.0.0", port=8087)
