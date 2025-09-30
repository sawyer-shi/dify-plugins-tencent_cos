import time
import os
from datetime import datetime
from collections.abc import Generator
from typing import Any, Dict

from qcloud_cos import CosConfig, CosS3Client
from qcloud_cos.cos_exception import CosServiceError
from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from dify_plugin.file.file import File
from .utils import get_file_type, get_file_extension

class UploadFileTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        try:
            # 从runtime credentials获取认证信息
            credentials = {
                'region': self.runtime.credentials.get('region'),
                'bucket': self.runtime.credentials.get('bucket'),
                'secret_id': self.runtime.credentials.get('secret_id'),
                'secret_key': self.runtime.credentials.get('secret_key')
            }
            
            # 验证工具参数中的认证信息
            self._validate_credentials(credentials)
            
            # 执行文件上传操作
            result = self._upload_file(tool_parameters, credentials)
            
            yield self.create_json_message(result)
            
            # 在text中输出成功信息，包含文件类型、大小（M单位）和访问链接
            file = tool_parameters.get('file')
            file_size = 0
            file_type = 'unknown'
            
            # 尝试获取文件大小
            if isinstance(file, File) and hasattr(file, 'blob'):
                file_size = len(file.blob)
            elif hasattr(file, 'read'):
                # 保存当前文件指针位置
                if hasattr(file, 'tell'):
                    current_pos = file.tell()
                else:
                    current_pos = None
                
                # 读取文件内容获取大小
                content = file.read()
                file_size = len(content)
                
                # 重置文件指针
                if hasattr(file, 'seek') and current_pos is not None:
                    file.seek(current_pos)
            elif isinstance(file, (str, bytes, os.PathLike)) and os.path.exists(file):
                file_size = os.path.getsize(file)
                
            # 尝试获取文件类型
            file_type = 'unknown'
            # 尝试获取文件类型
            file_type = get_file_type(file)
            
            # 转换文件大小为MB
            file_size_mb = file_size / (1024 * 1024) if file_size > 0 else 0
            
            # 使用单独的字符串格式化 - 英文消息
            success_message = "File uploaded successfully!\n"
            success_message += f"Filename: {result['filename']}\n"
            success_message += f"File type: {file_type}\n"
            success_message += f"File size: {file_size_mb:.2f} MB\n"
            success_message += f"Access URL: {result['file_url']}\n"
            success_message += f"Object key: {result['object_key']}"
            yield self.create_text_message(success_message)
        except Exception as e:
            # 在text中输出失败信息 - 英文消息
            yield self.create_text_message(f"Failed to upload file: {str(e)}")
            # 同时抛出异常以保持原有行为
            raise ValueError(f"Failed to upload file: {str(e)}")
    
    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        # 验证必填字段是否存在
        required_fields = ['region', 'bucket', 'secret_id', 'secret_key']
        for field in required_fields:
            if field not in credentials or not credentials[field]:
                raise ValueError(f"Missing required credential: {field}")
    
    def _upload_file(self, parameters: dict[str, Any], credentials: dict[str, Any]) -> dict:
        try:
            # 获取文件对象、目录和其他参数
            file = parameters.get('file')
            directory = parameters.get('directory')
            directory_mode = parameters.get('directory_mode', 'no_subdirectory')
            filename = parameters.get('filename')
            filename_mode = parameters.get('filename_mode', 'filename')
            
            # 验证必填参数
            if not file:
                raise ValueError("Missing required parameter: file")
            
            if not directory:
                raise ValueError("Missing required parameter: directory")
            
            # 对directory进行前后去空格处理
            directory = directory.strip()
            # 验证directory规则：禁止以空格、/或\开头
            if directory.startswith(' ') or directory.startswith('/') or directory.startswith('\\'):
                raise ValueError("Directory cannot start with space, / or \\ ")
            
            # 如果用户指定了filename，对其进行前后去空格处理
            if filename:
                filename = filename.strip()
                # 验证filename规则：禁止以空格、/或\开头
                if filename.startswith(' ') or filename.startswith('/') or filename.startswith('\\'):
                    raise ValueError("Filename cannot start with space, / or \\ ")
            
            # 验证认证参数
            required_auth_fields = ['region', 'bucket', 'secret_id', 'secret_key']
            for field in required_auth_fields:
                if field not in credentials or not credentials[field]:
                    raise ValueError(f"Missing required authentication parameter: {field}")
            
            # 生成文件名
            source_file_name = "unknown"
            if not filename:
                # 如果用户没有指定文件名，使用上传文件的原始文件名
                base_name = "upload"
                extension = ".dat"  # 默认扩展名
                
                # 尝试从文件对象获取原始文件名和扩展名 - 加强版
                # 1. 处理dify_plugin的File对象
                if hasattr(file, 'name') and file.name:
                    original_filename = file.name
                    source_file_name = original_filename
                    file_base_name, file_extension = os.path.splitext(original_filename)
                    if file_extension:
                        extension = file_extension
                        base_name = file_base_name
                
                # 2. 尝试从file.filename获取（常见于某些Web框架）
                elif hasattr(file, 'filename') and file.filename:
                    original_filename = file.filename
                    source_file_name = original_filename
                    file_base_name, file_extension = os.path.splitext(original_filename)
                    if file_extension:
                        extension = file_extension
                        base_name = file_base_name
                
                # 3. 尝试从文件内容类型推断扩展名
                if hasattr(file, 'content_type') and file.content_type:
                    extension = get_file_extension(file)
                
                # 4. 额外的检查：确保扩展名是小写的，并且包含点号
                if extension and not extension.startswith('.'):
                    extension = '.' + extension
                extension = extension.lower()
                
                # 根据filename_mode处理文件名
                if filename_mode == 'filename_timestamp':
                    # 使用年月日时分秒毫秒格式的时间戳
                    timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')[:-3]  # 去掉最后三位得到毫秒
                    filename = f"{base_name}_{timestamp}{extension}"
                else:
                    # 使用原始文件名作为默认文件名
                    filename = f"{base_name}{extension}"
            else:
                # 如果用户指定了文件名，将其作为源文件名
                source_file_name = filename
                # 获取用户指定文件名的基本名称和扩展名
                base_name, extension = os.path.splitext(filename)
                
                # 如果用户指定的文件名没有扩展名，尝试从原始文件获取扩展名
                if not extension:
                    # 尝试从文件对象获取原始文件的扩展名
                    original_extension = ""  
                    # 1. 处理dify_plugin的File对象
                    if hasattr(file, 'name') and file.name:
                        _, original_extension = os.path.splitext(file.name)
                    # 2. 尝试从file.filename获取
                    elif hasattr(file, 'filename') and file.filename:
                        _, original_extension = os.path.splitext(file.filename)
                    # 3. 如果找到了原始扩展名，使用它
                    if original_extension:
                        extension = original_extension
                    # 4. 确保扩展名是小写的，并且包含点号
                    if extension and not extension.startswith('.'):
                        extension = '.' + extension
                    extension = extension.lower()
                        
                # 根据filename_mode处理文件名
                if filename_mode == 'filename_timestamp':
                    # 使用年月日时分秒毫秒格式的时间戳
                    timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')[:-3]  # 去掉最后三位得到毫秒
                    filename = f"{base_name}_{timestamp}{extension}" 
                elif extension:
                    # 确保文件名包含扩展名
                    filename = f"{base_name}{extension}"
            
            # 根据目录模式生成完整的文件路径
            object_key = self._generate_object_key(directory, directory_mode, filename)
            
            # 创建腾讯云COS客户端
            config = CosConfig(
                Region=credentials['region'],
                SecretId=credentials['secret_id'],
                SecretKey=credentials['secret_key']
            )
            client = CosS3Client(config)
            
            # 上传文件 - 统一处理文件对象或文件路径
            try:
                # 处理dify_plugin的File对象
                if isinstance(file, File):
                    # 获取文件内容
                    file_content = file.blob
                    # 获取文件内容类型
                    content_type = getattr(file, 'content_type', 'application/octet-stream')
                    # 上传文件内容
                    response = client.put_object(
                        Bucket=credentials['bucket'],
                        Body=file_content,
                        Key=object_key,
                        ContentType=content_type
                    )
                # 尝试作为普通文件对象处理
                elif hasattr(file, 'read'):
                    # 重置文件指针到开头
                    if hasattr(file, 'seek'):
                        file.seek(0)
                    # 获取文件内容类型
                    content_type = getattr(file, 'content_type', 'application/octet-stream')
                    # 上传文件流
                    response = client.put_object(
                        Bucket=credentials['bucket'],
                        Body=file,
                        Key=object_key,
                        ContentType=content_type
                    )
                # 尝试作为文件路径处理
                elif isinstance(file, (str, bytes, os.PathLike)) and os.path.exists(file):
                    # 上传本地文件
                    response = client.upload_file(
                        Bucket=credentials['bucket'],
                        LocalFilePath=str(file),
                        Key=object_key
                    )
                else:
                    raise ValueError("Unsupported file type")
                
                # 构建文件URL
                # 腾讯云COS的URL格式: https://{bucket}.cos.{region}.myqcloud.com/{object_key}
                file_url = f"https://{credentials['bucket']}.cos.{credentials['region']}.myqcloud.com/{object_key}"
                
                # 返回结果字典
                return {
                    'filename': filename,
                    'source_filename': source_file_name,
                    'file_url': file_url,
                    'object_key': object_key,
                    'bucket': credentials['bucket'],
                    'region': credentials['region']
                }
            except CosServiceError as e:
                error_message = f"COS service error: {str(e)}"
                raise ValueError(error_message)
            
        except Exception as e:
            error_message = f"Failed to upload file: {str(e)}"
            raise ValueError(error_message)
    
    def _generate_object_key(self, directory: str, directory_mode: str, filename: str) -> str:
        """
        根据目录模式生成完整的对象键
        
        Args:
            directory: 目录名称
            directory_mode: 目录模式
            filename: 文件名
            
        Returns:
            完整的对象键
        """
        # 对directory进行前后去空格处理
        directory = directory.strip()
        
        # 根据目录模式生成路径
        if directory_mode == 'yyyy_mm_dd_hierarchy':
            # 年/月/日 层级目录
            date_path = datetime.now().strftime('%Y/%m/%d')
            object_key = f"{directory}/{date_path}/{filename}"
        elif directory_mode == 'yyyy_mm_dd_combined':
            # 年月日 一体目录
            date_path = datetime.now().strftime('%Y%m%d')
            object_key = f"{directory}/{date_path}/{filename}"
        else:
            # 默认：无子目录
            object_key = f"{directory}/{filename}"
        
        return object_key