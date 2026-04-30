import torch
import torch.nn as nn
from torch_geometric.nn import GCNConv
import numpy as np

class GCN(nn.Module):
    def __init__(self, num_users, num_items, embedding_dim=64, num_layers=3):
        super(GCN, self).__init__()
        self.num_users = num_users
        self.num_items = num_items
        self.embedding_dim = embedding_dim
        self.num_layers = num_layers

        self.embedding = nn.Embedding(num_users + num_items, embedding_dim)
        nn.init.normal_(self.embedding.weight, std=0.1)

        self.convs = nn.ModuleList()
        for _ in range(num_layers):
            self.convs.append(GCNConv(embedding_dim, embedding_dim, add_self_loops=False))

        self.leaky_relu = nn.LeakyReLU(0.2)

        self.lin_list = nn.ModuleList()
        for _ in range(num_layers):
            self.lin_list.append(nn.Linear(embedding_dim, embedding_dim))

    def forward(self, edge_index):
        x = self.embedding.weight

        emb_list = [x]

        for i, conv in enumerate(self.convs):
            x = conv(x, edge_index)
            x = self.lin_list[i](x)
            x = self.leaky_relu(x)
            emb_list.append(x)

        output = torch.stack(emb_list, dim=0).mean(dim=0)

        user_emb = output[:self.num_users]
        item_emb = output[self.num_users:]

        return user_emb, item_emb

    def predict(self, user_ids, item_ids):
        user_emb, item_emb = self.forward(self.edge_index)

        user_emb = user_emb[user_ids]
        item_emb = item_emb[item_ids]
        scores = (user_emb * item_emb).sum(dim=1)

        return scores

    def recommend(self, user_id, top_k=10, exclude_items=None):
        user_emb, item_emb = self.forward(self.edge_index)

        user_emb = user_emb[user_id].unsqueeze(0)

        scores = torch.matmul(user_emb, item_emb.t()).squeeze()

        if exclude_items is not None:
            scores[exclude_items] = -float('inf')

        _, top_indices = torch.topk(scores, top_k)

        return top_indices.cpu().numpy().tolist()

    def set_edge_index(self, edge_index):
        self.edge_index = edge_index
