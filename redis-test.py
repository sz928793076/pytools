import redis
from redis.exceptions import ConnectionError, AuthenticationError, TimeoutError

# Redis 连接配置
REDIS_HOST = "10.92.2.137"
REDIS_PORT = 6379
REDIS_PWD = "root"

def test_redis_connect():
    try:
        # 创建Redis客户端，设置短超时快速判断网络问题
        r = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PWD,
            socket_timeout=3,  # 3秒超时，判断网络不通
            decode_responses=True
        )
        # 发送ping测试连通性
        res = r.ping()
        if res:
            print("✅ 连接成功！网络正常、用户名密码全部正确")

    except TimeoutError:
        print("❌ 连接超时：网络不通，检查IP、端口、防火墙、安全组")
    except ConnectionError:
        print("❌ 无法建立连接：目标主机不可达/端口未开放/防火墙拦截")
    except AuthenticationError:
        print("❌ 认证失败：用户名或密码错误！网络是通的，但账号密码不对")
    except Exception as e:
        print(f"⚠️ 其他未知错误：{type(e).__name__}，详情：{str(e)}")

if __name__ == "__main__":
    print(f"正在测试 Redis {REDIS_HOST}:{REDIS_PORT} user={REDIS_USER} pwd={REDIS_PWD}")
    test_redis_connect()