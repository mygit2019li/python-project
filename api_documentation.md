# HivisionIDPhotos API 文档

## 概述

HivisionIDPhotos 是一个证件照生成系统，提供了一系列 API 接口来处理证件照相关的操作，包括生成证件照、人像抠图、添加背景色、生成排版照等。

## 开始之前

在请求 API 之前，请先运行后端服务：

```bash
python deploy_api.py
```

服务将运行在 `http://127.0.0.1:8080`

## 接口列表

| 接口名称 | 路径 | 方法 | 功能描述 |
|---------|------|------|----------|
| 生成证件照(底透明) | /idphoto | POST | 生成透明底色的证件照，支持高清和标准尺寸 |
| 人像抠图 | /human_matting | POST | 对人像进行抠图，生成透明底色的人像 |
| 添加背景色 | /add_background | POST | 为透明图像添加背景色，支持纯色和渐变效果 |
| 生成六寸排版照 | /generate_layout_photos | POST | 将证件照排列成六寸照片，方便打印 |
| 图像加水印 | /watermark | POST | 为图像添加文字水印，支持自定义样式 |
| 设置图像KB大小 | /set_kb | POST | 调整图像文件大小，以KB为单位 |
| 证件照裁切 | /idphoto_crop | POST | 对已有的透明证件照进行裁切，调整人像位置和大小 |
| 图片鉴黄检测 | /nsfw_check | POST | 检测图片是否包含不适当内容 |
| PDF转图片 | /pdf2img | POST | 将PDF文件逐页渲染为PNG图片返回 |

## 通用安全头

以下接口需要携带安全请求头，否则返回 401：

| 请求头 | 必填 | 说明 |
|-------|------|------|
| X-App-Id | 是 | 应用ID |
| X-Timestamp | 是 | 时间戳 |
| X-Signature | 是 | 请求签名，基于解密后的参数计算 |

`payload` 参数为 AES-ECB 加密后的 JSON 字符串（Base64编码），使用与 `API_SECRET_KEY` 约定的密钥加密。`payload` 为必填参数，缺失或解密失败会返回 400。

## 接口详情

### 1. 生成证件照(底透明)

**路径**：`/idphoto`

**方法**：`POST`

**功能**：生成透明底色的证件照，支持高清和标准尺寸，并包含美颜功能

**请求参数**：

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|-------|------|------|--------|------|
| input_image | file | 二选一 | None | 传入的图像文件，需为RGB三通道图像 |
| input_image_base64 | string | 二选一 | None | 传入的图像文件的base64编码，需为RGB三通道图像 |
| height | int | 否 | 413 | 标准证件照高度 |
| width | int | 否 | 295 | 标准证件照宽度 |
| human_matting_model | string | 否 | modnet_photographic_portrait_matting | 人像分割模型，可选值：modnet_photographic_portrait_matting、hivision_modnet、rmbg-1.4、birefnet-v1-lite |
| face_detect_model | string | 否 | mtcnn | 人脸检测模型，可选值：mtcnn、face_plusplus、retinaface-resnet50 |
| hd | bool | 否 | True | 是否生成高清证件照 |
| dpi | int | 否 | 300 | 图像分辨率 |
| face_align | bool | 否 | False | 是否进行人脸对齐 |
| whitening_strength | int | 否 | 0 | 美白强度，范围：0-100 |
| brightness_strength | float | 否 | 0 | 亮度调整强度，范围：-100-100 |
| contrast_strength | float | 否 | 0 | 对比度调整强度，范围：-100-100 |
| sharpen_strength | float | 否 | 0 | 锐化调整强度，范围：0-100 |
| saturation_strength | float | 否 | 0 | 饱和度调整强度，范围：-100-100 |
| head_measure_ratio | float | 否 | 0.2 | 面部面积与照片面积的比例 |
| head_height_ratio | float | 否 | 0.45 | 面部中心与照片顶部的高度比例 |
| top_distance_max | float | 否 | 0.12 | 头部与照片顶部距离的比例最大值 |
| top_distance_min | float | 否 | 0.10 | 头部与照片顶部距离的比例最小值 |

