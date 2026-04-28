from neo4j import GraphDatabase
import pandas as pd
from tqdm import tqdm

# =====================================
# Neo4j 配置（改成你自己的）
# =====================================
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "zxzdxc86"

CSV_PATH = r"E:\travel_recommend\data\scenic_spots_30000.csv"


class Neo4jImporter:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(
            uri,
            auth=(user, password)
        )

    def close(self):
        self.driver.close()

    def run_query(self, query, parameters=None):
        with self.driver.session() as session:
            session.run(query, parameters)

    # =====================================
    # 删除旧数据
    # =====================================
    def clear_database(self):
        print("正在删除旧数据...")

        query = """
        MATCH (n)
        DETACH DELETE n
        """

        self.run_query(query)
        print("旧数据删除完成")

    # =====================================
    # 创建约束（重点：使用 spot_id）
    # =====================================
    def create_constraints(self):
        print("创建约束中...")

        query = """
        CREATE CONSTRAINT scenic_spot_id_unique IF NOT EXISTS
        FOR (s:ScenicSpot)
        REQUIRE s.spot_id IS UNIQUE
        """

        self.run_query(query)

        print("约束创建完成")

    # =====================================
    # 导入景点节点（重点：兼容旧项目）
    # =====================================
    def import_scenic_spots(self, df):
        print("开始导入景点节点...")

        query = """
        UNWIND $rows AS row
        MERGE (s:ScenicSpot {spot_id: row.id})
        SET
            s.spot_id = row.id,
            s.id = row.id,
            s.name = row.name,
            s.city = row.city,
            s.rating = row.rating,
            s.address = row.address,
            s.type = row.type,
            s.main_type = row.main_type
        """

        batch_size = 1000

        for i in tqdm(range(0, len(df), batch_size)):
            batch = df.iloc[i:i + batch_size].to_dict("records")
            self.run_query(query, {"rows": batch})

        print("景点节点导入完成")

    # =====================================
    # ✅ 只在这里新增：创建 City 节点 + 归属关系
    # =====================================
    def create_city_nodes(self):
        print("创建城市节点...")

        query = """
        MATCH (s:ScenicSpot)
        WHERE s.city IS NOT NULL AND s.city <> ""
        WITH DISTINCT s.city AS city_name
        MERGE (c:City {name: city_name})
        """
        self.run_query(query)

        query2 = """
        MATCH (s:ScenicSpot), (c:City)
        WHERE s.city = c.name
        MERGE (s)-[:LOCATED_IN]->(c)
        """
        self.run_query(query2)

        print("城市节点创建完成")

    # =====================================
    # 创建同城市关系（优化版）
    # 防止 Neo4j 内存爆炸
    # =====================================
    def create_same_city_relationship(self):
        print("创建同城市关系（优化版）...")

        query = """
        MATCH (s:ScenicSpot)
        WITH s.city AS city, collect(s)[0..100] AS spots
        WHERE size(spots) > 1

        UNWIND spots AS a
        UNWIND spots AS b
        WITH a, b
        WHERE id(a) < id(b)

        MERGE (a)-[:IN_SAME_CITY_AS]->(b)
        """

        self.run_query(query)

        print("同城市关系创建完成")

    # =====================================
    # 创建同类别关系（优化版）
    # =====================================
    def create_same_category_relationship(self):
        print("创建同类别关系（优化版）...")

        query = """
        MATCH (s:ScenicSpot)
        WITH s.main_type AS type, collect(s)[0..100] AS spots
        WHERE size(spots) > 1

        UNWIND spots AS a
        UNWIND spots AS b
        WITH a, b
        WHERE id(a) < id(b)

        MERGE (a)-[:SAME_CATEGORY_AS]->(b)
        """

        self.run_query(query)

        print("同类别关系创建完成")

    # =====================================
    # 验证导入结果
    # =====================================
    def validate_import(self):
        print("\n开始验证导入结果...\n")

        queries = {
            "景点节点数量": """
                MATCH (s:ScenicSpot)
                RETURN count(s) AS count
            """,

            "拥有 spot_id 的景点数量": """
                MATCH (s:ScenicSpot)
                WHERE s.spot_id IS NOT NULL
                RETURN count(s) AS count
            """,

            "城市节点数量": """
                MATCH (c:City)
                RETURN count(c) AS count
            """,

            "同城市关系数量": """
                MATCH ()-[r:IN_SAME_CITY_AS]->()
                RETURN count(r) AS count
            """,

            "同类别关系数量": """
                MATCH ()-[r:SAME_CATEGORY_AS]->()
                RETURN count(r) AS count
            """
        }

        with self.driver.session() as session:
            for name, query in queries.items():
                result = session.run(query)
                count = result.single()["count"]
                print(f"{name}: {count}")

    # =====================================
    # 执行完整导入流程
    # =====================================
    def execute_all(self, df):
        self.clear_database()
        self.create_constraints()
        self.import_scenic_spots(df)
        self.create_city_nodes()  # 只加这一行
        self.create_same_city_relationship()
        self.create_same_category_relationship()
        self.validate_import()


# =====================================
# 提取主类别（非常关键）
# 避免 type 字段过于复杂导致爆炸
# =====================================
def extract_main_type(x):
    if pd.isna(x):
        return "未知"

    x = str(x)

    # 优先按 |
    if "|" in x:
        x = x.split("|")[0]

    # 再按 ;
    if ";" in x:
        x = x.split(";")[0]

    return x.strip()


# =====================================
# 主函数
# =====================================
def main():
    print("开始读取 CSV 数据...")

    df = pd.read_csv(CSV_PATH)

    # 字段统一
    df = df.rename(columns={
        "name_zh": "name"
    })

    # 去重（按 id）
    df = df.drop_duplicates(subset=["id"])

    # 主类别提取（关键优化）
    df["main_type"] = df["type"].apply(extract_main_type)

    print(f"CSV读取完成，共 {len(df)} 条景点数据")

    importer = Neo4jImporter(
        NEO4J_URI,
        NEO4J_USER,
        NEO4J_PASSWORD
    )

    try:
        importer.execute_all(df)
        print("\n全部导入完成！")

    finally:
        importer.close()


if __name__ == "__main__":
    main()