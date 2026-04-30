import sys
import os
import random
import torch
import numpy as np
import pandas as pd
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.data_service import DataProcessor
from app.services.knowledge_graph_service import KnowledgeGraphFeatureExtractor
from app.services.model_service import ModelTrainer
from app.models.usercf import UserCF

EMBEDDING_DIM = 64
NUM_LAYERS = 4
LEARNING_RATE = 0.001
WEIGHT_DECAY = 1e-5
EPOCHS = 300
BATCH_SIZE = 2048
K_NEIGHBORS = 20
TEST_RATIO = 0.2
RANDOM_SEED = 42
MIN_USERS = 500
MIN_INTERACTIONS_PER_USER = 20
NUM_SPOT_SUBSET = 500
ADD_SOCIAL_EDGES = True
ADD_ITEM_SIMILARITY_EDGES = True
MAX_ITEM_SIM_EDGES_RATIO = 1.5

SAVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'saved_models')

def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)

def generate_synthetic_footprints(spot_ids, spot_cities=None, spot_types=None, num_users=200, min_interactions=20, max_interactions=40, seed=42):
    random.seed(seed)
    np.random.seed(seed)

    subset_size = min(NUM_SPOT_SUBSET, len(spot_ids))
    spot_subset = random.sample(spot_ids, subset_size)

    city_groups = defaultdict(list)
    if spot_cities:
        for sid in spot_subset:
            city = spot_cities.get(sid, "unknown")
            city_groups[city].append(sid)

    type_groups = defaultdict(list)
    if spot_types:
        for sid in spot_subset:
            types = spot_types.get(sid, [])
            for t in types:
                type_groups[t].append(sid)

    available_types = [t for t, spots in type_groups.items() if len(spots) >= 3]

    footprints = {}

    for user_idx in range(num_users):
        user_id = f"synthetic_user_{user_idx + 1}"
        num_interactions = random.randint(min_interactions, max_interactions)

        visited_spots = set()

        if available_types:
            num_preferred_types = random.randint(2, min(3, len(available_types)))
            preferred_types = random.sample(available_types, num_preferred_types)

            type_count = int(num_interactions * random.uniform(0.55, 0.75))
            per_type = type_count // num_preferred_types

            for pt in preferred_types:
                type_spots = [s for s in type_groups[pt] if s not in visited_spots]
                sample_count = min(per_type + random.randint(-2, 2), len(type_spots))
                sample_count = max(sample_count, 0)
                if type_spots and sample_count > 0:
                    visited_spots.update(random.sample(type_spots, sample_count))

        city_count = int(num_interactions * random.uniform(0.10, 0.25))
        if city_groups:
            if visited_spots:
                visited_cities = set()
                for sid in visited_spots:
                    c = spot_cities.get(sid, "unknown") if spot_cities else "unknown"
                    visited_cities.add(c)
                preferred_city = random.choice(list(visited_cities)) if visited_cities else random.choice(list(city_groups.keys()))
            else:
                preferred_city = random.choice(list(city_groups.keys()))

            city_spots = [s for s in city_groups.get(preferred_city, []) if s not in visited_spots]
            if city_spots:
                visited_spots.update(random.sample(city_spots, min(city_count, len(city_spots))))

        random_count = num_interactions - len(visited_spots)
        if random_count > 0:
            remaining_spots = [s for s in spot_subset if s not in visited_spots]
            if remaining_spots:
                visited_spots.update(random.sample(remaining_spots, min(random_count, len(remaining_spots))))

        footprints[user_id] = {spot_id: True for spot_id in visited_spots}

    return footprints, spot_subset

