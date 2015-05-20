#1. change fully connected model into all conv model.
#2. given an image, load model, get the heat map.
#3. using nms-max to get the final bounding box and score.
import numpy as np
import matplotlib.pyplot as plt
#import Image
import sys
import PIL
import operator
from PIL import Image, ImageDraw
caffe_root = '../'

sys.path.insert(0, caffe_root + 'python')
import caffe
caffe.set_mode_cpu()
#configure plotting
plt.rcParams['figure.figsize'] = (10, 10)
plt.rcParams['image.interpolation'] = 'nearest'
plt.rcParams['image.cmap']='gray'





#helper show filter outputs
def show_filters(net):
	net.forward()
	plt.figure()
	filt_min, filt_max = net.blobs['conv'].data.min(), net.blobs['conv'].data.max()
	for i in range(3): # three feature map.
		plt.subplot(1,4,i+2)
		plt.title("filter #{} output".format(i))
		plt.imshow(net.blobs['conv'].data[0,i], vmin=filt_min, vmax=filt_max)
		plt.tight_layout()
		plt.axis('off')
		plt.show()


def generateBoundingBox(featureMap, scale):
    boundingBox = []
    stride = 32
    cellSize = 227
    #227 x 227 cell, stride=32
    for (x,y), prob in np.ndenumerate(featureMap):
       if(prob >= 0.5):
            boundingBox.append([float(stride * y)/ scale, float(x * stride)/scale, float(stride * y + cellSize - 1)/scale, float(stride * x + cellSize - 1)/scale, prob])
    #sort by prob, from max to min.
    #boxes = np.array(boundingBox)
    return boundingBox

def nms_max(boxes, overlapThresh=0.2):
    if len(boxes) == 0:
        return []

    # if the bounding boxes integers, convert them to floats --
    # this is important since we'll be doing a bunch of divisions
    #if boxes.dtype.kind == "i":
    #    boxes = boxes.astype("float")

    # initialize the list of picked indexes
    pick = []

    # grab the coordinates of the bounding boxes
    x1 = boxes[:,0]
    y1 = boxes[:,1]
    x2 = boxes[:,2]
    y2 = boxes[:,3]

    # compute the area of the bounding boxes and sort the bounding
    # boxes by the bottom-right y-coordinate of the bounding box
    area = (x2 - x1 + 1) * (y2 - y1 + 1)
    idxs = np.argsort(boxes[:,4])

    # keep looping while some indexes still remain in the indexes
    # list
    while len(idxs) > 0:
        # grab the last index in the indexes list and add the
        # index value to the list of picked indexes
        last = len(idxs) - 1
        i = idxs[last]
        pick.append(i)

        # find the largest (x, y) coordinates for the start of
        # the bounding box and the smallest (x, y) coordinates
        # for the end of the bounding box
        xx1 = np.maximum(x1[i], x1[idxs[:last]])
        yy1 = np.maximum(y1[i], y1[idxs[:last]])
        xx2 = np.minimum(x2[i], x2[idxs[:last]])
        yy2 = np.minimum(y2[i], y2[idxs[:last]])

         # compute the width and height of the bounding box
        w = np.maximum(0, xx2 - xx1 + 1)
        h = np.maximum(0, yy2 - yy1 + 1)
        #area of i.
        area_i = np.maximum(0, x2[i] - x1[i] + 1) * np.maximum(0, y2[i] - y1[i] + 1)
        area_array = np.zeros(len(idxs) - 1)
        area_array.fill(area_i)
        # compute the ratio of overlap
        #overlap = (w * h) / (area[idxs[:last]]  - w * h + area_array)
        overlap = (w * h) / (area[idxs[:last]])
        # delete all indexes from the index list that have
        idxs = np.delete(idxs, np.concatenate(([last],np.where(overlap > overlapThresh)[0])))

    # return only the bounding boxes that were picked using the
    # integer data type
    #result = np.delete(boxes[pick],np.where(boxes[pick][:, 4] < 0.9)[0],  axis=0)
    #print boxes[pick]
    return boxes[pick]

