
from __future__ import division
import math
import json
import random
import pprint
import scipy.misc
import numpy as np
from time import gmtime, strftime
from six.moves import xrange

import tensorflow as tf
import tensorflow.contrib.slim as slim


pp = pprint.PrettyPrinter()

get_stddev = lambda x, k_h, k_w: 1/math.sqrt(k_w*k_h*x.get_shape()[-1])

def show_all_variables():
  model_vars = tf.trainable_variables()
  slim.model_analyzer.analyze_vars(model_vars, print_info=True)

def get_image(image_path, input_height, input_width,
              crop_height=64, crop_width=64, 
              crop=True, grayscale=False):
  image = imread(image_path, grayscale)
  return transform(image, input_height, input_width,
                   crop_height, crop_width, crop)

def save_images(images, size, image_path):
  return imsave(inverse_transform(images), size, image_path)

def imread(path, grayscale = False):
  if (grayscale):
    return scipy.misc.imread(path, flatten = True).astype(np.float)
  else:
    return scipy.misc.imread(path).astype(np.float)

def merge_images(images, size):
  return inverse_transform(images)

def merge(images, size):
  h, w = images.shape[1], images.shape[2]
  if (images.shape[3] in (3,4)):
    c = images.shape[3]
    img = np.zeros((h * size[0], w * size[1], c))
    for idx, image in enumerate(images):
      i = idx % size[1]
      j = idx // size[1]
      img[j * h:j * h + h, i * w:i * w + w, :] = image
    return img
  elif images.shape[3]==1:
    img = np.zeros((h * size[0], w * size[1]))
    for idx, image in enumerate(images):
      i = idx % size[1]
      j = idx // size[1]
      img[j * h:j * h + h, i * w:i * w + w] = image[:,:,0]
    return img
  else:
    raise ValueError('in merge(images,size) images parameter '
                     'must have dimensions: HxW or HxWx3 or HxWx4')

def imsave(images, size, path):
  image = np.squeeze(merge(images, size))
  return scipy.misc.imsave(path, image)

def center_crop(x, crop_h, crop_w):
  if crop_w is None:
    crop_w = crop_h
  h, w = x.shape[:2]
  j = int(round((h - crop_h)/2.))
  i = int(round((w - crop_w)/2.))
  return x[j:j+crop_h, i:i+crop_w]

def crop_img_random(img, input_shape, crop_shape):
  x0 = np.random.randint(0, input_shape[0] + 1 - crop_shape[0], size=1)[0]
  x1 = np.random.randint(0, input_shape[1] + 1 - crop_shape[1], size=1)[0]
  crop_img = img[x0:x0+crop_shape[0], x1:x1+crop_shape[1]]
  return crop_img

def flip_img_random(img):
  if np.random.rand(1)[0] > 0.5:
    return np.flip(img, axis = 1)
  return img

def transform(image, input_height, input_width, crop_height, crop_width, crop):
  assert image.shape[0] == input_height and image.shape[1]== input_width, \
    'image size not equal to [input_height, input_width]'
  if crop:
    image = center_crop(image, crop_height, crop_width)
  return np.array(image)/127.5 - 1.

def inverse_transform(images):
  return (images+1.)/2.

