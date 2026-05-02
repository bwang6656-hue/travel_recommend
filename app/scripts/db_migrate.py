from app.models.database import engine, Base
from app.models.models import DBUser, DBHotel, DBFood, DBFootprint, DBFavorite, DBNotification, DBFeedback, DBChatHistory
from sqlalchemy import inspect, text


def migrate():
    insp = inspect(engine)

    existing_tables = insp.get_table_names()
    print(f"现有表：{existing_tables}")

    if "users" in existing_tables:
        columns = [col["name"] for col in insp.get_columns("users")]
        with engine.connect() as conn:
            if "role" not in columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(50) DEFAULT 'user' NOT NULL"))
                conn.commit()
                print("[OK] users表添加role字段")
            if "status" not in columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN status VARCHAR(50) DEFAULT 'active' NOT NULL"))
                conn.commit()
                print("[OK] users表添加status字段")
    else:
        print("[INFO] users表不存在，将通过create_all创建")

    new_tables = ["user_favorites", "user_notifications", "user_feedback", "chat_history"]
    for t in new_tables:
        if t not in existing_tables:
            print(f"[INFO] {t}表不存在，将通过create_all创建")

    Base.metadata.create_all(bind=engine)
    print("[OK] 数据库迁移完成，所有表已创建")


if __name__ == "__main__":
    migrate()
