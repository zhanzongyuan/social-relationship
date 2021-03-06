# coding=utf-8
import os, sys
import numpy as np
import torch
import torch.nn as nn
from torch.autograd import Variable
import torch.nn.functional as F
import numpy as np

class GGNN(nn.Module):
	def __init__(self, hidden_state_channel=10, output_channel=5,
				time_step = 5, adjacency_matrix = '', num_classes = 3):
		super(GGNN, self).__init__()
		self.time_step = time_step
		self.hidden_state_channel = hidden_state_channel
		self.output_channel = output_channel
		self.adjacency_matrix = adjacency_matrix
		self.num_classes = num_classes
		self.num_objects = 80
		self.cnt = 0

		self._in_matrix, self._out_matrix = self.load_nodes(self.adjacency_matrix)

		self._mask = Variable(torch.zeros(self.num_classes, self.num_objects), requires_grad=False).cuda()
		tmp = self._in_matrix[0:self.num_classes, self.num_classes:]  # reason in ggnn
		self._mask[np.where(tmp > 0)] = 1

		self._in_matrix = Variable(torch.from_numpy(self._in_matrix), requires_grad=False).cuda()
		self._out_matrix = Variable(torch.from_numpy(self._out_matrix), requires_grad=False).cuda()

		self.fc_eq3_w = nn.Linear(2*hidden_state_channel, hidden_state_channel)
		self.fc_eq3_u = nn.Linear(hidden_state_channel, hidden_state_channel)
		self.fc_eq4_w = nn.Linear(2*hidden_state_channel, hidden_state_channel)
		self.fc_eq4_u = nn.Linear(hidden_state_channel, hidden_state_channel)
		self.fc_eq5_w = nn.Linear(2*hidden_state_channel, hidden_state_channel)
		self.fc_eq5_u = nn.Linear(hidden_state_channel, hidden_state_channel)

		self.fc_output = nn.Linear(2*hidden_state_channel, output_channel)
		self.ReLU = nn.ReLU(True)

		# self.reason_fc1 = nn.Linear(hidden_state_channel, output_channel)
		self.reason_fc_x = nn.Linear(hidden_state_channel, output_channel)
		self.reason_fc_y = nn.Linear(hidden_state_channel, output_channel)
		self.reason_fc2 = nn.Linear(output_channel, 1)
	
		self._initialize_weights()

	def forward(self, input):
		"""GGNN forward process.

		Args:
			input: It is the graph node hidden status which is initial with feature from rois and [pu, p1, p2, bbox].
					And the object node is initial according to the object's category. Relationship node is initial with the same
					feature of [pu, p1, p2, bbox]. The shape of input is [batch_size x -1].
		"""
		batch_size = input.size()[0]
		input = input.view(-1, self.hidden_state_channel)

		node_num = self._in_matrix.size()[0]  # Number of relationship and object.
		batch_aog_nodes = input.view(-1, node_num, self.hidden_state_channel)  # Shape of [batch_size x node_num x hidden_state_channel].

		batch_in_matrix = self._in_matrix.repeat(batch_size, 1).view(batch_size, node_num, -1)  # view ?
		batch_out_matrix = self._out_matrix.repeat(batch_size, 1).view(batch_size, node_num, -1)

		# propogation process
		for t in xrange(self.time_step):
			"""hints
			torch.bmm: Performs a batch matrix-matrix product of matrices stored in batch1 and batch2.
					batch1 and batch2 must be 3-D tensors each containing the same number of matrices.
					If batch1 is a (b×n×m) tensor, batch2 is a (b×m×p) tensor, out will be a (b×n×p) tensor.
			"""
			
			"""eq(2): av = Av*h + b.

			av: a_v is the aggregate messsage from node v's neightbors. 
				a_v has shape of [batch_size x num_node x hidden_status_channel].
			Av: A_v is the sub-matrix of A that denotes the connetions of node v with its neighbors.
			"""
			av = torch.cat((torch.bmm(batch_in_matrix, batch_aog_nodes), torch.bmm(batch_out_matrix, batch_aog_nodes)), 2)
			av = av.view(batch_size * node_num, -1)

			flatten_aog_nodes = batch_aog_nodes.view(batch_size * node_num, -1)

			# eq(3)
			zv = torch.sigmoid(self.fc_eq3_w(av) + self.fc_eq3_u(flatten_aog_nodes))

			# eq(4)
			rv = torch.sigmoid(self.fc_eq4_w(av) + self.fc_eq3_u(flatten_aog_nodes))

			#eq(5)
			hv = torch.tanh(self.fc_eq5_w(av) + self.fc_eq5_u(rv * flatten_aog_nodes))
			
			flatten_aog_nodes = (1 - zv) * flatten_aog_nodes + zv * hv
			batch_aog_nodes = flatten_aog_nodes.view(batch_size, node_num, -1)

		output = torch.cat((flatten_aog_nodes, input), 1)
		output = self.fc_output(output)
		output = torch.tanh(output)

		####reasoning###
		fan = flatten_aog_nodes.view(batch_size, node_num, -1)
		num_objects = node_num - self.num_classes
		rnode = fan[:, 0:self.num_classes, :].contiguous().view(-1, self.hidden_state_channel) # relationship node
		rfcx = torch.tanh(self.reason_fc_x(rnode))
		rnode_enlarge = rfcx.contiguous().view(batch_size * self.num_classes, 1, -1).repeat(1, num_objects, 1)

		onode = fan[:, self.num_classes:, :].contiguous().view(-1, self.hidden_state_channel) # object node
		rfcy = torch.tanh(self.reason_fc_y(onode))	
		onode_enlarge = rfcy.contiguous().view(batch_size, 1, num_objects, -1).repeat(1, self.num_classes, 1, 1)
		
		rocat = (rnode_enlarge.contiguous().view(-1, self.output_channel)) * (onode_enlarge.contiguous().view(-1, self.output_channel))
		
		rfc2 = self.reason_fc2(rocat)
		rfc2 = torch.sigmoid(rfc2)
		
		mask_enlarge = self._mask.repeat(batch_size, 1, 1).view(-1, 1)
		rfc2 = rfc2 * mask_enlarge
		
		output = output.contiguous().view(batch_size, node_num, -1)
		routput = output[:, 0: self.num_classes, :]
		ooutput = output[:, self.num_classes:, :]
		ooutput_enlarge = ooutput.contiguous().view(batch_size, 1, -1).repeat(1, self.num_classes, 1).view(-1, self.output_channel)
		weight_ooutput = ooutput_enlarge * rfc2
		weight_ooutput = weight_ooutput.view(batch_size, self.num_classes, num_objects, -1)

		final_output = torch.cat((routput.contiguous().view(batch_size, self.num_classes, 1, -1), weight_ooutput), 2)

		return final_output

	def _initialize_weights(self):
		for m in self.reason_fc2.modules():
			if isinstance(m, nn.Linear):
				m.weight.data.normal_(0, 0.1)
				m.bias.data.zero_()
		for m in self.reason_fc_x.modules():
			if isinstance(m, nn.Linear):
				m.weight.data.normal_(0, 0.01)
				m.bias.data.zero_()
		for m in self.reason_fc_y.modules():
			if isinstance(m, nn.Linear):
				m.weight.data.normal_(0, 0.01)
				m.bias.data.zero_()

	def load_nodes(self, file):
		"""Load weight of every edge in graph.

		d_row is the number of relationships.
		d_col is the object of relationships.

		Args:
			file: The file path of graph weigth.
		
		Returns:
			in_matrix: The matrix has the shape of [num_node, num_node]  [relationship => object].
				This is the matrix recording the neightbor nodes connections that point in toward the node.
			out_matrix: The matrix has the shape of [num_node, num_node]  [object => relationship].
				This is the matrix recording the neightbor nodes connections that point out from the node.
		"""
		mat = np.load(file)
		d_row, d_col = mat.shape

		in_matrix = np.zeros((d_row + d_col, d_row + d_col))
		in_matrix[:d_row, d_row:] = mat  # [d_row x d_col]  [relationship x object]
		out_matrix = np.zeros((d_row + d_col, d_row + d_col))
		out_matrix[d_row:, :d_row] = mat.transpose()  # [d_col x d_row]  [object x relationship]

		return in_matrix.astype(np.float32), out_matrix.astype(np.float32)
