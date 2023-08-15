# -*- coding: utf-8 -*-
"""Hypergraph convolution.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/19p4pELrfwR2az0cwZHp5wQZ6gEePK5ih
"""

from torch.nn import Parameter
from torch_geometric.nn.dense.linear import Linear


def trans_to_cuda(variable):
    if torch.cuda.is_available():
        return variable.cuda()
    else:
        return variable
def trans_to_cpu(variable):
    if torch.cuda.is_available():
        return variable.cpu()
    else:
        return variable
from torch_geometric import nn
import torch
import torch.nn.functional as F
import torch.nn


class HW_Attention(torch.nn.Module):

    def __init__(self, dimensions,nodenumber,attention_type='general'):
        super(HW_Attention, self).__init__()

        if attention_type not in ['dot', 'general']:
            raise ValueError('Invalid attention type selected.')

        self.attention_type = attention_type
        if self.attention_type == 'general':
            self.linear_in = torch.nn.Linear(dimensions, dimensions, bias=False).to(device="cuda:0")

        self.linear_out = torch.nn.Linear(dimensions * 2, dimensions, bias=False).to(device="cuda:0")
        self.softmax = torch.nn.Softmax(dim=-1)
        self.tanh = torch.nn.Tanh()
        self.nodenumber = nodenumber
        self.ae = torch.nn.Parameter(torch.FloatTensor(self.nodenumber,1,1).to(device="cuda:0"))
        self.ab = torch.nn.Parameter(torch.FloatTensor(self.nodenumber,1,1).to(device="cuda:0"))

    def forward(self, query, context ):

        batch_size, output_len, dimensions = query.size()
        query_len = context.size(1)

        if self.attention_type == "general":
            query = query.reshape(batch_size * output_len, dimensions)
            query = self.linear_in(query.to(device="cuda:0"))

        attention_scores = torch.bmm(query, context.transpose(1, 2).contiguous())
        attention_scores = attention_scores.view(batch_size * output_len, query_len)
        attention_weights = self.softmax(attention_scores)

        attention_weights = attention_weights.view(batch_size, output_len, query_len)
        mix = attention_weights*(context.permute(0,2,1))
        delta_t = torch.flip(torch.arange(0, query_len), [0]).type(torch.float32)
        delta_t = delta_t.repeat(self.nodenumber,1).reshape(self.nodenumber,1,query_len)
        bt = torch.exp(-1*self.ab.to(device="cuda:0") * delta_t.to(device="cuda:0"))
        term_2 = F.relu(self.ae * mix * bt)
        mix = torch.sum(term_2+mix, -1).unsqueeze(1)
        combined = torch.cat((mix, query), dim=2)
        combined = combined.view(batch_size * output_len, 2 * dimensions)
        output = self.linear_out(combined).view(batch_size, output_len, dimensions)
        output = self.tanh(output)
        return output, attention_weights

class gruf(torch.nn.Module):
    def __init__(self, input_size, hidden_size):
        super(gruf, self).__init__()
        self.gru1 = torch.nn.GRU(input_size = input_size, hidden_size=hidden_size, batch_first=False).to(device="cuda:0")
    def forward(self, inputsx):

        full, last  = self.gru1(inputsx)
        return full,last


class HyperConv(Module):
    def __init__(self,inputx):
        super(HyperConv, self).__init__()
        self.emb_size = emb_size
        self.layers = 1
        self.heads = 4
        self.negative_slope = 0.2
        self.dropout = 0.5
        self.in_channels = 32
        self.out_channels = 32

        self.lin = Linear(self.in_channels, self.heads * self.out_channels, bias=False,
                             weight_initializer='glorot')

        self.att = Parameter(torch.Tensor(1, self.heads, 2 * self.out_channels))
        self.train_adjacency = inputx

    def forward(self):
        emb_size = self.train_adjacency.shape[1]
        print(emb_size)
        n_node = self.train_adjacency.shape[0]
        embedding = torch.nn.Embedding(2000,2000)
        values = self.train_adjacency.data
        print(values)
        indices = np.vstack((self.train_adjacency.row, self.train_adjacency.col))
        index_fliter = (values < 0.05).nonzero()
        values = np.delete(values, index_fliter)
        indices1 = np.delete(indices[0], index_fliter)
        indices2 = np.delete(indices[1], index_fliter)
        indices = [indices1, indices2]
        i = torch.LongTensor(indices)
        v = torch.FloatTensor(values)
        attention= HW_Attention(n_node,emb_size)
        shape = (1000,2000)
        adjacency = torch.sparse.FloatTensor(i, v, torch.Size(shape))
        item_embeddings = embedding.weight
        item_embedding_layer0 = item_embeddings
        final = [item_embedding_layer0]
        for i in range(self.layers):
            item_embeddings = torch.sparse.mm(trans_to_cuda(adjacency),item_embeddings.to(device="cuda:0"))
            final.append(item_embeddings)
        item_embedding=item_embeddings.unsqueeze(1)
        print(item_embedding.shape)
        item_embedding=item_embedding.reshape(1,n_node,emb_size)
        print(item_embedding.shape)
        self.grup = gruf(2000,2000)
        self.liear2 = torch.nn.Linear(2000,2000).to(device="cpu")
        context,query  = self.grup(item_embedding.to(device="cuda:0"))
        context=context.reshape(emb_size,1,n_node)
        query = query.reshape(emb_size,1,n_node)
        output, weights = attention(query.to(device="cuda:0"), context.to(device="cuda:0"))
        output = (output.reshape((n_node,emb_size)))
        output = self.liear2(output.cpu())

        return output