import torch
import os
import argparse
import tqdm
import sys
import cv2

import torch.nn.functional as F
import numpy as np

from PIL import Image

filepath = os.path.split(__file__)[0]
repopath = os.path.split(filepath)[0]
sys.path.append(repopath)

from lib import *
from utils.utils import *
from utils.dataloader import *
from utils.custom_transforms import *

def _args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=str, default='configs/InSPyReNet_SwinB.yaml')
    parser.add_argument('--source', type=str)
    parser.add_argument('--type', type=str, choices=['rgba', 'map', 'green'], default='map')
    parser.add_argument('--grid', action='store_true', default=False)
    parser.add_argument('--fix', action='store_true', default=False)
    parser.add_argument('--gpu', action='store_true', default=False)
    parser.add_argument('--verbose', action='store_true', default=False)
    return parser.parse_args()

def get_format(source):
    img_count = len([i for i in source if i.endswith(('.jpg', '.png', '.jpeg'))])
    vid_count = len([i for i in source if i.endswith(('.mp4', '.avi', '.mov'))])
    
    if img_count * vid_count != 0:
        return None
    elif img_count != 0:
        return 'Image'
    elif vid_count != 0:
        return 'Video'

def inference(opt, args):
    model = eval(opt.Model.name)(channels=opt.Model.channels,
                                pretrained=False)
    model.load_state_dict(torch.load(os.path.join(
        opt.Test.Checkpoint.checkpoint_dir, 'latest.pth'), map_location=torch.device('cpu')), strict=True)
    
    if args.gpu is True:
        model.cuda()
    model.eval()
    # model.zero_grad(set_to_none=True)
    
    if args.grid is True:
        model = InSPyReNet_Grid(model, opt.Test.Dataset.transforms.dynamic_resize.base_size)
        
    if args.fix is True:
        model = InSPyReNet_Fix(model, 384)

    if args.source.isnumeric() is True:
        save_dir = None
        _format = 'Webcam'

    elif os.path.isdir(args.source):
        save_dir = os.path.join('results', args.source.split(os.sep)[-1])
        _format = get_format(os.listdir(args.source))

    elif os.path.isfile(args.source):
        save_dir = 'results'
        _format = get_format([args.source])
        
    else:
        return

    if save_dir is not None:
        os.makedirs(save_dir, exist_ok=True)
    
    source_list = eval(_format + 'Loader')(args.source, opt.Test.Dataset.transforms)

    if args.verbose is True:
        sources = tqdm.tqdm(source_list, desc='Inference', total=len(
            source_list), position=1, leave=False, bar_format='{desc:<30}{percentage:3.0f}%|{bar:50}{r_bar}')
    else:
        sources = source_list
        
    writer = None
        
    for source in sources:
        if _format == 'Video' and writer is None:
            writer = cv2.VideoWriter(os.path.join(save_dir, source['name']), cv2.VideoWriter_fourcc(*'mp4v'), source_list.fps, source['shape'][::-1])            
        if _format == 'Video' and source['image'] is None:
            writer.release()
            writer = None
            continue
        
        if args.gpu is True:
            sample = to_cuda(source)
        else:
            sample = source

        with torch.no_grad():
            out = model(sample)
        pred = to_numpy(out['pred'], sample['shape'])
            
        # pred =    
        # print(pred.mean())

        if args.type == 'map':
            img = (np.stack([pred] * 3, axis=-1) * 255).astype(np.uint8)
        elif args.type == 'rgba':
            img = np.array(sample['original'])
            r, g, b = cv2.split(img)
            pred = (pred * 255).astype(np.uint8)
            img = cv2.merge([r, g, b, pred])
        elif args.type == 'green':
            bg = np.stack([np.zeros_like(pred), np.ones_like(pred), np.zeros_like(pred)], axis=-1) * 255
            img = np.array(sample['original'])
            img = img * pred[..., np.newaxis] + bg * (1 - pred[..., np.newaxis])
            img = img.astype(np.uint8)
        else:
            img = None
            
        # img = cv2.putText(img, '{:.4f}'.format(pred.mean()), (10, 10), 1, 1, color=(0, 0, 0))

        if _format == 'Image':
            Image.fromarray(img).save(os.path.join(save_dir, sample['name']))
        elif _format == 'Video':
            writer.write(img)
        elif _format == 'Webcam':
            cv2.imshow('InSPyReNet', img)
            

if __name__ == "__main__":
    args = _args()
    opt = load_config(args.config)
    inference(opt, args)