**响应参数**：

| 参数名 | 类型 | 说明 |
|-------|------|------|
| status | bool | 状态码，true表示成功 |
| image_base64_standard | string | 标准证件照的base64编码（PNG格式，透明背景） |
| image_base64_hd | string | 高清证件照的base64编码（PNG格式，透明背景），仅当hd为True时返回 |

### 2. 人像抠图

**路径**：`/human_matting`

**方法**：`POST`

**功能**：对人像进行抠图，生成透明底色的人像，并支持美颜功能

**请求参数**：

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|-------|------|------|--------|------|
| input_image | file | 二选一 | None | 传入的图像文件，需为RGB三通道图像 |
| input_image_base64 | string | 二选一 | None | 传入的图像文件的base64编码，需为RGB三通道图像 |
| human_matting_model | string | 否 | hivision_modnet | 人像分割模型，可选值：modnet_photographic_portrait_matting、hivision_modnet、rmbg-1.4、birefnet-v1-lite |
| dpi | int | 否 | 300 | 图像分辨率 |
| whitening_strength | int | 否 | 0 | 美白强度，范围：0-100 |
| brightness_strength | float | 否 | 0 | 亮度调整强度，范围：-100-100 |
| contrast_strength | float | 否 | 0 | 对比度调整强度，范围：-100-100 |
| sharpen_strength | float | 否 | 0 | 锐化调整强度，范围：0-100 |
| saturation_strength | float | 否 | 0 | 饱和度调整强度，范围：-100-100 |

**响应参数**：

| 参数名 | 类型 | 说明 |
|-------|------|------|
| status | bool | 状态码，true表示成功 |
| image_base64 | string | 抠图人像照的base64编码（PNG格式，透明背景） |

### 3. 添加背景色

**路径**：`/add_background`

**方法**：`POST`

**功能**：为透明图像添加背景色，支持纯色和渐变效果

**请求参数**：

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|-------|------|------|--------|------|
| input_image | file | 二选一 | None | 传入的图像文件，需为RGBA四通道图像 |
| input_image_base64 | string | 二选一 | None | 传入的图像文件的base64编码，需为RGBA四通道图像 |
| color | string | 否 | 000000 | 背景色HEX值，如"638cce" |
| kb | int | 否 | None | 输出照片的KB值，None表示不调整 |
| render | int | 否 | 0 | 渲染模式，0：纯色，1：上下渐变，2：中心渐变 |
| dpi | int | 否 | 300 | 图像分辨率 |

**响应参数**：

| 参数名 | 类型 | 说明 |
|-------|------|------|
| status | bool | 状态码，true表示成功 |
| image_base64 | string | 添加背景色之后的图像的base64编码 |

### 4. 生成六寸排版照

**路径**：`/generate_layout_photos`

**方法**：`POST`

**功能**：将证件照排列成六寸照片，方便打印

**请求参数**：

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|-------|------|------|--------|------|
| input_image | file | 二选一 | None | 传入的图像文件，需为RGB三通道图像 |
| input_image_base64 | string | 二选一 | None | 传入的图像文件的base64编码，需为RGB三通道图像 |
| height | int | 否 | 413 | 输入图像的高度 |
| width | int | 否 | 295 | 输入图像的宽度 |
| kb | int | 否 | None | 输出照片的KB值，None表示不调整 |
| dpi | int | 否 | 300 | 图像分辨率 |

**响应参数**：

| 参数名 | 类型 | 说明 |
|-------|------|------|
| status | bool | 状态码，true表示成功 |
| image_base64 | string | 六寸排版照的base64编码 |

### 5. 图像加水印

**路径**：`/watermark`

**方法**：`POST`