def generate_social_edges(user_ids, footprints, similarity_threshold=0.15, seed=42):
    random.seed(seed)
    social_edges = set()
    
    user_list = list(user_ids)
    num_users = len(user_list)
    
    for i in range(num_users):
        for j in range(i + 1, num_users):
            user1 = user_list[i]
            user2 = user_list[j]
            
            spots1 = set(footprints.get(user1, {}).keys())
            spots2 = set(footprints.get(user2, {}).keys())
            
            if len(spots1) == 0 or len(spots2) == 0:
                continue
            
            intersection = len(spots1 & spots2)
            union = len(spots1 | spots2)
            jaccard = intersection / union if union > 0 else 0
            
            if jaccard >= similarity_threshold:
                social_edges.add((user1, user2))
                social_edges.add((user2, user1))
    
    return list(social_edges)


def generate_item_similarity_edges(spot_ids, spot_cities, spot_types, max_edges=None, similarity_threshold=0.5, seed=42):
    random.seed(seed)
    item_edges = []
    
    spot_list = list(spot_ids)
    num_spots = len(spot_list)
    
    candidates = []
    for i in range(num_spots):
        for j in range(i + 1, num_spots):
            spot1 = spot_list[i]
            spot2 = spot_list[j]
            
            score = 0.0
            weight_sum = 0.0
            
            if spot_cities:
                city1 = spot_cities.get(spot1, '')
                city2 = spot_cities.get(spot2, '')
                if city1 and city2 and city1 == city2:
                    score += 0.5
                weight_sum += 0.5
            
            if spot_types:
                types1 = set(spot_types.get(spot1, []))
                types2 = set(spot_types.get(spot2, []))
                if types1 and types2:
                    common_types = len(types1 & types2)
                    max_types = max(len(types1), len(types2))
                    type_sim = common_types / max_types if max_types > 0 else 0
                    score += type_sim * 0.5
                weight_sum += 0.5
            
            if weight_sum > 0:
                score = score / weight_sum
                if score >= similarity_threshold:
                    candidates.append((score, spot1, spot2))
    
    candidates.sort(key=lambda x: -x[0])
    
    if max_edges and len(candidates) > max_edges:
        candidates = candidates[:max_edges]
    
    for _, spot1, spot2 in candidates:
        item_edges.append((spot1, spot2))
        item_edges.append((spot2, spot1))
    
    return item_edges


def train_test_split(footprints, test_ratio=0.2, seed=42):
    random.seed(seed)
    train_footprints = {}
    test_data = {}

    for user_id, spots in footprints.items():
        spot_list = list(spots.keys())
        if len(spot_list) < 2:
            train_footprints[user_id] = spots
            continue

        random.shuffle(spot_list)
        
        test_spots = [spot_list[-1]]
        train_spots = spot_list[:-1]

        train_footprints[user_id] = {s: True for s in train_spots}
        test_data[user_id] = test_spots

    return train_footprints, test_data

def train_gnn_model(model_type, edge_index, item_features, num_users, num_items, epochs):
    print(f"\n{'='*60}")
    print(f"训练模型: {model_type}")
    print(f"{'='*60}")

    trainer = ModelTrainer(
        model_type=model_type,
        embedding_dim=EMBEDDING_DIM,
        num_layers=NUM_LAYERS,
        learning_rate=LEARNING_RATE,
        weight_decay=WEIGHT_DECAY
    )
    trainer.init_model(num_users, num_items)
    trainer.model.set_edge_index(edge_index)

    if model_type == 'lightgcn_kg':
        trainer.train(edge_index, item_features, epochs=epochs, batch_size=BATCH_SIZE)
    else:
        trainer.train(edge_index, None, epochs=epochs, batch_size=BATCH_SIZE)

    model_path = os.path.join(SAVE_DIR, f'{model_type}.pt')
    trainer.save_model(model_path)
    print(f"模型已保存: {model_path}")

    return trainer

def train_usercf(edge_index, num_users, num_items):
    print(f"\n{'='*60}")
    print(f"训练模型: UserCF")
    print(f"{'='*60}")

    model = UserCF(k_neighbors=K_NEIGHBORS)
    model.fit(edge_index, num_users, num_items)

    model_path = os.path.join(SAVE_DIR, 'usercf.npz')
    model.save(model_path)
    print(f"模型已保存: {model_path}")

    return model

