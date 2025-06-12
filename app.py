from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import os
import threading
import json
from datetime import datetime
import tempfile
import shutil
from queue import Queue
from load_tester import URLManager, IPManager, ProxyManager, LoadTester

app = Flask(__name__)
CORS(app)

# 存储测试结果的全局变量
test_results = {}
test_status = {}
test_logs = {}
test_queues = {}
test_threads = {}
test_cancel_flags = {}

# 临时文件目录
TEMP_DIR = os.path.join(tempfile.gettempdir(), 'yace')
os.makedirs(TEMP_DIR, exist_ok=True)

def cleanup_temp_files():
    """清理临时文件"""
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)
        os.makedirs(TEMP_DIR)

def add_log(test_id: str, message: str, level: str = 'info'):
    """添加日志"""
    if test_id not in test_logs:
        test_logs[test_id] = []
    
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'message': message,
        'level': level
    }
    test_logs[test_id].append(log_entry)
    
    # 如果有消息队列，发送日志
    if test_id in test_queues:
        test_queues[test_id].put(log_entry)

def run_load_test(test_id, config):
    """执行负载测试的后台任务"""
    global test_results, test_status, test_cancel_flags
    
    try:
        add_log(test_id, "开始初始化测试...", "info")
        
        # 处理文件路径
        if config.get('fake_ip_file'):
            config['fake_ip_file'] = os.path.join(TEMP_DIR, os.path.basename(config['fake_ip_file']))
        
        # 处理代理文件路径
        if config.get('http_proxies'):
            config['http_proxies'] = os.path.join(TEMP_DIR, os.path.basename(config['http_proxies']))
        if config.get('socks5_proxies'):
            config['socks5_proxies'] = os.path.join(TEMP_DIR, os.path.basename(config['socks5_proxies']))
            
        # 初始化管理器
        url_manager = URLManager(url=config.get('url'), url_file=config.get('url_file'))
        add_log(test_id, f"目标URL: {config.get('url')}", "info")
        
        ip_manager = None
        if config.get('fake_ip'):
            ip_manager = IPManager(ip_file=config.get('fake_ip_file'))
            add_log(test_id, "IP伪造已启用", "info")
        
        proxy_manager = None
        if config.get('http_proxies') or config.get('socks5_proxies'):
            proxy_manager = ProxyManager(
                http_proxy_file=config.get('http_proxies'),
                socks5_proxy_file=config.get('socks5_proxies')
            )
            add_log(test_id, f"代理已启用，类型: {config.get('proxy_type', 'auto')}", "info")

        # 创建测试实例
        tester = LoadTester(
            url_manager=url_manager,
            method=config.get('method', 'GET'),
            num_requests=int(config.get('num_requests', 100)),
            num_threads=int(config.get('num_threads', 10)),
            headers=config.get('headers', {}),
            data=config.get('data', {}),
            timeout=int(config.get('timeout', 30)),
            proxy_timeout=int(config.get('proxy_timeout', 3)),
            fake_ip=config.get('fake_ip', False),
            ip_manager=ip_manager,
            user_agents=config.get('user_agents'),
            referers=config.get('referers'),
            requests_per_second=float(config.get('rate_limit')) if config.get('rate_limit') else None,
            proxy_manager=proxy_manager,
            proxy_type=config.get('proxy_type'),
            verify_ssl=not config.get('no_verify_ssl', False),
            logger=lambda msg, level='info': add_log(test_id, msg, level)
        )

        # 更新状态为运行中
        test_status[test_id] = {
            'status': 'running',
            'start_time': datetime.now().isoformat(),
            'config': config
        }
        
        add_log(test_id, "开始执行测试...", "info")

        # 执行测试
        def check_cancel():
            return test_cancel_flags.get(test_id, False)
        
        tester.run(check_cancel=check_cancel)

        # 保存结果
        results = {
            'response_times': tester.response_times,
            'success_count': tester.success_count,
            'failure_count': tester.failure_count,
            'errors': tester.errors,
            'proxy_errors': tester.proxy_errors,
            'proxy_timeouts': tester.proxy_timeouts,
            'ssl_errors': tester.ssl_errors,
            'start_time': tester.start_time.isoformat() if tester.start_time else None,
            'end_time': tester.end_time.isoformat() if tester.end_time else None
        }
        
        test_results[test_id] = results
        
        if check_cancel():
            test_status[test_id]['status'] = 'cancelled'
            add_log(test_id, "测试已取消", "warning")
        else:
            test_status[test_id]['status'] = 'completed'
            add_log(test_id, "测试已完成", "info")
        
        test_status[test_id]['end_time'] = datetime.now().isoformat()

    except Exception as e:
        test_status[test_id]['status'] = 'failed'
        test_status[test_id]['error'] = str(e)
        test_status[test_id]['end_time'] = datetime.now().isoformat()
        add_log(test_id, f"测试失败: {str(e)}", "error")
    finally:
        # 清理临时文件
        cleanup_temp_files()
        # 清理线程引用
        if test_id in test_threads:
            del test_threads[test_id]

