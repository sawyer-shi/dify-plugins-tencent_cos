from typing import Any, Dict
from qcloud_cos import CosConfig, CosS3Client
from qcloud_cos.cos_exception import CosServiceError

from dify_plugin.interfaces.tool import ToolProvider
from dify_plugin.errors.tool import ToolProviderCredentialValidationError


class TencentCosProvider(ToolProvider):
    def _validate_credentials(self, credentials: Dict[str, Any]) -> None:
        try:
            # 1. 检查必要凭据是否存在
            required_fields = ['secret_id', 'secret_key', 'region', 'bucket']
            for field in required_fields:
                if not credentials.get(field):
                    raise ToolProviderCredentialValidationError(f"{field} 不能为空")

            # 2. 验证directory和filename格式
            if 'directory' in credentials and credentials['directory']:
                dir_value = credentials['directory']
                if dir_value.startswith((' ', '/', '\\')):
                    raise ToolProviderCredentialValidationError("directory不能以空格、/或\\开头")

            if 'filename' in credentials and credentials['filename']:
                file_value = credentials['filename']
                if file_value.startswith((' ', '/', '\\')):
                    raise ToolProviderCredentialValidationError("filename不能以空格、/或\\开头")

            # 3. 创建腾讯云COS客户端
            config = CosConfig(
                Region=credentials['region'],
                SecretId=credentials['secret_id'],
                SecretKey=credentials['secret_key']
            )
            client = CosS3Client(config)

            # 4. 进行远程校验，获取Bucket信息
            try:
                response = client.head_bucket(Bucket=credentials['bucket'])
            except CosServiceError as e:
                if e.get_status_code() == 403:
                    raise ToolProviderCredentialValidationError("无效的SecretId或SecretKey")
                elif e.get_status_code() == 404:
                    raise ToolProviderCredentialValidationError("Bucket不存在")
                else:
                    raise ToolProviderCredentialValidationError(f"COS验证失败: {str(e)}")

        except CosServiceError as e:
            error_code = e.get_status_code()
            if error_code == 403:
                raise ToolProviderCredentialValidationError("无效的SecretId或SecretKey")
            elif error_code == 404:
                raise ToolProviderCredentialValidationError("Bucket不存在")
            else:
                raise ToolProviderCredentialValidationError(f"COS验证失败: {str(e)}")
        except Exception as e:
            raise ToolProviderCredentialValidationError(f"凭据验证发生未知错误: {str(e)}")
