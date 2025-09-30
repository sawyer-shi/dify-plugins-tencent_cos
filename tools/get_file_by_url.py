import os
import re
from urllib.parse import urlparse, unquote
from typing import Any, Dict, Optional, Generator
from dify_plugin.entities.tool import ToolInvokeMessage

from qcloud_cos import CosConfig, CosS3Client
from qcloud_cos.cos_exception import CosServiceError

from dify_plugin.interfaces.tool import Tool, ToolProvider
from .utils import get_extension_from_content_type


class GetFileByUrlTool(Tool):
    def _invoke(self, tool_parameters: Dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        try:
            # 验证工具参数中的认证信息
            self._validate_credentials()
            
            # 执行文件获取操作
            result = self._get_file_by_url(tool_parameters)
            
            # 提取文件扩展名
            _, extension = os.path.splitext(result['filename'])
            if not extension:
                # 如果没有扩展名，根据content_type尝试推断
                if result['content_type'] == 'image/png':
                    extension = '.png'
                elif result['content_type'] == 'image/jpeg':
                    extension = '.jpg'
                elif result['content_type'] == 'image/gif':
                    extension = '.gif'
                else:
                    extension = ''
                
                # 如果推断出了扩展名，添加到文件名中
                if extension:
                    result['filename'] = result['filename'] + extension
            
            # 构建文件元数据，确保包含支持图片显示的所有必要属性
            file_metadata = {
                'filename': result['filename'],
                'content_type': result['content_type'],
                'size': result['file_size'],
                'mime_type': result['content_type'],
                'extension': extension
            }
            
            # 如果是图片类型，添加特定标志以确保在Dify页面正常显示
            if result['content_type'].startswith('image/'):
                file_metadata['is_image'] = True
                file_metadata['display_as_image'] = True
                file_metadata['type'] = 'image'
            
            # 使用create_blob_message返回文件内容
            yield self.create_blob_message(
                result['file_content'],
                file_metadata
            )
            
            # 在text中输出成功消息、文件大小和类型，文件大小以MB为单位 - 英文消息
            file_size_mb = result['file_size'] / (1024 * 1024) if result['file_size'] > 0 else 0
            success_message = f"File downloaded successfully: {result['filename']}\nFile size: {file_size_mb:.2f} MB\nFile type: {result['content_type']}"
            yield self.create_text_message(success_message)
        except Exception as e:
            # 失败时在text中输出错误信息 - 英文消息
            yield self.create_text_message(f"Failed to download file: {str(e)}")
    
    def _validate_credentials(self) -> None:
        # 验证必填字段是否存在
        required_fields = ['region', 'bucket', 'secret_id', 'secret_key']
        for field in required_fields:
            if not self.runtime.credentials.get(field):
                raise ValueError(f"Missing required credential: {field}")
    
    def _get_file_by_url(self, parameters: dict[str, Any]) -> dict:
        try:
            # 获取文件URL
            file_url = parameters.get('file_url')
            
            if not file_url:
                raise ValueError("Missing required parameter: file_url")
            
            # 获取认证参数
            credentials = {
                'region': self.runtime.credentials.get('region'),
                'bucket': self.runtime.credentials.get('bucket'),
                'secret_id': self.runtime.credentials.get('secret_id'),
                'secret_key': self.runtime.credentials.get('secret_key')
            }
            
            # 解析URL获取bucket、region和object_key
            bucket, region, object_key = self._parse_cos_url(file_url)
            
            # 如果URL中的bucket与凭证中的bucket不一致，使用URL中的bucket
            if bucket and bucket != credentials['bucket']:
                bucket_name = bucket
            else:
                bucket_name = credentials['bucket']
            
            # 如果URL中的region与凭证中的region不一致，使用URL中的region
            if region and region != credentials['region']:
                region_name = region
            else:
                region_name = credentials['region']
            
            # 创建腾讯云COS客户端
            config = CosConfig(
                Region=region_name,
                SecretId=credentials['secret_id'],
                SecretKey=credentials['secret_key']
            )
            client = CosS3Client(config)
            
            # 获取文件内容
            response = client.get_object(
                Bucket=bucket_name,
                Key=object_key
            )
            
            # 读取文件内容
            file_content = response['Body'].get_raw_stream().read()
            
            # 获取文件大小
            file_size = len(file_content)
            
            # 获取文件类型
            content_type = response.get('ContentType', 'application/octet-stream')
            
            # 获取文件名
            filename = os.path.basename(object_key)
            
            # 返回结果字典
            return {
                'file_content': file_content,
                'filename': filename,
                'content_type': content_type,
                'file_size': file_size
            }
        except CosServiceError as e:
            error_message = f"COS service error: {str(e)}"
            raise ValueError(error_message)
        except Exception as e:
            error_message = f"Failed to retrieve file: {str(e)}"
            raise ValueError(error_message)
    
    def _parse_cos_url(self, url: str) -> tuple:
        """
        解析COS URL，支持标准格式和自定义域名格式
        标准格式: https://bucket.cos.region.myqcloud.com/object_key
        自定义域名格式: https://custom-domain/object_key
        """
        parsed_url = urlparse(url)
        
        # 处理URL编码
        object_key = unquote(parsed_url.path.lstrip('/'))
        
        # 如果是标准COS URL格式 (bucket.cos.region.myqcloud.com)
        if parsed_url.hostname and parsed_url.hostname.endswith('.myqcloud.com'):
            # 提取bucket和region
            hostname_parts = parsed_url.hostname.split('.')
            if len(hostname_parts) >= 4 and hostname_parts[1] == 'cos':
                bucket_name = hostname_parts[0]
                region_name = hostname_parts[2]
                return (bucket_name, region_name, object_key)
        
        # 对于自定义域名格式，需要额外的region或bucket验证
        # 此处仅返回None作为bucket和region，由调用方处理
        return None, None, object_key