def to_json(output_path, *layers):
  with open(output_path, "w") as layer_f:
    lines = ""
    for w, b, bn in layers:
      layer_idx = w.name.split('/')[0].split('h')[1]

      B = b.eval()

      if "lin/" in w.name:
        W = w.eval()
        depth = W.shape[1]
      else:
        W = np.rollaxis(w.eval(), 2, 0)
        depth = W.shape[0]

      biases = {"sy": 1, "sx": 1, "depth": depth, "w": ['%.2f' % elem for elem in list(B)]}
      if bn != None:
        gamma = bn.gamma.eval()
        beta = bn.beta.eval()

        gamma = {"sy": 1, "sx": 1, "depth": depth, "w": ['%.2f' % elem for elem in list(gamma)]}
        beta = {"sy": 1, "sx": 1, "depth": depth, "w": ['%.2f' % elem for elem in list(beta)]}
      else:
        gamma = {"sy": 1, "sx": 1, "depth": 0, "w": []}
        beta = {"sy": 1, "sx": 1, "depth": 0, "w": []}

      if "lin/" in w.name:
        fs = []
        for w in W.T:
          fs.append({"sy": 1, "sx": 1, "depth": W.shape[0], "w": ['%.2f' % elem for elem in list(w)]})

        lines += """
          var layer_%s = {
            "layer_type": "fc", 
            "sy": 1, "sx": 1, 
            "out_sx": 1, "out_sy": 1,
            "stride": 1, "pad": 0,
            "out_depth": %s, "in_depth": %s,
            "biases": %s,
            "gamma": %s,
            "beta": %s,
            "filters": %s
          };""" % (layer_idx.split('_')[0], W.shape[1], W.shape[0], biases, gamma, beta, fs)
      else:
        fs = []
        for w_ in W:
          fs.append({"sy": 5, "sx": 5, "depth": W.shape[3], "w": ['%.2f' % elem for elem in list(w_.flatten())]})

        lines += """
          var layer_%s = {
            "layer_type": "deconv", 
            "sy": 5, "sx": 5,
            "out_sx": %s, "out_sy": %s,
            "stride": 2, "pad": 1,
            "out_depth": %s, "in_depth": %s,
            "biases": %s,
            "gamma": %s,
            "beta": %s,
            "filters": %s
          };""" % (layer_idx, 2**(int(layer_idx)+2), 2**(int(layer_idx)+2),
               W.shape[0], W.shape[3], biases, gamma, beta, fs)
    layer_f.write(" ".join(lines.replace("'","").split()))

def make_gif(images, fname, duration=2, true_image=False):
  import moviepy.editor as mpy

  def make_frame(t):
    try:
      x = images[int(len(images)/duration*t)]
    except:
      x = images[-1]

    if true_image:
      return x.astype(np.uint8)
    else:
      return ((x+1)/2*255).astype(np.uint8)

  clip = mpy.VideoClip(make_frame, duration=duration)
  clip.write_gif(fname, fps = len(images) / duration)



def get_random_z(batch_size, z_dim):
  return np.random.uniform(-0.5, 0.5, [batch_size, z_dim]).astype(np.float32)

def get_gradient_z(batch_size, z_dim):
  values = np.arange(-0.9, 0.9, 1.8/batch_size)
  z_sample = get_random_z(batch_size, z_dim)
  for idx in xrange(z_dim):
      for kdx, z in enumerate(z_sample):
          z[idx] = values[kdx]
  return z_sample

def get_zero_z(batch_size, z_dim):
  return np.zeros([batch_size, z_dim])


