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
        nn.init.normal_(self.embedding.weight, std=0.1)# 正态分布初始化嵌入权重

        self.convs = nn.ModuleList()# 创建GCN卷积层列表，保存多层gcn
        for _ in range(num_layers):
            #add_self_loops=False表示不添加自环边，节点不会给自己传播信息
            self.convs.append(GCNConv(embedding_dim, embedding_dim, add_self_loops=False))

        self.leaky_relu = nn.LeakyReLU(0.2)

        self.lin_list = nn.ModuleList()# 创建线性层列表，每层GCN卷积后都跟一个线性变换，保持维度不变
        for _ in range(num_layers):
            self.lin_list.append(nn.Linear(embedding_dim, embedding_dim))

    def forward(self, edge_index):
        x = self.embedding.weight

        emb_list = [x]

        for i, conv in enumerate(self.convs):
            x = conv(x, edge_index)#聚合邻居节点信息
            x = self.lin_list[i](x)#线性变换y=Wx+b，增加模型表达能力
            x = self.leaky_relu(x)#非线性激活函数，增加模型的非线性表达能力
            emb_list.append(x)#保存每层GCN卷积后的节点嵌入，最后将所有层的嵌入进行平均，得到最终的节点表示
        #融合所有层的嵌入，得到最终的节点表示，平均融合可以缓解过拟合问题，同时保留不同层次的信息
        output = torch.stack(emb_list, dim=0).mean(dim=0)

        user_emb = output[:self.num_users]
        item_emb = output[self.num_users:]

        return user_emb, item_emb

    def predict(self, user_ids, item_ids):
        user_emb, item_emb = self.forward(self.edge_index)

        user_emb = user_emb[user_ids]
        item_emb = item_emb[item_ids]
        #计算用户和物品嵌入的点积作为预测评分，点积可以捕捉用户和物品之间的相似性，分数越高表示用户对物品的兴趣越大
        scores = (user_emb * item_emb).sum(dim=1)

        return scores

    def recommend(self, user_id, top_k=10, exclude_items=None):
        user_emb, item_emb = self.forward(self.edge_index)

        #unsqueeze(0)，在第零维增加一个维度，使得user_emb的形状从(num_users, embedding_dim)变为(1, embedding_dim)
        user_emb = user_emb[user_id].unsqueeze(0)

        #计算与所有景点相似度，得到用户与所有景点的得分
        scores = torch.matmul(user_emb, item_emb.t()).squeeze()

        if exclude_items is not None:
            scores[exclude_items] = -float('inf')

        _, top_indices = torch.topk(scores, top_k)

        return top_indices.cpu().numpy().tolist()

    #保存图结构，供后续使用
    def set_edge_index(self, edge_index):
        self.edge_index = edge_index
