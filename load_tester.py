#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import threading
import time
import statistics
import argparse
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Optional, Tuple, Union
from datetime import datetime
import json
from rich.console import Console
from rich.table import Table
from rich import print as rprint
import random
from urllib.parse import urlparse
import os
import urllib3
import ipaddress

# 禁用urllib3的不安全请求警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class URLManager:
    def __init__(self, url: str = None, url_file: str = None):
        self.urls: List[str] = []
        self.current_url: str = None
        
        def process_url(url: str) -> Optional[str]:
            """处理并验证URL"""
            if not url:
                return None
                
            # 确保URL是完整的URL
            if not url.startswith(('http://', 'https://')):
                url = f'https://{url}'
                
            try:
                # 验证URL格式
                parsed = urlparse(url)
                if parsed.netloc:  # 只要有域名部分就认为是有效的
                    return url
                print(f"警告: 忽略无效URL: {url}")
                return None
            except Exception as e:
                print(f"警告: 忽略无效URL: {url} ({str(e)})")
                return None
        
        # 处理单个URL
        if url:
            processed_url = process_url(url)
            if processed_url:
                self.urls.append(processed_url)
                self.current_url = processed_url
        
        # 处理URL文件
        if url_file and os.path.exists(url_file):
            with open(url_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        processed_url = process_url(line)
                        if processed_url:
                            self.urls.append(processed_url)
            
            if not self.current_url and self.urls:
                self.current_url = random.choice(self.urls)

    def get_random_url(self) -> str:
        """获取随机URL"""
        if self.urls:
            self.current_url = random.choice(self.urls)
            return self.current_url
        return None

    def get_current_url(self) -> str:
        """获取当前URL"""
        return self.current_url

    def has_multiple_urls(self) -> bool:
        """检查是否有多个URL"""
        return len(self.urls) > 1

class IPManager:
    def __init__(self, ip_file: str = None):
        self.ip_list: List[str] = []
        
        if ip_file and os.path.exists(ip_file):
            with open(ip_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        try:
                            # 验证IP地址格式
                            ipaddress.ip_address(line)
                            self.ip_list.append(line)
                        except ValueError:
                            print(f"警告: 忽略无效IP地址: {line}")

    def get_random_ip(self) -> str:
        """获取随机IP地址"""
        if self.ip_list:
            return random.choice(self.ip_list)
        else:
            # 如果没有预定义IP列表，则随机生成
            return f"{random.randint(1,255)}.{random.randint(0,255)}." \
                   f"{random.randint(0,255)}.{random.randint(1,255)}"

    def has_custom_ips(self) -> bool:
        """检查是否使用自定义IP列表"""
        return bool(self.ip_list)

class ProxyManager:
    def __init__(self, http_proxy_file: str = None, socks5_proxy_file: str = None):
        self.http_proxies: List[str] = []
        self.socks5_proxies: List[str] = []
        
        if http_proxy_file and os.path.exists(http_proxy_file):
            with open(http_proxy_file, 'r') as f:
                self.http_proxies = [line.strip() for line in f if line.strip() and not line.startswith('#')]
                
        if socks5_proxy_file and os.path.exists(socks5_proxy_file):
            with open(socks5_proxy_file, 'r') as f:
                self.socks5_proxies = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    def get_random_proxy(self, proxy_type: str = None) -> Optional[Dict[str, str]]:
        """获取随机代理"""
        if proxy_type == 'http' and self.http_proxies:
            proxy = random.choice(self.http_proxies)
            return {'http': f'http://{proxy}', 'https': f'http://{proxy}'}
        elif proxy_type == 'socks5' and self.socks5_proxies:
            proxy = random.choice(self.socks5_proxies)
            return {'http': f'socks5h://{proxy}', 'https': f'socks5h://{proxy}'}
        elif not proxy_type and (self.http_proxies or self.socks5_proxies):
            # 如果没有指定类型，随机选择一种可用的代理类型
            available_types = []
            if self.http_proxies:
                available_types.append('http')
            if self.socks5_proxies:
                available_types.append('socks5')
            if available_types:
                return self.get_random_proxy(random.choice(available_types))
        return None

    def has_proxies(self) -> bool:
        """检查是否有可用代理"""
        return bool(self.http_proxies or self.socks5_proxies)

class LoadTester:
    def __init__(self, url_manager: URLManager,
                 method: str = 'GET', 
                 num_requests: int = 100,
                 num_threads: int = 10,
                 headers: Dict = None,
                 data: Dict = None,
                 timeout: int = 30,
                 proxy_timeout: int = 3,
                 fake_ip: bool = False,
                 ip_manager: Optional[IPManager] = None,
                 user_agents: List[str] = None,
                 referers: List[str] = None,
                 requests_per_second: Optional[float] = None,
                 proxy_manager: Optional[ProxyManager] = None,
                 proxy_type: Optional[str] = None,
                 verify_ssl: bool = True,
                 logger=None):
        self.url_manager = url_manager
        self.method = method.upper()
        self.num_requests = num_requests
        self.num_threads = num_threads
        self.headers = headers or {}
        self.data = data or {}
        self.timeout = timeout
        self.proxy_timeout = proxy_timeout
        self.fake_ip = fake_ip
        self.ip_manager = ip_manager
        self.requests_per_second = requests_per_second
        self.proxy_manager = proxy_manager
        self.proxy_type = proxy_type
        self.verify_ssl = verify_ssl
        self.logger = logger or (lambda msg, level='info': None)
        
        # 计算每个线程的请求间隔（如果设置了速率限制）
        if self.requests_per_second:
            self.request_interval = 1.0 / self.requests_per_second
        else:
            self.request_interval = None
            
        # 默认User-Agent列表
        self.user_agents = user_agents or [
            "Mozilla/5.0 (compatible; Baiduspider/2.0; +http://www.baidu.com/search/spider.html)",
            "Mozilla/5.0 (Linux;u;Android 4.2.2;zh-cn;) AppleWebKit/534.46 (KHTML,like Gecko) Version/5.1 Mobile Safari/10600.6.3 (compatible; Baiduspider/2.0; +http://www.baidu.com/search/spider.html)",
            "Mozilla/5.0 (compatible; Baiduspider-render/2.0; +http://www.baidu.com/search/spider.html)"
        ]
        
        # 设置默认的Referer列表
        self.referers = referers or [
            "https://www.google.com/",
            "https://www.bing.com/",
            "https://www.baidu.com/",
            "https://www.yahoo.com/",
            None  # 有时不带referer
        ]
        
        # 结果统计
        self.response_times: Dict[str, List[float]] = {}
        self.success_count: Dict[str, int] = {}
        self.failure_count: Dict[str, int] = {}
        self.errors: Dict[str, List[str]] = {}
        self.proxy_errors: Dict[str, int] = {}
        self.proxy_timeouts: Dict[str, int] = {}
        self.ssl_errors: Dict[str, int] = {}
        
        self.start_time = None
        self.end_time = None
        
        self.console = Console()

    def _init_url_stats(self, url: str) -> None:
        """初始化URL统计数据"""
        if url not in self.response_times:
            self.response_times[url] = []
            self.success_count[url] = 0
            self.failure_count[url] = 0
            self.errors[url] = []
            self.proxy_errors[url] = 0
            self.proxy_timeouts[url] = 0
            self.ssl_errors[url] = 0

    def get_request_headers(self) -> Dict:
        """生成请求头"""
        headers = self.headers.copy()
        
        # 添加随机User-Agent
        if not headers.get('User-Agent'):
            headers['User-Agent'] = random.choice(self.user_agents)
            
        # 添加随机X-Forwarded-For
        if self.fake_ip:
            fake_ip = self.ip_manager.get_random_ip() if self.ip_manager else \
                     f"{random.randint(1,255)}.{random.randint(0,255)}." \
                     f"{random.randint(0,255)}.{random.randint(1,255)}"
            headers['X-Forwarded-For'] = fake_ip
            headers['X-Real-IP'] = fake_ip
            
        # 添加随机Referer（如果referers列表不为空）
        if self.referers and not headers.get('Referer'):
            referer = random.choice(self.referers)
            if referer:
                headers['Referer'] = referer
                
        return headers

    def make_request(self, check_cancel=None) -> None:
        """执行单个请求"""
        if check_cancel and check_cancel():
            return
            
        # 随机获取目标URL
        target_url = self.url_manager.get_random_url()
        if not target_url:
            return

        self._init_url_stats(target_url)
        
        try:
            start_time = time.time()
            headers = self.get_request_headers()
            
            # 获取代理（如果启用）
            proxies = None
            current_timeout = self.timeout
            if self.proxy_manager and self.proxy_manager.has_proxies():
                proxies = self.proxy_manager.get_random_proxy(self.proxy_type)
                if proxies:  # 只有在成功获取代理时才使用代理超时
                    current_timeout = self.proxy_timeout
                    self.logger(f"使用代理: {proxies}")
            
            try:
                # 确保URL是完整的URL
                if not target_url.startswith(('http://', 'https://')):
                    target_url = f'https://{target_url}'
                
                # 验证URL格式
                parsed = urlparse(target_url)
                if not parsed.netloc:
                    raise requests.exceptions.InvalidURL(f"无效的URL: {target_url}")
                
                # 发送请求
                if self.method == 'GET':
                    response = requests.get(
                        target_url, 
                        headers=headers,
                        proxies=proxies,
                        timeout=current_timeout,
                        verify=self.verify_ssl,
                        allow_redirects=True
                    )
                else:
                    response = requests.post(
                        target_url,
                        headers=headers,
                        json=self.data,
                        proxies=proxies,
                        timeout=current_timeout,
                        verify=self.verify_ssl,
                        allow_redirects=True
                    )
            except requests.exceptions.InvalidURL as e:
                self.failure_count[target_url] += 1
                error_msg = f"无效的URL: {target_url}"
                self.errors[target_url].append(error_msg)
                self.logger(error_msg, "error")
                return
            
            elapsed_time = time.time() - start_time
            self.response_times[target_url].append(elapsed_time)
            
            if response.status_code == 200:
                self.success_count[target_url] += 1
                self.logger(f"请求成功: {response.status_code}, 耗时: {elapsed_time:.2f}秒")
            else:
                self.failure_count[target_url] += 1
                self.errors[target_url].append(f"状态码: {response.status_code}")
                self.logger(f"请求失败: {response.status_code}, 耗时: {elapsed_time:.2f}秒", "error")
                
            # 如果设置了请求速率限制，则等待适当的时间
            if self.request_interval:
                time_to_wait = self.request_interval - elapsed_time
                if time_to_wait > 0:
                    time.sleep(time_to_wait)
                    
        except requests.exceptions.ProxyError as e:
            self.failure_count[target_url] += 1
            self.proxy_errors[target_url] += 1
            self.errors[target_url].append(f"代理错误: {str(e)}")
            self.logger(f"代理错误: {str(e)}", "error")
        except requests.exceptions.ConnectTimeout as e:
            self.failure_count[target_url] += 1
            if proxies:
                self.proxy_timeouts[target_url] += 1
            self.errors[target_url].append(f"连接超时: {str(e)}")
            self.logger(f"连接超时: {str(e)}", "error")
        except requests.exceptions.SSLError as e:
            self.failure_count[target_url] += 1
            self.ssl_errors[target_url] += 1
            self.errors[target_url].append(f"SSL错误: {str(e)}")
            self.logger(f"SSL错误: {str(e)}", "error")
        except requests.exceptions.RequestException as e:
            self.failure_count[target_url] += 1
            error_msg = str(e)
            
            # 处理各种请求异常
            if isinstance(e, requests.exceptions.ConnectionError):
                if "Failed to resolve" in error_msg:
                    error_msg = f"无法解析域名: {target_url}"
                elif "Connection refused" in error_msg:
                    error_msg = f"连接被拒绝: {target_url}"
                elif "Connection reset by peer" in error_msg:
                    error_msg = f"连接被重置: {target_url}"
                else:
                    error_msg = f"连接错误: {target_url}"
            elif isinstance(e, requests.exceptions.ReadTimeout):
                error_msg = f"读取超时: {target_url}"
            elif isinstance(e, requests.exceptions.ConnectTimeout):
                error_msg = f"连接超时: {target_url}"
            elif isinstance(e, requests.exceptions.SSLError):
                error_msg = f"SSL错误: {target_url}"
            elif isinstance(e, requests.exceptions.InvalidURL):
                error_msg = f"无效的URL: {target_url}"
            else:
                error_msg = f"请求错误: {target_url} - {str(e)}"
                
            self.errors[target_url].append(error_msg)
            self.logger(error_msg, "error")
        except Exception as e:
            self.failure_count[target_url] += 1
            self.errors[target_url].append(f"其他错误: {str(e)}")
            self.logger(f"其他错误: {str(e)}", "error")

    def run(self, check_cancel=None) -> None:
        """运行测试"""
        self.start_time = datetime.now()
        
        with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
            futures = []
            
            # 随机分配请求
            for _ in range(self.num_requests):
                if check_cancel and check_cancel():
                    break
                futures.append(executor.submit(self.make_request, check_cancel))
            
            # 等待所有任务完成或取消
            for future in futures:
                try:
                    future.result()
                except Exception as e:
                    self.logger(f"线程执行错误: {str(e)}", "error")
        
        self.end_time = datetime.now()
        
        # 输出统计信息
        self.print_results()

    def print_results(self) -> None:
        """打印测试结果"""
        if not self.start_time or not self.end_time:
            return

        total_time = (self.end_time - self.start_time).total_seconds()
        
        for url in self.response_times:
            if not self.response_times[url]:
                continue
                
            total_requests = self.success_count[url] + self.failure_count[url]
            success_rate = (self.success_count[url] / total_requests * 100) if total_requests > 0 else 0
            
            self.logger(f"\n测试结果 - {url}", "info")
            self.logger(f"总请求数: {total_requests}", "info")
            self.logger(f"成功请求: {self.success_count[url]} ({success_rate:.2f}%)", "info")
            self.logger(f"失败请求: {self.failure_count[url]}", "info")
            self.logger(f"代理错误: {self.proxy_errors[url]}", "info")
            self.logger(f"代理超时: {self.proxy_timeouts[url]}", "info")
            self.logger(f"SSL错误: {self.ssl_errors[url]}", "info")
            
            if self.response_times[url]:
                avg_time = statistics.mean(self.response_times[url])
                min_time = min(self.response_times[url])
                max_time = max(self.response_times[url])
                median_time = statistics.median(self.response_times[url])
                std_dev = statistics.stdev(self.response_times[url]) if len(self.response_times[url]) > 1 else 0
                
                self.logger(f"平均响应时间: {avg_time:.2f}秒", "info")
                self.logger(f"最小响应时间: {min_time:.2f}秒", "info")
                self.logger(f"最大响应时间: {max_time:.2f}秒", "info")
                self.logger(f"响应时间中位数: {median_time:.2f}秒", "info")
                self.logger(f"响应时间标准差: {std_dev:.2f}秒", "info")
                self.logger(f"每秒请求数(RPS): {total_requests/total_time:.2f}", "info")
            
            if self.errors[url]:
                self.logger("\n错误信息:", "error")
                for error in self.errors[url]:
                    self.logger(error, "error")

def main():
    parser = argparse.ArgumentParser(description='HTTP压力测试工具')
    parser.add_argument('url', nargs='?', help='测试目标URL')
    parser.add_argument('--url-file', type=str,
                       help='包含多个URL的文件路径（每行一个URL）')
    parser.add_argument('-n', '--num-requests', type=int, default=100,
                       help='总请求数 (默认: 100)')
    parser.add_argument('-t', '--num-threads', type=int, default=10,
                       help='并发线程数 (默认: 10)')
    parser.add_argument('-m', '--method', default='GET',
                       choices=['GET', 'POST'],
                       help='HTTP请求方法 (默认: GET)')
    parser.add_argument('--headers', type=json.loads, default={},
                       help='HTTP请求头 (JSON格式)')
    parser.add_argument('--data', type=json.loads, default={},
                       help='POST请求数据 (JSON格式)')
    parser.add_argument('--timeout', type=int, default=30,
                       help='请求超时时间(秒) (默认: 30)')
    parser.add_argument('--proxy-timeout', type=int, default=3,
                       help='代理请求超时时间(秒) (默认: 3)')
    parser.add_argument('--fake-ip', action='store_true',
                       help='启用IP伪造 (X-Forwarded-For)')
    parser.add_argument('--fake-ip-file', type=str,
                       help='自定义伪造IP列表文件路径')
    parser.add_argument('--user-agents', type=str,
                       help='自定义User-Agent列表文件路径')
    parser.add_argument('--referers', type=str,
                       help='自定义Referer列表文件路径')
    parser.add_argument('--rate-limit', type=float,
                       help='每秒每线程的最大请求数')
    parser.add_argument('--http-proxies', type=str,
                       help='HTTP代理列表文件路径')
    parser.add_argument('--socks5-proxies', type=str,
                       help='SOCKS5代理列表文件路径')
    parser.add_argument('--proxy-type', choices=['http', 'socks5'],
                       help='指定使用的代理类型（如果不指定则随机使用）')
    parser.add_argument('--no-verify-ssl', action='store_true',
                       help='禁用SSL证书验证')

    args = parser.parse_args()

    if not args.url and not args.url_file:
        parser.error("必须提供URL或URL文件")

    # 初始化URL管理器
    url_manager = URLManager(args.url, args.url_file)
    if not url_manager.get_current_url():
        parser.error("未找到有效的URL")

    # 加载自定义User-Agent列表
    user_agents = None
    if args.user_agents:
        try:
            with open(args.user_agents, 'r') as f:
                user_agents = [line.strip() for line in f if line.strip()]
        except Exception as e:
            print(f"警告: 无法加载User-Agent文件: {e}")

    # 加载自定义Referer列表
    referers = None
    if args.referers:
        try:
            with open(args.referers, 'r') as f:
                referers = [line.strip() for line in f if line.strip()]
        except Exception as e:
            print(f"警告: 无法加载Referer文件: {e}")

    # 初始化IP管理器
    ip_manager = None
    if args.fake_ip:
        ip_manager = IPManager(args.fake_ip_file)

    # 初始化代理管理器
    proxy_manager = None
    if args.http_proxies or args.socks5_proxies:
        proxy_manager = ProxyManager(args.http_proxies, args.socks5_proxies)
        if not proxy_manager.has_proxies():
            print("警告: 未找到可用的代理")

    tester = LoadTester(
        url_manager=url_manager,
        method=args.method,
        num_requests=args.num_requests,
        num_threads=args.num_threads,
        headers=args.headers,
        data=args.data,
        timeout=args.timeout,
        proxy_timeout=args.proxy_timeout,
        fake_ip=args.fake_ip,
        ip_manager=ip_manager,
        user_agents=user_agents,
        referers=referers,
        requests_per_second=args.rate_limit,
        proxy_manager=proxy_manager,
        proxy_type=args.proxy_type,
        verify_ssl=not args.no_verify_ssl
    )
    
    tester.run()

if __name__ == '__main__':
    main() 