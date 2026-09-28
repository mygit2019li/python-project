"""
NSFW 图片检测模块
使用 NudeNet 进行图片鉴黄
"""
from nudenet import NudeDetector
import numpy as np
import cv2
import tempfile
import os


class NSFWChecker:
    """图片鉴黄检测器"""
    
    # 定义不安全的标签类型及其严重程度权重
    UNSAFE_LABELS = {
        'FEMALE_BREAST_EXPOSED': 1.0,
        'FEMALE_GENITALIA_EXPOSED': 1.0,
        'MALE_GENITALIA_EXPOSED': 1.0,
        'BUTTOCKS_EXPOSED': 0.8,
        'ANUS_EXPOSED': 1.0,
        'FEMALE_BREAST_COVERED': 0.3,
        'BELLY_EXPOSED': 0.1,
    }
    
    # 安全阈值：综合得分低于此值认为安全
    SAFE_THRESHOLD = 0.5
    
    def __init__(self):
        """初始化检测器"""
        self.detector = NudeDetector()
    
    def check_image_from_numpy(self, img_array: np.ndarray) -> dict:
        """
        检测 numpy 数组格式的图片
        
        Args:
            img_array: numpy 数组格式的图片 (RGB 或 BGR)
            
        Returns:
            dict: {
                'is_safe': bool,
                'score': float (0-1, 越高越不安全),
                'details': list of detected items,
                'message': str
            }
        """
        # NudeNet 需要文件路径，所以我们需要临时保存图片
        temp_file = None
        try:
            # 确保图片是 BGR 格式（OpenCV 默认）
            if len(img_array.shape) == 3 and img_array.shape[2] == 3:
                # 假设输入是 RGB，转换为 BGR
                img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            else:
                img_bgr = img_array
            
            # 创建临时文件
            temp_file = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
            temp_path = temp_file.name
            temp_file.close()
            
            # 保存图片到临时文件
            cv2.imwrite(temp_path, img_bgr)
            
            # 调用检测器
            results = self.detector.detect(temp_path)
            
            return self._analyze_results(results)
            
        finally:
            # 清理临时文件
            if temp_file and os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def check_image_from_bytes(self, image_bytes: bytes) -> dict:
        """
        检测字节格式的图片
        
        Args:
            image_bytes: 图片的字节数据
            
        Returns:
            dict: 检测结果
        """
        # 将字节转换为 numpy 数组
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            return {
                'is_safe': False,
                'score': 1.0,
                'details': [],
                'message': '无法解析图片'
            }
        
        return self.check_image_from_numpy(img)
    
    def check_image_from_path(self, image_path: str) -> dict:
        """
        检测文件路径的图片
        
        Args:
            image_path: 图片文件路径
            
        Returns:
            dict: 检测结果
        """
        if not os.path.exists(image_path):
            return {
                'is_safe': False,
                'score': 1.0,
                'details': [],
                'message': '图片文件不存在'
            }
        
        results = self.detector.detect(image_path)
        return self._analyze_results(results)
    
    def _analyze_results(self, results: list) -> dict:
        """
        分析检测结果
        
        Args:
            results: NudeNet 检测结果列表
            
        Returns:
            dict: 分析后的结果
        """
        if not results:
            return {
                'is_safe': True,
                'score': 0.0,
                'details': [],
                'message': '图片安全'
            }
        
        # 筛选不安全的检测结果
        unsafe_detections = []
        max_score = 0.0
        
        for detection in results:
            label = detection.get('class', '')
            confidence = detection.get('score', 0.0)
            
            if label in self.UNSAFE_LABELS:
                weight = self.UNSAFE_LABELS[label]
                weighted_score = confidence * weight
                
                unsafe_detections.append({
                    'label': label,
                    'confidence': round(confidence, 3),
                    'weighted_score': round(weighted_score, 3)
                })
                
                if weighted_score > max_score:
                    max_score = weighted_score
        
        # 计算综合得分
        if unsafe_detections:
            # 使用最高加权得分作为综合得分
            final_score = min(max_score, 1.0)
        else:
            final_score = 0.0
        
        is_safe = final_score < self.SAFE_THRESHOLD
        
        if is_safe:
            message = '图片安全'
        else:
            message = '检测到不适当内容'
        
        return {
            'is_safe': is_safe,
            'score': round(final_score, 3),
            'details': unsafe_detections,
            'message': message
        }


# 全局检测器实例（延迟初始化）
_nsfw_checker = None


def get_nsfw_checker() -> NSFWChecker:
    """获取全局 NSFW 检测器实例"""
    global _nsfw_checker
    if _nsfw_checker is None:
        _nsfw_checker = NSFWChecker()
    return _nsfw_checker
