import torch
import torch.nn as nn
import torch.optim as optim
from app.models.lightgcn import LightGCN
from app.models.lightgcn_kg import LightGCNWithKG
from app.models.gcn import GCN
from app.services.data_service import data_processor
import os
import numpy as np

class ModelTrainer:
    def __init__(self, model_type='lightgcn_kg', embedding_dim=64, num_layers=3, learning_rate=0.001, weight_decay=1e-4):
        self.model_type = model_type
        self.embedding_dim = embedding_dim
        self.num_layers = num_layers
        self.learning_rate = learning_rate
        self.weight_decay = weight_decay
        self.model = None
        self.optimizer = None
        self._item_popularity = None
        self._neg_sampling_weights = None

    def init_model(self, num_users, num_items):
        if self.model_type == 'lightgcn':
            self.model = LightGCN(
                num_users=num_users,
                num_items=num_items,
                embedding_dim=self.embedding_dim,
                num_layers=self.num_layers
            )
        elif self.model_type == 'lightgcn_kg':
            self.model = LightGCNWithKG(
                num_users=num_users,
                num_items=num_items,
                embedding_dim=self.embedding_dim,
                num_layers=self.num_layers
            )
        elif self.model_type == 'gcn':
            self.model = GCN(
                num_users=num_users,
                num_items=num_items,
                embedding_dim=self.embedding_dim,
                num_layers=self.num_layers
            )
        else:
            raise ValueError(f"Unknown model_type: {self.model_type}. Supported: 'lightgcn', 'lightgcn_kg', 'gcn'")

        self.optimizer = optim.Adam(
            self.model.parameters(),
            lr=self.learning_rate,
            weight_decay=self.weight_decay
        )

    def _build_popularity_weights(self, edge_index, num_users, num_items):
        item_counts = torch.zeros(num_items, dtype=torch.float32)
        user_indices = edge_index[0]
        item_indices = edge_index[1]
        mask = (user_indices < num_users) & (item_indices >= num_users)
        pos_item_indices = item_indices[mask] - num_users
        for idx in pos_item_indices:
            item_counts[idx] += 1
        
        item_counts = torch.pow(item_counts + 1, 0.75)
        total = item_counts.sum()
        if total > 0:
            self._neg_sampling_weights = item_counts / total
        else:
            self._neg_sampling_weights = None

    def train(self, edge_index, item_features=None, epochs=100, batch_size=2048):
        self.model.train()
        
        num_users = self.model.num_users
        num_items = self.model.num_items
        self._build_popularity_weights(edge_index, num_users, num_items)

        for epoch in range(epochs):
            self.optimizer.zero_grad()

            if self.model_type == 'lightgcn_kg':
                user_emb, item_emb = self.model(edge_index, item_features)
            else:
                user_emb, item_emb = self.model(edge_index)

            loss = self.bpr_loss(user_emb, item_emb, edge_index)

            loss.backward()
            self.optimizer.step()

            if (epoch + 1) % 10 == 0:
                print(f"  Epoch {epoch+1}/{epochs}, Loss: {loss.item():.4f}")

    def bpr_loss(self, user_emb, item_emb, edge_index):
        num_users = user_emb.shape[0]
        num_items = item_emb.shape[0]
        
        user_indices = edge_index[0]
        item_indices = edge_index[1]
        
        mask = (user_indices < num_users) & (item_indices >= num_users)
        
        user_indices = user_indices[mask]
        pos_item_indices = item_indices[mask] - num_users
        
        if pos_item_indices.shape[0] == 0:
            return torch.tensor(0.0, requires_grad=True)
        
        if self._neg_sampling_weights is not None:
            neg_indices = torch.multinomial(self._neg_sampling_weights, pos_item_indices.shape[0], replacement=True)
        else:
            neg_indices = torch.randint(0, num_items, (pos_item_indices.shape[0],), device=user_emb.device)

        pos_scores = (user_emb[user_indices] * item_emb[pos_item_indices]).sum(dim=1)
        neg_scores = (user_emb[user_indices] * item_emb[neg_indices]).sum(dim=1)

        loss = -torch.log(torch.sigmoid(pos_scores - neg_scores) + 1e-8).mean()

        return loss

    def evaluate(self, test_data, top_k=10, item_features=None):
        self.model.eval()

        with torch.no_grad():
            precision, recall, ndcg, hit_ratio = self.calculate_metrics(test_data, top_k, item_features)

            print(f"Precision@{top_k}: {precision:.4f}")
            print(f"Recall@{top_k}: {recall:.4f}")
            print(f"Hit Ratio@{top_k}: {hit_ratio:.4f}")
            print(f"NDCG@{top_k}: {ndcg:.4f}")

            return precision, recall, ndcg, hit_ratio

    def calculate_metrics(self, test_data, top_k, item_features=None):
        precision_list = []
        recall_list = []
        ndcg_list = []
        hit_list = []

        for user_id, test_items in test_data.items():
            user_idx = data_processor.user_id_to_idx(user_id)
            if user_idx == -1:
                continue

            exclude_items = [data_processor.spot_id_to_idx(spot_id) for spot_id in test_items]
            exclude_items = [idx for idx in exclude_items if idx != -1]

            train_items = self._get_train_items(user_idx, exclude_items)

            if self.model_type == 'lightgcn_kg':
                recommendations = self.model.recommend(user_idx, top_k, train_items, item_features)
            else:
                recommendations = self.model.recommend(user_idx, top_k, train_items)

            recommended_spot_ids = [data_processor.idx_to_spot_id(idx) for idx in recommendations]

            intersection = set(recommended_spot_ids) & set(test_items)
            precision = len(intersection) / top_k
            recall = len(intersection) / len(test_items) if len(test_items) > 0 else 0
            hit = 1 if len(intersection) > 0 else 0
            ndcg = self.calculate_ndcg(recommended_spot_ids, test_items, top_k)

            precision_list.append(precision)
            recall_list.append(recall)
            ndcg_list.append(ndcg)
            hit_list.append(hit)

        if not precision_list:
            return 0, 0, 0, 0

        return (
            sum(precision_list) / len(precision_list),
            sum(recall_list) / len(recall_list),
            sum(ndcg_list) / len(ndcg_list),
            sum(hit_list) / len(hit_list)
        )

    def _get_train_items(self, user_idx, test_item_indices):
        edge_index = self.model.edge_index
        train_items = set()
        if isinstance(edge_index, torch.Tensor):
            edge_np = edge_index.cpu().numpy()
            for i in range(edge_np.shape[1]):
                if edge_np[0, i] == user_idx:
                    item_idx = edge_np[1, i] - self.model.num_users
                    if item_idx not in test_item_indices:
                        train_items.add(item_idx)
        return list(train_items)

    def calculate_ndcg(self, recommendations, ground_truth, top_k):
        dcg = 0.0
        idcg = 0.0

        for i, item in enumerate(recommendations[:top_k]):
            if item in ground_truth:
                dcg += 1.0 / np.log2(i + 2)

        for i in range(min(len(ground_truth), top_k)):
            idcg += 1.0 / np.log2(i + 2)

        return dcg / idcg if idcg > 0 else 0.0

    def save_model(self, path):
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else '.', exist_ok=True)
        torch.save({
            'model_type': self.model_type,
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict()
        }, path)

    def load_model(self, path):
        checkpoint = torch.load(path, weights_only=False)
        self.model_type = checkpoint.get('model_type', self.model_type)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])

    def get_model(self):
        return self.model

model_trainer = ModelTrainer()