def main():
    set_seed(RANDOM_SEED)
    os.makedirs(SAVE_DIR, exist_ok=True)

    print("=" * 60)
    print("四模型对比实验 - 统一训练")
    print("=" * 60)

    print("\n[1/5] 初始化数据处理器...")
    data_processor = DataProcessor()

    print("[2/5] 加载用户足迹数据...")
    footprints = None
    use_synthetic = False

    try:
        from app.services.neo4j_service import get_user_footprints_from_mysql
        from app.config.config import SQLALCHEMY_DATABASE_URL
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        engine = create_engine(SQLALCHEMY_DATABASE_URL)
        Session = sessionmaker(bind=engine)
        db = Session()

        try:
            footprints = get_user_footprints_from_mysql(db)
        finally:
            db.close()
    except Exception as e:
        print(f"  从MySQL加载足迹失败: {e}")

    if footprints and len(footprints) >= MIN_USERS:
        print(f"  从MySQL加载用户足迹: {len(footprints)} 个用户")
    else:
        if footprints:
            print(f"  MySQL中仅有 {len(footprints)} 个用户，不足 {MIN_USERS} 个")
        print(f"  生成模拟用户足迹数据 ({MIN_USERS} 个用户)...")
        spot_ids = list(data_processor.spot_id_to_index.keys())

        from app.services.neo4j_service import get_all_spots_from_db
        all_spots = get_all_spots_from_db()
        spot_cities = {sid: info.get('city', 'unknown') for sid, info in all_spots.items()}
        
        spot_types = {}
        for sid, info in all_spots.items():
            types_str = info.get('types', '')
            if types_str:
                types = [t.strip() for t in types_str.split('|') if t.strip()]
                spot_types[sid] = types
            else:
                spot_types[sid] = []

        footprints, spot_subset = generate_synthetic_footprints(
            spot_ids,
            spot_cities=spot_cities,
            spot_types=spot_types,
            num_users=MIN_USERS,
            min_interactions=MIN_INTERACTIONS_PER_USER,
            seed=RANDOM_SEED
        )
        use_synthetic = True
        print(f"  已生成 {len(footprints)} 个模拟用户")
        print(f"  景点子集大小: {len(spot_subset)}")

    print(f"  总用户数: {len(footprints)}")

    print("\n[3/5] 划分训练/测试集...")
    train_footprints, test_data = train_test_split(footprints, TEST_RATIO, RANDOM_SEED)
    print(f"  训练用户数: {len(train_footprints)}")
    print(f"  测试用户数: {len(test_data)}")

    print("\n[4/5] 构建交互图和特征...")
    data_processor.filter_spots_by_footprints(train_footprints)
    edge_index = data_processor.process_user_footprints(train_footprints)
    
    original_edge_count = edge_index.shape[1]
    
    if ADD_SOCIAL_EDGES:
        print("  添加用户社交关系边...")
        social_edges = generate_social_edges(
            train_footprints.keys(),
            train_footprints,
            seed=RANDOM_SEED
        )
        social_edge_list = []
        for user1, user2 in social_edges:
            u1_idx = data_processor.user_id_to_index.get(user1, -1)
            u2_idx = data_processor.user_id_to_index.get(user2, -1)
            if u1_idx != -1 and u2_idx != -1:
                social_edge_list.append([u1_idx, u2_idx])
        if social_edge_list:
            social_edge_tensor = torch.tensor(social_edge_list, dtype=torch.long).t()
            edge_index = torch.cat([edge_index, social_edge_tensor], dim=1)
        print(f"  添加社交边数: {len(social_edge_list) // 2}")
    
    if ADD_ITEM_SIMILARITY_EDGES:
        print("  添加物品相似性边...")
        spot_subset = set()
        for spots in train_footprints.values():
            spot_subset.update(spots.keys())
        
        from app.services.neo4j_service import get_all_spots_from_db
        all_spots = get_all_spots_from_db()
        spot_cities = {sid: info.get('city', 'unknown') for sid, info in all_spots.items()}
        spot_types = {}
        for sid, info in all_spots.items():
            types_str = info.get('types', '')
            if types_str:
                spot_types[sid] = [t.strip() for t in types_str.split('|') if t.strip()]
            else:
                spot_types[sid] = []
        
        max_item_edges = int(original_edge_count * MAX_ITEM_SIM_EDGES_RATIO)
        item_edges = generate_item_similarity_edges(
            spot_subset,
            spot_cities,
            spot_types,
            max_edges=max_item_edges,
            seed=RANDOM_SEED
        )
        item_edge_list = []
        for spot1, spot2 in item_edges:
            s1_idx = data_processor.spot_id_to_index.get(spot1, -1)
            s2_idx = data_processor.spot_id_to_index.get(spot2, -1)
            if s1_idx != -1 and s2_idx != -1:
                s1_idx += data_processor.get_num_users()
                s2_idx += data_processor.get_num_users()
                item_edge_list.append([s1_idx, s2_idx])
        if item_edge_list:
            item_edge_tensor = torch.tensor(item_edge_list, dtype=torch.long).t()
            edge_index = torch.cat([edge_index, item_edge_tensor], dim=1)
        print(f"  添加物品相似边数: {len(item_edge_list) // 2}")
    
    item_features = data_processor.get_item_features()
    num_users = data_processor.get_num_users()
    num_items = data_processor.get_num_items()
    print(f"  用户数: {num_users}, 景点数: {num_items}")
    print(f"  交互边数: {original_edge_count}, 总边数: {edge_index.shape[1]}")
    print(f"  数据密度: {original_edge_count / 2 / (num_users * num_items) * 100:.2f}%")

    filtered_test_data = {}
    total_test_items = 0
    valid_test_items = 0
    for user_id, test_items in test_data.items():
        valid_items = [item for item in test_items if item in data_processor.spot_id_to_index]
        if valid_items:
            filtered_test_data[user_id] = valid_items
        total_test_items += len(test_items)
        valid_test_items += len(valid_items)
    print(f"  测试集物品过滤: {valid_test_items}/{total_test_items} 有效")

    import pickle
    meta_path = os.path.join(SAVE_DIR, 'experiment_meta.pkl')
    with open(meta_path, 'wb') as f:
        pickle.dump({
            'test_data': filtered_test_data,
            'num_users': num_users,
            'num_items': num_items,
            'edge_index': edge_index,
            'item_features': item_features,
            'user_id_to_index': dict(data_processor.user_id_to_index),
            'index_to_user_id': dict(data_processor.index_to_user_id),
            'spot_id_to_index': dict(data_processor.spot_id_to_index),
            'index_to_spot_id': {int(k): v for k, v in data_processor.index_to_spot_id.items()},
            'use_synthetic': use_synthetic,
        }, f)
    print(f"实验元数据已保存: {meta_path}")

    print("\n[5/5] 训练四个模型...")

    usercf_model = train_usercf(edge_index, num_users, num_items)

    gcn_trainer = train_gnn_model('gcn', edge_index, item_features, num_users, num_items, EPOCHS)

    lightgcn_trainer = train_gnn_model('lightgcn', edge_index, item_features, num_users, num_items, EPOCHS)

    lightgcn_kg_trainer = train_gnn_model('lightgcn_kg', edge_index, item_features, num_users, num_items, EPOCHS)

    print("\n" + "=" * 60)
    print("所有模型训练完成！")
    print(f"模型保存目录: {SAVE_DIR}")
    print("请运行 evaluate.py 进行评估对比")
    print("=" * 60)

if __name__ == '__main__':
    main()
