# coding=utf-8
import torch
import os
class Checkpoint:
	def __init__(self, checkpoint_dir='', filename=''):
		self.contextual = {}
		self.contextual['b_epoch'] = 0
		self.contextual['b_batch'] = -1
		self.contextual['prec'] = 0
		self.contextual['loss'] = 0
		self.checkpoint_dir = checkpoint_dir
		self.filename=filename
		self.best_prec1 = 0
		self.best=False
	
	def record_contextual(self, contextual):
		self.contextual = contextual
		if self.contextual['prec'] > self.best_prec1:
			self.best = True
			self.best_prec1 = self.contextual['prec']
		else:
			self.best = False


	def save_checkpoint(self, model):
		path = os.path.join(self.checkpoint_dir, self.filename)

		# Save contextual.
		torch.save(self.contextual, path+'_contextual.pth')
		print('...Contextual saved')

		# Save model.
		torch.save(model.state_dict(), path+'.pth')
		print('...Model saved')

		if (self.best):
			torch.save(self.contextual, path+'_contextual_best.pth')
			torch.save(model.state_dict(), path+'_best.pth')
			print('...Best model and contextual saved')

	def load_checkpoint(self, model):
		path = os.path.join(self.checkpoint_dir, self.filename)

		# Load contextual.
		if path and os.path.isfile(path+'_contextual.pth'):
			print("====> Loading checkpoint contextual '{}'...".format(path+'_contextual.pth'))
			self.contextual = torch.load(path+'_contextual.pth')

			# Update best prec.
			if self.contextual['prec'] > self.best_prec1:
				self.best = True
				self.best_prec1 = self.contextual['prec']
			else:
				self.best = False
		else:
			print("====> No checkpoint contextual at '{}'".format(path+'_contextual.pth'))

		# Load model.
		if path and os.path.isfile(path+'.pth'):
			print("====> Loading model '{}'...".format(path+'.pth'))
			model.load_state_dict(torch.load(path+'.pth'))
		else:
			print("====> No pretrain model at '{}'".format(path+'.pth'))