def get_sample_z_dict(branchgan, config, option=0, level=-1, index=None):
  if branchgan.use_z_pyramid:
      if option == 0:
        random_z = get_random_z(config.batch_size, branchgan.dims[0])
        sample_z_dict = {branchgan.z_pyramid[0]:random_z}
        for level_tmp in range(1, branchgan.n_levels-1, 1):
          random_z = get_random_z(config.batch_size, branchgan.dims[level_tmp])
          sample_z_dict [branchgan.z_pyramid[level_tmp]] = random_z
      elif option < 4:
        random_z = get_random_z(1, branchgan.dims[0])
        random_z = np.squeeze(np.tile( random_z, (config.batch_size, 1)))
        sample_z_dict = {branchgan.z_pyramid[0]:random_z}
        for level_tmp in range(1, branchgan.n_levels-1, 1):
          random_z = get_random_z(1, branchgan.dims[level_tmp])
          random_z = np.squeeze(np.tile( random_z, (config.batch_size, 1)))
          sample_z_dict [branchgan.z_pyramid[level_tmp]] = random_z
        if level is not -1:
          gradient_z = get_gradient_z(config.batch_size, branchgan.dims[level])
          sample_z_dict [branchgan.z_pyramid[level]] = gradient_z
      elif option ==4:
        random_z = get_random_z(1, branchgan.dims[0])
        random_z = np.squeeze(np.tile( random_z, (config.batch_size, 1)))
        sample_z_dict = {branchgan.z_pyramid[0]:random_z}
        for level_tmp in range(1, branchgan.n_levels-1, 1):
          random_z = get_random_z(1, branchgan.dims[level_tmp])
          random_z = np.squeeze(np.tile( random_z, (config.batch_size, 1)))
          sample_z_dict [branchgan.z_pyramid[level_tmp]] = random_z
        if level is not -1 and index is not None:
          base= -0.9
          for i in range(config.batch_size):
            sample_z_dict[branchgan.z_pyramid[level]][i, index] = base + i*1.8/(config.batch_size-1)
      elif option ==5:
        random_z = np.random.uniform(-0.8, 0.8, [1, branchgan.z_dim]).astype(np.float32)
        random_z = np.squeeze(np.tile( random_z, (config.batch_size, 1)))
        sample_z_dict = {branchgan.z_pyramid[0]:random_z}
        for level_tmp in range(1, branchgan.n_levels-1, 1):
          gradient_z = np.ones([config.batch_size, branchgan.z_dim]) * 0.5
          for i in range(5-level_tmp):
              gradient_z[i, :] =  gradient_z[i, :] * (-0.5)
          sample_z_dict [branchgan.z_pyramid[level_tmp]] = gradient_z
  else:
    if option == 0:
      random_z = get_random_z(config.batch_size, branchgan.z_dim)
      sample_z_dict = {branchgan.z: random_z}
  return sample_z_dict

def visualize(sess, branchgan, config, option=1, name=""):
  #image_frame_dim = int(math.ceil(config.batch_size**.5))
  image_frame_size = image_manifold_size(config.batch_size)
  if option == 0:
    z_dict = get_sample_z_dict(branchgan, config, option=0)
    samples = sess.run(branchgan.G_pyramid[-1], feed_dict=z_dict)
    save_images(samples, image_frame_size, './tests/test_'+name+'_all_rand_%s.png' % strftime("%Y-%m-%d-%H-%M-%S", gmtime()))
  elif option == 1:
    if branchgan.use_z_pyramid:
      for level in xrange(branchgan.n_levels - 1):
        z_dict = get_sample_z_dict(branchgan, config, option=1, level=level)
        samples = sess.run(branchgan.G_pyramid[-1], feed_dict=z_dict)
        save_images(samples, image_frame_size, './tests/test_'+name+'_-1_gradient_level_%s_option2.png' % (level))
        #samples = sess.run(branchgan.G_pyramid[-2], feed_dict=z_dict)
        #save_images(samples, image_frame_size, './tests/test_'+name+'_-2_gradient_level_%s_option2.png' % (level))
        #samples = sess.run(branchgan.G_pyramid[-3], feed_dict=z_dict)
        #save_images(samples, image_frame_size, './tests/test_'+name+'_-3_gradient_level_%s_option2.png' % (level))
        #samples = sess.run(branchgan.G_pyramid[-4], feed_dict=z_dict)
        #save_images(samples, image_frame_size, './tests/test_'+name+'_-4_gradient_level_%s_option2.png' % (level))
        #samples = sess.run(branchgan.G_pyramid[-5], feed_dict=z_dict)
        #save_images(samples, image_frame_size, './tests/test_'+name+'_-5_gradient_level_%s_option2.png' % (level))
    else:
      values = np.arange(-0.9, 1.0, 1.9 /config.batch_size)
      for idx in xrange(branchgan.z_dim):
        print(" [*] %d" % idx)
        random_z = np.random.uniform(-0.5, 0.5, size=(1 , branchgan.z_dim))
        z_sample = np.squeeze(np.tile( random_z, (config.batch_size, 1)))
        for kdx, z in enumerate(z_sample):
          z[idx] = values[kdx]
        sample_z_dict = {branchgan.z: z_sample}
        samples = sess.run(branchgan.G_pyramid[-1], feed_dict=sample_z_dict)
        save_images(samples, image_frame_size, './tests/test_'+name+'_'+str(idx)+'_gradient_option1.png' )
  elif option == 2:
    if branchgan.use_z_pyramid:
      for level in xrange(branchgan.n_levels - 1):
          z_dict = get_sample_z_dict(branchgan, config, option=2, level=level)
          samples = sess.run(branchgan.G_pyramid[-1], feed_dict=z_dict)
          make_gif(samples, './tests/test_'+name+'_gif_gradient_'+str(level)+'_option2.gif')
    else:
      z_dict = get_sample_z_dict(branchgan, config, option=2)
      samples = sess.run(branchgan.G_pyramid[-1], feed_dict=z_dict)
      make_gif(samples, './tests/test_'+name+'_gif_gradient_option3.gif')
  print('[SUCCESS] images saved to ./tests/')