@app.route('/')
def index():
    """渲染主页"""
    return render_template('index.html')

@app.route('/api/test', methods=['POST'])
def start_test():
    """启动新的负载测试"""
    config = request.json
    test_id = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 初始化测试相关的变量
    test_queues[test_id] = Queue()
    test_cancel_flags[test_id] = False
    test_logs[test_id] = []
    
    # 在新线程中启动测试
    thread = threading.Thread(target=run_load_test, args=(test_id, config))
    thread.daemon = True
    test_threads[test_id] = thread
    thread.start()
    
    return jsonify({
        'test_id': test_id,
        'status': 'started'
    })

@app.route('/api/test/<test_id>/cancel', methods=['POST'])
def cancel_test(test_id):
    """取消测试"""
    if test_id in test_status and test_status[test_id]['status'] == 'running':
        test_cancel_flags[test_id] = True
        add_log(test_id, "正在取消测试...", "warning")
        return jsonify({'status': 'cancelling'})
    return jsonify({'error': 'Test not found or not running'}), 404

@app.route('/api/test/<test_id>/status')
def get_test_status(test_id):
    """获取测试状态"""
    if test_id in test_status:
        return jsonify(test_status[test_id])
    return jsonify({'error': 'Test not found'}), 404

@app.route('/api/test/<test_id>/logs')
def get_test_logs(test_id):
    """获取测试日志"""
    if test_id in test_logs:
        # 获取上次日志ID
        last_log_id = request.args.get('last_log_id', '-1')
        last_log_id = int(last_log_id)
        
        # 返回新日志
        new_logs = test_logs[test_id][last_log_id + 1:]
        return jsonify({
            'logs': new_logs,
            'last_log_id': len(test_logs[test_id]) - 1
        })
    return jsonify({'error': 'Test not found'}), 404

@app.route('/api/test/<test_id>/results')
def get_test_results(test_id):
    """获取测试结果"""
    if test_id in test_results:
        return jsonify(test_results[test_id])
    return jsonify({'error': 'Results not found'}), 404

@app.route('/api/tests')
def list_tests():
    """列出所有测试"""
    tests = []
    for test_id in test_status:
        test_info = test_status[test_id].copy()
        test_info['id'] = test_id
        tests.append(test_info)
    return jsonify(tests)

@app.route('/api/create_temp_file', methods=['POST'])
def create_temp_file():
    """创建临时文件"""
    try:
        data = request.json
        filename = data.get('filename')
        content = data.get('content')
        
        if not filename or content is None:
            return jsonify({'error': '缺少必要参数'}), 400
            
        file_path = os.path.join(TEMP_DIR, filename)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
            
        return jsonify({'success': True, 'path': file_path})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # 确保模板目录存在
    os.makedirs('templates', exist_ok=True)
    app.run(debug=True, host='0.0.0.0', port=5000) 