**功能**：为图像添加文字水印，支持自定义样式

**请求参数**：

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|-------|------|------|--------|------|
| input_image | file | 二选一 | None | 传入的图像文件，需为RGB三通道图像 |
| input_image_base64 | string | 二选一 | None | 传入的图像文件的base64编码，需为RGB三通道图像 |
| text | string | 否 | Hello | 水印文本 |
| size | int | 否 | 20 | 水印字体大小 |
| opacity | float | 否 | 0.5 | 水印透明度 |
| angle | int | 否 | 30 | 水印旋转角度 |
| color | string | 否 | #000000 | 水印颜色，如"#000000" |
| space | int | 否 | 25 | 水印间距 |
| kb | int | 否 | None | 输出照片的KB值，None表示不调整 |
| dpi | int | 否 | 300 | 图像分辨率 |

**响应参数**：

| 参数名 | 类型 | 说明 |
|-------|------|------|
| status | bool | 状态码，true表示成功 |
| image_base64 | string | 添加水印之后的图像的base64编码 |
| error | string | 错误信息，仅当status为false时返回 |

### 6. 设置图像KB大小

**路径**：`/set_kb`

**方法**：`POST`

**功能**：调整图像文件大小，以KB为单位

**请求参数**：

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|-------|------|------|--------|------|
| input_image | file | 二选一 | None | 传入的图像文件，需为RGB三通道图像 |
| input_image_base64 | string | 二选一 | None | 传入的图像文件的base64编码，需为RGB三通道图像 |
| dpi | int | 否 | 300 | 图像分辨率 |
| kb | int | 否 | 50 | 输出照片的KB值 |

**响应参数**：

| 参数名 | 类型 | 说明 |
|-------|------|------|
| status | bool | 状态码，true表示成功 |
| image_base64 | string | 设置KB大小之后的图像的base64编码 |
| error | string | 错误信息，仅当status为false时返回 |

### 7. 证件照裁切

**路径**：`/idphoto_crop`

**方法**：`POST`

**功能**：对已有的透明证件照进行裁切，调整人像位置和大小，并支持美颜功能

**请求参数**：

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|-------|------|------|--------|------|
| input_image | file | 二选一 | None | 传入的图像文件，需为RGBA四通道图像 |
| input_image_base64 | string | 二选一 | None | 传入的图像文件的base64编码，需为RGBA四通道图像 |
| height | int | 否 | 413 | 标准证件照高度 |
| width | int | 否 | 295 | 标准证件照宽度 |
| face_detect_model | string | 否 | mtcnn | 人脸检测模型，可选值：mtcnn、face_plusplus、retinaface-resnet50 |
| hd | bool | 否 | True | 是否生成高清证件照 |
| dpi | int | 否 | 300 | 图像分辨率 |
| head_measure_ratio | float | 否 | 0.2 | 面部面积与照片面积的比例 |
| head_height_ratio | float | 否 | 0.45 | 面部中心与照片顶部的高度比例 |
| top_distance_max | float | 否 | 0.12 | 头部与照片顶部距离的比例最大值 |
| top_distance_min | float | 否 | 0.10 | 头部与照片顶部距离的比例最小值 |
| whitening_strength | int | 否 | 0 | 美白强度，范围：0-100 |
| brightness_strength | float | 否 | 0 | 亮度调整强度，范围：-100-100 |
| contrast_strength | float | 否 | 0 | 对比度调整强度，范围：-100-100 |
| sharpen_strength | float | 否 | 0 | 锐化调整强度，范围：0-100 |
| saturation_strength | float | 否 | 0 | 饱和度调整强度，范围：-100-100 |

**响应参数**：

| 参数名 | 类型 | 说明 |
|-------|------|------|
| status | bool | 状态码，true表示成功 |
| image_base64_standard | string | 标准证件照的base64编码（PNG格式，透明背景） |
| image_base64_hd | string | 高清证件照的base64编码（PNG格式，透明背景），仅当hd为True时返回 |

