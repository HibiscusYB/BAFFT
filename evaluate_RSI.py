import argparse
import scipy
from scipy import ndimage
import numpy as np
import sys
from packaging import version

import torch
from torch.autograd import Variable
import torchvision.models as models
import torch.nn.functional as F
from torch.utils import data, model_zoo
from model.deeplab import Res_Deeplab
from model.deeplab_multi import DeeplabMulti
from model.deeplab_vgg import DeeplabVGG
from model.deeplabv3 import DeepLab
from dataset.cityscapes_dataset import cityscapesDataSet
from dataset.Inria_dataset import InriaDataSet
from dataset.MassBuilding_dataset import MassBuildingDataSet
from dataset.MassRoad_dataset import MassRoadDataSet
from dataset.DeepGlobe_dataset import DeepGlobeDataSet
from collections import OrderedDict
import os
from PIL import Image

import matplotlib.pyplot as plt
import torch.nn as nn
IMG_MEAN = np.array((104.00698793,116.66876762,122.67891434), dtype=np.float32)

DATA_DIRECTORY = '/home/yb/dataset/Massachusetts_Road_dataset' #'/home/yb/dataset/Massachusetts_Building_dataset'
DATA_LIST_PATH = './dataset/MassRoad_list/val.txt'
SAVE_PATH ='./result/DeepGlobe2MassRoad_deeplabv3+' #'./result/MassBuilding2Inria_deeplabv3+' #

IGNORE_LABEL = 255
NUM_CLASSES = 2
NUM_STEPS = 567 # Number of images in the validation set.
RESTORE_FROM = './snapshots_ssl/MassRoad2DeepGlobe_cate_deeplabv3+/Best.pth' #'http://vllab.ucmerced.edu/ytsai/CVPR18/GTA2Cityscapes_multi-ed35151c.pth'
RESTORE_FROM_VGG = 'http://vllab.ucmerced.edu/ytsai/CVPR18/GTA2Cityscapes_vgg-ac4ac9f6.pth'
RESTORE_FROM_ORC = 'http://vllab1.ucmerced.edu/~whung/adaptSeg/cityscapes_oracle-b7b9934.pth'
SET = 'val'

MODEL = 'Deeplabv3+'#'DeeplabMulti'#

palette = [0,0,0,255,255,255]
zero_pad = 256 * 3 - len(palette)
for i in range(zero_pad):
    palette.append(0)


def colorize_mask(mask):
    # mask: numpy array of the mask
    new_mask = Image.fromarray(mask.astype(np.uint8)).convert('P')
    new_mask.putpalette(palette)

    return new_mask

def get_arguments():
    """Parse all the arguments provided from the CLI.

    Returns:
      A list of parsed arguments.
    """
    parser = argparse.ArgumentParser(description="DeepLab-ResNet Network")
    parser.add_argument("--model", type=str, default=MODEL,
                        help="Model Choice (DeeplabMulti/DeeplabVGG/Oracle).")
    parser.add_argument("--data-dir", type=str, default=DATA_DIRECTORY,
                        help="Path to the directory containing the Cityscapes dataset.")
    parser.add_argument("--data-list", type=str, default=DATA_LIST_PATH,
                        help="Path to the file listing the images in the dataset.")
    parser.add_argument("--ignore-label", type=int, default=IGNORE_LABEL,
                        help="The index of the label to ignore during the training.")
    parser.add_argument("--num-classes", type=int, default=NUM_CLASSES,
                        help="Number of classes to predict (including background).")
    parser.add_argument("--restore-from", type=str, default=RESTORE_FROM,
                        help="Where restore model parameters from.")
    parser.add_argument("--gpu", type=int, default=0,
                        help="choose gpu device.")
    parser.add_argument("--set", type=str, default=SET,
                        help="choose evaluation set.")
    parser.add_argument("--save", type=str, default=SAVE_PATH,
                        help="Path to save result.")
    return parser.parse_args()


def main():
    """Create the model and start the evaluation process."""

    args = get_arguments()

    gpu0 = args.gpu

    if not os.path.exists(args.save):
        os.makedirs(args.Inriasave)

    if args.model == 'DeeplabMulti':
        model = DeeplabMulti(num_classes=args.num_classes)
    elif args.model == 'Deeplabv3+':
        model = DeepLab(backbone='resnet', output_stride=16, num_classes=args.num_classes)
    elif args.model == 'Oracle':
        model = Res_Deeplab(num_classes=args.num_classes)
        if args.restore_from == RESTORE_FROM:
            args.restore_from = RESTORE_FROM_ORC
    elif args.model == 'DeeplabVGG':
        model = DeeplabVGG(num_classes=args.num_classes)
        if args.restore_from == RESTORE_FROM:
            args.restore_from = RESTORE_FROM_VGG

    if args.restore_from[:4] == 'http' :
        saved_state_dict = model_zoo.load_url(args.restore_from)
    else:
        saved_state_dict = torch.load(args.restore_from)
    model.load_state_dict(saved_state_dict)

    model.eval()
    model.cuda(gpu0)

    testloader = data.DataLoader(MassRoadDataSet(args.data_dir, args.data_list, crop_size=(512,512), mean=IMG_MEAN, scale=False, mirror=False),
                                    batch_size=1, shuffle=False, pin_memory=True)


    if version.parse(torch.__version__) >= version.parse('0.4.0'):
        interp = nn.Upsample(size=(500,500), mode='bilinear', align_corners=True)
    else:
        interp = nn.Upsample(size=(500,500), mode='bilinear')

    for index, batch in enumerate(testloader):
        if index % 100 == 0:
            print ('%d processd' % index)
        image, _,_, name = batch
        if args.model == 'DeeplabMulti':
            with torch.no_grad():
                output1, output2 = model(Variable(image).cuda(gpu0))
            output = interp(output2).cpu().data[0].numpy()
        elif args.model == 'Deeplabv3+':
            with torch.no_grad():
                output1, output2 = model(Variable(image).cuda(gpu0))
            output = interp(output2).cpu().data[0].numpy()
        elif args.model == 'DeeplabVGG' or args.model == 'Oracle':
            output = model(Variable(image, volatile=True).cuda(gpu0))
            output = interp(output).cpu().data[0].numpy()

        output = output.transpose(1,2,0)
        output = np.asarray(np.argmax(output, axis=2), dtype=np.uint8)

        output_col = colorize_mask(output)
        output = Image.fromarray(output)

        name = name[0].split('/')[-1]+'.png'
        output.save('%s/%s' % (args.save, name))
        output_col.save('%s/%s_color.png' % (args.save, name.split('.')[0]))


if __name__ == '__main__':
    main()