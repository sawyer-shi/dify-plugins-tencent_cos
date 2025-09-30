# 文件类型与扩展名映射
CONTENT_TYPE_MAPPING = {
    # 图片类型
    'image/jpeg': 'jpg',
    'image/jpg': 'jpg',
    'image/png': 'png',
    'image/gif': 'gif',
    'image/webp': 'webp',
    'image/bmp': 'bmp',
    'image/tiff': 'tiff',
    'image/svg+xml': 'svg',
    'image/x-icon': 'ico',
    
    # 文档类型
    'application/pdf': 'pdf',
    'application/msword': 'doc',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
    'application/vnd.ms-excel': 'xls',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'xlsx',
    'application/vnd.ms-powerpoint': 'ppt',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'pptx',
    
    # 文本类型
    'text/plain': 'txt',
    'text/html': 'html',
    'text/css': 'css',
    'text/javascript': 'js',
    'application/json': 'json',
    'application/xml': 'xml',
    'text/xml': 'xml',
    
    # 压缩文件
    'application/zip': 'zip',
    'application/x-rar-compressed': 'rar',
    'application/x-tar': 'tar',
    'application/x-gzip': 'gz',
    'application/x-7z-compressed': '7z',
    
    # 音频类型
    'audio/mpeg': 'mp3',
    'audio/wav': 'wav',
    'audio/ogg': 'ogg',
    'audio/x-wav': 'wav',
    'audio/aac': 'aac',
    'audio/flac': 'flac',
    
    # 视频类型
    'video/mp4': 'mp4',
    'video/mpeg': 'mpeg',
    'video/quicktime': 'mov',
    'video/x-msvideo': 'avi',
    'video/x-ms-wmv': 'wmv',
    'video/webm': 'webm',
    'video/x-flv': 'flv',
    
    # 其他类型
    'application/octet-stream': 'bin',
    'application/x-shockwave-flash': 'swf',
    'application/x-www-form-urlencoded': 'txt',
}

def get_file_type(file):
    """
    根据文件对象或文件名获取文件类型
    
    Args:
        file: 文件对象或文件名
        
    Returns:
        str: 文件类型
    """
    # 尝试从文件对象获取内容类型
    if hasattr(file, 'content_type') and file.content_type:
        content_type = file.content_type.lower()
        # 查找主类型（如image/jpeg中的image）
        main_type = content_type.split('/')[0]
        return main_type
    
    # 尝试从文件名获取文件类型
    if hasattr(file, 'name') and file.name:
        filename = file.name.lower()
        if filename.endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.svg', '.ico')):
            return 'image'
        elif filename.endswith(('.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx')):
            return 'document'
        elif filename.endswith(('.txt', '.html', '.css', '.js', '.json', '.xml')):
            return 'text'
        elif filename.endswith(('.zip', '.rar', '.tar', '.gz', '.7z')):
            return 'archive'
        elif filename.endswith(('.mp3', '.wav', '.ogg', '.aac', '.flac')):
            return 'audio'
        elif filename.endswith(('.mp4', '.mpeg', '.mov', '.avi', '.wmv', '.webm', '.flv')):
            return 'video'
    
    # 默认返回未知类型
    return 'unknown'

def get_file_extension(file):
    """
    根据文件对象或文件名获取文件扩展名
    
    Args:
        file: 文件对象或文件名
        
    Returns:
        str: 文件扩展名（包含点号，如.jpg）
    """
    # 尝试从文件对象获取内容类型
    if hasattr(file, 'content_type') and file.content_type:
        content_type = file.content_type.lower()
        # 查找映射的扩展名
        if content_type in CONTENT_TYPE_MAPPING:
            extension = CONTENT_TYPE_MAPPING[content_type]
            return f'.{extension}'
    
    # 尝试从文件名获取扩展名
    if hasattr(file, 'name') and file.name:
        filename = file.name
        # 使用os.path.splitext获取扩展名
        import os
        _, extension = os.path.splitext(filename)
        if extension:
            return extension.lower()
    
    # 尝试从file.filename获取（常见于某些Web框架）
    if hasattr(file, 'filename') and file.filename:
        filename = file.filename
        # 使用os.path.splitext获取扩展名
        import os
        _, extension = os.path.splitext(filename)
        if extension:
            return extension.lower()
    
    # 默认返回空字符串
    return ''