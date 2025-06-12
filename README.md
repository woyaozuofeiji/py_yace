# Python YACE (Yet Another Concurrent Engine)

一个功能强大的Python并发压测工具，支持HTTP/HTTPS请求、代理、IP伪造等高级功能。

## 特性

- 支持GET/POST请求
- 支持单URL和多URL测试
  - 可以指定单个URL
  - 可以从文件加载多个URL
  - 支持随机URL测试
- 自定义并发线程数和请求数量
- 详细的性能指标统计
- 美观的结果展示（使用rich库）
- IP伪造（X-Forwarded-For和X-Real-IP）
  - 支持随机生成IP
  - 支持从文件加载IP列表
- 请求头伪造
  - 随机User-Agent
  - 随机Referer
  - 支持自定义User-Agent和Referer列表
- 代理支持
  - HTTP和SOCKS5代理
  - 代理列表文件配置
  - 随机切换代理
  - 代理超时设置
  - 代理错误统计
- SSL证书处理
  - 可选择忽略SSL证书验证
  - SSL错误独立统计
- 性能控制
  - 请求速率限制
  - 超时控制
    - 普通请求：30秒
    - 代理请求：3秒

## 安装

1. 克隆仓库：
```bash
git clone https://github.com/yourusername/py_yace.git
cd py_yace
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

## 使用方法

### 基本用法

```bash
# 测试单个URL
python load_tester.py http://example.com

# 使用URL列表文件
python load_tester.py --url-file urls.txt

# 同时指定URL和URL文件
python load_tester.py http://example.com --url-file urls.txt

# 指定请求数和并发数
python load_tester.py http://example.com -n 1000 -t 20

# POST请求
python load_tester.py http://example.com -m POST --data '{"key": "value"}'
```

### URL列表文件

urls.txt 格式：
```
# 每行一个URL
https://www.example.com
http://api.example.com/test
https://example.com/api/v1/data
# 支持注释，以#开头的行会被忽略
# 空行也会被忽略
```

### IP伪造

```bash
# 使用随机生成的IP
python load_tester.py http://example.com --fake-ip

# 使用自定义IP列表
python load_tester.py http://example.com --fake-ip --fake-ip-file fake_ips.txt
```

fake_ips.txt 格式：
```
# 每行一个IP地址
1.2.3.4
5.6.7.8
# 支持注释，以#开头的行会被忽略
10.20.30.40
```

### 自定义请求头

```bash
# 使用自定义User-Agent列表
python load_tester.py http://example.com --user-agents user_agents.txt

# 使用自定义Referer列表
python load_tester.py http://example.com --referers referers.txt

# 添加自定义请求头
python load_tester.py http://example.com --headers '{"Custom-Header": "Value"}'
```

### 代理支持

```bash
# 使用HTTP代理
python load_tester.py http://example.com --http-proxies http_proxies.txt

# 使用SOCKS5代理
python load_tester.py http://example.com --socks5-proxies socks5_proxies.txt

# 指定代理类型
python load_tester.py http://example.com --http-proxies http_proxies.txt --proxy-type http
```

代理列表文件格式：
```
# HTTP代理格式：ip:port 或 user:pass@ip:port
127.0.0.1:8080
user:pass@proxy.example.com:8080

# SOCKS5代理格式：ip:port 或 user:pass@ip:port
127.0.0.1:1080
user:pass@socks.example.com:1080
```

### SSL设置

```bash
# 禁用SSL证书验证
python load_tester.py https://example.com --no-verify-ssl
```

### 性能控制

```bash
# 设置请求超时
python load_tester.py http://example.com --timeout 60

# 设置代理超时
python load_tester.py http://example.com --proxy-timeout 5

# 限制请求速率（每秒每线程的请求数）
python load_tester.py http://example.com --rate-limit 10
```

## 完整参数列表

```
参数:
  url                   测试目标URL（可选，如果提供--url-file）
  --url-file           包含多个URL的文件路径（每行一个URL）
  -n, --num-requests    总请求数 (默认: 100)
  -t, --num-threads     并发线程数 (默认: 10)
  -m, --method         HTTP请求方法 (GET/POST, 默认: GET)
  --headers            HTTP请求头 (JSON格式)
  --data              POST请求数据 (JSON格式)
  --timeout           请求超时时间(秒) (默认: 30)
  --proxy-timeout     代理请求超时时间(秒) (默认: 3)
  --fake-ip           启用IP伪造 (X-Forwarded-For)
  --fake-ip-file      自定义伪造IP列表文件路径
  --user-agents       自定义User-Agent列表文件路径
  --referers          自定义Referer列表文件路径
  --rate-limit        每秒每线程的最大请求数
  --http-proxies      HTTP代理列表文件路径
  --socks5-proxies    SOCKS5代理列表文件路径
  --proxy-type        指定使用的代理类型(http/socks5)
  --no-verify-ssl     禁用SSL证书验证
```

## 输出示例

```
┌────────────────────┬─────────────────────────┐
│ 指标               │ 数值                    │
├────────────────────┼─────────────────────────┤
│ URL                │ http://example.com      │
│ 请求方法           │ GET                     │
│ 总请求数           │ 100                     │
│ 并发线程数         │ 10                      │
│ 成功请求数         │ 98                      │
│ 失败请求数         │ 2                       │
│ 总执行时间         │ 5.23 秒                 │
│ 平均响应时间       │ 234.56 ms              │
│ 最小响应时间       │ 123.45 ms              │
│ 最大响应时间       │ 345.67 ms              │
│ 响应时间中位数     │ 234.56 ms              │
│ 响应时间标准差     │ 45.67 ms               │
│ RPS (每秒请求数)   │ 19.12                   │
│ IP伪造             │ 启用 (使用自定义IP列表) │
└────────────────────┴─────────────────────────┘
```

## 注意事项

1. 使用代理时建议设置较短的超时时间（默认3秒）
2. 对于HTTPS请求，如果遇到SSL证书问题，可以使用`--no-verify-ssl`选项
3. 使用IP伪造功能时，建议提供有效的IP地址列表
4. 设置请求速率限制时，考虑服务器的承受能力
5. 在使用工具时请遵守相关法律法规和目标服务器的使用政策

## 许可证

MIT License 