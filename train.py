from multiprocessing.spawn import freeze_support

import torch
from torch import nn
from torch.utils.data import DataLoader
from tqdm import tqdm
from data_util import TrainDataset
import network
import argparse
import os

parser = argparse.ArgumentParser()

parser.add_argument('--crop_size', default=96, type=int, help='training images crop size')
parser.add_argument('--block_size', default=32, type=int, help='CS block size')
parser.add_argument('--sub_rate', default=0.1, type=float, help='sampling sub rate')
parser.add_argument('--batchsize', default=64, type=int, help='train batch size')
parser.add_argument('--num_epochs', default=100, type=int)
parser.add_argument('--load_epochs', default=0, type=int)
opt = parser.parse_args()

CROP_SIZE = opt.crop_size
BLOCK_SIZE = opt.block_size
NUM_EPOCHS = opt.num_epochs
LOAD_EPOCHS = opt.load_epochs

dataset = TrainDataset('processed_images', CROP_SIZE, BLOCK_SIZE)

batchsize = 64
train_dataloader = DataLoader(dataset, num_workers=0, batch_size=batchsize, shuffle=True)

'''
for X in train_dataloader:
    print(f"Shape of X [N, C, H, W]: {X.shape}")
    break
'''
device = (
    "cuda"
    if torch.cuda.is_available()
    else "mps"
    if torch.backends.mps.is_available()
    else "cpu"
)

net = network.CSNet(BLOCK_SIZE, opt.sub_rate).to(device)
print(net)

loss_fn = nn.MSELoss()
loss_fn.to(device)

optimizer = torch.optim.Adam(net.parameters(), 0.0004, betas=(0.9, 0.999))
scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=30, gamma=0.5)
best_pth = 99999

for epoch in range(LOAD_EPOCHS, NUM_EPOCHS + 1):
    train_bar = tqdm(train_dataloader)
    # print(train_bar)
    running_res = {'batch_size': 0, 'g_loss': 0, }
    net.train()
    # scheduler.step()
    for data, target in train_bar:
        # print(target)
        batch_size = data.size(0)
        if batch_size <= 0:
            continue
        running_res['batch_size'] += batch_size
        target = target.to(device)
        data = data.to(device)
        optimizer.zero_grad()
        fake_img = net(data).to(device)
        g_loss = loss_fn(fake_img, target)
        g_loss.backward()
        optimizer.step()
        scheduler.step()

        running_res['g_loss'] += g_loss.item() * batch_size

        train_bar.set_description(desc='[%d] Loss_G: %.4f lr: %.7f' % (
            epoch, running_res['g_loss'] / running_res['batch_size'], optimizer.param_groups[0]['lr']))
        save_dir = 'epochs' + '_subrate_' + str(opt.sub_rate) + '_blocksize_' + str(BLOCK_SIZE)
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
        if epoch % 5 == 0:
            if running_res['g_loss'] / running_res['batch_size'] < best_pth:
                best_pth = running_res['g_loss'] / running_res['batch_size']
                torch.save(net.state_dict(),
                           save_dir + '/A_BEST_%d_%6f.pth' % (epoch, running_res['g_loss'] / running_res['batch_size']))
            else:
                torch.save(net.state_dict(), save_dir + '/net_epoch_%d_%6f.pth' % (
                    epoch, running_res['g_loss'] / running_res['batch_size']))