def visualize_all_dims(sess, branchgan, config, name=""):
    image_frame_size = image_manifold_size(config.batch_size)
    if branchgan.use_z_pyramid:
      for level in xrange(branchgan.n_levels - 1):
        for i in range(branchgan.z_dim):
          z_dict = get_sample_z_dict(branchgan, config, option=4, level=level, index=i)
          print(level, i)
          samples = sess.run(branchgan.G_pyramid[-1], feed_dict=z_dict)
          save_images(samples, image_frame_size, './tests/test_dim'+name+'_gradient_level_%s_%s.png' % (level, i))
    print('[SUCCESS] images saved to ./tests/')


def fusion(branchgan, config):
    z_dict = get_sample_z_dict(branchgan, config, option=5)
    left = 0
    right = 1
    z_dict[branchgan.z_pyramid[0]][left] = np.random.uniform(-0.8, 0.8, size=( branchgan.z_dim))
    for i in range(branchgan.n_levels-1):
      z_dict[branchgan.z_pyramid[i]][right] = z_dict[branchgan.z_pyramid[i]][4]
    for split in [2,3,4]:
      for i in range(branchgan.n_levels-1):
        if i <split -1:
          z_dict[branchgan.z_pyramid[i]][split] = z_dict[branchgan.z_pyramid[i]][left]
        else:
          z_dict[branchgan.z_pyramid[i]][split] = z_dict[branchgan.z_pyramid[i]][right]
    for split in [5,6,7]:
      for i in range(branchgan.n_levels-1):
        if i <split -4:
          z_dict[branchgan.z_pyramid[i]][split] = z_dict[branchgan.z_pyramid[i]][right]
        else:
          z_dict[branchgan.z_pyramid[i]][split] = z_dict[branchgan.z_pyramid[i]][left]
    return z_dict


def synthesize(sess, branchgan, config, option=1, name=""):
  #image_frame_dim = int(math.ceil(config.batch_size**.5))
  image_frame_size = image_manifold_size(config.batch_size)
  if branchgan.use_z_pyramid:
      for num in xrange(10):
        z_dict = get_sample_z_dict(branchgan, config, option=5)
        samples = sess.run(branchgan.G_pyramid[-1], feed_dict=z_dict)
        print(samples[1:5].shape)
        save_images(np.flip(samples[0:5],axis=0), [1,5], './tests/test_'+name+'_synthesis_num_%s_option2.png' % (num))
  print('[SUCCESS] images saved to ./tests/')

def imagefusion(sess, branchgan, config, name=""):
    image_frame_size = image_manifold_size(config.batch_size)
    if branchgan.use_z_pyramid:
        for exp in range(6):
          fusion_z_dict = fusion(branchgan, config)
          samples = sess.run(branchgan.G_pyramid[-1], feed_dict=fusion_z_dict)
          for i in range(8):
            scipy.misc.imsave('./tests/test_'+name+'_fusion_'+str(exp)+'_'+str(i)+'.png', inverse_transform(samples[i]))
    print('[SUCCESS] images saved to ./tests/')


def image_manifold_size(num_images):
  manifold_h = int(np.floor(np.sqrt(num_images)))
  manifold_w = int(np.ceil(np.sqrt(num_images)))
  assert manifold_h * manifold_w == num_images
  return manifold_h, manifold_w

def random_rotate_image(image):
    angle = np.random.uniform(low=-10.0, high=10.0)
    return misc.imrotate(image, angle, 'bicubic')
