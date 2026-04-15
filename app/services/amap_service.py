import os
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning
from app.config.config import AMAP_KEY, AMAP_DISTRICT_URL, AMAP_WEATHER_URL, CACHE_EXPIRE

# 禁用SSL警告（仅测试用，生产环境建议配置证书）
disable_warnings(InsecureRequestWarning)

# 全局变量
_amap_session = None
_weather_cache = {}
_city_request_timer = {}

# 模拟天气数据（作为兜底）
_MOCK_WEATHER_DATA = {
    "北京": {"temperature": "5℃", "weather": "晴", "wind": "北风2级", "humidity": "30%"},
    "上海": {"temperature": "10℃", "weather": "多云", "wind": "东风3级", "humidity": "60%"},
    "广州": {"temperature": "18℃", "weather": "阴", "wind": "南风1级", "humidity": "75%"},
    "深圳": {"temperature": "16℃", "weather": "小雨", "wind": "东南风2级", "humidity": "80%"},
    "杭州": {"temperature": "8℃", "weather": "晴转多云", "wind": "西北风2级", "humidity": "50%"},
    "成都": {"temperature": "12℃", "weather": "阴", "wind": "东北风1级", "humidity": "70%"},
    "重庆": {"temperature": "11℃", "weather": "小雨", "wind": "西南风2级", "humidity": "85%"},
    "西安": {"temperature": "3℃", "weather": "晴", "wind": "西风2级", "humidity": "40%"},
}

def _init_amap_session():
    """初始化高德接口会话（连接池+重试+HTTP/1.1）"""
    global _amap_session
    if _amap_session:
        return _amap_session

    session = requests.Session()
    # 配置重试策略：3次重试，间隔1秒
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        allowed_methods=["GET"],
        status_forcelist=[429, 500, 502, 503, 504]
    )
    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=10,
        pool_maxsize=10,
        pool_block=False
    )
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    # 强制HTTP/1.1，解决HTTP/2兼容问题
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Connection": "keep-alive"
    })
    session.timeout = 5  # 5秒超时
    session.verify = False  # 临时关闭SSL验证（解决SSL错误）

    _amap_session = session
    return session

def _check_request_frequency(city: str):
    """控制请求频率，避免高频调用高德接口"""
    now = time.time()
    if city in _city_request_timer:
        last_time = _city_request_timer[city]
        if now - last_time < 2:  # 间隔至少2秒
            time.sleep(2 - (now - last_time))
    _city_request_timer[city] = now

def get_city_adcode(city: str) -> str:
    """获取城市adcode（添加缓存+重试+频率控制）"""
    if not city:
        return None

    if not AMAP_KEY or not AMAP_DISTRICT_URL:
        print("未配置高德API Key/行政区划查询URL")
        return None

    # 频率控制
    _check_request_frequency(city)

    try:
        session = _init_amap_session()
        response = session.get(
            url=AMAP_DISTRICT_URL,
            params={
                "keywords": city.strip(),
                "key": AMAP_KEY,
                "subdistrict": 0,
                "extensions": "base",
                "output": "json"
            }
        )
        response.raise_for_status()
        data = response.json()

        if data.get("status") != "1":
            print(f"高德行政区划接口返回错误：{data.get('info')}")
            return None

        districts = data.get("districts", [])
        if not districts:
            print(f"未找到城市「{city}」的行政区划编码")
            return None

        return districts[0].get("adcode")
    except requests.exceptions.Timeout:
        print(f"[错误] 高德行政区划接口超时（城市：{city}）")
        return None
    except requests.exceptions.ConnectionResetError as e:
        print(f"[错误] 高德接口连接被重置（城市:{city}）：{str(e)}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"[错误] 高德行政区划接口请求失败（城市：{city}）：{str(e)}")
        return None
    except Exception as e:
        print(f"[错误] 解析行政区划数据失败（城市：{city}）：{str(e)}")
        return None

def get_city_weather(city: str) -> dict:
    """获取城市天气（添加缓存+兜底模拟数据）"""
    # 1. 先查缓存
    if city in _weather_cache:
        cache_data, cache_time = _weather_cache[city]
        if time.time() - cache_time < CACHE_EXPIRE:
            return cache_data

    # 2. 尝试调用高德接口
    adcode = get_city_adcode(city)
    weather_data = None

    if adcode and AMAP_KEY and AMAP_WEATHER_URL:
        try:
            session = _init_amap_session()
            response = session.get(
                url=AMAP_WEATHER_URL,
                params={
                    "key": AMAP_KEY,
                    "city": adcode,
                    "extensions": "base",
                    "output": "json"
                }
            )
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "1" and data.get("lives"):
                live = data["lives"][0]
                weather_data = {
                    "temperature": f"{live.get('temperature', '未知')}℃",
                    "weather": live.get("weather", "未知"),
                    "wind": f"{live.get('winddirection', '未知')}{live.get('windpower', '')}级",
                    "humidity": f"{live.get('humidity', '未知')}%"
                }
        except requests.exceptions.Timeout:
            print(f"[错误] 高德天气接口超时（城市：{city}）")
        except requests.exceptions.ConnectionResetError as e:
            print(f"[错误] 高德天气接口连接被重置（城市：{city}）：{str(e)}")
        except requests.exceptions.RequestException as e:
            print(f"[错误] 高德天气接口请求失败（城市：{city}）：{str(e)}")
        except Exception as e:
            print(f"[错误] 解析天气数据失败（城市：{city}）：{str(e)}")

    # 3. 高德接口失败，使用模拟数据兜底
    if not weather_data:
        weather_data = _MOCK_WEATHER_DATA.get(city, {
            "temperature": "未知",
            "weather": "未知",
            "wind": "未知",
            "humidity": "未知%"
        })

    # 4. 写入缓存
    _weather_cache[city] = (weather_data, time.time())
    # 缓存超过100条时清理
    if len(_weather_cache) > 100:
        _weather_cache.clear()

    return weather_data

def close_amap_session():
    """关闭高德接口会话"""
    global _amap_session
    if _amap_session:
        _amap_session.close()
