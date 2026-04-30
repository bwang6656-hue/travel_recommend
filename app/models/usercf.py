import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import torch

class UserCF:
    def __init__(self, k_neighbors=20):
        self.k_neighbors = k_neighbors
        self.user_similarity = None
        self.interaction_matrix = None
        self.num_users = 0
        self.num_items = 0

    def fit(self, edge_index, num_users, num_items):
        self.num_users = num_users
        self.num_items = num_items

        self.interaction_matrix = np.zeros((num_users, num_items), dtype=np.float32)

        if isinstance(edge_index, torch.Tensor):
            edge_index = edge_index.cpu().numpy()

        for i in range(edge_index.shape[1]):
            user_idx = edge_index[0, i]
            item_idx = edge_index[1, i]
            if user_idx < num_users and item_idx >= num_users:
                self.interaction_matrix[user_idx, item_idx - num_users] = 1.0

        self.user_similarity = cosine_similarity(self.interaction_matrix)

        np.fill_diagonal(self.user_similarity, 0)

    def predict(self, user_id, item_ids):
        if self.user_similarity is None:
            raise RuntimeError("Model not fitted yet. Call fit() first.")

        sim_scores = self.user_similarity[user_id]
        top_k_indices = np.argsort(sim_scores)[-self.k_neighbors:]
        top_k_sims = sim_scores[top_k_indices]

        scores = []
        for item_id in item_ids:
            item_col = self.interaction_matrix[:, item_id]
            numerator = np.sum(top_k_sims * item_col[top_k_indices])
            denominator = np.sum(np.abs(top_k_sims)) + 1e-8
            scores.append(numerator / denominator)

        return np.array(scores)

    def recommend(self, user_id, top_k=10, exclude_items=None):
        if self.user_similarity is None:
            raise RuntimeError("Model not fitted yet. Call fit() first.")

        sim_scores = self.user_similarity[user_id]
        top_k_neighbor_indices = np.argsort(sim_scores)[-self.k_neighbors:]
        top_k_sims = sim_scores[top_k_neighbor_indices]

        all_item_scores = np.zeros(self.num_items)
        for i, neighbor_idx in enumerate(top_k_neighbor_indices):
            all_item_scores += top_k_sims[i] * self.interaction_matrix[neighbor_idx]

        if exclude_items is not None:
            for item_idx in exclude_items:
                if 0 <= item_idx < self.num_items:
                    all_item_scores[item_idx] = -float('inf')

        top_indices = np.argsort(all_item_scores)[-top_k:][::-1]

        return top_indices.tolist()

    def save(self, path):
        import os
        os.makedirs(os.path.dirname(path), exist_ok=True)
        np.savez(
            path,
            user_similarity=self.user_similarity,
            interaction_matrix=self.interaction_matrix,
            num_users=self.num_users,
            num_items=self.num_items,
            k_neighbors=self.k_neighbors
        )

    def load(self, path):
        if not path.endswith('.npz'):
            path = path + '.npz'
        data = np.load(path, allow_pickle=True)
        self.user_similarity = data['user_similarity']
        self.interaction_matrix = data['interaction_matrix']
        self.num_users = int(data['num_users'])
        self.num_items = int(data['num_items'])
        self.k_neighbors = int(data['k_neighbors'])