### 8. 图片鉴黄检测

**路径**：`/nsfw_check`

**方法**：`POST`

**功能**：检测图片是否包含不适当内容（NSFW），建议在图片上传后、处理前调用

**请求参数**：

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|-------|------|------|--------|------|
| input_image | file | 二选一 | None | 传入的图像文件 |
| payload | string | 二选一 | None | 加密参数，解密后包含 input_image_base64 字段（图像文件的base64编码） |

注：`input_image_base64` 与 `input_image` 至少提供其一，否则返回 400。

**响应参数**：

| 参数名 | 类型 | 说明 |
|-------|------|------|
| status | bool | 状态码，true表示请求成功 |
| is_safe | bool | 图片是否安全 |
| score | float | NSFW综合得分（0-1，越高越不安全） |
| details | list | 检测到的不安全内容详情 |
| message | string | 检测结果描述 |

检测过程异常时返回 `status: false`、`is_safe: false`、`score: 1.0`，并在 `message` 中携带错误信息。

### 9. PDF转图片

**路径**：`/pdf2img`

**方法**：`POST`

**功能**：将PDF文件逐页渲染为PNG图片并返回

**请求参数**：

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|-------|------|------|--------|------|
| file | file | 是 | None | 传入的PDF文件，大小不超过20MB |
| payload | string | 是 | None | 加密参数，解密后可包含 dpi 字段 |
| dpi（payload内） | int | 否 | 150 | 渲染分辨率，范围72-300，超出将被截断 |

**响应参数**：

| 参数名 | 类型 | 说明 |
|-------|------|------|
| status | bool | 状态码，true表示成功 |
| page_count | int | PDF总页数 |
| images | list | 每页图片的base64编码列表（PNG格式），最多返回30页 |

注：PDF超过30页时仅渲染前30页，`page_count` 仍为总页数。

## 请求示例

### 使用cURL请求示例

#### 生成证件照

```bash
curl -X POST "http://127.0.0.1:8080/idphoto" \
-F "input_image=@demo/images/test0.jpg" \
-F "height=413" \
-F "width=295" \
-F "human_matting_model=modnet_photographic_portrait_matting" \
-F "face_detect_model=mtcnn" \
-F "hd=true" \
-F "dpi=300"
```

#### 添加背景色

```bash
curl -X POST "http://127.0.0.1:8080/add_background" \
-F "input_image=@test.png" \
-F "color=638cce" \
-F "kb=200" \
-F "render=0" \
-F "dpi=300"
```

### 使用Python请求示例

#### 生成证件照

```python
import requests

url = "http://127.0.0.1:8080/idphoto"
input_image_path = "demo/images/test0.jpg"

files = {"input_image": open(input_image_path, "rb")}
data = {
    "height": 413,
    "width": 295,
    "human_matting_model": "modnet_photographic_portrait_matting",
    "face_detect_model": "mtcnn",
    "hd": True,
    "dpi": 300,
}

response = requests.post(url, files=files, data=data).json()
print(response)
```

## 错误处理

所有接口返回的状态码为`false`时，表示请求失败。对于部分接口，会返回`error`字段，包含具体的错误信息。

## 注意事项

1. 所有图像参数都支持两种传入方式：文件上传和base64编码
2. 建议使用PNG格式处理透明图像，JPG格式处理非透明图像
3. 接口默认使用300DPI分辨率，可根据需要调整
4. 部分接口支持调整图像大小（KB），可根据实际需求设置
5. 人脸检测失败时，接口会返回`status: false`

## 技术栈

- 后端框架：FastAPI
- 图像处理：OpenCV、NumPy
- 人脸检测：MTCNN、Face++、RetinaFace
- 人像分割：MODNet、RMBG-1.4、BirefNet

## 版本信息

当前版本：1.0.0

## 联系方式

如有问题或建议，请通过GitHub Issues反馈。