def convert_full_conv():
 # Load the original network and extract the fully connected layers' parameters.
    net = caffe.Net('net_surgery/deploy.prototxt',
                    'net_surgery/alexNet__iter_60000.caffemodel',
                    caffe.TEST)
    params = ['fc6', 'fc7', 'fc8_flickr']
    fc_params = {pr: (net.params[pr][0].data, net.params[pr][1].data) for pr in params}
    # Load the fully convolutional network to transplant the parameters.
    net_full_conv = caffe.Net('net_surgery/face_full_conv2.prototxt',
                              'net_surgery/face_full_conv.caffemodel',
                              caffe.TEST)
    params_full_conv = ['fc6-conv', 'fc7-conv', 'fc8-conv']
    conv_params = {pr: (net_full_conv.params[pr][0].data, net_full_conv.params[pr][1].data) for pr in params_full_conv}
    for pr, pr_conv in zip(params, params_full_conv):
       conv_params[pr_conv][0].flat = fc_params[pr][0].flat  # flat unrolls the arrays
       conv_params[pr_conv][1][...] = fc_params[pr][1]
    net_full_conv.save('net_surgery/face_full_conv.caffemodel')

def face_detection(imgFile):
    scales = []
    factor = 0.793700526
    img = Image.open(imgFile)
    min = 0
    if(img.size[0] > img.size[1]):
        min = img.size[1]
    else:
        min = img.size[0]
    scales.append(1)
    scales.append(3)
    min = min * factor
    factor_count = 1
    while(min >= 227):
        scales.append(factor * factor_count)
        min = min * factor
        factor_count += 1
    total_boxes = []
    for scale in scales:
        #resize image
        scale_img = img.resize((int(img.size[0] * scale), int(img.size[1] * scale)))
        scale_img.save("tmp.jpg")
        #modify the full_conv prototxt.
        prototxt = open('net_surgery/face_full_conv.prototxt', 'r')
        new_line = ""
        for i, line in enumerate(prototxt):
            if i== 5:
                new_line += "input_dim: " + str(scale_img.size[0]) + "\n"
            elif i== 6:
                new_line += "input_dim: " + str(scale_img.size[1]) + "\n"
            else:
                new_line += line
        output = open('net_surgery/face_full_conv2.prototxt', 'w')
        output.write(new_line)
        output.close()
        prototxt.close()
        net_full_conv = caffe.Net('net_surgery/face_full_conv2.prototxt',
                              'net_surgery/face_full_conv.caffemodel',
                              caffe.TEST)
        # load input and configure preprocessing
        im = caffe.io.load_image("tmp.jpg")
        transformer = caffe.io.Transformer({'data': net_full_conv.blobs['data'].data.shape})
        transformer.set_mean('data', np.load('../python/caffe/imagenet/ilsvrc_2012_mean.npy').mean(1).mean(1))
        transformer.set_transpose('data', (2,0,1))
        transformer.set_channel_swap('data', (2,1,0))
        transformer.set_raw_scale('data', 255.0)

        # make classification map by forward and print prediction indices at each location
        out = net_full_conv.forward_all(data=np.asarray([transformer.preprocess('data', im)]))
       # print out['prob'][0,1]
        boxes = generateBoundingBox(out['prob'][0,1], scale)
        #print boxes
        if(boxes):
            total_boxes.extend(boxes)

            # boxes_nms = np.array(total_boxes)
            # true_boxes = nms(boxes_nms, overlapThresh=0.3)
            # #display the nmx bounding box in  image.
            # draw = ImageDraw.Draw(scale_img)
            # for box in true_boxes:
            #     draw.rectangle((box[0], box[1], box[2], box[3]) )
            # scale_img.show()

    #nms
    boxes_nms = np.array(total_boxes)
    true_boxes = nms_max(boxes_nms, overlapThresh=0.3)
    #display the nmx bounding box in  image.
    draw = ImageDraw.Draw(img)
    print "width:", img.size[0], "height:",  img.size[1]
    for box in true_boxes:
        draw.rectangle((box[0], box[1], box[2], box[3]) )
    img.show()

if __name__ == "__main__":
    face_detection("/mnt/data/fddb/2002/08/11/big/img_290.jpg")
