from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine
app = FastAPI()

#1.创建异步引擎
ASYNC_DATABASE_URL = "mysql+aiomysql://root:zxzdxc86@localhost:3306/book?charset=utf8"
async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=True,#可选，输出SQL日志
    pool_size=10,#连接池活跃的连接数
    max_overflow=10,#允许额外的连接数
)

#2. 定义模型类： 基类 + 表对应的模型类
#基类：创建时间 + 更新时间；  书籍表：id， 书名， 作者， 价格， 出版社

#3. 建表：定义函数建表，fastapi启动时调用建表的函数