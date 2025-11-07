# WeRead Bot 开发指导

## 目录

- [项目概述](#项目概述)
- [技术栈](#技术栈)
- [项目结构](#项目结构)
- [核心设计原则](#核心设计原则)
- [主要类结构](#主要类结构)
- [开发环境](#开发环境)
- [代码规范](#代码规范)
- [错误处理](#错误处理)
- [日志记录](#日志记录)
- [配置管理](#配置管理)
- [异步编程](#异步编程)
- [测试策略](#测试策略)
- [Git 工作流](#git-工作流)
- [部署指南](#部署指南)
- [功能扩展](#功能扩展)
- [质量标准](#质量标准)
- [文档维护](#文档维护)
- [常见问题](#常见问题)
- [安全指南](#安全指南)
- [性能优化](#性能优化)
- [配置生成器](#配置生成器)

## 项目概述

WeRead Bot 是一个功能完善的微信读书自动阅读机器人，使用 Python 3.9+ 开发，采用单一文件设计便于部署。支持多用户、异步编程、配置驱动和智能阅读管理。

## 技术栈

- **Python 3.9+**: 主要开发语言
- **异步编程**: 使用 `asyncio` 进行异步操作
- **配置管理**: YAML 配置文件 + 环境变量
- **HTTP 请求**: `requests` 库 + 自定义重试机制
- **定时任务**: `schedule` 库
- **通知系统**: 支持多种通知渠道
- **日志系统**: 支持轮转日志和多格式输出
- **前端技术**: HTML5 + Tailwind CSS + shadcn/ui（配置生成器）

## 项目结构

```
weread-bot/
├── weread-bot.py          # 主程序文件（单一文件设计）
├── config-generator.html  # 配置生成器（可视化界面）
├── config.yaml.example    # 配置文件模板
├── requirements.txt       # 依赖包列表
├── README.md             # 项目说明文档
├── CLAUDE.md            # 开发指导文档（本文件）
└── logs/                # 日志文件目录（运行时创建）
```

## 核心设计原则

1. **单一文件设计**: 所有代码集中在一个文件中，便于部署和使用
2. **模块化组织**: 使用类和函数进行逻辑分离，保持代码清晰
3. **配置驱动**: 通过 YAML 配置文件和环境变量控制行为
4. **异步优先**: 使用 async/await 处理 I/O 密集型操作
5. **防御性编程**: 全面的错误处理和日志记录

## 主要类结构

```python
# 配置管理
WeReadConfig              # 主配置类
ConfigManager            # 配置管理器

# 核心业务逻辑
WeReadApplication        # 应用程序管理器
WeReadSessionManager     # 会话管理器
SmartReadingManager      # 智能阅读管理器

# 辅助功能
HttpClient              # HTTP 客户端
NotificationService     # 通知服务
HumanBehaviorSimulator   # 人类行为模拟器

# 配置数据类
NetworkConfig, ReadingConfig, NotificationConfig
HackConfig, UserConfig, LoggingConfig, SmartRandomConfig
ScheduleConfig, DaemonConfig, NotificationChannel

# 工具类
CurlParser, RandomHelper, UserAgentRotator
```

## 开发环境

### 基本要求
- Python 3.9+
- 推荐使用虚拟环境

### 快速开始
```bash
# 创建并激活虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 安装开发依赖（可选）
pip install black flake8 mypy
```

## 代码规范

### 命名约定
- **类名**: `PascalCase` (如 `WeReadBot`)
- **函数名**: `snake_case` (如 `parse_curl_command`)
- **变量名**: `snake_case` (如 `reading_config`)
- **常量**: `UPPER_SNAKE_CASE` (如 `READ_URL`)

### 代码风格
- 使用 4 个空格缩进
- 最大行长度：120 字符
- 使用类型注解
- 编写完整的文档字符串

### 文档字符串示例
```python
def parse_curl_command(curl_command: str) -> Tuple[Dict[str, str], Dict[str, str], Dict[str, Any]]:
    """解析 CURL 命令，提取 headers、cookies 和请求数据。

    Args:
        curl_command: 完整的 CURL 命令字符串

    Returns:
        包含三个元素的元组：(headers, cookies, request_data)

    Raises:
        ValueError: 当 CURL 命令格式无效时
    """
```

## 错误处理

### 基本原则
1. **不要静默失败**: 所有异常都应该被记录
2. **提供有意义的错误信息**: 帮助用户和开发者理解问题
3. **优雅降级**: 当次要功能失败时，主要功能应继续工作
4. **资源清理**: 使用 `try/finally` 或 `with` 语句

### 异常处理模式
```python
try:
    response = await self.http_client.post_json(url, data, headers, cookies)
    return response
except requests.Timeout:
    logging.error(f"请求超时: {url}")
    raise  # 重新抛出异常，让调用者处理
except Exception as e:
    logging.error(f"请求失败: {e}")
    return None  # 返回默认值
```

## 日志记录

### 日志级别
- **DEBUG**: 详细调试信息，仅开发时使用
- **INFO**: 正常操作信息，用户关心的状态变化
- **WARNING**: 潜在问题，不影响功能
- **ERROR**: 错误情况，影响部分功能
- **CRITICAL**: 严重错误，程序无法继续

### 日志格式
```python
logging.info("✅ 用户配置加载成功: %s", user_name)
logging.warning("⚠️ 网络请求失败，正在重试: %s", error_msg)
logging.error("❌ 用户认证失败: %s", auth_error)
logging.debug("🔍 请求数据: book_id=%s, chapter_id=%s", book_id, chapter_id)
```

## 配置管理

### 配置优先级
环境变量 > YAML 配置文件 > 默认值

### 添加新配置项流程
1. 在相应的 dataclass 中添加字段
2. 在 `_load_config()` 方法中添加加载逻辑
3. 在环境变量处理中添加映射
4. 更新配置文件模板

```python
# 1. 添加配置项
@dataclass
class NetworkConfig:
    timeout: int = 30
    retry_times: int = 3
    connection_pool_size: int = 10  # 新增

# 2. 添加加载逻辑
config.network = NetworkConfig(
    timeout=int(self._get_config_value(...)),
    retry_times=int(self._get_config_value(...)),
    connection_pool_size=int(self._get_config_value(  # 新增
        config_data, "network.connection_pool_size",
        "CONNECTION_POOL_SIZE", "10"
    )),
)
```

## 异步编程

### 基本原则
- 所有 I/O 操作都应该是异步的
- 使用 `async/await` 语法
- 避免在异步函数中调用阻塞操作

```python
# 好的实践
async def fetch_data(self, url: str) -> dict:
    try:
        response = await self.http_client.post_json(url, data, headers, cookies)
        return response
    except Exception as e:
        logging.error(f"获取数据失败: {e}")
        return {}

# 避免阻塞操作
async def process_data(self):
    await asyncio.sleep(1)  # 非阻塞
    # 不要使用 time.sleep(1)  # 阻塞
```

## Git 工作流

### 分支策略
- **主分支**: `main` 保持稳定可发布状态
- **开发分支**: 在功能分支上开发

### 提交信息格式
```bash
git commit -m "feat: 添加新的通知渠道支持"
git commit -m "fix: 修复章节索引计算错误"
git commit -m "docs: 更新 README 使用说明"
git commit -m "refactor: 重构配置管理模块"
```

### 版本控制
遵循 `MAJOR.MINOR.PATCH` 语义化版本格式：
- **MAJOR**: 不兼容的 API 更改
- **MINOR**: 向后兼容的功能添加
- **PATCH**: 向后兼容的错误修复

## 测试策略

### 单元测试
由于采用单一文件设计，建议：
1. 提取关键函数进行独立测试
2. 使用 `unittest.mock` 模拟外部依赖
3. 测试配置解析逻辑
4. 测试工具类函数

### 集成测试
1. 测试完整的阅读流程
2. 测试多用户场景
3. 测试通知功能
4. 测试错误恢复机制

### 测试工具
```python
# 示例：测试配置解析
import unittest
from unittest.mock import patch, MagicMock

class TestConfigManager(unittest.TestCase):
    def setUp(self):
        self.config_manager = ConfigManager()

    @patch('builtins.open')
    def test_load_config_from_file(self, mock_open):
        # 测试配置文件加载
        pass

    def test_parse_curl_command(self):
        # 测试 CURL 命令解析
        pass
```

## 部署指南

### Docker 部署
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY weread-bot.py .
CMD ["python", "weread-bot.py"]
```

### 发布流程
1. 更新版本号 (`weread-bot.py:__version__`)
2. 更新 CHANGELOG.md
3. 创建 Git 标签
4. 构建 Docker 镜像（如适用）
5. 部署到目标环境

### 环境配置
- **开发环境**: 使用 `config.yaml.dev`
- **测试环境**: 使用环境变量覆盖配置
- **生产环境**: 使用 `config.yaml.prod` + 环境变量

## 功能扩展

### 添加新通知渠道
1. 在 `NotificationMethod` 枚举中添加新渠道
2. 在 `NotificationService._send_notification_to_channel()` 中添加处理逻辑
3. 在 `ConfigManager._create_channels_from_env_vars()` 中添加环境变量支持
4. 更新配置文件模板

### 添加新阅读模式
1. 在 `ReadingMode` 枚举中添加新模式
2. 在 `SmartReadingManager.get_next_reading_position()` 中添加逻辑
3. 更新配置文档

### 添加 Hack 配置项
当遇到兼容性问题时，可添加 Hack 配置项：

1. 在 `HackConfig` 数据类中添加新字段
2. 在 `ConfigManager._load_config()` 方法中添加加载逻辑
3. 在相应的业务逻辑中使用配置值
4. 更新配置文件模板和文档

**示例**: `cookie_refresh_ql` 配置项用于解决 Cookie 刷新时的兼容性问题。

## 质量标准

### 代码质量
- **工程原则**: 遵循 SOLID、DRY、关注点分离
- **性能意识**: 注意算法复杂度、内存使用、IO优化
- **测试思维**: 设计可测试的代码，考虑边界条件和错误处理

### 安全要求
- **数据安全**: 不在日志中记录敏感信息，保护配置文件
- **运行安全**: 验证外部输入，遵循最小权限原则
- **隐私保护**: 妥善处理用户数据，避免记录敏感信息

## 文档维护

### 同步更新原则
每次代码更新后必须检查并同步更新：
- **README.md** - 用户文档
- **CLAUDE.md** - 开发指导
- **config.yaml.example** - 配置模板
- **代码注释** - 重要函数和类的文档字符串

### 更新检查清单

#### 功能新增
- [ ] README.md 中添加新功能说明
- [ ] 更新配置文件模板（如涉及新配置项）
- [ ] 添加相关代码注释和文档字符串

#### 配置变更
- [ ] 更新 config.yaml.example
- [ ] 在 README.md 中说明配置变更
- [ ] 在 CLAUDE.md 中更新配置管理部分

#### Bug 修复
- [ ] 更新相关文档说明
- [ ] 如影响用户使用，在 README.md 中添加说明

### 文档质量要求
- **README.md**: 清晰的项目概述、完整的安装使用指南、准确的配置说明
- **CLAUDE.md**: 详细的技术架构、完整的开发指南、代码规范和最佳实践
- **代码注释**: 公开函数和类必须有完整文档字符串，复杂逻辑需要详细注释

## 常见问题

### 调试技巧
1. 使用 `--verbose` 参数启用详细日志
2. 检查配置文件格式和内容
3. 手动测试网络连接和 API
4. 使用 Python 调试器进行逐步调试

### 性能问题
1. 检查日志中的性能指标
2. 监控内存使用情况
3. 检查网络响应时间
4. 验证异步操作的正确性

### 配置问题
1. 使用 YAML 验证工具检查配置文件格式
2. 确认环境变量正确设置
3. 检查文件访问权限
4. 确认依赖包版本兼容

## 安全指南

### 数据安全
- 不在日志中记录敏感信息（如密码、Token）
- 保护配置文件不被未授权访问
- 使用 HTTPS 和安全的认证方式
- 定期更新依赖包，修复安全漏洞

### 运行安全
- 验证所有外部输入
- 遵循最小权限原则
- 避免异常暴露系统信息
- 使用安全的临时文件处理

### 隐私保护
- 妥善处理用户个人信息
- 避免记录敏感的用户数据
- 谨慎处理通知中的个人信息
- 遵循相关的隐私法规

## 性能优化

### 网络优化
1. **连接池**: 复用 HTTP 连接
2. **超时设置**: 设置合理的超时时间
3. **重试机制**: 使用指数退避重试
4. **速率限制**: 避免过于频繁的请求

### 内存优化
1. **资源释放**: 及时关闭文件和网络连接
2. **数据结构**: 选择合适的数据结构
3. **缓存策略**: 合理使用缓存避免重复计算

### 异步优化
1. **并发控制**: 使用 `asyncio.Semaphore` 限制并发
2. **超时处理**: 使用 `asyncio.wait_for()` 设置超时
3. **错误处理**: 妥善处理异步异常

## 配置生成器

`config-generator.html` 提供可视化配置界面，基于以下技术栈：
- **HTML5**: 语义化标签和现代 Web 特性
- **Tailwind CSS**: 实用优先的 CSS 框架
- **shadcn/ui**: 高质量 UI 组件设计
- **JavaScript ES6+**: 现代 JavaScript 特性
- **js-yaml**: YAML 解析和生成库
- **Lucide Icons**: 现代化图标库

### 使用方式
1. 在浏览器中打开 `config-generator.html`
2. 填写各项配置参数
3. 生成 YAML 配置文件
4. 复制配置内容到 `config.yaml`

---
